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

import holidays
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from database import Database
from line_sender import LineSender
from parsers import get_parser
from parsers.base import ParseError
from utils import format_result_message, generate_summary_report, generate_history_report, setup_logging

logger = setup_logging()
TZ = ZoneInfo("Asia/Bangkok")

# International stock exchange holiday calendars (from Investing.com)
STOCK_HOLIDAYS_MAP = {
    "นิเคอิเช้า": (holidays.Japan(), "ญี่ปุ่น (Tokyo Stock Exchange)"),
    "นิเคอิบ่าย": (holidays.Japan(), "ญี่ปุ่น (Tokyo Stock Exchange)"),
    "จีนเช้า": (holidays.China(), "จีน (Shanghai/Shenzhen Stock Exchange)"),
    "จีนบ่าย": (holidays.China(), "จีน (Shanghai/Shenzhen Stock Exchange)"),
    "ฮั่งเส็งเช้า": (holidays.HongKong(), "ฮ่องกง (Hong Kong Stock Exchange)"),
    "ฮั่งเส็งบ่าย": (holidays.HongKong(), "ฮ่องกง (Hong Kong Stock Exchange)"),
    "ไต้หวัน": (holidays.Taiwan(), "ไต้หวัน (Taiwan Stock Exchange)"),
    "หุ้นเกาหลี": (holidays.SouthKorea(), "เกาหลีใต้ (Korea Exchange)"),
    "หุ้นสิงคโปร์": (holidays.Singapore(), "สิงคโปร์ (Singapore Exchange)"),
    "หุ้นไทยเย็น": (holidays.Thailand(), "ไทย (ตลาดหลักทรัพย์แห่งประเทศไทย)"),
    "หุ้นอังกฤษ": (holidays.UnitedKingdom(), "อังกฤษ (London Stock Exchange)"),
    "หุ้นเยอรมัน": (holidays.Germany(), "เยอรมัน (Frankfurt Stock Exchange)"),
    "หุ้นรัสเซีย": (holidays.Russia(), "รัสเซีย (Moscow Exchange)"),
    "หุ้นดาวโจนส์": (holidays.UnitedStates(), "สหรัฐอเมริกา (New York Stock Exchange)"),
    "หวยดาวโจนส์": (holidays.UnitedStates(), "สหรัฐอเมริกา (New York Stock Exchange)"),
}

STOCK_TO_VIP_MAP = {
    "นิเคอิเช้า": "นิเคอิเช้า VIP",
    "นิเคอิบ่าย": "นิเคอิบ่าย VIP",
    "จีนเช้า": "จีนเช้า VIP",
    "จีนบ่าย": "จีนบ่าย VIP",
    "ฮั่งเส็งเช้า": "ฮั่งเส็งเช้า VIP",
    "ฮั่งเส็งบ่าย": "ฮั่งเส็งบ่าย VIP",
    "ไต้หวัน": "ไต้หวัน VIP",
    "หุ้นเกาหลี": "เกาหลี VIP",
    "หุ้นสิงคโปร์": "สิงคโปร์ VIP",
    "หุ้นอังกฤษ": "อังกฤษVIP",
    "หุ้นเยอรมัน": "เยอรมันVIP",
    "หุ้นรัสเซีย": "รัสเซียVIP",
    "หุ้นดาวโจนส์": "หวยดาวโจนส์ VIP",
    "หวยดาวโจนส์": "หวยดาวโจนส์ VIP",
}

VIP_TO_STOCK_MAP = {
    "นิเคอิเช้า VIP": "นิเคอิเช้า",
    "นิเคอิบ่าย VIP": "นิเคอิบ่าย",
    "จีนเช้า VIP": "จีนเช้า",
    "จีนบ่าย VIP": "จีนบ่าย",
    "ฮั่งเส็งเช้า VIP": "ฮั่งเส็งเช้า",
    "ฮั่งเส็งบ่าย VIP": "ฮั่งเส็งบ่าย",
    "ไต้หวัน VIP": "ไต้หวัน",
    "เกาหลี VIP": "หุ้นเกาหลี",
    "สิงคโปร์ VIP": "หุ้นสิงคโปร์",
    "อังกฤษVIP": "หุ้นอังกฤษ",
    "เยอรมันVIP": "หุ้นเยอรมัน",
    "รัสเซียVIP": "หุ้นรัสเซีย",
    "หวยดาวโจนส์ VIP": "หุ้นดาวโจนส์",
}


def is_stock_holiday(stock_name: str, target_date: date) -> tuple[bool, str, str]:
    """Check if a stock lottery is closed on target_date due to market holiday.
    Returns (is_holiday, market_name, holiday_name).
    """
    if stock_name in STOCK_HOLIDAYS_MAP:
        cal, market_name = STOCK_HOLIDAYS_MAP[stock_name]
        if target_date in cal:
            h_name = cal.get(target_date)
            return True, market_name, str(h_name)
    return False, "", ""


