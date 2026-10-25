from flask import Flask, jsonify, abort, send_file, Response, request, session, g, stream_with_context
from flask_cors import CORS
from werkzeug.exceptions import HTTPException
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import timedelta
import os
import logging
import threading
import socket
import webbrowser
import secrets
import random
import sqlite3
import hmac
from functools import wraps
import sys
import time
from mutagen import File

app = Flask(__name__)

# Set MUSIC_PLAYER_SECRET_KEY in production so sessions survive restarts.
app.config['SECRET_KEY'] = os.environ.get('MUSIC_PLAYER_SECRET_KEY') or secrets.token_hex(32)
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = os.environ.get('MUSIC_PLAYER_HTTPS', '').lower() == 'true'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=12)
app.config['INVITE_CODE'] = os.environ.get('MUSIC_PLAYER_INVITE_CODE') or secrets.token_hex(16)

# Pre-computed dummy hash to prevent timing-based username enumeration on login
DUMMY_PASSWORD_HASH = generate_password_hash(secrets.token_hex(16))

cors_origins = os.environ.get('MUSIC_PLAYER_CORS_ORIGINS', '').strip()
if cors_origins:
    CORS(app, origins=[origin.strip() for origin in cors_origins.split(',')], supports_credentials=True)

currentradioID = 0
RADIO_DECK = []
RADIO_HISTORY = []
RADIO_LOCK = threading.Lock()
timer = None
HOST = os.environ.get('MUSIC_PLAYER_HOST', '0.0.0.0')
PORT = int(os.environ.get('MUSIC_PLAYER_PORT', '8080'))

# In-memory cache for scanned library metadata
LIBRARY_CACHE = []
LIBRARY_LOCK = threading.Lock()

# Ephemeral one-time stream tokens: { token: { user_id, song_id, key_bytes, expires_at } }
STREAM_TOKENS = {}
STREAM_TOKENS_LOCK = threading.Lock()
STREAM_TOKEN_TTL_SECONDS = 30

# Brute-force rate limiter for authentication routes: { ip: [timestamps] }
AUTH_ATTEMPTS = {}
AUTH_LOCK = threading.Lock()
MAX_AUTH_ATTEMPTS = 8
AUTH_WINDOW_SECONDS = 300


@app.after_request
def add_security_headers(response):
    response.headers.setdefault('X-Content-Type-Options', 'nosniff')
    response.headers.setdefault('X-Frame-Options', 'DENY')
    response.headers.setdefault('Referrer-Policy', 'no-referrer')
    response.headers.setdefault('Permissions-Policy', 'microphone=(), camera=()')
    response.headers.setdefault(
        'Content-Security-Policy',
        "default-src 'self'; "
        "img-src 'self' data: blob: https://raw.githubusercontent.com; "
        "media-src 'self' blob:; "
        "style-src 'self' 'unsafe-inline'; "
        "script-src 'self' 'unsafe-inline'; "
        "connect-src 'self'; "
        "frame-ancestors 'none';"
    )
    return response


def get_app_root():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def get_resource_path(relative_path):
    if getattr(sys, 'frozen', False):
        base_path = getattr(sys, '_MEIPASS', get_app_root())
        return os.path.join(base_path, relative_path)
    return os.path.join(get_app_root(), relative_path)


def get_external_or_bundled_path(relative_path):
    external_path = os.path.join(get_app_root(), relative_path)
    if os.path.exists(external_path):
        return external_path
    return get_resource_path(relative_path)


APP_ROOT = get_app_root()
DIRECTORY = os.path.realpath(get_external_or_bundled_path("music"))
HTML_PATH = get_resource_path('musicplayer_server.html')
DATABASE_PATH = os.path.join(APP_ROOT, 'music_player_users.db')

logging.basicConfig(level=logging.INFO)


def is_safe_subpath(path, base_dir=DIRECTORY):
    """Ensures a file path resolves strictly inside the allowed music directory."""
    try:
        real_base = os.path.realpath(base_dir)
        real_target = os.path.realpath(path)
        return os.path.commonpath([real_base, real_target]) == real_base
    except ValueError:
        return False


