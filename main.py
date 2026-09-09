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
import json
import re
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
            if self.path == "/api/last_group":
                self.send_response(200)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.end_headers()
                try:
                    with open("data/last_captured_group.txt", "r", encoding="utf-8") as f:
                        self.wfile.write(f.read().encode("utf-8"))
                except Exception:
                    self.wfile.write(b"")
                return
            super().do_GET()

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
                        source = ev.get("source", {})
                        if source.get("type") == "group":
                            gid = source.get("groupId")
                            logger.info("LINE Webhook group source captured: %s", gid)
                            try:
                                with open("data/last_captured_group.txt", "w", encoding="utf-8") as f:
                                    f.write(gid)
                            except Exception:
                                pass

                        if ev.get("type") == "message" and ev.get("message", {}).get("type") == "text":
                            txt = ev["message"]["text"].strip()
                            reply_token = ev.get("replyToken")
                            
                            # 0) Handle 'ขอ [ชื่อหวย]', 'ขอแนวทาง [ชื่อหวย]', 'แนวทาง [ชื่อหวย]'
                            pred_match = re.match(r"^(?:ขอ(?:แนวทาง)?|แนวทาง)\s*(?P<query>.+)$", txt, re.IGNORECASE)
                            if pred_match:
                                q = pred_match.group("query").strip()
                                from predictor_bot import PredictorBot, resolve_lottery
                                target_name, flag = resolve_lottery(q)
                                if target_name:
                                    pbot = PredictorBot(group_id_path="data/predictor_group_id.txt")
                                    pbot.reply_or_push_prediction(target_name, flag=flag, reply_token=reply_token, group_id=gid)
                                continue

                            # 1) Handle 'สถิติ [ชื่อหวย]' command
                            if txt.startswith("สถิติ"):
                                lotto_query = txt.replace("สถิติ", "").strip()
                                if lotto_query:
                                    matched_lotto = None
                                    try:
                                        with open("config.json", encoding="utf-8") as f:
                                            cfg = json.load(f)
                                            for c in cfg:
                                                if lotto_query in c["name"] or c["name"] in lotto_query:
                                                    matched_lotto = c
                                                    break
                                    except Exception:
                                        pass
                                    target_name = matched_lotto["name"] if matched_lotto else lotto_query
                                    flag = matched_lotto.get("flag", "🎯") if matched_lotto else "🎯"

                                    # If regular stock is closed on holiday, swap to VIP substitute
                                    try:
                                        from scheduler import STOCK_TO_VIP_MAP, is_stock_holiday, TZ
                                        from datetime import datetime
                                        today = datetime.now(TZ).date()
                                        if target_name in STOCK_TO_VIP_MAP:
                                            is_hol, _, _ = is_stock_holiday(target_name, today)
                                            if is_hol:
                                                target_name = STOCK_TO_VIP_MAP[target_name]
                                                if matched_lotto:
                                                    with open("config.json", encoding="utf-8") as f:
                                                        cfg = json.load(f)
                                                        for c in cfg:
                                                            if c["name"] == target_name:
                                                                flag = c.get("flag", "🎯")
                                                                break
                                    except Exception:
                                        pass

                                    history = db.get_history_results(target_name, limit=15)
                                    if history:
                                        from utils import generate_history_report
                                        report = generate_history_report(target_name, history, flag=flag)
                                        sender.send_text(report)
                                continue

                            # 2) Handle quick result dispatch format e.g. "นอยHD 123 45"
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

    server = None
    for attempt in range(5):
        try:
            socketserver.TCPServer.allow_reuse_address = True
            server = socketserver.TCPServer(("0.0.0.0", PORT), Handler)
            logger.info("Serving LIFF, Quick API & LINE Webhook on 0.0.0.0:%d", PORT)
            break
        except Exception as e:
            logger.warning("HTTP server bind attempt %d failed: %s. Retrying in 2s...", attempt + 1, e)
            time.sleep(2)
    if server:
        with server:
            server.serve_forever()


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
