# -*- coding: utf-8 -*-
"""Parser for Hanoi lotteries from https://www.press.in.th/hanoi-lotto/"""

from __future__ import annotations

import requests
from bs4 import BeautifulSoup
from datetime import datetime
from zoneinfo import ZoneInfo

from parsers.base import BaseParser, ParseError
from utils import setup_logging

logger = setup_logging()
TZ = ZoneInfo("Asia/Bangkok")


class PressHanoiParser(BaseParser):
    """Parses Hanoi Special, Hanoi Normal, and Hanoi VIP from press.in.th."""

    def __init__(self, url: str | None = None, lotto_name: str | None = None) -> None:
        target_url = url or "https://www.press.in.th/hanoi-lotto/"
        super().__init__(url=target_url)
        self.lotto_name = lotto_name or ""

    def parse(self) -> dict[str, str]:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        }
        try:
            resp = requests.get(self.url, headers=headers, timeout=15)
            resp.raise_for_status()
            resp.encoding = "utf-8"
        except Exception as exc:
            raise ParseError(f"HTTP request to {self.url} failed: {exc}") from exc

        soup = BeautifulSoup(resp.text, "html.parser")
        tables = soup.find_all("table")

        if not tables:
            raise ParseError(f"No result tables found on {self.url}")

        # Table index mapping on press.in.th:
        # Table 0: ผลฮานอยพิเศษ (17:30)
        # Table 1: ผลหวยฮานอยปกติ (18:30)
        # Table 2: ผลนอยvip (19:30)
        clean_name = self.lotto_name.replace("หวย", "").replace(" ", "").strip()
        target_table_idx = 0
        if "พิเศษ" in clean_name or "สามัคคี" in clean_name:
            target_table_idx = 0
        elif "vip" in clean_name.lower() or "พัฒนา" in clean_name:
            target_table_idx = 2
        elif "ปกติ" in clean_name or "ฮานอย" in clean_name:
            target_table_idx = 1

        if target_table_idx >= len(tables):
            target_table_idx = 0

        table = tables[target_table_idx]
        rows = table.find_all("tr")

        today_dt = datetime.now(TZ)
        today_d = today_dt.day
        today_m = today_dt.month
        today_y2 = today_dt.year % 100

        for row in rows[1:]:
            cols = [c.get_text(strip=True) for c in row.find_all(["td", "th"])]
            if len(cols) >= 5:
                row_date_str = cols[0]
                full4 = cols[1]
                top3 = cols[2]
                bot2 = cols[4]

                # Check if this row is for today
                # row_date_str can be DD/MM/YY e.g. 11/09/26
                is_today = False
                parts = row_date_str.split("/")
                if len(parts) == 3:
                    try:
                        d, m, y = int(parts[0]), int(parts[1]), int(parts[2])
                        if d == today_d and m == today_m and (y == today_y2 or y == (today_y2 + 43) % 100):
                            is_today = True
                    except Exception:
                        pass

                if not is_today:
                    continue

                # Ensure result is valid digits (not "รอผล")
                if top3 and bot2 and top3.isdigit() and bot2.isdigit() and len(top3) == 3 and len(bot2) == 2:
                    logger.info("PressHanoiParser found result for %s: top3=%s bottom2=%s (date=%s)", self.lotto_name, top3, bot2, row_date_str)
                    return {
                        "name": self.lotto_name,
                        "top3": top3.zfill(3),
                        "bottom2": bot2.zfill(2),
                        "full": full4 if full4.isdigit() else f"{top3}{bot2}",
                    }

        raise ParseError(f"Result for '{self.lotto_name}' is not yet available on press.in.th for today")
