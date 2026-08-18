# -*- coding: utf-8 -*-
"""Parser for Laos Star (laostars.com) - JS heavy."""

from __future__ import annotations

import re
from typing import Optional

from bs4 import BeautifulSoup

from parsers.base import BaseParser, ParseError
from utils import extract_digits


from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Asia/Bangkok")


class LaoStarParser(BaseParser):
    name = "ลาว Star"
    url = "https://www.laostars.com"
    use_playwright = True

    def parse(self) -> dict[str, str]:
        soup = self.fetch_soup()
        return self._extract(soup)

    def _extract(self, soup: BeautifulSoup) -> dict[str, str]:
        top3 = ""
        bottom2 = ""
        text = soup.get_text("\n", strip=True)

        # ตัดข้อความให้เหลือเฉพาะกล่องผลหวยล่าสุดของวันนี้ (ตัดส่วนตารางย้อนหลังออก)
        yesterday = (datetime.now(TZ) - timedelta(days=1)).day
        split_pattern = rf"\b{yesterday}\s*(?:สิงหา|สิงหาคม|มกรา|กุมภา|มีนา|เมษา|พฤษภา|มิถุนา|กรกฎา|กันยา|ตุลา|พฤศจิกา|ธันวา|ສິງຫາ|[ก-๙a-zA-Z]+)\b|ผลการออก|ย้อนหลัง|ผลย้อนหลัง"
        top_block = re.split(split_pattern, text, flags=re.IGNORECASE)[0]

        m3 = re.search(
            r"(?:3\s*(?:ໂຕ|ตัว|digit|ตัวบน)|top\s*3|ເລກ\s*3)\s*(\d{3})",
            top_block,
            re.IGNORECASE,
        )
        if m3:
            top3 = m3.group(1)

        m2 = re.search(
            r"(?:2\s*(?:ໂຕລຸ່ມ|ตัวล่าง|digit|bottom)|bottom\s*2|ເລກ\s*2\s*ລຸ່ມ)\s*(\d{2})",
            top_block,
            re.IGNORECASE,
        )
        if m2:
            bottom2 = m2.group(1)

        if not (top3 and bottom2):
            for el in soup.select(".result, .number, h1, h2"):
                t = el.get_text(strip=True)
                if "---" in t or "--" in t:
                    raise ParseError(f"{self.name}: Results for today are still pending (dashes found in main box)")

            for el in soup.select(".result, .number, td, .prize, h1, h2, h3, span"):
                t = el.get_text(strip=True)
                if t in top_block:
                    d = extract_digits(t)
                    if len(d) == 3 and not top3:
                        top3 = d
                    elif len(d) == 2 and not bottom2:
                        bottom2 = d

        if not (top3 and bottom2):
            raise ParseError(f"Could not extract result for today from {self.url} (result may not be out yet)")

        return {
            "name": self.name,
            "top3": top3,
            "bottom2": bottom2,
            "full": top3 + bottom2,
        }


def create_parser(url: Optional[str] = None) -> LaoStarParser:
    return LaoStarParser(url=url)
