from flask import Flask, jsonify, abort, send_file
from flask_cors import CORS
import os
import logging
import urllib.request as ul

app = Flask(__name__)
CORS(app)

DIRECTORY = "../music-player/yourmusic"   #music folder location
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

def list_songs_with_ids(dir):
    songs = {}
    song_id = 0

    for root, dirs, files in os.walk(dir):
        for file in files:
            if file.endswith(('.mp3', '.flac', '.wav')):
                prefix = os.path.splitext(file)[0]
                if prefix not in songs.values():
                    songs[song_id] = prefix
                    song_id += 1

    return songs

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
    app.run(host=HOST, port=PORT)