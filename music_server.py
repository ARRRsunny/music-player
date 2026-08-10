from flask import Flask, jsonify, abort, send_file, Response
from flask_cors import CORS
import os
import logging
import urllib.request as ul
import threading
import socket
import webbrowser
from io import BytesIO
import sys
import time
from mutagen import File
import numpy as np
app = Flask(__name__)

CORS(app)

currentradioID = 0
timer = None


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
DIRECTORY = get_external_or_bundled_path("music")   # music folder location in the executable directory or bundle
HTML_PATH = get_resource_path('musicplayer_server.html')

logging.basicConfig(level=logging.INFO)

"""
@app.route("/", methods=["GET"])
def serve_html():
    try:
        url = "https://raw.githubusercontent.com/ARRRsunny/music-player/refs/heads/main/musicplayer_server.html"
        with ul.urlopen(url) as client:
    
            htmldata = client.read().decode('utf-8')
        return htmldata
    except Exception as e:
        logging.error("Error serving HTML: %s", e)
        abort(500, "Internal server error")
"""

@app.route("/", methods=["GET"])
def serve_html():
    try:
        return send_file(HTML_PATH)
    except Exception as e:
        logging.error("Error serving HTML: %s", e)
        abort(500, "Internal server error")

@app.route("/<int:song_id>/<file_type>", methods=["GET"])
def serve_files(song_id, file_type):
    try:
        files = get_files_by_id(DIRECTORY, song_id)
        if not files:
            abort(404, "Song not found")

        ext_map = {
            'audio': ['.mp3', '.flac', '.wav'],
            'image': ['.jpg', '.png'],
            'lyrics': ['.lrc']
        }

        for ext in ext_map.get(file_type, []):
            if ext in files:
                return send_file(files[ext], mimetype=get_content_type(ext))

        audio_path = get_audio_file_path_by_id(DIRECTORY, song_id)
        if file_type == 'lyrics' and audio_path:
            lyrics = get_embedded_lyrics(audio_path)
            if lyrics:
                return Response(lyrics, mimetype='text/plain; charset=utf-8')

        if file_type == 'image' and audio_path:
            embedded_image = get_embedded_image(audio_path)
            if embedded_image:
                image_data, mime_type = embedded_image
                return Response(image_data, mimetype=mime_type)

        abort(404, f"{file_type.capitalize()} not found")
    except Exception as e:
        logging.error("Error serving files: %s", e)
        abort(500, "Internal server error")

@app.route("/songs", methods=["GET"])
def list_songs():
    try:
        song_list = list_songs_with_ids(DIRECTORY)
        return jsonify(song_list)
    except Exception as e:
        logging.error("Error listing songs: %s", e)
        abort(500, "Internal server error")

@app.route("/radio", methods=["GET"])
def radio_state():
    try:
        current_progress = timer.get_elapsed_time() if timer else "00:00"
        pack = [currentradioID, current_progress]
        return jsonify(pack)
    except Exception as e:
        logging.error("Error retrieving radio state: %s", e)
        abort(500, "Internal server error")

