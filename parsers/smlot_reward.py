# -*- coding: utf-8 -*-
"""Parser for member.smlot.net/reports/reward.

Parses all lottery results from the central SMLOT reward report table.
Supports automatic login via Playwright using SMLOT_USERNAME and SMLOT_PASSWORD from .env.
"""

from __future__ import annotations

import os
import re
import time
from typing import Any, Dict, Optional
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup
from dotenv import load_dotenv

from parsers.base import BaseParser, ParseError
from utils import extract_digits, setup_logging

load_dotenv()
logger = setup_logging()
TZ = ZoneInfo("Asia/Bangkok")

# SMLOT Name Mapping (SMLOT table name <-> Standard lotto_line_bot name)
SMLOT_NAME_MAP: dict[str, str] = {
    # Daily / Laos / Hanoi
    "หวยลาว Extra": "ลาว Extra",
    "หวยลาวExtra": "ลาว Extra",
    "ลาว Extra": "ลาว Extra",
    "ฮานอยอาเซียน": "ฮานอยอาเซียน",
    "หวยลาว TV": "ลาว TV",
    "หวยลาวTV": "ลาว TV",
    "ลาว TV": "ลาว TV",
    "ฮานอย HD": "ฮานอย HD",
    "ฮานอย สตาร์": "ฮานอย Star",
    "ฮานอยสตาร์": "ฮานอย Star",
    "ลาว HD": "ลาว HD",
    "หวยฮานอย TV": "ฮานอย TV",
    "หวยฮานอยTV": "ฮานอย TV",
    "ลาว TV": "ลาว TV",
    "หวยลาวสตาร์": "ลาว Star",
    "หวยลาว สตาร์": "ลาว Star",
    "ลาวสตาร์": "ลาว Star",
    "ลาว สตาร์": "ลาว Star",
    "หวยฮานอย กาชาด": "ฮานอย กาชาด",
    "หวยฮานอยกาชาด": "ฮานอย กาชาด",
    "ฮานอย กาชาด": "ฮานอย กาชาด",
    "ฮานอยกาชาด": "ฮานอย กาชาด",
    # Normal Stock
    "นิเคอิ รอบเช้า": "นิเคอิเช้า",
    "นิเคอิ(เช้า)": "นิเคอิเช้า",
    "นิเคอิ เช้า": "นิเคอิเช้า",
    "จีนรอบเช้า": "จีนเช้า",
    "จีน(เช้า)": "จีนเช้า",
    "จีน เช้า": "จีนเช้า",
    "ฮั่งเส็งรอบเช้า": "ฮั่งเส็งเช้า",
    "ฮั่งเส็ง(เช้า)": "ฮั่งเส็งเช้า",
    "หุ้นไต้หวัน": "ไต้หวัน",
    "ไต้หวัน": "ไต้หวัน",
    "นิเคอิ รอบบ่าย": "นิเคอิบ่าย",
    "นิเคอิ(บ่าย)": "นิเคอิบ่าย",
    "จีนรอบบ่าย": "จีนบ่าย",
    "จีน(บ่าย)": "จีนบ่าย",
    "ฮั่งเส็งรอบบ่าย": "ฮั่งเส็งบ่าย",
    "ฮั่งเส็ง(บ่าย)": "ฮั่งเส็งบ่าย",
    "หุ้นสิงคโปร์": "หุ้นสิงคโปร์",
    "สิงคโปร์": "หุ้นสิงคโปร์",
    "หุ้นไทยปิดเย็น": "หุ้นไทยเย็น",
    "หุ้นไทยเย็น": "หุ้นไทยเย็น",
    "หุ้นเกาหลี": "หุ้นเกาหลี",
    "เกาหลี": "หุ้นเกาหลี",
    # VIP Stock
    "นิเคอิ(เช้า) VIP": "นิเคอิเช้า VIP",
    "นิเคอิเช้า VIP": "นิเคอิเช้า VIP",
    "เวียดนาม VIP เช้า": "เวียดนาม VIP เช้า",
    "จีน(เช้า) VIP": "จีนเช้า VIP",
    "จีนเช้า VIP": "จีนเช้า VIP",
    "ฮั่งเส็ง(เช้า) VIP": "ฮั่งเส็งเช้า VIP",
    "ฮั่งเส็งเช้า VIP": "ฮั่งเส็งเช้า VIP",
    "ไต้หวัน VIP": "ไต้หวัน VIP",
    "หุ้นไต้หวัน VIP": "ไต้หวัน VIP",
    "เกาหลี VIP": "เกาหลี VIP",
    "หุ้นเกาหลี VIP": "เกาหลี VIP",
    "นิเคอิ(บ่าย) VIP": "นิเคอิบ่าย VIP",
    "นิเคอิบ่าย VIP": "นิเคอิบ่าย VIP",
    "จีน(บ่าย) VIP": "จีนบ่าย VIP",
    "จีนบ่าย VIP": "จีนบ่าย VIP",
    "ฮั่งเส็ง(บ่าย) VIP": "ฮั่งเส็งบ่าย VIP",
    "ฮั่งเส็งบ่าย VIP": "ฮั่งเส็งบ่าย VIP",
}