WEEKDAY_STOCKS = {
    "หุ้นดาวโจนส์", "หวยหุ้นดาวโจนส์",
    "นิเคอิเช้า", "นิเคอิบ่าย",
    "จีนเช้า", "จีนบ่าย",
    "ฮั่งเส็งเช้า", "ฮั่งเส็งบ่าย",
    "ไต้หวัน", "หุ้นเกาหลี",
    "หุ้นสิงคโปร์", "หุ้นไทยเย็น",
    "หุ้นอังกฤษ", "หุ้นเยอรมัน", "หุ้นรัสเซีย",
}


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

        # Exact chain: When Round N closes -> Send 10-day history of Round N+1 immediately!
        self.WEEKEND_CHAIN = [
            ("07:30", ["ลาว Extra"]),
            ("08:20", ["นิเคอิเช้า VIP", "ฮานอยอาเซียน"]),
            ("09:05", ["จีนเช้า VIP", "ลาว TV", "ฮั่งเส็งเช้า VIP"]),
            ("10:25", ["ฮานอย HD", "ไต้หวัน VIP"]),
            ("11:25", ["ฮานอย Star", "เกาหลี VIP"]),
            ("12:25", ["นิเคอิบ่าย VIP", "ลาว HD"]),
            ("13:35", ["ฮานอย TV", "จีนบ่าย VIP"]),
            ("14:15", ["ฮั่งเส็งบ่าย VIP", "ลาว Star"]),
            ("15:35", ["ฮานอย กาชาด", "สิงคโปร์ VIP"]),
            ("16:05", ["หวยฮานอย พิเศษ"]),
            ("17:00", ["หวยฮานอย"]),
            ("17:05", ["ลาวสามัคคี", "ลาวอาเซียน"]),
            ("18:00", ["หวยฮานอย VIP"]),
            ("20:50", ["หวยลาวSTAR VIP", "อังกฤษVIP"]),
            ("21:40", ["รัสเซียVIP", "เยอรมันVIP", "ฮานอยEXTRA"]),
            ("22:05", ["หวยลาว กาชาด", "หวยดาวโจนส์ VIP"]),
        ]

        self.WEEKDAY_CHAIN = [
            ("07:30", ["ลาว Extra"]),
            ("08:20", ["นิเคอิเช้า", "ฮานอยอาเซียน"]),
            ("09:20", ["จีนเช้า", "ลาว TV"]),
            ("10:20", ["ฮั่งเส็งเช้า", "ฮานอย HD"]),
            ("11:05", ["ไต้หวัน", "ฮานอย Star"]),
            ("12:05", ["หุ้นเกาหลี", "นิเคอิบ่าย"]),
            ("12:50", ["ฮานอย TV", "จีนบ่าย", "ลาว HD"]),
            ("14:05", ["ฮั่งเส็งบ่าย"]),
            ("14:50", ["ฮานอย กาชาด", "หุ้นสิงคโปร์", "ลาว Star", "หุ้นไทยเย็น"]),
            ("16:05", ["หวยฮานอย พิเศษ"]),
            ("16:15", ["ลาวสามัคคี", "ลาวอาเซียน", "หวยลาวSTAR VIP"]),
            ("17:00", ["หวยฮานอย"]),
            ("18:00", ["หวยฮานอย VIP"]),
            ("19:05", ["หวยลาวพัฒนา (จ-ศ)"]),
            ("21:40", ["หุ้นอังกฤษ", "หุ้นรัสเซีย", "หุ้นเยอรมัน", "ฮานอยEXTRA"]),
            ("22:05", ["หวยลาว กาชาด", "หวยดาวโจนส์ VIP", "หุ้นดาวโจนส์"]),
        ]

        # Register weekend chain
        for trig_time, next_lottos in self.WEEKEND_CHAIN:
            h, m = map(int, trig_time.split(":"))
            trig = CronTrigger(hour=h, minute=m, day_of_week="sat,sun", timezone=TZ)
            self.scheduler.add_job(
                self.send_history_by_names,
                trigger=trig,
                args=[next_lottos],
                id=f"chain_wk_{trig_time.replace(':', '_')}",
                replace_existing=True,
                misfire_grace_time=300,
            )

        # Register weekday chain
        for trig_time, next_lottos in self.WEEKDAY_CHAIN:
            h, m = map(int, trig_time.split(":"))
            trig = CronTrigger(hour=h, minute=m, day_of_week="mon-fri", timezone=TZ)
            self.scheduler.add_job(
                self.send_history_by_names,
                trigger=trig,
                args=[next_lottos],
                id=f"chain_wd_{trig_time.replace(':', '_')}",
                replace_existing=True,
                misfire_grace_time=300,
            )

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

    def send_history_by_names(self, lotto_names: list[str]) -> None:
        """Send 15-day historical statistics report for the specified list of next-round lotteries.
        If a regular stock is closed on a weekday holiday, automatically swap to its VIP substitute.
        """
        if not self.sender:
            return

        today = datetime.now(TZ).date()
        is_weekend = (today.weekday() in (5, 6))

        # Check stock holiday substitutions for weekday chains
        actual_names = []
        for name in lotto_names:
            if not is_weekend and name in STOCK_TO_VIP_MAP:
                is_hol, market_name, h_name = is_stock_holiday(name, today)
                if is_hol:
                    vip_name = STOCK_TO_VIP_MAP[name]
                    logger.info(
                        "Stock '%s' is closed today (%s - %s). Swapping history to VIP: '%s'",
                        name, market_name, h_name, vip_name
                    )
                    actual_names.append(vip_name)
                    continue
            actual_names.append(name)

        name_to_flag = {l["name"]: l.get("flag", "🎯") for l in self.lotteries}
        reports = []
        for name in actual_names:
            flag = name_to_flag.get(name, "🎯")
            history = self.db.get_history_results(name, limit=15)
            if history:
                report_text = generate_history_report(name, history, flag=flag)
                reports.append(report_text)

        if reports:
            combined_message = "\n----------------------------\n".join(reports)
            names_summary = " + ".join(actual_names)
            logger.info("Sending next-round 15-day history report for: %s", names_summary)
            self.sender.send_text(combined_message)

    def _backfill_results_for_date(self, target_date: date) -> dict[str, dict]:
        """Fetch and backfill all available results from SMLOT and Edaylotto for target_date to ensure 100% completeness."""
        db_results = {r["lottery_name"]: r for r in self.db.get_daily_results(result_date=target_date)}
        date_type = "today" if target_date == datetime.now(TZ).date() else "yesterday"

        # 1. Backfill from SMLOT
        try:
            from parsers.smlot_reward import SmlotRewardParser
            smlot_all = SmlotRewardParser.fetch_all_smlot_results(force_refresh=True, date_type=date_type)
            for name, res in smlot_all.items():
                if name not in db_results:
                    self.db.save_result(name, res["top3"], res["bottom2"], res.get("full", ""), result_date=target_date)
        except Exception as e:
            logger.warning("Error backfilling %s results from SMLOT: %s", date_type, e)

        # 2. Backfill from Edaylotto for all targets
        try:
            from parsers.edaylotto import get_product_code, EdaylottoClient
            eday_client = EdaylottoClient()
            for lotto in self.lotteries:
                lname = lotto["name"]
                if lname not in db_results and get_product_code(lname):
                    res = eday_client.get_result(lname, target_date)
                    if res:
                        self.db.save_result(lname, res["top3"], res["bottom2"], res.get("full", ""), result_date=target_date)
        except Exception as e:
            logger.warning("Error backfilling %s results from edaylotto: %s", date_type, e)

        return {r["lottery_name"]: r for r in self.db.get_daily_results(result_date=target_date)}

    def send_daily_summary(self, target_date: date | None = None) -> None:
        """Send the full formatted summary text report for the day into the LINE group."""
        if not self.sender:
            logger.warning("No sender configured – cannot send daily summary report")
            return

        today = target_date or datetime.now(TZ).date()
        db_results = self._backfill_results_for_date(today)
        if not db_results:
            logger.info("No lottery results recorded for %s – skip summary report", today)
            return

        is_weekend = (today.weekday() in (5, 6))
        daily_results = list(db_results.values())
        if is_weekend:
            filtered_results = [r for r in daily_results if r["lottery_name"] not in WEEKDAY_STOCKS]
        else:
            filtered_results = daily_results

        if not filtered_results:
            return

        # Sort chronologically by scheduled draw time in config
        time_order = {lotto["name"]: lotto.get("time", "99:99") for lotto in self.lotteries}
        sorted_results = sorted(filtered_results, key=lambda x: time_order.get(x["lottery_name"], "99:99"))

        report_text = generate_summary_report(sorted_results, target_date=today)
        logger.info("Sending Daily Summary Report for %s (%d lotteries):\n%s", today, len(sorted_results), report_text)
        self.sender.send_text(report_text)

    def send_yesterday_summary(self) -> None:
        """Send yesterday's summary report for ALL lotteries from website into the LINE group upon startup."""
        if not self.sender:
            logger.warning("No sender configured – cannot send yesterday summary report")
            return

        yesterday = datetime.now(TZ).date() - timedelta(days=1)
        logger.info("Generating Yesterday's Full Summary Report for %s...", yesterday)
        is_weekend = (yesterday.weekday() in (5, 6))

        db_results = self._backfill_results_for_date(yesterday)
        daily_results = list(db_results.values())
        if is_weekend:
            filtered_results = [r for r in daily_results if r["lottery_name"] not in WEEKDAY_STOCKS]
        else:
            filtered_results = daily_results

        if filtered_results:
            # Sort chronologically by scheduled draw time in config
            time_order = {lotto["name"]: lotto.get("time", "99:99") for lotto in self.lotteries}
            sorted_results = sorted(filtered_results, key=lambda x: time_order.get(x["lottery_name"], "99:99"))

            report_text = generate_summary_report(sorted_results, target_date=yesterday)
            logger.info("Sending Yesterday's Full Summary Report (%d lotteries):\n%s", len(sorted_results), report_text)
            self.sender.send_text(report_text)

    def check_pending_due_today(self) -> None:
        """Check and send any lotteries whose draw time has passed today and not sent yet."""
        now_dt = datetime.now(TZ)
        today = now_dt.date()
        is_weekend = (today.weekday() in (5, 6))
        current_time_str = now_dt.strftime("%H:%M")

        grouped_by_time = defaultdict(list)
        for lotto in self.lotteries:
            name = lotto["name"]
            if is_weekend:
                if not lotto.get("weekend", False):
                    continue
            else:
                # On weekdays, if this is a stock VIP, only check it if its regular stock is on holiday
                if name in VIP_TO_STOCK_MAP:
                    reg_stock = VIP_TO_STOCK_MAP[name]
                    is_hol, _, _ = is_stock_holiday(reg_stock, today)
                    if not is_hol:
                        continue
                if name == "หวยไทย" and today.day not in (1, 16):
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

        pending_lottos = []
        for l in lotto_list:
            name = l["name"]
            if is_weekend:
                if l.get("weekend", False) and not self.db.already_sent(name, today):
                    pending_lottos.append(l)
            else:
                # On weekdays, stock VIPs are only active if their regular stock is closed on holiday
                if name in VIP_TO_STOCK_MAP:
                    reg_stock = VIP_TO_STOCK_MAP[name]
                    is_hol, _, _ = is_stock_holiday(reg_stock, today)
                    if is_hol and not self.db.already_sent(name, today):
                        pending_lottos.append(l)
                else:
                    # Thai government lottery only draws on the 1st and 16th of the month
                    if name == "หวยไทย" and today.day not in (1, 16):
                        continue
                    if not self.db.already_sent(name, today):
                        pending_lottos.append(l)

        if not pending_lottos:
            return

        # Check for stock market holidays (Investing.com calendar)
        active_lottos = []
        for lotto in pending_lottos:
            name = lotto["name"]
            is_hol, market_name, h_name = is_stock_holiday(name, today)
            if is_hol:
                flag = lotto.get("flag", "📈")
                vip_sub = STOCK_TO_VIP_MAP.get(name)
                sub_text = f"\n🔄 สลับส่งผลและสถิติ: {vip_sub} แทนครับ" if vip_sub else "\n⚠️ รอบนี้ไม่มีการออกผลรางวัลครับ"
                holiday_msg = (
                    f"🛑 {flag} แจ้งเตือนตลาดปิด : {name}\n"
                    f"🪐 แอดBaras 🛸\n"
                    f"➖➖➖➖➖➖➖➖\n"
                    f"📅 วันนี้ {today.strftime('%d/%m/%Y')} ตลาดหลักทรัพย์{market_name} ปิดทำการ\n"
                    f"เนื่องในวันหยุด: {h_name}"
                    f"{sub_text}"
                )
                logger.info("Stock market closed for %s on %s (%s). Sending notification...", name, today, h_name)
                if self.sender:
                    self.sender.send_text(holiday_msg)
                # Mark as recorded for today so we don't notify repeatedly
                self.db.save_result(name, "000", "00", full_result="HOLIDAY")
                continue
            active_lottos.append(lotto)

        pending_lottos = active_lottos
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
        full = result.get("full", top3 + bottom2)
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
            # Check and broadcast winning celebration to dedicated predictor group
            try:
                from predictor_bot import PredictorBot
                pbot = PredictorBot(group_id_path="data/predictor_group_id.txt")
                pbot.check_and_send_win(name, top3, bottom2, result_date=result_date, flag=flag)
            except Exception as pe:
                logger.debug("Predictor win check note: %s", pe)
        else:
            logger.error("LINE send failed for %s – will retry next attempt", name)

    def shutdown(self) -> None:
        self.scheduler.shutdown(wait=False)
        logger.info("Scheduler shut down")
