# Music Player

A lightweight Flask-based music server with a simple web UI for playback, lyrics, and album art. This repository includes the Flask backend, a local `music` folder for songs, and a bundled executable for Windows.

![MusicPlay](https://github.com/ARRRsunny/music-player/blob/main/assets/image.png)

---

## Features

- **Audio Streaming**: Serve `.mp3`, `.flac`, and `.wav` files.
- **Lyrics Support**: Serve `.lrc` lyrics files or embedded lyrics from audio metadata.
- **Album Art**: Serve `.jpg` and `.png` images or embedded cover art.
- **Song Listing API**: List available songs with unique IDs.
- **Web UI**: `musicplayer_server.html` provides a browser-based player interface.
- **Windows Executable**: A bundled `music_server.exe` is included for easy launch.

---

## Project Structure

```
.
├── assets/
├── music/                  # Store audio, lyrics, and image files
├── music_server.py         # Flask server
├── music_server.exe        # Bundled Windows executable
├── music_server.spec       # PyInstaller spec file
├── musicplayer_server.html # Web UI file
├── README.md
├── requirements.txt
└── __pycache__/
```

---

## Requirements

- Python 3.8+ (for running from source)
- `pip` for installing dependencies
- `flask`
- `flask-cors`
- `mutagen`
- `numpy`

---

## Install Dependencies

```bash
pip install -r requirements.txt
```

---

## Running from Source

1. Place your music files under the `music/` folder.
   - Supported audio: `.mp3`, `.flac`, `.wav`
   - Supported lyrics: `.lrc`
   - Supported images: `.jpg`, `.png`

2. Start the server:

```bash
python music_server.py
```

3. Open your browser:

```text
http://127.0.0.1:8080
```

---

## Running the Windows Executable

If you want to run the bundled Windows executable, place the `music/` folder next to `music_server.exe` and launch the exe.

The server uses the local `music/` folder first, so files should be available in the same directory as the executable.

---

## API Endpoints

- `GET /`
  - Serves the web UI from `musicplayer_server.html`.

- `GET /songs`
  - Returns a JSON list of available songs and IDs.

- `GET /<song_id>/<file_type>`
  - Serves the requested file type for a song.
  - Supported `file_type` values:
    - `audio`
    - `image`
    - `lyrics`

- `GET /radio`
  - Returns the current radio song ID and elapsed playback time.

---

## Notes

- The server scans the `music/` folder recursively and assigns song IDs from audio filenames.
- Audio will be served only if the corresponding file exists and is readable.
- If the web UI or executable is bundled, make sure the external `music/` folder is present next to the runtime.

---

## Troubleshooting

- **No music found**
  - Ensure `music/` exists alongside `music_server.py` or `music_server.exe`.
  - Verify supported file extensions are present.

- **Audio returns 500**
  - Check the server logs for path or `send_file` errors.
  - Confirm the song ID maps to an existing audio file.

- **UI does not load**
  - Make sure `musicplayer_server.html` is present in the project root.

---

## Author

Developed by [@ARRRsunny](https://github.com/ARRRsunny).
