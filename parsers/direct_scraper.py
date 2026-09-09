# -*- coding: utf-8 -*-
"""
Direct Scrapers for Official Lottery Websites.
Extracts results directly from source pages & APIs with maximum speed and fallback safety.
"""

from __future__ import annotations

import re
import time
import logging
from datetime import datetime, date
from typing import Optional, Dict, Any
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup
from utils import extract_digits, setup_logging

logger = setup_logging()
TZ = ZoneInfo("Asia/Bangkok")
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
}

# ---------------------------------------------------------
# 1. Hanoi & Lao Direct Fast APIs (Sub-second response)
# ---------------------------------------------------------
HANOI_API_MAP = {
    "ฮานอย HD": "https://api.xosohd.com/result",
    "ฮานอย Star": "https://api.minhngocstar.com/result",
    "ฮานอย TV": "https://api.minhngoctv.com/result",
    "ฮานอย กาชาด": "https://api.xosoredcross.com/result",
    "ฮานอยEXTRA": "https://api.xosoextra.com/result",
}

LAO_API_MAP = {
    "ลาว Extra": "https://api.laoextra.com/result",
    "ลาว TV": "https://api.lao-tv.com/result",
    "ลาว Star": "https://api.laostars.com/result",
    "หวยลาว กาชาด": "https://api.lao-redcross.com/result",
}


def scrape_hanoi_api(lotto_name: str, target_date: Optional[date] = None) -> Optional[Dict[str, str]]:
    """
    Hanoi JSON API:
    - 3 Top = prize_1st[-3:] (e.g. 93225 -> 225)
    - 2 Bottom = prize_2nd[-2:] (e.g. 85719 -> 19)
    """
    api_url = HANOI_API_MAP.get(lotto_name)
    if not api_url:
        return None
    target_date = target_date or datetime.now(TZ).date()

    try:
        res = requests.get(api_url, headers=HEADERS, timeout=5)
        if res.status_code == 200:
            data = res.json().get("data", {})
            lotto_date_str = data.get("lotto_date")
            if lotto_date_str and lotto_date_str != target_date.strftime("%Y-%m-%d"):
                return None

            results = data.get("results", {})
            p1 = results.get("prize_1st") or ""
            p2 = results.get("prize_2nd") or ""

            if len(p1) >= 3 and len(p2) >= 2:
                top3 = p1[-3:]
                bot2 = p2[-2:]
                return {
                    "name": lotto_name,
                    "top3": top3,
                    "bottom2": bot2,
                    "full": p1,
                }
    except Exception as exc:
        logger.debug("Hanoi API error for %s: %s", lotto_name, exc)
    return None


def scrape_lao_api(lotto_name: str, target_date: Optional[date] = None) -> Optional[Dict[str, str]]:
    """
    Lao JSON API (5 digits):
    - 3 Top = digit3 or digit5[-3:] (e.g. 39862 -> 862)
    - 2 Bottom = digit2_bottom or digit5[:2] (e.g. 39862 -> 39)
    """
    api_url = LAO_API_MAP.get(lotto_name)
    if not api_url:
        return None
    target_date = target_date or datetime.now(TZ).date()

    try:
        res = requests.get(api_url, headers=HEADERS, timeout=5)
        if res.status_code == 200:
            data = res.json().get("data", {})
            lotto_date_str = data.get("lotto_date")
            if lotto_date_str and lotto_date_str != target_date.strftime("%Y-%m-%d"):
                return None

            results = data.get("results", {})
            d5 = results.get("digit5") or ""
            top3 = results.get("digit3") or (d5[-3:] if len(d5) == 5 else "")
            bot2 = results.get("digit2_bottom") or (d5[:2] if len(d5) == 5 else "")

            if len(top3) == 3 and len(bot2) == 2:
                return {
                    "name": lotto_name,
                    "top3": top3,
                    "bottom2": bot2,
                    "full": d5,
                }
    except Exception as exc:
        logger.debug("Lao API error for %s: %s", lotto_name, exc)
    return None


# ---------------------------------------------------------
# 2. Lao Union (ลาวสามัคคี www.laounion.com)
# ---------------------------------------------------------
def scrape_lao_union(target_date: Optional[date] = None) -> Optional[Dict[str, str]]:
    """
    ลาวสามัคคี (www.laounion.com):
    ตัวเลข 27834 -> บน 834, ล่าง 78 (หลักพันกับหลักร้อย)
    """
    url = "https://www.laounion.com"
    try:
        res = requests.get(url, headers=HEADERS, timeout=6)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, "lxml")
            matches = re.findall(r"\b\d{4,5}\b", soup.get_text(" ", strip=True))
            if matches:
                full = matches[0]
                top3 = full[-3:]
                bot2 = full[1:3] if len(full) == 5 else full[:2]
                return {
                    "name": "ลาวสามัคคี",
                    "top3": top3,
                    "bottom2": bot2,
                    "full": full,
                }
    except Exception as exc:
        logger.debug("Lao union error: %s", exc)
    return None


