# -*- coding: utf-8 -*-
"""Scheduler that checks lottery results only after draw time.

Rules:
- Do not check the website before the configured draw time.
- When draw time arrives, start checking every 1 minute.
- Maximum 30 attempts (≈ 30 minutes).
- Lotteries sharing the same draw time (e.g. 10:30) are grouped into 1 combined Flex card.
- Stop immediately when valid results are found and sent.
"""

from __future__ import annotations

import json
import time
from collections import defaultdict
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
        """Register all jobs grouped by draw time and start the scheduler."""
        grouped_by_time = defaultdict(list)
        for lotto in self.lotteries:
            grouped_by_time[lotto["time"]].append(lotto)

        for time_str, lotto_list in grouped_by_time.items():
            hour, minute = map(int, time_str.split(":"))
            trigger = CronTrigger(hour=hour, minute=minute, timezone=TZ)
            names_str = " + ".join([x["name"] for x in lotto_list])
            self.scheduler.add_job(
                self._check_group_loop,
                trigger=trigger,
                args=[lotto_list],
                id=f"group_{time_str.replace(':', '_')}",
                replace_existing=True,
                misfire_grace_time=300,
            )
            logger.info("Scheduled time slot %s (%s) (Asia/Bangkok)", time_str, names_str)

        self.scheduler.start()
        logger.info("Scheduler started")

    def check_pending_due_today(self) -> None:
        """Check and send any lotteries whose draw time has passed today and not sent yet."""
        now_dt = datetime.now(TZ)
        today = now_dt.date()
        current_time_str = now_dt.strftime("%H:%M")

        grouped_by_time = defaultdict(list)
        for lotto in self.lotteries:
            if lotto["time"] <= current_time_str and not self.db.already_sent(lotto["name"], today):
                grouped_by_time[lotto["time"]].append(lotto)

        for time_str, lotto_list in grouped_by_time.items():
            names_str = " + ".join([x["name"] for x in lotto_list])
            logger.info("Time slot %s (%s) has pending lotteries. Checking now...", time_str, names_str)
            self.scheduler.add_job(
                self._check_group_loop,
                args=[lotto_list],
                id=f"immediate_group_{time_str.replace(':', '_')}_{int(time.time())}",
                replace_existing=True,
            )

    def _check_group_loop(self, lotto_list: list[dict[str, Any]]) -> None:
        """Poll lotteries in a group every 60s up to 30 times. Batch send when available."""
        today = datetime.now(TZ).date()

        pending_lottos = [l for l in lotto_list if not self.db.already_sent(l["name"], today)]
        if not pending_lottos:
            return

        names_title = " + ".join([x["name"] for x in pending_lottos])
        logger.info("=== Start checking time slot (%s) (polling up to 30 min) ===", names_title)
        max_attempts = 30
        interval_sec = 60

        for attempt in range(1, max_attempts + 1):
            logger.info("(%s) attempt %d/%d...", names_title, attempt, max_attempts)
            collected_results = []
            
            for lotto in list(pending_lottos):
                if self.db.already_sent(lotto["name"], today):
                    pending_lottos.remove(lotto)
                    continue

                res = self._scrape(lotto)
                if res:
                    collected_results.append({
                        "lotto": lotto,
                        "result": res
                    })

            if collected_results:
                if len(collected_results) > 1:
                    # Combined card for multiple lotteries
                    items_to_send = []
                    for item in collected_results:
                        l = item["lotto"]
                        r = item["result"]
                        items_to_send.append({
                            "name": l["name"],
                            "top3": r["top3"],
                            "bottom2": r["bottom2"],
                            "flag": l.get("flag", "🎯")
                        })
                    
                    if self.sender:
                        ok = self.sender.send_combined_result_flex(items_to_send)
                        if ok:
                            for item in collected_results:
                                l = item["lotto"]
                                r = item["result"]
                                self.db.save_result(l["name"], r["top3"], r["bottom2"], r.get("full", ""), result_date=today)
                                if l in pending_lottos:
                                    pending_lottos.remove(l)
                    else:
                        for item in collected_results:
                            l = item["lotto"]
                            r = item["result"]
                            self.db.save_result(l["name"], r["top3"], r["bottom2"], r.get("full", ""), result_date=today)
                            if l in pending_lottos:
                                pending_lottos.remove(l)
                else:
                    # Single lottery card
                    item = collected_results[0]
                    l = item["lotto"]
                    r = item["result"]
                    self._send_and_save(l, r, today=today)
                    if l in pending_lottos:
                        pending_lottos.remove(l)

            if not pending_lottos:
                logger.info("All lotteries in group (%s) sent – stop polling", names_title)
                return

            if attempt < max_attempts:
                time.sleep(interval_sec)

        logger.error("Group (%s): timeout after %d attempts", names_title, max_attempts)

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
        """Format message, push to LINE, then record in DB."""
        name = lotto["name"]
        flag = lotto.get("flag", "🎯")
        top3 = result["top3"]
        bottom2 = result["bottom2"]
        full = result.get("full", "")
        result_date = today or datetime.now(TZ).date()

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
