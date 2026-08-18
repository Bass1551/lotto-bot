# -*- coding: utf-8 -*-
"""Parsers for VIP stock lottery sites.

VIP sites usually display the result already as top3 / bottom2
or a 5-digit number. We try both patterns.
"""

from __future__ import annotations

import re
from typing import Optional

from bs4 import BeautifulSoup

from parsers.base import BaseParser, ParseError
from utils import extract_digits


from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Asia/Bangkok")


class VipStockParser(BaseParser):
    """Generic VIP stock result parser."""

    use_playwright = True  # most VIP sites are JS-rendered

    def parse(self) -> dict[str, str]:
        soup = self.fetch_soup()
        return self._extract(soup)

    def _extract(self, soup: BeautifulSoup) -> dict[str, str]:
        top3 = ""
        bottom2 = ""
        full = ""

        text = soup.get_text("\n", strip=True)

        # ตัดข้อความให้เหลือเฉพาะกล่องผลหวยล่าสุดของวันนี้ (ตัดส่วนตารางย้อนหลังออก)
        yesterday = (datetime.now(TZ) - timedelta(days=1)).day
        split_pattern = rf"\b{yesterday}\s*(?:สิงหา|สิงหาคม|มกรา|กุมภา|มีนา|เมษา|พฤษภา|มิถุนา|กรกฎา|กันยา|ตุลา|พฤศจิกา|ธันวา|ສິງຫາ|[ก-๙a-zA-Z]+)\b|ผลการออก|ย้อนหลัง|ผลย้อนหลัง|history|previous"
        top_block = re.split(split_pattern, text, flags=re.IGNORECASE)[0]

        # 0) เช็คถ้ามี --- หรือ -- ในกล่องหลัก แสดงว่าผลของวันนี้ยังไม่ออก
        if "---" in top_block or "--" in top_block:
            raise ParseError(f"{self.name}: Results for today are still pending (dashes found in main box)")

        # 1) Look for explicit top3 / bottom2 labels
        m3 = re.search(
            r"(?:3\s*(?:ตัว|digit|ตัวบน|บน)|top\s*3|สามตัว)\s*(\d{3})",
            top_block,
            re.IGNORECASE,
        )
        if m3:
            top3 = m3.group(1)

        m2 = re.search(
            r"(?:2\s*(?:ตัว|digit|ตัวล่าง|ล่าง)|bottom\s*2|สองตัว)\s*(\d{2})",
            top_block,
            re.IGNORECASE,
        )
        if m2:
            bottom2 = m2.group(1)

        # 2) Common CSS classes used by VIP lottery sites
        if not top3 or not bottom2:
            for sel in [
                ".result",
                ".result-number",
                ".number",
                ".prize",
                ".ketqua",
                ".top",
                ".bottom",
                "h1",
                "h2",
                "h3",
                ".digit",
                "#result",
            ]:
                for el in soup.select(sel):
                    t = el.get_text(strip=True)
                    if t in top_block:
                        d = extract_digits(t)
                        if len(d) == 5 and not full:
                            full = d
                        elif len(d) == 3 and not top3:
                            top3 = d
                        elif len(d) == 2 and not bottom2:
                            bottom2 = d

        # Derive top3/bottom2 from full if needed
        if full and (not top3 or not bottom2):
            top3 = full[-3:]
            bottom2 = full[:2]

        if not (top3 and bottom2):
            nums = re.findall(r"\b(\d{2,5})\b", top_block)
            for n in nums:
                if len(n) == 3 and not top3:
                    top3 = n
                elif len(n) == 2 and not bottom2:
                    bottom2 = n
                if top3 and bottom2:
                    break

        if not (top3 and bottom2):
            raise ParseError(
                f"{self.name}: Could not extract result for today from {self.url} (result may not be out yet)"
            )

        return {
            "name": self.name,
            "top3": top3,
            "bottom2": bottom2,
            "full": full or (top3 + bottom2),
        }


# Concrete VIP parsers
class NikkeiMorningVipParser(VipStockParser):
    name = "นิเคอิเช้า VIP"
    url = "https://nikkeivipstock.com"


class NikkeiAfternoonVipParser(VipStockParser):
    name = "นิเคอิบ่าย VIP"
    url = "https://nikkeivipstock.com"


class ChinaMorningVipParser(VipStockParser):
    name = "จีนเช้า VIP"
    url = "https://shenzhenindex.com"


class ChinaAfternoonVipParser(VipStockParser):
    name = "จีนบ่าย VIP"
    url = "https://shenzhenindex.com"


class HangsengMorningVipParser(VipStockParser):
    name = "ฮั่งเส็งเช้า VIP"
    url = "https://hangsengvip.com"


class HangsengAfternoonVipParser(VipStockParser):
    name = "ฮั่งเส็งบ่าย VIP"
    url = "https://www.hsi-vip.com/"


class TaiwanVipParser(VipStockParser):
    name = "ไต้หวัน VIP"
    url = "https://tsecvipindex.com"


class KoreaVipParser(VipStockParser):
    name = "เกาหลี VIP"
    url = "https://ktopvipindex.com"
