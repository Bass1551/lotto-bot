# -*- coding: utf-8 -*-
import http.server
import socketserver
import os
import threading
import time
import json
import re
import requests

PORT = int(os.environ.get("PORT", 8000))
DIRECTORY = "public"

def keep_alive():
    """Keep Render web service awake 24/7 by pinging itself every 3 minutes."""
    time.sleep(10)
    url = os.environ.get("RENDER_EXTERNAL_URL") or "https://lotto-bot-uy9t.onrender.com"
    while True:
        try:
            r = requests.get(url, timeout=10)
            print(f"[Keep-Alive] Pinged {url} -> status {r.status_code}")
        except Exception as e:
            print(f"[Keep-Alive] Ping error: {e}")
        time.sleep(180)

class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)

    def do_GET(self):
        if self.path in ("/", "/health", "/ping"):
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"OK")
            return
        super().do_GET()

    def do_POST(self):
        if self.path == "/webhook":
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length).decode("utf-8")
            try:
                data = json.loads(body)
                events = data.get("events", [])
                for ev in events:
                    source = ev.get("source", {})
                    gid = source.get("groupId")
                    if source.get("type") == "group" and gid:
                        try:
                            with open("data/predictor_group_id.txt", "w", encoding="utf-8") as f:
                                f.write(gid)
                        except Exception:
                            pass

                    if ev.get("type") == "message" and ev.get("message", {}).get("type") == "text":
                        txt = ev["message"]["text"].strip()
                        reply_token = ev.get("replyToken")

                        # Handle 'ขอ...', 'ขอแนวทาง...', 'แนวทาง...', 'ขอดู...', 'ขอเลข...' or colloquial shorthand
                        from predictor_bot import PredictorBot, resolve_lottery
                        target_name = None
                        flag = "🎯"

                        pred_match = re.match(r"^(?:ขอ(?:แนวทาง|ดู|เลข)?|แนวทาง|เลข)\s*(?P<query>.+)$", txt, re.IGNORECASE)
                        if pred_match:
                            q = pred_match.group("query").strip()
                            target_name, flag = resolve_lottery(q)
                        else:
                            if len(txt) <= 25 and txt not in ["สวัสดี", "ดีครับ", "ดีค่ะ", "ทดสอบ", "เทส", "test", "hi", "hello", "ok"]:
                                target_name, flag = resolve_lottery(txt)

                        if target_name:
                            try:
                                pbot = PredictorBot(group_id_path="data/predictor_group_id.txt")
                                pbot.reply_or_push_prediction(target_name, flag=flag, reply_token=reply_token, group_id=gid)
                            except Exception as pe:
                                print(f"[Webhook] Predictor error: {pe}")
            except Exception as e:
                print(f"[Webhook] Error: {e}")

            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"OK")
            return

        super().do_POST()

if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    t = threading.Thread(target=keep_alive, daemon=True)
    t.start()
    print(f"Serving LIFF & Webhook on 0.0.0.0:{PORT}")
    with socketserver.TCPServer(("0.0.0.0", PORT), Handler) as httpd:
        httpd.serve_forever()