# Reverse map for inverse lookup
for _k, _v in list(SMLOT_NAME_MAP.items()):
    if _v not in SMLOT_NAME_MAP:
        SMLOT_NAME_MAP[_v] = _k


import threading

class SmlotRewardParser(BaseParser):
    """Parser that fetches all results from member.smlot.net/reports/reward."""

    name = "SMLOT Reward Report"
    url = "https://member.smlot.net/reports/reward"
    use_playwright = True

    _cache_data: dict[str, dict[str, str]] = {}
    _cache_time: float = 0.0
    _CACHE_TTL_SECONDS: float = 60.0
    _lock = threading.Lock()

    def __init__(self, url: Optional[str] = None, lotto_name: Optional[str] = None) -> None:
        super().__init__(url=url)
        self.target_lotto_name = lotto_name

    @classmethod
    def fetch_all_smlot_results(cls, force_refresh: bool = False) -> dict[str, dict[str, str]]:
        with cls._lock:
            now = time.time()
            if not force_refresh and cls._cache_data and (now - cls._cache_time < cls._CACHE_TTL_SECONDS):
                return cls._cache_data

            username = os.getenv("SMLOT_USERNAME", "").strip() or "bdd999bas"
            password = os.getenv("SMLOT_PASSWORD", "").strip() or "Dd123456."

            if not username or not password:
                raise ParseError(
                    "SMLOT_USERNAME และ SMLOT_PASSWORD ไม่ได้ถูกตั้งค่าในไฟล์ .env "
                    "กรุณากรอกข้อมูลเข้าใช้งาน member.smlot.net ในไฟล์ .env"
                )

            try:
                from playwright.sync_api import sync_playwright
            except ImportError as exc:
                raise ParseError("Playwright is required for SMLOT scraping") from exc

            logger.info("Opening SMLOT report page via Playwright: https://member.smlot.net/reports/reward")
            results: dict[str, dict[str, str]] = {}

            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(
                    user_agent=(
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/124.0.0.0 Safari/537.36"
                    )
                )
                page = context.new_page()

                page.goto("https://member.smlot.net/reports/reward", wait_until="networkidle", timeout=30000)

                if "/login" in page.url or page.locator("input[name='username']").count() > 0:
                    logger.info("SMLOT requires login. Logging in with user '%s'...", username[:3] + "***")
                    page.fill("input[name='username']", username)
                    page.fill("input[name='pass']", password)
                    page.click("button[type='submit'], button.btn")
                    page.wait_for_load_state("networkidle", timeout=30000)
                    time.sleep(2)

                    if "/reports/reward" not in page.url:
                        page.goto("https://member.smlot.net/reports/reward", wait_until="networkidle", timeout=30000)
                        time.sleep(1)

                page.wait_for_selector("table, tr", timeout=15000)
                html = page.content()
                browser.close()

            soup = BeautifulSoup(html, "lxml")
            results = cls._parse_smlot_html(soup)

            if not results:
                raise ParseError("No lottery results table found on member.smlot.net/reports/reward")

            cls._cache_data = results
            cls._cache_time = now
            logger.info("Successfully fetched %d lottery results from SMLOT", len(results))
            return results

    @classmethod
    def _parse_smlot_html(cls, soup: BeautifulSoup) -> dict[str, dict[str, str]]:
        results: dict[str, dict[str, str]] = {}

        for tr in soup.find_all("tr"):
            tds = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
            if len(tds) < 6:
                continue

            raw_name = tds[0]
            top3 = extract_digits(tds[3], length=3)
            bottom2 = extract_digits(tds[5], length=2)

            if not top3 or not bottom2:
                bottom2 = extract_digits(tds[4], length=2)

            if len(top3) == 3 and len(bottom2) == 2:
                mapped_name = SMLOT_NAME_MAP.get(raw_name, raw_name)
                res_dict = {
                    "raw_name": raw_name,
                    "top3": top3,
                    "bottom2": bottom2,
                    "full": top3 + bottom2,
                }
                results[raw_name] = res_dict
                results[mapped_name] = res_dict

        return results

    @staticmethod
    def _get_lotto_tokens(name: str) -> set[str]:
        main_names = [
            "นิเคอิ", "ฮั่งเส็ง", "จีน", "ไต้หวัน", "เกาหลี", "สิงคโปร์", "สิงค์โปร์",
            "อังกฤษ", "เยอรมัน", "รัสเซีย", "ดาวโจนส์", "ไทย", "อียิปต์", "อินเดีย",
            "มาเลเซีย", "ฮานอย", "ลาว",
        ]
        sessions = ["เช้า", "บ่าย", "เย็น", "ดึก"]
        suffixes = [
            "vip", "star", "extra", "tv", "hd", "อาเซียน", "กาชาด", "สามัคคี",
            "พัฒนา", "สันติภาพ", "ประตูชัย", "ประชาชน", "midnight", "mid night",
            "พิเศษ", "ปกติ", "เฉพาะกิจ",
        ]
        name_lower = name.lower()
        tokens = set()
        for m in main_names:
            if m in name_lower:
                tokens.add(m.replace("สิงค์โปร์", "สิงคโปร์"))
        for s in sessions:
            if s in name_lower:
                tokens.add(s)
        for suf in suffixes:
            if suf in name_lower:
                tokens.add(suf)
        return tokens

    def parse(self) -> dict[str, str]:
        target_name = self.target_lotto_name or self.name
        all_results = self.fetch_all_smlot_results()
        is_target_vip = "VIP" in target_name.upper()

        # 1) Direct exact match
        result = all_results.get(target_name)

        # 2) Mapped exact match
        if not result:
            mapped = SMLOT_NAME_MAP.get(target_name)
            if mapped:
                result = all_results.get(mapped)

        # 3) Smart normalized token matching (handles word reordering e.g. ฮั่งเส็ง VIP เช้า vs ฮั่งเส็งเช้า VIP)
        if not result:
            target_tokens = self._get_lotto_tokens(target_name)
            for key, val in all_results.items():
                is_key_vip = "VIP" in key.upper()
                if is_target_vip != is_key_vip:
                    continue

                key_tokens = self._get_lotto_tokens(key)
                if target_tokens and key_tokens and target_tokens == key_tokens:
                    result = val
                    break

        # 4) Fallback clean substring search
        if not result:
            clean_target = re.sub(r"[^\wก-๙]", "", target_name).lower()
            for key, val in all_results.items():
                is_key_vip = "VIP" in key.upper()
                if is_target_vip != is_key_vip:
                    continue

                clean_key = re.sub(r"[^\wก-๙]", "", key).lower()
                if clean_target in clean_key or clean_key in clean_target:
                    result = val
                    break

        if not result:
            raise ParseError(
                f"SMLOT parser: Result for '{target_name}' is not yet available "
                f"on member.smlot.net/reports/reward"
            )

        return {
            "name": target_name,
            "top3": result["top3"],
            "bottom2": result["bottom2"],
            "full": result["full"],
        }


def create_parser(url: Optional[str] = None) -> SmlotRewardParser:
    return SmlotRewardParser(url=url)
