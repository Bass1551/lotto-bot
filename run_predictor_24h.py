# -*- coding: utf-8 -*-
"""
Run Predictor Bot 24/7 Standalone.
Runs ONLY the LINE Webhook server for responding to 'ขอแนวทาง [ชื่อหวย]' requests.
Automated lottery scheduler is disabled – completely quiet unless a user asks for predictions.
"""

from __future__ import annotations

import os
import sys
import time
import signal
import threading
import urllib3

from database import Database
from line_sender import LineSender
from utils import setup_logging

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
logger = setup_logging()

# Import HTTP server from main
from main import start_http_server, keep_alive_loop


def main() -> None:
    logger.info("=" * 60)
    logger.info("🔮 STARTING PREDICTOR BOT (24/7 STANDALONE MODE) 🛸")
    logger.info("=" * 60)
    logger.info("Rules for 24/7 Predictor Bot:")
    logger.info("1. Passive & Reactive only: Sends messages ONLY when a user types:")
    logger.info("   - 'ขอแนวทาง [ชื่อหวย]' หรือ 'ขอ [ชื่อหวย]' หรือ 'แนวทาง [ชื่อหวย]'")
    logger.info("2. Automated lottery scheduler is COMPLETELY DISABLED.")
    logger.info("3. Zero automatic results, zero yesterday summary, zero stock holiday spam.")
    logger.info("=" * 60)

    db = Database("lottery_results.db")

    try:
        sender = LineSender()
    except (ValueError, RuntimeError) as e:
        logger.error("%s", e)
        logger.error("Please set LINE_CHANNEL_ACCESS_TOKEN and LINE_GROUP_ID in .env")
        sys.exit(1)

    # Start HTTP server thread for Webhook & Dashboard
    http_thread = threading.Thread(target=start_http_server, args=(db, sender), daemon=True)
    http_thread.start()

    # Start Keep-Alive Ping Thread for Render
    ping_thread = threading.Thread(target=keep_alive_loop, daemon=True)
    ping_thread.start()

    def handle_signal(signum, frame):
        logger.info("Predictor Bot shutting down cleanly...")
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    logger.info("✅ Predictor Bot is online and listening for requests 24/7...")
    try:
        while True:
            time.sleep(10)
    except KeyboardInterrupt:
        logger.info("Predictor Bot stopped.")


if __name__ == "__main__":
    main()