# ---------------------------------------------------------
# 3. 3 Rath VIP (lottosuperrich.com) - อังกฤษ VIP (21:50), เยอรมัน VIP (22:50), รัสเซีย VIP (23:50)
# ---------------------------------------------------------
def scrape_superrich_vip(lotto_name: str, target_date: Optional[date] = None) -> Optional[Dict[str, str]]:
    """
    3 Rath VIP from lottosuperrich.com:
    - 21:50:00 -> อังกฤษ VIP (Top=last 3 of 1st, Bot=last 2 of 2nd)
    - 22:50:00 -> เยอรมัน VIP
    - 23:50:00 -> รัสเซีย VIP
    """
    time_key_map = {
        "อังกฤษVIP": "21:50:00",
        "เยอรมันVIP": "22:50:00",
        "รัสเซียVIP": "23:50:00",
    }
    expected_time = time_key_map.get(lotto_name)
    if not expected_time:
        return None

    target_date = target_date or datetime.now(TZ).date()
    target_date_str = target_date.strftime("%d/%m/%y")

    try:
        res = requests.get("https://lottosuperrich.com/", headers=HEADERS, timeout=6)
        if res.status_code != 200:
            return None

        # Parse text chunks separated by DATE
        text = res.text
        # Fallback to simple regex on raw html
        # Pattern: DATE \n DD/MM/YY \n 1st \n (\d{5}) \n 2nd \n (\d{5}) \n (HH:MM:SS)
        soup = BeautifulSoup(text, "lxml")
        body_text = soup.get_text(" ", strip=True)

        pattern = re.compile(
            rf"DATE\s*(\d{{2}}/\d{{2}}/\d{{2}})\s*1st\s*(\d{{5}})\s*2nd\s*(\d{{5}})\s*({expected_time})"
        )
        m = pattern.search(body_text)
        if m:
            d_str, top5, bot5, _ = m.groups()
            if d_str == target_date_str:
                return {
                    "name": lotto_name,
                    "top3": top5[-3:],
                    "bottom2": bot5[-2:],
                    "full": top5,
                }
    except Exception as exc:
        logger.debug("Superrich scrape error for %s: %s", lotto_name, exc)
    return None


# ---------------------------------------------------------
# Master Direct Scraper Dispatcher
# ---------------------------------------------------------
def scrape_direct_official(lottery_name: str, target_date: Optional[date] = None) -> Optional[Dict[str, str]]:
    """
    Tries fast official direct scrape. Returns dict(name, top3, bottom2, full) or None.
    If None is returned, scheduler will seamlessly fallback to SMLOT.
    """
    target_date = target_date or datetime.now(TZ).date()

    # 1. Hanoi APIs
    if lottery_name in HANOI_API_MAP:
        res = scrape_hanoi_api(lottery_name, target_date=target_date)
        if res:
            logger.info("Fast Direct scrape SUCCESS for '%s' (Hanoi API): %s-%s", lottery_name, res["top3"], res["bottom2"])
            return res

    # 2. Lao APIs
    if lottery_name in LAO_API_MAP:
        res = scrape_lao_api(lottery_name, target_date=target_date)
        if res:
            logger.info("Fast Direct scrape SUCCESS for '%s' (Lao API): %s-%s", lottery_name, res["top3"], res["bottom2"])
            return res

    # 3. Lao Union
    if lottery_name == "ลาวสามัคคี":
        res = scrape_lao_union(target_date=target_date)
        if res:
            logger.info("Fast Direct scrape SUCCESS for '%s' (Lao Union): %s-%s", lottery_name, res["top3"], res["bottom2"])
            return res

    # 4. Superrich 3 Rath VIP
    if lottery_name in ("อังกฤษVIP", "เยอรมันVIP", "รัสเซียVIP"):
        res = scrape_superrich_vip(lottery_name, target_date=target_date)
        if res:
            logger.info("Fast Direct scrape SUCCESS for '%s' (Superrich VIP): %s-%s", lottery_name, res["top3"], res["bottom2"])
            return res

    return None
