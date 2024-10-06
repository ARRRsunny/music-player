from http.server import HTTPServer, BaseHTTPRequestHandler
import time
import urllib.request as ul

HOST = "1.1.1.1"  #your ip
PORT = 1234   # any port

class NeuralHTTP(BaseHTTPRequestHandler):
    def do_GET(self):
        url = "https://raw.githubusercontent.com/ARRRsunny/music-player/main/musicplayer.html"
        req = ul.Request(url)
        with ul.urlopen(req) as client:
            htmldata = client.read().decode('utf-8')
        
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        self.wfile.write(htmldata.encode('utf-8'))
    
    def do_POST(self):
        self.send_response(200)
        self.send_header("Content-type", "application/json")
        self.end_headers()
        
        date = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(time.time()))
        self.wfile.write(bytes("time: " + date, "utf-8"))

server = HTTPServer((HOST, PORT), NeuralHTTP)
print("Server started")
server.serve_forever()
server.server_close()

print("Server stopped")