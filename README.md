# Music Player

This project is a lightweight, containerized music player application built with Flask and Docker. It comes with a simple web-based UI for playback control, song management, and radio functionality. The application is designed to serve audio files, lyrics, and album art, while supporting various playback modes such as looping, queueing, and random play.

![MusicPlay](https://github.com/ARRRsunny/music-player/blob/main/assets/image.png)

---

## Features

### Backend Features:
- **Music Playback**: Serve audio files (`.mp3`, `.flac`, `.wav`) with metadata.
- **Lyrics and Album Art**: Serve lyrics (`.lrc`) and cover images (`.jpg`, `.png`) for each song.
- **Radio Loop**: Automatically plays random songs in a loop with a timer.
- **REST API**: Expose endpoints to list songs, serve files, and manage radio states.

### Frontend Features:
- **Web-Based UI**:  
  A simple interface for controlling playback, selecting songs, and managing playback modes.
- **Playback Controls**:
  - Play/Pause (`▶️`)
  - Volume Adjustment (`🔊`)
  - Skip to Next (`⏩`) or Previous (`⏪`) song
- **Playback Modes**:  
  - `Loop`: Repeat the current song or playlist.
  - `Random`: Play songs in random order.
  - `Once`: Play a selected song once without looping.
  - `Queue`: Play songs in a specific order.
  - `Radio`: Continuous random song playback.
- **Lyrics Display**:  
  Displays lyrics for the current song if available.
- **Address Input**:  
  A section to send commands or configurations, such as connecting to specific servers or playlists.

---

## Project Structure

```
.
├── app.py                # Flask application
├── requirements.txt       # Python dependencies
├── Dockerfile             # Dockerfile for Flask app
├── music/                 # Directory to store music files
├── start.sh               # Setting Zerotier
└── musicplayer_server.html # Web-based UI
```

---

## Prerequisites

- **Docker**: Install [Docker](https://www.docker.com/get-started).
- **ZeroTier (Optional)**: If you want to access the app from an external network, you can use [ZeroTier](https://www.zerotier.com/).
- Music files should be placed in a `music` directory in the root of the project.

---

## Setup and Installation

1. **Clone the Repository**:

   ```bash
   git clone https://github.com/ARRRsunny/music-player.git
   cd music-player
   ```

2. **Prepare Your Music Files**:
   - Create a folder named `music` in the root directory.
   - Add your `.mp3`, `.flac`, `.wav`, `.lrc`, `.jpg`, and `.png` files to the `music` folder.


3. **Build and Start the Containers**:

   ```bash
   docker build -t flask-zerotier .
   ```
   Run the container while using, replacing <NETWORK_ID> and <API_TOKEN>:
   ```bash
   docker run -d \
   --name flask-app \
   --cap-add=NET_ADMIN \
   --device=/dev/net/tun \
   -e ZEROTIER_NETWORK_ID=<NETWORK_ID> \
   -e ZEROTIER_API_TOKEN=<API_TOKEN> \
   flask-zerotier
   ```
4. **Setting Zerotier**:
   Join network:
   ```bash
   docker exec flask-app zerotier-cli join <NETWORK_ID>
   200 join OK
   ```
   Confirm Zerotier IP:
   ```bash
   docker exec flask-app zerotier-cli listnetworks
   ```
   Get your ZeroTier address and check the service status:
   ```bash
   docker exec flask-app zerotier-cli status
   200 info 998765f00d 1.2.13 ONLINE
   ```

5. **Access**:
   - Open your browser and navigate to `http://<your-ip>:8080`.

---

## UI Overview

The UI (`musicplayer_server.html`) is served by the Flask backend and provides the following features:

1. **Play and Pause**:  
   - Button: `▶️`  
   - Start or pause the playback of the selected song.

2. **Playback Time Display**:  
   - Displays the current playback time in the format `0:00`.

3. **Volume Control**:  
   - Button: `🔊`  
   - Adjusts the playback volume.

4. **Previous and Next Song**:  
   - Buttons:  
     - `⏪`: Plays the previous song in the queue.  
     - `⏩`: Skips to the next song.

5. **Playback Modes**:  
   - `Loop`, `Random`, `Once`, `Queue`, and `Radio`.

6. **Lyrics Display**:  
   - Section: `Lyrics will appear here...`  
   - Displays the lyrics for the currently playing song if available.

7. **Address Input**:  
   - Section: `Address` with a `send` button.  
   - Allows users to input and send specific commands or addresses.

---

## API Endpoints

### Flask API

- **`GET /`**  
  Serves the web interface from `musicplayer_server.html`.

- **`GET /songs`**  
  Returns a JSON object with all available songs and their IDs.

- **`GET /<song_id>/<file_type>`**  
  Serves specific file types (`audio`, `image`, `lyrics`) for a given song ID.  
  Example: `/1/audio` serves the audio file for song ID 1.

- **`GET /radio`**  
  Returns the current song ID and elapsed time in the radio loop.

---

## Deployment and Configuration

## Example Use Cases

1. **List Songs**:
   - Request: `GET /songs`
   - Response:  
     ```json
     {
       "0": "song1",
       "1": "song2"
     }
     ```

2. **Fetch Audio File**:
   - Request: `GET /0/audio`
   - Response: Returns the `.mp3`, `.flac`, or `.wav` file for song ID `0`.

3. **Radio Loop**:
   - Automatically plays a random song every time the timer expires.

---

## Troubleshooting

1. **Music Directory Not Found**:
   - Ensure the `music` directory exists and contains valid audio files.

2. **Flask Crashes**:
   - Check the Flask logs for errors using:
     ```bash
     docker logs flask-app
     ```

3. **API Not Accessible**:
   - Ensure the containers are running:
     ```bash
     docker logs flask-app
     ```

---


## Author

Developed by [@ARRRsunny](https://github.com/ARRRsunny).