@app.route("/state", methods=["GET"])
def server_state():
    try:
        songs = list_songs_with_ids(DIRECTORY)
        current_progress = timer.get_elapsed_time() if timer else "00:00"

        state = {
            "status": "running" if timer and timer.running else "idle",
            "music_directory": DIRECTORY,
            "host": HOST,
            "port": PORT,
            "hostname": socket.gethostname(),
            "ip_addresses": get_local_ip_addresses(),
            "total_songs": len(songs),
            "audio_file_count": count_files_by_extension(DIRECTORY, ['.mp3', '.flac', '.wav']),
            "lyrics_file_count": count_files_by_extension(DIRECTORY, ['.lrc']),
            "image_file_count": count_files_by_extension(DIRECTORY, ['.jpg', '.png']),
            "current_song_id": currentradioID,
            "current_song_name": songs.get(currentradioID),
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
        self.duration = duration
        self.elapsed = 0
        self.running = False
        self.callback = callback
        self._lock = threading.Lock()

    def start(self):
        self.running = True
        self._thread = threading.Thread(target=self._run)
        self._thread.start()

    def _run(self):
        while self.running and self.elapsed < self.duration:
            time.sleep(1)
            with self._lock:
                self.elapsed += 1
        if self.callback:
            self.callback()

    def stop(self):
        self.running = False
        self._thread.join()

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


def count_files_by_extension(dir_path, extensions):
    count = 0
    valid_extensions = tuple(ext.lower() for ext in extensions)

    for root, dirs, files in os.walk(dir_path):
        for file in files:
            if file.lower().endswith(valid_extensions):
                count += 1

    return count


def list_songs_with_ids(dir_path):
    songs = {}
    song_id = 0

    for root, dirs, files in os.walk(dir_path):
        for file in files:
            if file.endswith(('.mp3', '.flac', '.wav')):
                prefix = os.path.splitext(file)[0]
                if prefix not in songs.values():
                    songs[song_id] = prefix
                    song_id += 1

    return songs

def read_timelist(dir_path):
    lengthlist = {}
    song_id = 0
    for root, dirs, files in os.walk(dir_path):
        for file in files:
            if file.endswith(('.mp3', '.flac', '.wav')):
                file_path = os.path.join(root, file)
                try:
                    audio = File(file_path)
                    if audio is not None and getattr(audio, "info", None) is not None:
                        length = int(audio.info.length)
                        lengthlist[song_id] = length
                        song_id += 1
                except Exception as e:
                    logging.warning("Skipping unreadable audio file %s: %s", file_path, e)
    return lengthlist

def run_timer(song_id, lengthlist):
    global timer
    timeleng = lengthlist.get(song_id)
    if timeleng:
        timer = CountdownTimer(timeleng, callback=radioloop)
        timer.start()

def radioloop():
    global currentradioID
    currentradioID = np.random.randint(len(list_songs_with_ids(DIRECTORY)))
    lengths = read_timelist(DIRECTORY)
    run_timer(currentradioID, lengths)
    info = transform_file_paths(get_files_by_id(DIRECTORY, currentradioID))
    print("Radio loop triggered!",f"ID:{currentradioID}",info)


def transform_file_paths(data):
    transformed_data = {}

    for ext, path in data.items():
        file_name = path.split('/')[-1].split('\\')[-1]
        transformed_data[ext] = file_name

    return transformed_data

def get_files_by_id(dir, id):
    songs = list_songs_with_ids(dir)
    if id not in songs:
        return None
    
    song_name = songs[id]
    matched_files = {}

    for root, dirs, files in os.walk(dir):
        for file in files:
            if file.startswith(song_name):
                ext = os.path.splitext(file)[1]
                if ext in ['.mp3', '.flac', '.wav', '.lrc', '.jpg', '.png']:
                    matched_files[ext] = os.path.join(root, file)

    return matched_files


def get_audio_file_path_by_id(dir_path, id):
    songs = list_songs_with_ids(dir_path)
    if id not in songs:
        return None

    song_name = songs[id]
    for root, dirs, files in os.walk(dir_path):
        for file in files:
            if file.startswith(song_name) and file.lower().endswith(('.mp3', '.flac', '.wav')):
                return os.path.join(root, file)

    return None


def get_embedded_lyrics(file_path):
    try:
        audio = File(file_path)
        if audio is None or getattr(audio, 'tags', None) is None:
            return None

        if file_path.lower().endswith('.mp3'):
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
    if os.path.exists(DIRECTORY):
        radioloop()
    else:
        logging.error(f"no folder found {DIRECTORY}")

    print("Available IP addresses:")
    print(" - 127.0.0.1")
    for addr in get_local_ip_addresses():
        print(f" - {addr}")

    HOST = input("Enter the IP address to use: ") or "0.0.0.0"
    PORT = int(input("Enter the port to use: ") or "8080")    

    def open_browser_on_start():
        try:
            host_for_browser = HOST if HOST and HOST != "0.0.0.0" else "127.0.0.1"
            url = f'http://{host_for_browser}:{PORT}/'
            time.sleep(1)
            webbrowser.open_new_tab(url)
        except Exception as e:
            logging.info("Failed to open browser: %s", e)

    threading.Thread(target=open_browser_on_start, daemon=True).start()

    app.run(host=HOST, port=PORT)
    
    