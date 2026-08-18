# -*- coding: utf-8 -*-
"""Parser for Hanoi HD (xosohd.com)."""

from __future__ import annotations

import re
from typing import Optional

from bs4 import BeautifulSoup

from parsers.base import BaseParser, ParseError
from utils import extract_digits


from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Asia/Bangkok")


class HanoiHdParser(BaseParser):
    """Hanoi HD lottery parser."""

    name = "ฮานอย HD"
    url = "https://xosohd.com"
    use_playwright = True

    def parse(self) -> dict[str, str]:
        soup = self.fetch_soup()
        return self._extract(soup)

    def _extract(self, soup: BeautifulSoup) -> dict[str, str]:
        text = soup.get_text("\n", strip=True)
        yesterday = (datetime.now(TZ) - timedelta(days=1)).day
        split_pattern = rf"\b{yesterday}\s*(?:สิงหา|สิงหาคม|มกรา|กุมภา|มีนา|เมษา|พฤษภา|มิถุนา|กรกฎา|กันยา|ตุลา|พฤศจิกา|ธันวา|ສິງຫາ|[ก-๙a-zA-Z]+)\b|ผลการออก|ย้อนหลัง|ผลย้อนหลัง"
        top_block = re.split(split_pattern, text, flags=re.IGNORECASE)[0]

        # เช็คว่าผลของวันนี้ยังเป็น --- หรือไม่
        if "---" in top_block or "--" in top_block:
            raise ParseError(f"{self.name}: Results for today are still pending (dashes found in main box)")

        candidates = []
        for sel in [".result-number", ".ketqua", ".result", "#result", ".xo-so", "h1", "h2", ".number"]:
            for el in soup.select(sel):
                t = el.get_text(strip=True)
                if t in top_block:
                    digits = extract_digits(t)
                    if len(digits) >= 5:
                        candidates.append(digits)

        if not candidates:
            matches = re.findall(r"\b(\d{5})\b", top_block)
            candidates.extend(matches)

        if not candidates:
            raise ParseError(f"No result found for today on {self.url} (result may not be out yet)")

        full = candidates[0][-5:]
        top3 = full[-3:]
        # กติกาฮานอย: 2 ตัวล่าง คิดจาก 2 ตัวท้ายของรางวัลที่ 1 (G1 / candidate 1) ถ้ามี
        if len(candidates) >= 2 and len(candidates[1]) >= 2:
            bottom2 = candidates[1][-2:]
        else:
            bottom2 = full[:2]

        return {
            "name": self.name,
            "top3": top3,
            "bottom2": bottom2,
            "full": full,
        }


def create_parser(url: Optional[str] = None) -> HanoiHdParser:
    return HanoiHdParser(url=url)
