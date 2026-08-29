# -*- coding: utf-8 -*-
"""
Lottery Bot – main entry point.
"""

from __future__ import annotations

import os
import signal
import sys
import time
import threading
import http.server
import socketserver
import urllib3

from database import Database
from line_sender import LineSender
from scheduler import LotteryScheduler
from utils import setup_logging

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
logger = setup_logging()

PORT = int(os.environ.get("PORT", 8000))
DIRECTORY = "public"

def start_http_server(db: Database, sender: LineSender):
    """Start internal HTTP server for Render health checks, LIFF static files, Quick API, and LINE Webhook."""
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=DIRECTORY, **kwargs)

        def do_POST(self):
            if self.path == "/api/send":
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length).decode("utf-8")
                try:
                    data = json.loads(body)
                    name = data.get("name", "")
                    top3 = str(data.get("top3", "")).zfill(3)[-3:]
                    bot2 = str(data.get("bottom2", "")).zfill(2)[-2:]

                    flag = "🎯"
                    try:
                        with open("config.json", encoding="utf-8") as f:
                            cfg = json.load(f)
                            for c in cfg:
                                if c["name"] == name:
                                    flag = c.get("flag", "🎯")
                                    break
                    except Exception:
                        pass

                    ok = sender.send_result_flex(name=name, top3=top3, bottom2=bot2, flag=flag)
                    if ok:
                        db.save_result(name, top3, bot2)

                    res_bytes = json.dumps({"ok": ok}).encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(res_bytes)))
                    self.end_headers()
                    self.wfile.write(res_bytes)
                except Exception as exc:
                    err_bytes = json.dumps({"ok": False, "error": str(exc)}).encode("utf-8")
                    self.send_response(500)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(err_bytes)
                return

            elif self.path == "/webhook":
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length).decode("utf-8")
                try:
                    data = json.loads(body)
                    events = data.get("events", [])
                    for ev in events:
                        if ev.get("type") == "message" and ev.get("message", {}).get("type") == "text":
                            txt = ev["message"]["text"].strip()
                            pattern = re.compile(r"^(?:ส่งผล\s*)?(?P<name>[\u0E00-\u0E7Fa-zA-Z0-9\s]+?)\s+(?P<top3>\d{3})[\s\-\/]+(?P<bot2>\d{2})$")
                            m = pattern.match(txt)
                            if m:
                                raw_name = m.group("name").strip()
                                top3 = m.group("top3")
                                bot2 = m.group("bot2")

                                matched_lotto = None
                                try:
                                    with open("config.json", encoding="utf-8") as f:
                                        cfg = json.load(f)
                                        for c in cfg:
                                            if raw_name in c["name"] or c["name"] in raw_name:
                                                matched_lotto = c
                                                break
                                except Exception:
                                    pass

                                target_name = matched_lotto["name"] if matched_lotto else raw_name
                                flag = matched_lotto.get("flag", "🎯") if matched_lotto else "🎯"

                                ok = sender.send_result_flex(name=target_name, top3=top3, bottom2=bot2, flag=flag)
                                if ok:
                                    db.save_result(target_name, top3, bot2)
                except Exception as exc:
                    logger.error("Webhook processing error: %s", exc)

                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"OK")
                return

            super().do_POST()

    try:
        with socketserver.TCPServer(("0.0.0.0", PORT), Handler) as httpd:
            logger.info("Serving LIFF, Quick API & LINE Webhook on 0.0.0.0:%d", PORT)
            httpd.serve_forever()
    except Exception as e:
        logger.error("HTTP server error: %s", e)


def keep_alive_loop():
    """Ping Render Web Service every 4 minutes to prevent Render Free Tier from sleeping."""
    import requests
    render_url = os.environ.get("RENDER_EXTERNAL_URL", "https://lotto-bot-uy9t.onrender.com")
    time.sleep(20)
    while True:
        try:
            r = requests.get(render_url, timeout=15)
            logger.info("Keep-Alive Ping to %s -> Status %d (Prevents Render Sleep)", render_url, r.status_code)
        except Exception as err:
            logger.debug("Keep-Alive ping note: %s", err)
        time.sleep(240)  # Ping every 4 minutes (240s)


def main() -> None:
    logger.info("=" * 50)
    logger.info("Lottery Bot starting...")
    logger.info("=" * 50)

    db = Database("lottery_results.db")

    try:
        sender = LineSender()
    except (ValueError, RuntimeError) as e:
        logger.error("%s", e)
        logger.error("Please set LINE_CHANNEL_ACCESS_TOKEN and LINE_GROUP_ID in .env")
        sys.exit(1)

    # Start HTTP server thread for Render Web Service Health Check & Quick API
    http_thread = threading.Thread(target=start_http_server, args=(db, sender), daemon=True)
    http_thread.start()

    # Start Keep-Alive Ping Thread to prevent Render Free Tier Sleep
    ping_thread = threading.Thread(target=keep_alive_loop, daemon=True)
    ping_thread.start()

    bot = LotteryScheduler(config_path="config.json", db=db, sender=sender)
    bot.start()
    bot.send_yesterday_summary()
    bot.check_pending_due_today()

    def handle_signal(signum, frame):
        logger.info("Received signal %s – shutting down...", signum)
        bot.shutdown()
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    logger.info("Bot is running 24/7 on Cloud Server.")
    try:
        while True:
            time.sleep(10)
    except KeyboardInterrupt:
        bot.shutdown()

if __name__ == "__main__":
    main()
