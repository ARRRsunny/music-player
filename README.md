# Music Player

This is a lightweight, containerized music player application built with Flask, Nginx, and Docker. The application supports serving audio files, images, and lyrics from a directory, and includes a basic radio loop functionality.

![MusicPlay](https://github.com/ARRRsunny/music-player/blob/main/assets/image.png)
---

## Features

- **Music Playback**: Serve audio files (`.mp3`, `.flac`, `.wav`) with metadata.
- **Lyrics and Album Art**: Serve lyrics (`.lrc`) and cover images (`.jpg`, `.png`) for each song.
- **Radio Loop**: Automatically plays random songs in a loop with a timer.
- **REST API**: Expose endpoints to list songs, serve files, and manage radio states.
- **Web Interface**: A simple HTML-based front-end for song selection and playback.
- **Nginx Reverse Proxy**: Acts as a reverse proxy for the Flask application.
- **Dockerized**: Fully containerized using Docker and Docker Compose.

---

## Project Structure

```
.
├── main.py                # Flask application
├── requirements.txt       # Python dependencies
├── nginx.conf             # Nginx configuration
├── Dockerfile             # Dockerfile for Flask app
├── Dockerfile-nginx.txt   # Dockerfile for Nginx
├── docker-compose.yml     # Docker Compose configuration
└── music/                 # Directory to store music files
```

---

## Prerequisites

- **Docker**: Install [Docker](https://www.docker.com/get-started).
- **Docker Compose**: Install [Docker Compose](https://docs.docker.com/compose/install/).
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

3. **Edit the Address in `nginx.conf`**:
   - Open `nginx.conf` and replace `youraddress:8080` with either:
     - Your **local machine's IP address** (e.g., `192.168.x.x:8080`).
     - Or, your **ZeroTier IP address** if you're using ZeroTier.

   Example:
   ```nginx
   server_name 192.168.1.100:8080; # Replace with your IP
   ```

4. **Build and Start the Containers**:

   ```bash
   docker-compose up --build
   ```

5. **Access the Application**:
   - Open your web browser and navigate to `http://<your-ip>:8080`.

---

## Important Configuration Details

### Flask Address

The Flask application runs on `0.0.0.0` to ensure it listens on all network interfaces. Nginx will forward requests to this internal Flask address.  

You **must** update the `nginx.conf` file with your own IP address to make the application accessible from your network or ZeroTier.

---

## Endpoints

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

### Nginx Configuration

- Nginx is configured to reverse proxy requests to the Flask application.
- Proxy passes requests to `http://flask:8080`.

---

## Docker Configuration

### Flask Service

- **Dockerfile**:
  - Based on `python:3.9-slim`.
  - Installs dependencies from `requirements.txt`.
  - Exposes port `8080` for Flask.

### Nginx Service

- **Dockerfile-nginx.txt**:
  - Based on `nginx:alpine`.
  - Copies the custom `nginx.conf` file into the container.
  - Configures Nginx to listen and proxy requests to Flask.

### Networking

- Both services are connected to a `bridge` network named `app-network`.

---

## Environment Variables

- `DIRECTORY`: The folder where music files are stored (default: `music`).
- `HOST`: Flask binds to `0.0.0.0` to listen on all interfaces.
- `PORT`: Port for the Flask app (default: `8080`).

---

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

## Deployment

### Production Deployment

For production setup:
1. Use a production-grade WSGI server like Gunicorn for Flask.
2. Secure Nginx with HTTPS using certificates (e.g., Let's Encrypt).
3. Use ZeroTier to make the application accessible over a secure virtual network if needed.

---

## Troubleshooting

1. **Music Directory Not Found**:
   - Ensure the `music` directory exists and contains valid audio files.

2. **Nginx Fails to Start**:
   - Check the `nginx.conf` file for syntax errors.

3. **Flask Crashes**:
   - Check the Flask logs for errors using:
     ```bash
     docker-compose logs flask
     ```

4. **API Not Accessible**:
   - Ensure the containers are running:
     ```bash
     docker-compose ps
     ```

---

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

---

## Author

Developed by [@ARRRsunny](https://github.com/ARRRsunny).
