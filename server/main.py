from flask import Flask, jsonify, abort, send_file
from flask_cors import CORS
import os
import logging
import urllib.request as ul
import threading
from mutagen.wave import WAVE 
import time
from mutagen import File
import numpy as np
app = Flask(__name__)

CORS(app)

currentradioID = 0
timer = None

DIRECTORY = "../"   #music folder location
HOST = "1.1.1.1"  #change to the ip use want to use
PORT = 1234 #0-65535

logging.basicConfig(level=logging.INFO)

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

def read_timelist(dir_path):
    lengthlist = {}
    song_id = 0
    for root, dirs, files in os.walk(dir_path):
        for file in files:
            if file.endswith(('.mp3', '.flac', '.wav')):
                file_path = os.path.join(root, file)
                audio = File(file_path)
                if audio is not None:
                    length = int(audio.info.length)
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
    radioloop()
    app.run(host=HOST, port=PORT)
    