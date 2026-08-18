# -*- coding: utf-8 -*-
"""Generic stock-index parsers used as lottery sources.

Stock lotteries typically take the last 3 and last 2 digits
(or other combinations) of the closing index value.
"""

from __future__ import annotations

import re
from typing import Optional

from bs4 import BeautifulSoup

from parsers.base import BaseParser, ParseError
from utils import extract_digits


class StockBaseParser(BaseParser):
    """Base for stock-index based lotteries."""

    def _extract_index_value(self, soup: BeautifulSoup) -> str:
        """Try common selectors to find the main index number."""
        selectors = [
            ".price",
            ".index-value",
            ".index",
            ".last",
            ".value",
            "[data-field='last']",
            ".quote",
            "h1",
            "h2",
            ".number",
        ]
        for sel in selectors:
            for el in soup.select(sel):
                text = el.get_text(strip=True)
                # Keep digits and decimal point
                cleaned = re.sub(r"[^\d.]", "", text)
                if re.match(r"^\d+\.?\d*$", cleaned) and len(cleaned.replace(".", "")) >= 4:
                    return cleaned

        # Fallback: largest number-looking string on page
        text = soup.get_text(" ", strip=True)
        candidates = re.findall(r"\b\d{1,3}(?:,\d{3})*(?:\.\d+)?\b", text)
        if candidates:
            # prefer the one with most digits
            best = max(candidates, key=lambda x: len(re.sub(r"\D", "", x)))
            return best.replace(",", "")

        raise ParseError(f"Could not find index value on {self.url}")

    def _extract_index_and_change(self, soup: BeautifulSoup) -> tuple[str, str]:
        """Find main index number and change value."""
        value = ""
        change = ""

        for sel in [".price", ".index-value", ".index", ".last", ".value", "h1", "h2", ".number"]:
            for el in soup.select(sel):
                t = el.get_text(strip=True)
                cleaned = re.sub(r"[^\d.]", "", t)
                if re.match(r"^\d+\.\d{2}$", cleaned) or (len(cleaned.replace(".", "")) >= 4 and "." in cleaned):
                    value = cleaned
                    break
            if value:
                break

        if not value:
            value = self._extract_index_value(soup)

        # Find change value (e.g. +130.11, -23.62)
        for el in soup.select(".change, .chg, .diff, .net-change, span"):
            t = el.get_text(strip=True)
            m = re.search(r"[-+]\s*(\d+\.\d{2})", t)
            if m:
                change = m.group(1)
                break

        return value, change

    def parse(self) -> dict[str, str]:
        soup = self.fetch_soup()
        text = soup.get_text(" ", strip=True)
        if "---" in text or "N/A" in text or "--.--" in text:
            for sel in [".price", ".index-value", ".index", ".last"]:
                el = soup.select_one(sel)
                if el and ("---" in el.get_text() or "N/A" in el.get_text() or "--" in el.get_text()):
                    raise ParseError(f"{self.name}: Stock index for today is still pending (dashes/N/A found)")

        value, change = self._extract_index_and_change(soup)
        digits = extract_digits(value)

        if len(digits) < 4:
            raise ParseError(f"{self.name}: Index value too short or pending: {value}")

        # กติกาหวยหุ้นไทย:
        # 3 ตัวบน = หลักหน่วยของดัชนีปิด + ทศนิยม 2 ตำแหน่งของดัชนีปิด
        # 2 ตัวล่าง = ทศนิยม 2 ตำแหน่งของค่าเปลี่ยนแปลง (Change)
        if "." in value:
            parts = value.split(".")
            int_part = re.sub(r"\D", "", parts[0])
            dec_part = re.sub(r"\D", "", parts[1])
            if int_part and len(dec_part) >= 2:
                top3 = int_part[-1] + dec_part[:2]
            else:
                top3 = digits[-3:]
        else:
            top3 = digits[-3:]

        if change and "." in change:
            c_dec = re.sub(r"\D", "", change.split(".")[1])
            if len(c_dec) >= 2:
                bottom2 = c_dec[:2]
            else:
                bottom2 = digits[-5:-3] if len(digits) >= 5 else digits[:2]
        else:
            bottom2 = digits[-5:-3] if len(digits) >= 5 else digits[:2]

        return {
            "name": self.name,
            "top3": top3,
            "bottom2": bottom2,
            "full": digits[-5:],
        }


class NikkeiMorningParser(StockBaseParser):
    name = "นิเคอิเช้า"
    url = "https://indexes.nikkei.co.jp/en/nkave"


class NikkeiAfternoonParser(StockBaseParser):
    name = "นิเคอิบ่าย"
    url = "https://indexes.nikkei.co.jp/en/nkave"


class ChinaMorningParser(StockBaseParser):
    name = "จีนเช้า"
    url = "http://www.szse.cn/English/index.html"


class ChinaAfternoonParser(StockBaseParser):
    name = "จีนบ่าย"
    url = "http://www.szse.cn/English/index.html"


class HangsengMorningParser(StockBaseParser):
    name = "ฮั่งเส็งเช้า"
    url = "https://www.hsi.com.hk/eng"


class HangsengAfternoonParser(StockBaseParser):
    name = "ฮั่งเส็งบ่าย"
    url = "https://www.hsi.com.hk/eng"


class TaiwanParser(StockBaseParser):
    name = "ไต้หวัน"
    url = "https://www.twse.com.tw/en/"


class KoreaParser(StockBaseParser):
    name = "หุ้นเกาหลี"
    url = "http://global.krx.co.kr/main/main.jsp"


class SingaporeParser(StockBaseParser):
    name = "หุ้นสิงคโปร์"
    url = "https://www.sgx.com/indices"


class ThaiEveningParser(StockBaseParser):
    name = "หุ้นไทยเย็น"
    url = "https://www.set.or.th/th/market/index/set/overview"


# Factory helpers
def create_nikkei_morning(url: Optional[str] = None) -> NikkeiMorningParser:
    return NikkeiMorningParser(url=url)


def create_nikkei_afternoon(url: Optional[str] = None) -> NikkeiAfternoonParser:
    return NikkeiAfternoonParser(url=url)


def create_china_morning(url: Optional[str] = None) -> ChinaMorningParser:
    return ChinaMorningParser(url=url)


def create_china_afternoon(url: Optional[str] = None) -> ChinaAfternoonParser:
    return ChinaAfternoonParser(url=url)


def create_hangseng_morning(url: Optional[str] = None) -> HangsengMorningParser:
    return HangsengMorningParser(url=url)


def create_hangseng_afternoon(url: Optional[str] = None) -> HangsengAfternoonParser:
    return HangsengAfternoonParser(url=url)


def create_taiwan(url: Optional[str] = None) -> TaiwanParser:
    return TaiwanParser(url=url)


def create_korea(url: Optional[str] = None) -> KoreaParser:
    return KoreaParser(url=url)


def create_singapore(url: Optional[str] = None) -> SingaporeParser:
    return SingaporeParser(url=url)


def create_thai_evening(url: Optional[str] = None) -> ThaiEveningParser:
    return ThaiEveningParser(url=url)
