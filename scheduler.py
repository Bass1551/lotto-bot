# -*- coding: utf-8 -*-
"""Scheduler that checks lottery results only after draw time.

Rules:
- Do not check the website before the configured draw time.
- When draw time arrives, start checking every 1 minute.
- Maximum 10 attempts (≈ 10 minutes).
- Stop immediately when a valid result is found and sent.
- If 10 minutes pass without result → log and wait for next day.
"""

from __future__ import annotations

import json
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from database import Database
from line_sender import LineSender
from parsers import get_parser
from parsers.base import ParseError
from utils import format_result_message, setup_logging

logger = setup_logging()
TZ = ZoneInfo("Asia/Bangkok")


class LotteryScheduler:
    """Main orchestrator: schedule + scrape + send + deduplicate."""

    def __init__(
        self,
        config_path: str = "config.json",
        db: Database | None = None,
        sender: LineSender | None = None,
    ) -> None:
        self.config_path = Path(config_path)
        self.db = db or Database()
        self.sender = sender
        self.scheduler = BackgroundScheduler(timezone=TZ)
        self.lotteries: list[dict[str, Any]] = []
        self._load_config()

    def _load_config(self) -> None:
        with open(self.config_path, encoding="utf-8") as f:
            self.lotteries = json.load(f)
        logger.info("Loaded %d lotteries from %s", len(self.lotteries), self.config_path)

    def start(self) -> None:
        """Register all jobs and start the scheduler."""
        for lotto in self.lotteries:
            name = lotto["name"]
            time_str = lotto["time"]  # "HH:MM"
            hour, minute = map(int, time_str.split(":"))

            # Trigger exactly at draw time every day
            trigger = CronTrigger(hour=hour, minute=minute, timezone=TZ)
            self.scheduler.add_job(
                self._check_loop,
                trigger=trigger,
                args=[lotto],
                id=f"lotto_{name}",
                replace_existing=True,
                misfire_grace_time=300,  # allow 5 min late start
            )
            logger.info("Scheduled %s at %s (Asia/Bangkok)", name, time_str)

        self.scheduler.start()
        logger.info("Scheduler started")

    def check_pending_due_today(self) -> None:
        """Check and send any lotteries whose draw time has passed today and not sent yet."""
        now_dt = datetime.now(TZ)
        today = now_dt.date()
        current_time_str = now_dt.strftime("%H:%M")

        logger.info("Checking pending lotteries due today (Current time: %s)...", current_time_str)
        for lotto in self.lotteries:
            name = lotto["name"]
            draw_time_str = lotto["time"]
            if draw_time_str <= current_time_str and not self.db.already_sent(name, today):
                logger.info("Lottery '%s' (due at %s) has not been sent today. Checking now...", name, draw_time_str)
                # Run check loop in a non-blocking thread
                self.scheduler.add_job(
                    self._check_loop,
                    args=[lotto],
                    id=f"immediate_{name}_{int(time.time())}",
                    replace_existing=True,
                )

    def _check_loop(self, lotto: dict[str, Any]) -> None:
        """Called at draw time. Poll every 60 s up to 30 times."""
        name = lotto["name"]
        today = datetime.now(TZ).date()

        if self.db.already_sent(name, today):
            logger.info("%s already sent today – skip", name)
            return

        logger.info("=== Start checking %s (polling up to 30 min) ===", name)
        max_attempts = 30
        interval_sec = 60

        for attempt in range(1, max_attempts + 1):
            logger.info("%s attempt %d/%d (waiting for site to update)...", name, attempt, max_attempts)
            try:
                result = self._scrape(lotto)
                if result:
                    self._send_and_save(lotto, result, today=today)
                    logger.info("%s result sent successfully – stop polling", name)
                    return
            except Exception as exc:
                logger.warning("%s attempt %d failed: %s", name, attempt, exc)

            if attempt < max_attempts:
                time.sleep(interval_sec)

        logger.error(
            "%s: no result after %d attempts – give up until tomorrow",
            name,
            max_attempts,
        )

    def _scrape(self, lotto: dict[str, Any]) -> dict[str, str] | None:
        """Run the appropriate parser. Returns result dict or None."""
        parser_key = lotto["parser"]
        url = lotto.get("url")
        parser = get_parser(parser_key, url=url, lotto_name=lotto["name"])
        try:
            return parser.run()
        except ParseError as e:
            logger.warning("ParseError for %s: %s", lotto["name"], e)
            return None

    def _send_and_save(
        self,
        lotto: dict[str, Any],
        result: dict[str, str],
        today: date | None = None,
    ) -> None:
        """Format message, push to LINE, then record in DB (atomic-ish)."""
        name = lotto["name"]
        flag = lotto.get("flag", "🎯")
        top3 = result["top3"]
        bottom2 = result["bottom2"]
        full = result.get("full", "")
        # ใช้วันที่ที่ส่งมาจาก _check_loop (เขตเวลาไทย) ถ้าไม่มีก็ fallback
        result_date = today or datetime.now(TZ).date()

        # Double-check duplicate right before sending (ใช้ result_date เดียวกัน)
        if self.db.already_sent(name, result_date):
            logger.info("%s was already sent by another process – skip", name)
            return

        message = format_result_message(name, top3, bottom2, flag=flag)
        logger.info("Prepared message:\n%s", message)

        if self.sender is None:
            logger.warning("No LineSender configured – message not sent (dry-run)")
            self.db.save_result(name, top3, bottom2, full, result_date=result_date)
            return

        ok = self.sender.send_result_flex(name, top3, bottom2, flag=flag)
        if ok:
            self.db.save_result(name, top3, bottom2, full, result_date=result_date)
        else:
            logger.error("LINE send failed for %s – will retry next attempt", name)

    def shutdown(self) -> None:
        self.scheduler.shutdown(wait=False)
        logger.info("Scheduler shut down")