def check_rate_limit(ip):
    now = time.time()
    with AUTH_LOCK:
        attempts = [t for t in AUTH_ATTEMPTS.get(ip, []) if now - t < AUTH_WINDOW_SECONDS]
        AUTH_ATTEMPTS[ip] = attempts
        return len(attempts) >= MAX_AUTH_ATTEMPTS


def record_failed_auth(ip):
    now = time.time()
    with AUTH_LOCK:
        attempts = [t for t in AUTH_ATTEMPTS.get(ip, []) if now - t < AUTH_WINDOW_SECONDS]
        attempts.append(now)
        AUTH_ATTEMPTS[ip] = attempts


def clear_failed_auth(ip):
    with AUTH_LOCK:
        AUTH_ATTEMPTS.pop(ip, None)


def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(DATABASE_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute('PRAGMA foreign_keys = ON')
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()


def init_db():
    with sqlite3.connect(DATABASE_PATH) as db:
        db.execute('PRAGMA foreign_keys = ON')
        db.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE COLLATE NOCASE,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        db.execute('''
            CREATE TABLE IF NOT EXISTS favorites (
                user_id INTEGER NOT NULL,
                song_key TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, song_key),
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        ''')
        db.execute('''
            CREATE TABLE IF NOT EXISTS playlists (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        ''')
        db.execute('''
            CREATE TABLE IF NOT EXISTS playlist_songs (
                playlist_id INTEGER NOT NULL,
                song_key TEXT NOT NULL,
                position INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (playlist_id, song_key),
                FOREIGN KEY (playlist_id) REFERENCES playlists(id) ON DELETE CASCADE
            )
        ''')


init_db()


def ensure_csrf_token():
    if 'csrf_token' not in session:
        session['csrf_token'] = secrets.token_hex(32)
    return session['csrf_token']


def login_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': 'Authentication required'}), 401
        if request.method in ('POST', 'PUT', 'PATCH', 'DELETE'):
            sent_csrf = request.headers.get('X-CSRF-Token', '')
            expected_csrf = session.get('csrf_token', '')
            if not expected_csrf or not hmac.compare_digest(sent_csrf, expected_csrf):
                return jsonify({'error': 'Invalid or missing CSRF token'}), 403
        return view(*args, **kwargs)
    return wrapped_view


# ==================== LIBRARY SCANNING & METADATA ====================

def extract_tag_text(audio, keys):
    if not audio or getattr(audio, 'tags', None) is None:
        return None
    tags = audio.tags
    for k in keys:
        if k in tags:
            val = tags[k]
            if isinstance(val, list) and val:
                return str(val[0]).strip()
            if hasattr(val, 'text') and val.text:
                return str(val.text[0]).strip()
            return str(val).strip()
    return None


def scan_library(dir_path):
    """Scans the music directory once and caches metadata, durations, and file paths."""
    global LIBRARY_CACHE
    catalog = []
    if not os.path.exists(dir_path):
        with LIBRARY_LOCK:
            LIBRARY_CACHE = []
        return []

    seen_prefixes = {}
    for root, dirs, files in os.walk(dir_path, followlinks=False):
        dirs.sort()
        for file in sorted(files):
            full_path = os.path.join(root, file)
            if not is_safe_subpath(full_path, dir_path):
                continue
            ext = os.path.splitext(file)[1].lower()
            if ext in ('.mp3', '.flac', '.wav', '.lrc', '.jpg', '.png'):
                prefix = os.path.splitext(file)[0]
                if prefix not in seen_prefixes:
                    seen_prefixes[prefix] = {}
                seen_prefixes[prefix][ext] = full_path

    song_id = 0
    for prefix, files_map in seen_prefixes.items():
        audio_ext = next((e for e in ('.mp3', '.flac', '.wav') if e in files_map), None)
        if not audio_ext:
            continue

        audio_path = files_map[audio_ext]
        title = prefix
        artist = "Unknown Artist"
        album = "Unknown Album"
        duration = 0

        if " - " in prefix:
            parts = prefix.split(" - ", 1)
            artist, title = parts[0].strip(), parts[1].strip()

        try:
            audio = File(audio_path)
            if audio is not None:
                if getattr(audio, 'info', None) and getattr(audio.info, 'length', None):
                    duration = int(audio.info.length)
                tag_title = extract_tag_text(audio, ['TIT2', 'title', 'TITLE'])
                tag_artist = extract_tag_text(audio, ['TPE1', 'artist', 'ARTIST'])
                tag_album = extract_tag_text(audio, ['TALB', 'album', 'ALBUM'])
                if tag_title:
                    title = tag_title
                if tag_artist:
                    artist = tag_artist
                if tag_album:
                    album = tag_album
        except Exception as e:
            logging.warning("Metadata error on %s: %s", audio_path, e)

        has_lrc = '.lrc' in files_map or bool(get_embedded_lyrics(audio_path))
        has_img = ('.jpg' in files_map) or ('.png' in files_map) or bool(get_embedded_image(audio_path))

        catalog.append({
            'id': song_id,
            'key': prefix,
            'name': prefix,
            'title': title,
            'artist': artist,
            'album': album,
            'duration': duration,
            'has_lyrics': has_lrc,
            'has_cover': has_img,
            'files': files_map,
            'audio_path': audio_path,
            'audio_ext': audio_ext
        })
        song_id += 1

    with LIBRARY_LOCK:
        LIBRARY_CACHE = catalog
    return catalog


def get_library():
    with LIBRARY_LOCK:
        if LIBRARY_CACHE or not os.path.exists(DIRECTORY):
            return list(LIBRARY_CACHE)
    return scan_library(DIRECTORY)


def get_song_by_id(song_id):
    lib = get_library()
    if 0 <= song_id < len(lib):
        return lib[song_id]
    return None


# ==================== AUTHENTICATION ROUTES ====================

@app.route('/auth/me', methods=['GET'])
def auth_me():
    user_id = session.get('user_id')
    if user_id is None:
        return jsonify({'authenticated': False})

    user = get_db().execute(
        'SELECT username FROM users WHERE id = ?', (user_id,)
    ).fetchone()
    if user is None:
        session.clear()
        return jsonify({'authenticated': False})
    return jsonify({
        'authenticated': True,
        'username': user['username'],
        'csrf_token': ensure_csrf_token()
    })


@app.route('/auth/signup', methods=['POST'])
def signup():
    client_ip = request.remote_addr or 'unknown'
    if check_rate_limit(client_ip):
        return jsonify({'error': 'Too many attempts. Please wait 5 minutes.'}), 429

    data = request.get_json(silent=True) or {}
    username = str(data.get('username', '')).strip()
    password = str(data.get('password', ''))
    invite_code = str(data.get('invite_code', ''))

    configured_invite_code = app.config.get('INVITE_CODE')
    if not configured_invite_code:
        return jsonify({'error': 'Sign-up is not configured on this server.'}), 503
    if not hmac.compare_digest(invite_code, configured_invite_code):
        record_failed_auth(client_ip)
        return jsonify({'error': 'Invalid invite code.'}), 403

    if not 3 <= len(username) <= 32:
        return jsonify({'error': 'Username must be 3-32 characters.'}), 400
    if len(password) < 8:
        return jsonify({'error': 'Password must be at least 8 characters.'}), 400

    db = get_db()
    existing_user = db.execute(
        'SELECT 1 FROM users WHERE username = ? COLLATE NOCASE',
        (username,)
    ).fetchone()
    if existing_user is not None:
        return jsonify({'error': 'That username is already registered.'}), 409

    try:
        cursor = db.execute(
            'INSERT INTO users (username, password_hash) VALUES (?, ?)',
            (username, generate_password_hash(password))
        )
        db.commit()
    except sqlite3.IntegrityError:
        return jsonify({'error': 'That username is already registered.'}), 409

    clear_failed_auth(client_ip)
    session.clear()
    session.permanent = True
    session['user_id'] = cursor.lastrowid
    session['username'] = username
    return jsonify({
        'authenticated': True,
        'username': username,
        'csrf_token': ensure_csrf_token()
    }), 201


@app.route('/auth/login', methods=['POST'])
def login():
    client_ip = request.remote_addr or 'unknown'
    if check_rate_limit(client_ip):
        return jsonify({'error': 'Too many failed login attempts. Try again in 5 minutes.'}), 429

    data = request.get_json(silent=True) or {}
    username = str(data.get('username', '')).strip()
    password = str(data.get('password', ''))

    user = get_db().execute(
        'SELECT id, username, password_hash FROM users WHERE username = ? COLLATE NOCASE',
        (username,)
    ).fetchone()

    if user is None:
        check_password_hash(DUMMY_PASSWORD_HASH, password)
        record_failed_auth(client_ip)
        return jsonify({'error': 'Invalid username or password.'}), 401

    if not check_password_hash(user['password_hash'], password):
        record_failed_auth(client_ip)
        return jsonify({'error': 'Invalid username or password.'}), 401

    clear_failed_auth(client_ip)
    session.clear()
    session.permanent = True
    session['user_id'] = user['id']
    session['username'] = user['username']
    return jsonify({
        'authenticated': True,
        'username': user['username'],
        'csrf_token': ensure_csrf_token()
    })


@app.route('/auth/logout', methods=['POST'])
@login_required
def logout():
    user_id = session.get('user_id')
    with STREAM_TOKENS_LOCK:
        for tok in [k for k, v in STREAM_TOKENS.items() if v['user_id'] == user_id]:
            STREAM_TOKENS.pop(tok, None)
    session.clear()
    return jsonify({'authenticated': False})


# ==================== SECURE STREAMING & MEDIA ROUTES ====================

@app.route("/", methods=["GET"])
def serve_html():
    try:
        return send_file(HTML_PATH)
    except Exception as e:
        logging.error("Error serving HTML: %s", e)
        abort(500, "Internal server error")


@app.route("/stream/token/<int:song_id>", methods=["POST"])
@login_required
def issue_stream_token(song_id):
    """Issues a short-lived, single-use stream ticket and XOR pad key."""
    song = get_song_by_id(song_id)
    if not song or not song.get('audio_path') or not is_safe_subpath(song['audio_path']):
        abort(404, "Song not found")

    now = time.time()
    token = secrets.token_urlsafe(32)
    key_bytes = secrets.token_bytes(32)

    with STREAM_TOKENS_LOCK:
        # Purge expired tokens
        expired = [k for k, v in STREAM_TOKENS.items() if v['expires_at'] < now]
        for k in expired:
            STREAM_TOKENS.pop(k, None)

        STREAM_TOKENS[token] = {
            'user_id': session['user_id'],
            'song_id': song_id,
            'key_bytes': key_bytes,
            'expires_at': now + STREAM_TOKEN_TTL_SECONDS
        }

    return jsonify({
        'token': token,
        'key': key_bytes.hex(),
        'mime': get_content_type(song['audio_ext'])
    })


def xor_file_stream(file_path, key_bytes):
    """Streams the audio file XOR-obfuscated in 64KB chunks so raw network captures are unplayable."""
    chunk_size = 65536  # Multiple of 32 bytes
    full_pad = key_bytes * (chunk_size // len(key_bytes))
    full_pad_int = int.from_bytes(full_pad, 'big')

    with open(file_path, 'rb') as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            n = len(chunk)
            if n == chunk_size:
                obfuscated = (int.from_bytes(chunk, 'big') ^ full_pad_int).to_bytes(chunk_size, 'big')
            else:
                pad_slice = full_pad[:n]
                obfuscated = (int.from_bytes(chunk, 'big') ^ int.from_bytes(pad_slice, 'big')).to_bytes(n, 'big')
            yield obfuscated


@app.route("/stream/audio/<token>", methods=["GET"])
@login_required
def serve_obfuscated_stream(token):
    # Block direct browser navigation, <a download>, or external origins
    if request.headers.get('X-Stream-Client') != 'MusicPlayerWeb':
        abort(403, "Direct downloads are disabled.")

    sec_fetch_dest = request.headers.get('Sec-Fetch-Dest', '')
    if sec_fetch_dest and sec_fetch_dest not in ('empty',):
        abort(403, "Direct navigation to audio streams is forbidden.")

    sec_fetch_site = request.headers.get('Sec-Fetch-Site', '')
    if sec_fetch_site and sec_fetch_site not in ('same-origin',):
        abort(403, "Cross-origin streaming is forbidden.")

    now = time.time()
    with STREAM_TOKENS_LOCK:
        ticket = STREAM_TOKENS.pop(token, None)  # Consumed immediately (single-use)

    if not ticket or ticket['expires_at'] < now or ticket['user_id'] != session.get('user_id'):
        abort(403, "Expired or invalid stream token.")

    song = get_song_by_id(ticket['song_id'])
    if not song or not song.get('audio_path') or not is_safe_subpath(song['audio_path']):
        abort(404, "Audio not found")

    headers = {
        'Cache-Control': 'no-store, no-cache, must-revalidate, private, max-age=0',
        'Pragma': 'no-cache',
        'Expires': '0',
        'Content-Disposition': 'inline',
        'X-Content-Type-Options': 'nosniff'
    }
    return Response(
        stream_with_context(xor_file_stream(song['audio_path'], ticket['key_bytes'])),
        mimetype='application/octet-stream',
        headers=headers
    )


@app.route("/<int:song_id>/<file_type>", methods=["GET"])
@login_required
def serve_files(song_id, file_type):
    # Direct audio file serving is blocked; audio must use /stream/token + /stream/audio
    if file_type == 'audio':
        abort(403, "Direct audio file downloads are disabled.")

    try:
        song = get_song_by_id(song_id)
        if not song:
            abort(404, "Song not found")

        files = song['files']
        ext_map = {
            'image': ['.jpg', '.png'],
            'lyrics': ['.lrc']
        }

        for ext in ext_map.get(file_type, []):
            if ext in files and is_safe_subpath(files[ext]):
                return send_file(files[ext], mimetype=get_content_type(ext), conditional=True)

        audio_path = song['audio_path']
        if file_type == 'lyrics' and audio_path and is_safe_subpath(audio_path):
            lyrics = get_embedded_lyrics(audio_path)
            if lyrics:
                return Response(lyrics, mimetype='text/plain; charset=utf-8')

        if file_type == 'image' and audio_path and is_safe_subpath(audio_path):
            embedded_image = get_embedded_image(audio_path)
            if embedded_image:
                image_data, mime_type = embedded_image
                return Response(image_data, mimetype=mime_type)

        abort(404, f"{file_type.capitalize()} not found")
    except HTTPException:
        raise
    except Exception as e:
        logging.error("Error serving files: %s", e)
        abort(500, "Internal server error")


@app.route("/songs", methods=["GET"])
@login_required
def list_songs():
    """Backwards-compatible simple song map."""
    try:
        lib = get_library()
        return jsonify({s['id']: s['name'] for s in lib})
    except Exception as e:
        logging.error("Error listing songs: %s", e)
        abort(500, "Internal server error")


@app.route("/songs/metadata", methods=["GET"])
@login_required
def list_songs_metadata():
    """Rich metadata endpoint including user favorites."""
    try:
        lib = get_library()
        db = get_db()
        fav_rows = db.execute(
            'SELECT song_key FROM favorites WHERE user_id = ?',
            (session['user_id'],)
        ).fetchall()
        fav_keys = {r['song_key'] for r in fav_rows}

        result = []
        for s in lib:
            result.append({
                'id': s['id'],
                'key': s['key'],
                'name': s['name'],
                'title': s['title'],
                'artist': s['artist'],
                'album': s['album'],
                'duration': s['duration'],
                'has_lyrics': s['has_lyrics'],
                'has_cover': s['has_cover'],
                'favorite': s['key'] in fav_keys
            })
        return jsonify(result)
    except Exception as e:
        logging.error("Error listing song metadata: %s", e)
        abort(500, "Internal server error")


@app.route("/library/rescan", methods=["POST"])
@login_required
def rescan_library_endpoint():
    try:
        lib = scan_library(DIRECTORY)
        return jsonify({'status': 'ok', 'total_songs': len(lib)})
    except Exception as e:
        logging.error("Error rescanning library: %s", e)
        abort(500, "Internal server error")


# ==================== FAVORITES & PLAYLISTS ====================

@app.route("/favorites/<int:song_id>", methods=["POST"])
@login_required
def toggle_favorite(song_id):
    song = get_song_by_id(song_id)
    if not song:
        abort(404, "Song not found")

    db = get_db()
    user_id = session['user_id']
    song_key = song['key']

    existing = db.execute(
        'SELECT 1 FROM favorites WHERE user_id = ? AND song_key = ?',
        (user_id, song_key)
    ).fetchone()

    if existing:
        db.execute('DELETE FROM favorites WHERE user_id = ? AND song_key = ?', (user_id, song_key))
        db.commit()
        return jsonify({'favorite': False, 'song_id': song_id})
    else:
        db.execute('INSERT INTO favorites (user_id, song_key) VALUES (?, ?)', (user_id, song_key))
        db.commit()
        return jsonify({'favorite': True, 'song_id': song_id})


@app.route("/playlists", methods=["GET", "POST"])
@login_required
def handle_playlists():
    db = get_db()
    user_id = session['user_id']
    lib = get_library()
    key_to_id = {s['key']: s['id'] for s in lib}

    if request.method == "GET":
        fav_rows = db.execute(
            'SELECT song_key FROM favorites WHERE user_id = ? ORDER BY created_at ASC',
            (user_id,)
        ).fetchall()
        fav_song_ids = [key_to_id[r['song_key']] for r in fav_rows if r['song_key'] in key_to_id]

        output = [{
            'id': 'favorites',
            'name': 'Favorites',
            'is_system': True,
            'song_ids': fav_song_ids
        }]

        pls = db.execute(
            'SELECT id, name, created_at FROM playlists WHERE user_id = ? ORDER BY id ASC',
            (user_id,)
        ).fetchall()
        for p in pls:
            songs_rows = db.execute(
                'SELECT song_key FROM playlist_songs WHERE playlist_id = ? ORDER BY position ASC',
                (p['id'],)
            ).fetchall()
            song_ids = [key_to_id[r['song_key']] for r in songs_rows if r['song_key'] in key_to_id]
            output.append({
                'id': p['id'],
                'name': p['name'],
                'is_system': False,
                'song_ids': song_ids
            })
        return jsonify(output)

    data = request.get_json(silent=True) or {}
    name = str(data.get('name', '')).strip()
    if not 1 <= len(name) <= 50:
        return jsonify({'error': 'Playlist name must be 1-50 characters.'}), 400
    if name.lower() == 'favorites':
        return jsonify({'error': 'Favorites is a reserved playlist name.'}), 400

    cursor = db.execute(
        'INSERT INTO playlists (user_id, name) VALUES (?, ?)',
        (user_id, name)
    )
    db.commit()
    return jsonify({'id': cursor.lastrowid, 'name': name, 'is_system': False, 'song_ids': []}), 201


@app.route("/playlists/<playlist_id>", methods=["DELETE"])
@login_required
def delete_playlist(playlist_id):
    if playlist_id == 'favorites':
        return jsonify({'error': 'Cannot delete the Favorites playlist.'}), 400
    try:
        pid = int(playlist_id)
    except ValueError:
        abort(404, "Playlist not found")

    db = get_db()
    db.execute('DELETE FROM playlists WHERE id = ? AND user_id = ?', (pid, session['user_id']))
    db.commit()
    return jsonify({'deleted': True})


@app.route("/playlists/<playlist_id>/songs", methods=["POST", "DELETE"])
@login_required
def modify_playlist_songs(playlist_id):
    db = get_db()
    user_id = session['user_id']

    data = request.get_json(silent=True) or {}
    song_id = data.get('song_id')
    song = get_song_by_id(song_id) if isinstance(song_id, int) else None
    if not song:
        return jsonify({'error': 'Invalid song ID'}), 400

    if playlist_id == 'favorites':
        if request.method == "POST":
            db.execute(
                'INSERT OR IGNORE INTO favorites (user_id, song_key) VALUES (?, ?)',
                (user_id, song['key'])
            )
            db.commit()
            return jsonify({'added': True, 'favorite': True})
        else:
            db.execute(
                'DELETE FROM favorites WHERE user_id = ? AND song_key = ?',
                (user_id, song['key'])
            )
            db.commit()
            return jsonify({'removed': True, 'favorite': False})

    try:
        pid = int(playlist_id)
    except ValueError:
        abort(404, "Playlist not found")

    pl = db.execute(
        'SELECT id FROM playlists WHERE id = ? AND user_id = ?',
        (pid, user_id)
    ).fetchone()
    if not pl:
        abort(404, "Playlist not found")

    if request.method == "POST":
        pos_row = db.execute(
            'SELECT COALESCE(MAX(position), 0) + 1 AS next_pos FROM playlist_songs WHERE playlist_id = ?',
            (pid,)
        ).fetchone()
        db.execute(
            'INSERT OR IGNORE INTO playlist_songs (playlist_id, song_key, position) VALUES (?, ?, ?)',
            (pid, song['key'], pos_row['next_pos'])
        )
        db.commit()
        return jsonify({'added': True})
    else:
        db.execute(
            'DELETE FROM playlist_songs WHERE playlist_id = ? AND song_key = ?',
            (pid, song['key'])
        )
        db.commit()
        return jsonify({'removed': True})


# ==================== RADIO & SERVER STATE ====================

def choose_next_radio_song(direction="next"):
    global currentradioID, RADIO_DECK, RADIO_HISTORY
    lib = get_library()
    if not lib:
        return None

    total = len(lib)
    with RADIO_LOCK:
        if direction == "previous":
            while RADIO_HISTORY:
                prev_id = RADIO_HISTORY.pop()
                if 0 <= prev_id < total and prev_id != currentradioID:
                    RADIO_DECK.insert(0, currentradioID)
                    currentradioID = prev_id
                    return currentradioID

        if currentradioID is not None and 0 <= currentradioID < total:
            if not RADIO_HISTORY or RADIO_HISTORY[-1] != currentradioID:
                RADIO_HISTORY.append(currentradioID)
                if len(RADIO_HISTORY) > 100:
                    RADIO_HISTORY.pop(0)

        RADIO_DECK = [sid for sid in RADIO_DECK if 0 <= sid < total]
        if not RADIO_DECK:
            RADIO_DECK = list(range(total))
            random.shuffle(RADIO_DECK)
            if total > 1 and RADIO_DECK[0] == currentradioID:
                swap_idx = random.randint(1, total - 1)
                RADIO_DECK[0], RADIO_DECK[swap_idx] = RADIO_DECK[swap_idx], RADIO_DECK[0]

        currentradioID = RADIO_DECK.pop(0)
        return currentradioID


@app.route("/radio", methods=["GET"])
@login_required
def radio_state():
    try:
        current_progress = timer.get_elapsed_time() if timer else "00:00"
        pack = [currentradioID, current_progress]
        return jsonify(pack)
    except Exception as e:
        logging.error("Error retrieving radio state: %s", e)
        abort(500, "Internal server error")


@app.route("/radio/<direction>", methods=["POST"])
@login_required
def change_radio_song(direction):
    try:
        lib = get_library()
        if not lib:
            abort(404, "No songs available")
        if direction not in ("next", "previous"):
            abort(400, "Unknown radio direction")

        next_id = choose_next_radio_song(direction)
        run_timer(next_id)
        return jsonify({
            "song_id": next_id,
            "song_name": lib[next_id]['title'],
            "progress": "00:00"
        })
    except HTTPException:
        raise
    except Exception as e:
        logging.error("Error changing radio song: %s", e)
        abort(500, "Internal server error")


@app.route("/state", methods=["GET"])
@login_required
def server_state():
    """Returns playback state without leaking server filesystem paths or internal IPs."""
    try:
        lib = get_library()
        current_progress = timer.get_elapsed_time() if timer else "00:00"
        current_song = get_song_by_id(currentradioID)

        state = {
            "status": "running" if timer and timer.running else "idle",
            "total_songs": len(lib),
            "current_song_id": currentradioID,
            "current_song_name": current_song['title'] if current_song else None,
            "current_progress": current_progress,
            "radio_running": bool(timer and timer.running),
            "server_duration": timer.elapsed if timer else 0
        }
        return jsonify(state)
    except Exception as e:
        logging.error("Error retrieving server state: %s", e)
        abort(500, "Internal server error")


class CountdownTimer:
    def __init__(self, duration, callback=None):
        self.duration = max(1, int(duration))
        self.elapsed = 0
        self.running = False
        self.callback = callback
        self._lock = threading.Lock()

    def start(self):
        self.running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self):
        while self.running and self.elapsed < self.duration:
            time.sleep(1)
            with self._lock:
                self.elapsed += 1
        if self.running and self.callback:
            self.callback()

    def stop(self):
        self.running = False
        if hasattr(self, '_thread') and self._thread.is_alive() and self._thread is not threading.current_thread():
            self._thread.join(timeout=1.5)

    def get_elapsed_time(self):
        with self._lock:
            mins, secs = divmod(self.elapsed, 60)
            return '{:02d}:{:02d}'.format(mins, secs)


def get_local_ip_addresses():
    addresses = []
    seen = set()
    try:
        hostname = socket.gethostname()
        if hostname:
            addresses.append(hostname)
            seen.add(hostname)
        for info in socket.getaddrinfo(hostname, None, family=socket.AF_INET, type=socket.SOCK_DGRAM):
            ip = info[4][0]
            if ip and ip not in seen and not ip.startswith("127."):
                addresses.append(ip)
                seen.add(ip)
    except Exception:
        pass

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            ip = sock.getsockname()[0]
            if ip and ip not in seen:
                addresses.append(ip)
                seen.add(ip)
    except Exception:
        pass
    return addresses


def run_timer(song_id):
    global timer
    song = get_song_by_id(song_id)
    timeleng = song['duration'] if song and song['duration'] > 0 else 180
    if timer:
        timer.stop()
    timer = CountdownTimer(timeleng, callback=radioloop)
    timer.start()


def radioloop():
    lib = get_library()
    if not lib:
        return
    next_id = choose_next_radio_song("next")
    if next_id is not None:
        run_timer(next_id)
        logging.info("Radio switched to ID %s: %s", next_id, lib[next_id]['title'])


def get_embedded_lyrics(file_path):
    try:
        audio = File(file_path)
        if audio is None or getattr(audio, 'tags', None) is None:
            return None

        if file_path.lower().endswith(('.mp3', '.wav')):
            if hasattr(audio.tags, 'getall'):
                for frame in audio.tags.getall('USLT'):
                    if frame.text:
                        return str(frame.text)

        if file_path.lower().endswith('.flac'):
            for key in ('lyrics', 'LYRICS', 'unsyncedlyrics', 'UNSYNCEDLYRICS'):
                value = audio.tags.get(key)
                if value:
                    if isinstance(value, list):
                        return '\n'.join(str(v) for v in value)
                    return str(value)

        for key, value in audio.tags.items():
            if key.lower().startswith('lyrics') or key.lower() in ('unsyncedlyrics', 'lyrics'):
                if isinstance(value, list):
                    return '\n'.join(str(v) for v in value)
                return str(value)
    except Exception:
        pass
    return None


def get_embedded_image(file_path):
    try:
        audio = File(file_path)
        if audio is None:
            return None

        if getattr(audio, 'tags', None) is not None:
            try:
                if hasattr(audio.tags, 'getall'):
                    apic_frames = audio.tags.getall('APIC')
                    if apic_frames:
                        image = apic_frames[0]
                        return image.data, image.mime
            except Exception:
                pass

            if isinstance(audio.tags, dict):
                for value in audio.tags.values():
                    if hasattr(value, 'data') and hasattr(value, 'mime'):
                        return value.data, value.mime

        if hasattr(audio, 'pictures') and audio.pictures:
            picture = audio.pictures[0]
            return picture.data, picture.mime
    except Exception:
        pass
    return None


def get_content_type(ext):
    return {
        '.mp3': 'audio/mpeg',
        '.flac': 'audio/flac',
        '.wav': 'audio/wav',
        '.lrc': 'text/plain',
        '.jpg': 'image/jpeg',
        '.png': 'image/png'
    }.get(ext, 'application/octet-stream')


if __name__ == "__main__":
    init_db()
    if os.path.exists(DIRECTORY):
        logging.info(f"Music directory found: {DIRECTORY}")
        scan_library(DIRECTORY)
        radioloop()
    else:
        logging.error(f"No music folder found at {DIRECTORY}")

    print("Available IP addresses:")
    print(" - 127.0.0.1")
    for addr in get_local_ip_addresses():
        print(f" - {addr}")

    HOST = input("Enter the IP address to use (default 0.0.0.0): ").strip() or "0.0.0.0"
    PORT = int(input("Enter the port to use (default 8080): ").strip() or "8080")
    logging.info("Invite Code: %s", app.config.get('INVITE_CODE'))

    def open_browser_on_start():
        try:
            host_for_browser = HOST if HOST and HOST != "0.0.0.0" else "127.0.0.1"
            url = f'http://{host_for_browser}:{PORT}/'
            time.sleep(1)
            webbrowser.open_new_tab(url)
        except Exception as e:
            logging.info("Failed to open browser: %s", e)

    threading.Thread(target=open_browser_on_start, daemon=True).start()
    app.run(host=HOST, port=PORT, threaded=True)