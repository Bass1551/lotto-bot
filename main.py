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

def start_http_server():
    """Start internal HTTP server for Render health checks and LIFF static files."""
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=DIRECTORY, **kwargs)

    try:
        with socketserver.TCPServer(("0.0.0.0", PORT), Handler) as httpd:
            logger.info("Serving LIFF & Render Health check on 0.0.0.0:%d", PORT)
            httpd.serve_forever()
    except Exception as e:
        logger.error("HTTP server error: %s", e)

def main() -> None:
    logger.info("=" * 50)
    logger.info("Lottery Bot starting...")
    logger.info("=" * 50)

    # Start HTTP server thread for Render Web Service Health Check
    http_thread = threading.Thread(target=start_http_server, daemon=True)
    http_thread.start()

    db = Database("lottery_results.db")

    try:
        sender = LineSender()
    except (ValueError, RuntimeError) as e:
        logger.error("%s", e)
        logger.error("Please set LINE_CHANNEL_ACCESS_TOKEN and LINE_GROUP_ID in .env")
        sys.exit(1)

    bot = LotteryScheduler(config_path="config.json", db=db, sender=sender)
    bot.start()
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
