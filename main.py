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

            if self.path in ("/dashboard", "/dashboard/"):
                self.path = "/dashboard.html"
                return super().do_GET()

            if self.path == "/api/lottery_status":
                from datetime import datetime
                from zoneinfo import ZoneInfo
                from parsers.direct_scraper import get_official_url

                tz = ZoneInfo("Asia/Bangkok")
                now_dt = datetime.now(tz)
                today_date = now_dt.date()
                today_str = today_date.isoformat()
                current_time_str = now_dt.strftime("%H:%M")

                daily_results = db.get_daily_results(today_date)
                sent_map = {r["lottery_name"]: r for r in daily_results}

                cfg_lottos = []
                try:
                    with open("config.json", "r", encoding="utf-8") as f:
                        cfg_lottos = json.load(f)
                except Exception:
                    pass

                items = []
                for l in cfg_lottos:
                    name = l["name"]
                    t_str = l.get("time", "00:00")
                    flag = l.get("flag", "🎯")
                    off_url = get_official_url(name)
                    is_sent = name in sent_map
                    res_obj = sent_map.get(name, {})

                    if is_sent:
                        status = "sent"
                    elif current_time_str >= t_str:
                        status = "checking"
                    else:
                        status = "pending"

                    items.append({
                        "name": name,
                        "time": t_str,
                        "flag": flag,
                        "status": status,
                        "is_sent": is_sent,
                        "top3": res_obj.get("top3", ""),
                        "bottom2": res_obj.get("bottom2", ""),
                        "full": res_obj.get("full_result", ""),
                        "sent_at": res_obj.get("sent_at", ""),
                        "official_url": off_url,
                        "smlot_url": "https://member.smlot.net/",
                    })

                resp_data = {
                    "today": today_str,
                    "current_time": current_time_str,
                    "lotteries": items,
                }
                res_bytes = json.dumps(resp_data, ensure_ascii=False).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Content-Length", str(len(res_bytes)))
                self.end_headers()
                self.wfile.write(res_bytes)
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
                        source_type = source.get("type")
                        target_id = source.get("groupId") or source.get("roomId") or source.get("userId")
                        if source_type == "group" and target_id:
                            logger.info("LINE Webhook group source captured: %s", target_id)
                            try:
                                with open("data/last_captured_group.txt", "w", encoding="utf-8") as f:
                                    f.write(target_id)
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
                                    candidate_tokens = []
                                    try:
                                        candidate_tokens.append(pbot.get_token())
                                    except Exception:
                                        pass
                                    if hasattr(sender, "bot_chain"):
                                        for b in sender.bot_chain:
                                            tok = b.get("token")
                                            if tok and tok not in candidate_tokens:
                                                candidate_tokens.append(tok)
                                    pbot.reply_or_push_prediction(
                                        target_name,
                                        flag=flag,
                                        reply_token=reply_token,
                                        group_id=target_id,
                                        candidate_tokens=candidate_tokens
                                    )
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

    ports_to_try = [PORT]
    for p in (10000, 8000, 8080):
        if p not in ports_to_try:
            ports_to_try.append(p)

    def run_server_instance(port: int):
        try:
            socketserver.TCPServer.allow_reuse_address = True
            with socketserver.TCPServer(("0.0.0.0", port), Handler) as s:
                logger.info("Serving LIFF, Quick API & LINE Webhook on 0.0.0.0:%d", port)
                s.serve_forever()
        except Exception as err:
            logger.debug("Port %d bind notice: %s", port, err)

    # Launch auxiliary ports in daemon threads
    for extra_port in ports_to_try[1:]:
        threading.Thread(target=run_server_instance, args=(extra_port,), daemon=True).start()

    # Run primary port in main server thread
    run_server_instance(ports_to_try[0])


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

    is_cloud_server = bool(os.environ.get("RENDER") or os.environ.get("RENDER_EXTERNAL_URL"))
    default_scheduler = "false" if is_cloud_server else "true"
    enable_scheduler = os.environ.get("ENABLE_SCHEDULER", default_scheduler).lower() in ("true", "1", "yes")
    if "--only-predictor" in sys.argv:
        enable_scheduler = False

    bot = None
    if enable_scheduler:
        bot = LotteryScheduler(config_path="config.json", db=db, sender=sender)
        bot.start()
        bot.send_yesterday_summary()
        bot.check_pending_due_today()

        # Send Lao Extra history if starting up in the morning before draw time
        from zoneinfo import ZoneInfo
        from datetime import datetime
        now_bkk = datetime.now(ZoneInfo("Asia/Bangkok"))
        if now_bkk.strftime("%H:%M") < "08:30" and not db.already_sent("ลาว Extra", now_bkk.date()):
            bot.send_history_by_names(["ลาว Extra"])
    else:
        logger.info("=" * 55)
        logger.info("🔮 Running in PREDICTOR BOT ONLY MODE (24/7 Standalone)")
        logger.info("Lottery Scheduler is DISABLED. Only 'ขอแนวทาง / ขอ / แนวทาง' commands will be handled.")
        logger.info("=" * 55)

    def handle_signal(signum, frame):
        logger.info("Received signal %s – shutting down...", signum)
        if bot:
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
