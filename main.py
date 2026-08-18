# -*- coding: utf-8 -*-
"""
Lottery Bot – main entry point.

Usage:
    1. pip install -r requirements.txt
    2. playwright install chromium          # only if any site needs JS
    3. Edit .env  → put real LINE_CHANNEL_ACCESS_TOKEN and LINE_GROUP_ID
    4. python main.py

The bot will stay running and check each lottery only after its configured
draw time, every 1 minute, maximum 10 minutes, then stop until next day.
"""

from __future__ import annotations

import signal
import sys
import time
import urllib3

from database import Database
from line_sender import LineSender
from scheduler import LotteryScheduler
from utils import setup_logging

# Suppress InsecureRequestWarning when verify=False is used on some sites
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = setup_logging()


def main() -> None:
    logger.info("=" * 50)
    logger.info("Lottery Bot starting...")
    logger.info("=" * 50)

    db = Database("lottery_results.db")

    # LINE sender – will raise if tokens are missing
    try:
        sender = LineSender()
    except (ValueError, RuntimeError) as e:
        logger.error("%s", e)
        logger.error(
            "Please set LINE_CHANNEL_ACCESS_TOKEN and LINE_GROUP_ID in .env"
        )
        sys.exit(1)

    bot = LotteryScheduler(config_path="config.json", db=db, sender=sender)
    bot.start()
    bot.check_pending_due_today()

    # Graceful shutdown
    def handle_signal(signum, frame):
        logger.info("Received signal %s – shutting down...", signum)
        bot.shutdown()
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    logger.info("Bot is running. Press Ctrl+C to stop.")
    try:
        while True:
            time.sleep(10)
    except KeyboardInterrupt:
        bot.shutdown()


if __name__ == "__main__":
    main()
