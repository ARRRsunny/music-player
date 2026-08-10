from flask import Flask, jsonify, abort, send_file, Response
from flask_cors import CORS
import io
import os
import logging
import urllib.request as ul
import threading
from mutagen.wave import WAVE
import time
from mutagen import File, MutagenError
import numpy as np
app = Flask(__name__)

CORS(app)

currentradioID = 0
timer = None




DIRECTORY = "music"   #music folder location in docker
HOST = "0.0.0.0"  #change to the ip use want to use
PORT = 8080 #0-65535

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
        return send_file("musicplayer_server.html")
    except Exception as e:
        logging.error("Error serving HTML: %s", e)
        abort(500, "Internal server error")

@app.route("/<int:song_id>/<file_type>", methods=["GET"])
def serve_files(song_id, file_type):
    try:
        files = get_files_by_id(DIRECTORY, song_id)
        if not files:
            abort(404, "Song not found")

        if file_type == 'audio':
            audio_path = get_audio_path(files)
            if audio_path:
                return send_file(audio_path, mimetype=get_content_type(os.path.splitext(audio_path)[1]))
            abort(404, "Audio not found")

        if file_type == 'image':
            if '.jpg' in files or '.png' in files:
                ext = '.jpg' if '.jpg' in files else '.png'
                return send_file(files[ext], mimetype=get_content_type(ext))

            audio_path = get_audio_path(files)
            if not audio_path:
                abort(404, "Image not found")

            image_data = extract_embedded_image(audio_path)
            if image_data:
                data, mime_type = image_data
                return send_file(io.BytesIO(data), mimetype=mime_type)

            abort(404, "Image not found")

        if file_type == 'lyrics':
            if '.lrc' in files:
                return send_file(files['.lrc'], mimetype='text/plain')

            audio_path = get_audio_path(files)
            if not audio_path:
                abort(404, "Lyrics not found")

            lyrics_text = extract_embedded_lyrics(audio_path)
            if lyrics_text:
                return Response(lyrics_text, mimetype='text/plain')

            abort(404, "Lyrics not found")

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

def get_audio_path(file_map):
    for ext in ['.mp3', '.flac', '.wav']:
        if ext in file_map:
            return file_map[ext]
    return None


def extract_embedded_image(file_path):
    try:
        audio = File(file_path)
    except MutagenError as e:
        logging.warning("Unable to read embedded artwork from %s: %s", file_path, e)
        return None

    if audio is None or not hasattr(audio, 'tags') or audio.tags is None:
        return None

    # MP3 ID3 APIC frames
    try:
        apics = audio.tags.getall('APIC')
    except Exception:
        apics = []

    if apics:
        apic = apics[0]
        return apic.data, apic.mime

    # FLAC pictures
    if hasattr(audio, 'pictures') and audio.pictures:
        pic = audio.pictures[0]
        return pic.data, pic.mime

    # Some formats may present a single APIC tag under a string key
    for key in audio.tags.keys():
        if key.startswith('APIC'):
            tag = audio.tags[key]
            if isinstance(tag, list):
                tag = tag[0]
            if hasattr(tag, 'data'):
                mime_type = getattr(tag, 'mime', 'image/jpeg')
                return tag.data, mime_type

    return None


def extract_embedded_lyrics(file_path):
    try:
        audio = File(file_path)
    except MutagenError as e:
        logging.warning("Unable to read embedded lyrics from %s: %s", file_path, e)
        return None

    if audio is None or not hasattr(audio, 'tags') or audio.tags is None:
        return None

    # MP3 ID3 USLT frames
    try:
        uslts = audio.tags.getall('USLT')
    except Exception:
        uslts = []

    if uslts:
        return uslts[0].text

    # FLAC and Vorbis comment lyrics fields
    for key in ['LYRICS', 'UNSYNCEDLYRICS', 'lyrics', 'LYRIC', 'TEXT']:
        value = audio.tags.get(key)
        if value:
            return value[0] if isinstance(value, list) else value

    return None

def read_timelist(dir_path):
    lengthlist = {}
    song_id = 0
    for root, dirs, files in os.walk(dir_path):
        for file in files:
            if file.endswith(('.mp3', '.flac', '.wav')):
                file_path = os.path.join(root, file)
                try:
                    audio = File(file_path)
                except MutagenError as e:
                    logging.warning("Skipping invalid audio file %s: %s", file_path, e)
                    continue

                if audio is None or not hasattr(audio, 'info') or audio.info is None:
                    logging.warning("Skipping unsupported or unreadable audio file %s", file_path)
                    continue

                try:
                    length = int(audio.info.length)
                except Exception as e:
                    logging.warning("Unable to read length from %s: %s", file_path, e)
                    continue

                lengthlist[song_id] = length
                song_id += 1
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
        
    app.run(host=HOST, port=PORT)
    
    