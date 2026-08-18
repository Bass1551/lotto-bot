# -*- coding: utf-8 -*-
import http.server
import socketserver
import os
import threading
import time
import requests

PORT = 8000
DIRECTORY = "public"

def keep_alive():
    """Keep Render web service awake 24/7 by pinging itself every 4 minutes."""
    time.sleep(10)
    url = os.environ.get("RENDER_EXTERNAL_URL") or "https://lotto-bot-uy9t.onrender.com"
    while True:
        try:
            r = requests.get(url, timeout=10)
            print(f"[Keep-Alive] Pinged {url} -> status {r.status_code}")
        except Exception as e:
            print(f"[Keep-Alive] Ping error: {e}")
        time.sleep(240)

class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)

if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    t = threading.Thread(target=keep_alive, daemon=True)
    t.start()
    with socketserver.TCPServer(("0.0.0.0", PORT), Handler) as httpd:
        print(f"Serving LIFF HTML on 0.0.0.0:{PORT}")
        httpd.serve_forever()
