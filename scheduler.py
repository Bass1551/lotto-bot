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
from utils import format_result_message, generate_summary_report, setup_logging

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

        # Schedule nightly summary report at 23:59
        self.scheduler.add_job(
            self.send_daily_summary,
            trigger=CronTrigger(hour=23, minute=59, timezone=TZ),
            id="daily_summary_report",
            replace_existing=True,
        )
        logger.info("Scheduled daily summary report at 23:59 (Asia/Bangkok)")

        self.scheduler.start()
        logger.info("Scheduler started")

    def send_daily_summary(self, target_date: date | None = None) -> None:
        """Send the full formatted summary text report for the day into the LINE group."""
        if not self.sender:
            logger.warning("No sender configured – cannot send daily summary report")
            return

        today = target_date or datetime.now(TZ).date()
        daily_results = self.db.get_daily_results(result_date=today)
        if not daily_results:
            logger.info("No lottery results recorded for %s – skip summary report", today)
            return

        report_text = generate_summary_report(daily_results, target_date=today)
        logger.info("Sending Daily Summary Report for %s:\n%s", today, report_text)
        self.sender.send_text(report_text)

    def send_yesterday_summary(self) -> None:
        """Send yesterday's summary report for ALL configured lotteries into the LINE group upon startup."""
        if not self.sender:
            logger.warning("No sender configured – cannot send yesterday summary report")
            return

        yesterday = datetime.now(TZ).date() - timedelta(days=1)
        logger.info("Generating Yesterday's Full Summary Report for %s...", yesterday)

        db_results = {r["lottery_name"]: r for r in self.db.get_daily_results(result_date=yesterday)}

        full_results = []
        for lotto in self.lotteries:
            name = lotto["name"]
            flag = lotto.get("flag", "🎯")

            if name in db_results:
                r = db_results[name]
                full_results.append({
                    "lottery_name": name,
                    "top3": r["top3"],
                    "bottom2": r["bottom2"],
                    "flag": flag,
                })
            else:
                try:
                    res = self._scrape(lotto)
                    if res:
                        full_results.append({
                            "lottery_name": name,
                            "top3": res["top3"],
                            "bottom2": res["bottom2"],
                            "flag": flag,
                        })
                except Exception:
                    pass

        if full_results:
            report_text = generate_summary_report(full_results, target_date=yesterday)
            logger.info("Sending Yesterday's Full Summary Report (%d lotteries):\n%s", len(full_results), report_text)
            self.sender.send_text(report_text)

    def check_pending_due_today(self) -> None:
        """Check and send any lotteries whose draw time has passed today and not sent yet."""
        now_dt = datetime.now(TZ)
        today = now_dt.date()
        is_weekend = (today.weekday() in (5, 6))
        current_time_str = now_dt.strftime("%H:%M")

        grouped_by_time = defaultdict(list)
        for lotto in self.lotteries:
            if is_weekend and not lotto.get("weekend", False):
                continue
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
        is_weekend = (today.weekday() in (5, 6))

        if is_weekend:
            pending_lottos = [l for l in lotto_list if l.get("weekend", False) and not self.db.already_sent(l["name"], today)]
        else:
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

                try:
                    res = self._scrape(lotto)
                    if res:
                        collected_results.append({
                            "lotto": lotto,
                            "result": res
                        })
                except Exception as exc:
                    logger.warning("Error scraping %s on attempt %d: %s", lotto["name"], attempt, exc)

            if collected_results:
                is_group_full = (len(collected_results) == len(pending_lottos)) or (attempt == max_attempts)
                is_single = (len(lotto_list) == 1)

                if is_group_full or is_single:
                    if len(collected_results) > 1:
                        # Combined card for multiple ready lotteries
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
                        # Send single ready lottery
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
        now_dt = datetime.now(TZ)
        if today is None:
            if now_dt.strftime("%H:%M") < "06:00" or lotto.get("overnight", False):
                result_date = now_dt.date() - timedelta(days=1)
            else:
                result_date = now_dt.date()
        else:
            result_date = today

        if self.db.already_sent(name, result_date):
            logger.info("%s was already sent for date %s – skip", name, result_date)
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
