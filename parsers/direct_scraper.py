# -*- coding: utf-8 -*-
"""
Direct Scrapers for Official Lottery Websites.
Extracts results directly from source pages and APIs with maximum speed,
strict date verification, and seamless fallback safety.
"""

from __future__ import annotations

import re
import time
import logging
from datetime import datetime, date, timedelta
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
# Official Website URL Reference Directory
# ---------------------------------------------------------
OFFICIAL_URL_MAP: dict[str, str] = {
    # Hanoi APIs
    "ฮานอย HD": "https://xosohd.com/",
    "ฮานอย Star": "https://minhngocstar.com/",
    "ฮานอย TV": "https://minhngoctv.com/",
    "ฮานอย กาชาด": "https://xosoredcross.com/",
    "ฮานอยEXTRA": "https://xosoextra.com/",
    "ฮานอยอาเซียน": "https://hanoiasean.com/",
    "ฮานอยพัฒนา": "https://xosohd.com/",
    "ฮานอย (ปกติ)": "https://www.press.in.th/hanoi-lotto/",
    "หวยฮานอย": "https://www.press.in.th/hanoi-lotto/",
    "ฮานอยปกติ": "https://www.press.in.th/hanoi-lotto/",
    "หวยฮานอย พิเศษ": "https://www.press.in.th/hanoi-lotto/",
    "ฮานอยพิเศษ": "https://www.press.in.th/hanoi-lotto/",
    "หวยฮานอย VIP": "https://www.press.in.th/hanoi-lotto/",
    "ฮานอย VIP": "https://www.press.in.th/hanoi-lotto/",
    # Lao APIs & Sites
    "ลาว Extra": "https://laoextra.com/",
    "ลาว TV": "https://lao-tv.com/",
    "ลาว HD": "https://laoshd.com/",
    "ลาว Star": "https://laostars.com/",
    "หวยลาว กาชาด": "https://lao-redcross.com/",
    "ลาวกาชาด": "https://lao-redcross.com/",
    "ลาว กาชาด": "https://lao-redcross.com/",
    "ลาวสามัคคี": "https://www.laounion.com/",
    "ลาวอาเซียน": "https://lotterylaosasean.com/",
    "ลาวสตาร์ VIP": "https://laostars.com/",
    "ลาวSTAR VIP": "https://laostars.com/",
    "ลาวพัฒนา (จ-พ-ศ)": "https://lao-tv.com/",
    "ลาวสตาร์": "https://laostars.com/",
    # VIP Stocks
    "นิเคอิเช้า VIP": "https://nikkeivipstock.com/",
    "นิเคอิบ่าย VIP": "https://nikkeivipstock.com/",
    "จีนเช้า VIP": "https://shenzhenindex.com/",
    "จีนบ่าย VIP": "https://shenzhenindex.com/",
    "ฮั่งเส็งเช้า VIP": "https://www.hsi-vip.com/",
    "ฮั่งเส็งบ่าย VIP": "https://www.hsi-vip.com/",
    "ไต้หวัน VIP": "https://twvipstock.com/",
    "เกาหลี VIP": "https://ktopvipindex.com/",
    "สิงคโปร์ VIP": "https://sgxvip.com/",
    "สิงค์โปร์ VIP": "https://sgxvip.com/",
    "ฮานอยสามัคคี": "https://member.smlot.net/reports/reward",
    "หวยดาวโจนส์ VIP": "https://dowjonespowerball.com/",
    # 3 Rath VIP
    "อังกฤษVIP": "https://lottosuperrich.com/",
    "เยอรมันVIP": "https://lottosuperrich.com/",
    "รัสเซียVIP": "https://lottosuperrich.com/",
    # Major Stocks
    "นิเคอิเช้า": "https://indexes.nikkei.co.jp/en/nkave",
    "นิเคอิบ่าย": "https://indexes.nikkei.co.jp/en/nkave",
    "จีนเช้า": "http://www.szse.cn/English/index.html",
    "จีนบ่าย": "http://www.szse.cn/English/index.html",
    "ฮั่งเส็งเช้า": "https://www.google.com/finance/quote/HSI:INDEXHANGSENG",
    "ฮั่งเส็งบ่าย": "https://www.google.com/finance/quote/HSI:INDEXHANGSENG",
    "หุ้นเกาหลี": "https://m.investing.com/indices/kospi",
    "หุ้นไต้หวัน": "https://www.twse.com.tw/en/",
    "หุ้นสิงคโปร์": "https://www.sgx.com/wps/portal/sgxweb/home/marketinfo/indices/indice",
    "หุ้นไทยเย็น": "https://marketdata.set.or.th/mkt/marketsummary.do",
    "หวยดาวโจนส์": "https://th.investing.com/indices/us-30",
    "อังกฤษ": "http://www.bloomberg.com/quote/UKX:IND",
    "เยอรมัน": "http://www.marketwatch.com/investing/index/dax?countrycode=dx",
    "รัสเซีย": "https://m.investing.com/indices/rts-standard",
}


def get_official_url(lottery_name: str) -> str:
    """Return the official reference URL or SMLOT default."""
    return OFFICIAL_URL_MAP.get(lottery_name, "https://member.smlot.net/")


# ---------------------------------------------------------
# Strict Date Guardrail Utilities
# ---------------------------------------------------------
def verify_date_guardrail(text: str, target_date: date) -> bool:
    """
    Ensures the text or response strictly matches `target_date`.
    Rejects pages displaying yesterday's results or pending placeholders.
    """
    if not text:
        return False

    # 1. Pending placeholders check
    if "---" in text or "กำลังออกผล" in text or "正在开奖" in text:
        return False

    # 2. Target date formatted strings
    EN_MONTHS_SHORT = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]
    EN_MONTHS_FULL = ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december"]
    m_short = EN_MONTHS_SHORT[target_date.month - 1]
    m_full = EN_MONTHS_FULL[target_date.month - 1]

    d_patterns = [
        target_date.strftime("%Y-%m-%d"),  # 2026-09-09
        target_date.strftime("%d/%m/%Y"),  # 09/09/2026
        target_date.strftime("%d-%m-%Y"),  # 09-09-2026
        target_date.strftime("%d.%m.%Y"),  # 09.09.2026
        target_date.strftime("%y/%m/%d"),  # 26/09/09
        target_date.strftime("%d/%m/%y"),  # 09/09/26
        target_date.strftime("%d-%m-%y"),  # 09-09-26
        f"{target_date.day:02d}/{target_date.month:02d}",  # 09/09
        f"{target_date.day}/{target_date.month}",          # 9/9
        f"{m_short} {target_date.day:02d}, {target_date.year}", # Sep 10, 2026
        f"{m_short} {target_date.day}, {target_date.year}",     # Sep 9, 2026
        f"{m_full} {target_date.day:02d}, {target_date.year}",  # September 10, 2026
        f"{m_full} {target_date.day}, {target_date.year}",      # September 9, 2026
        f"{m_short}/{target_date.day:02d}/{target_date.year}", # Sep/10/2026
        f"{m_short}/{target_date.day}/{target_date.year}",     # Sep/9/2026
        f"{m_short}/{target_date.day:02d}/{str(target_date.year)[-2:]}", # Sep/10/26
        f"{m_full}/{target_date.day:02d}/{target_date.year}",  # September/10/2026
    ]

    target_matched = any(p.lower() in text.lower() for p in d_patterns)
    if target_matched:
        return True

    # Check if yesterday's date is prominently present while target is missing
    yesterday = target_date - timedelta(days=1)
    y_m_short = EN_MONTHS_SHORT[yesterday.month - 1]
    y_patterns = [
        yesterday.strftime("%Y-%m-%d"),
        yesterday.strftime("%d/%m/%Y"),
        yesterday.strftime("%d-%m-%Y"),
        f"{y_m_short} {yesterday.day:02d}, {yesterday.year}",
        f"{y_m_short} {yesterday.day}, {yesterday.year}",
        f"{y_m_short}/{yesterday.day:02d}/{yesterday.year}",
        f"{y_m_short}/{yesterday.day}/{yesterday.year}",
    ]
    if any(p.lower() in text.lower() for p in y_patterns):
        return False

    return False


# ---------------------------------------------------------
# 1. Hanoi & Lao Direct Fast APIs (Sub-second response)
# ---------------------------------------------------------
HANOI_API_MAP = {
    "ฮานอย HD": "https://api.xosohd.com/result",
    "ฮานอยHD": "https://api.xosohd.com/result",
    "ฮานอย Star": "https://api.minhngocstar.com/result",
    "ฮานอยStar": "https://api.minhngocstar.com/result",
    "ฮานอยสตาร์": "https://api.minhngocstar.com/result",
    "ฮานอย TV": "https://api.minhngoctv.com/result",
    "ฮานอยTV": "https://api.minhngoctv.com/result",
    "ฮานอย กาชาด": "https://api.xosoredcross.com/result",
    "ฮานอยกาชาด": "https://api.xosoredcross.com/result",
    "ฮานอยEXTRA": "https://api.xosoextra.com/result",
    "ฮานอย Extra": "https://api.xosoextra.com/result",
    "ฮานอยExtra": "https://api.xosoextra.com/result",
    "ฮานอยอาเซียน": "https://hanoiasean.com/api/result",
}

LAO_API_MAP = {
    "ลาว Extra": "https://api.laoextra.com/result",
    "ลาวExtra": "https://api.laoextra.com/result",
    "ลาว TV": "https://api.lao-tv.com/result",
    "ลาวTV": "https://api.lao-tv.com/result",
    "ลาว HD": "https://api.laoshd.com/api/result",
    "ลาวHD": "https://api.laoshd.com/api/result",
    "ลาว Star": "https://api.laostars.com/result",
    "ลาวStar": "https://api.laostars.com/result",
    "ลาวสตาร์": "https://api.laostars.com/result",
    "ลาวอาเซียน": "https://hi.lotterylaosasean.com/result",
    "หวยลาว กาชาด": "https://api.lao-redcross.com/result",
    "หวยลาวกาชาด": "https://api.lao-redcross.com/result",
    "ลาวกาชาด": "https://api.lao-redcross.com/result",
    "ลาว กาชาด": "https://api.lao-redcross.com/result",
}



def scrape_hanoi_api(lotto_name: str, target_date: Optional[date] = None) -> Optional[Dict[str, str]]:
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
                logger.debug("Hanoi API date mismatch: %s != %s", lotto_date_str, target_date)
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
                logger.debug("Lao API date mismatch: %s != %s", lotto_date_str, target_date)
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
    url = "https://www.laounion.com"
    target_date = target_date or datetime.now(TZ).date()
    try:
        res = requests.get(url, headers=HEADERS, timeout=6)
        if res.status_code == 200:
            text = res.text
            if "---" in text:
                return None
            soup = BeautifulSoup(text, "lxml")
            clean_text = soup.get_text(" ", strip=True)
            has_today = verify_date_guardrail(clean_text, target_date)
            matches = re.findall(r"\b\d{4,5}\b", clean_text)
            if matches and (has_today or len(matches) > 0):
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
# 3. 3 Rath VIP (lottosuperrich.com)
# ---------------------------------------------------------
def scrape_superrich_vip(lotto_name: str, target_date: Optional[date] = None) -> Optional[Dict[str, str]]:
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

        soup = BeautifulSoup(res.text, "lxml")
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
            else:
                logger.debug("Superrich VIP date mismatch: %s != %s", d_str, target_date_str)
    except Exception as exc:
        logger.debug("Superrich scrape error for %s: %s", lotto_name, exc)
    return None


# ---------------------------------------------------------
# 4. Fast REST APIs for VIP (Dow Jones Powerball & Korea VIP)
# ---------------------------------------------------------
def scrape_dowjones_powerball_vip(target_date: Optional[date] = None) -> Optional[Dict[str, str]]:
    url = "https://api.dowjonespowerball.com/result"
    target_date = target_date or datetime.now(TZ).date()
    target_str = target_date.strftime("%Y-%m-%d")
    try:
        res = requests.get(url, headers=HEADERS, timeout=5)
        if res.status_code == 200:
            data = res.json().get("data", {})
            show_1st = data.get("show_1st", "")
            lotto_date = data.get("lotto_date", "")
            if show_1st and not show_1st.startswith(target_str) and lotto_date != target_str:
                logger.debug("Dow Jones VIP date mismatch: show_1st=%s, lotto_date=%s vs %s", show_1st, lotto_date, target_str)
                return None
            results = data.get("results", {})
            p1 = str(results.get("prize_1st", ""))
            p2 = str(results.get("prize_2nd", ""))
            if len(p1) >= 3 and len(p2) >= 2:
                top3 = p1[-3:]
                bot2 = p2[-2:]
                return {
                    "name": "หวยดาวโจนส์ VIP",
                    "top3": top3,
                    "bottom2": bot2,
                    "full": p1,
                }
    except Exception as exc:
        logger.debug("Dow Jones Powerball API error: %s", exc)
    return None


def scrape_korea_vip_api(target_date: Optional[date] = None) -> Optional[Dict[str, str]]:
    url = "https://api.ktopvipindex.com/api/kr"
    target_date = target_date or datetime.now(TZ).date()
    target_str = target_date.strftime("%Y-%m-%d")
    try:
        res = requests.get(url, headers=HEADERS, timeout=5)
        if res.status_code == 200:
            kr_data = res.json().get("data", {})
            kr_date = kr_data.get("date")
            if kr_date and kr_date != target_str:
                logger.debug("Korea VIP date mismatch: %s != %s", kr_date, target_str)
                return None
            kr_prices = kr_data.get("prices", {})
            if kr_prices.get("available") and kr_prices.get("note") == "Close":
                p_val = kr_prices.get("price", 0)
                d_val = str(kr_prices.get("diff", ""))
                p_str = f"{p_val:.2f}"
                top3 = p_str.split(".")[0][-1] + p_str.split(".")[1]
                bot2 = d_val.split(".")[1] if "." in d_val else d_val[-2:]
                if len(top3) == 3 and len(bot2) == 2:
                    return {
                        "name": "เกาหลี VIP",
                        "top3": top3,
                        "bottom2": bot2,
                        "full": f"{p_str} | {d_val}",
                    }
    except Exception as exc:
        logger.debug("Korea VIP API error: %s", exc)
    return None


# ---------------------------------------------------------
# 5. VIP Stocks (nikkeivipstock, shenzhenindex, hsi-vip, tsecvipindex, ktopvipindex, dowjonespowerball)
# ---------------------------------------------------------
VIP_STOCK_URLS = {
    "นิเคอิเช้า VIP": ("https://nikkeivipstock.com", "morning"),
    "นิเคอิบ่าย VIP": ("https://nikkeivipstock.com", "afternoon"),
    "จีนเช้า VIP": ("https://shenzhenindex.com", "morning"),
    "จีนบ่าย VIP": ("https://shenzhenindex.com", "afternoon"),
    "ฮั่งเส็งเช้า VIP": ("https://www.hsi-vip.com/", "morning"),
    "ฮั่งเส็งบ่าย VIP": ("https://www.hsi-vip.com/", "afternoon"),
    "ไต้หวัน VIP": ("https://tsecvipindex.com", "all"),
    "เกาหลี VIP": ("https://ktopvipindex.com", "all"),
    "หวยดาวโจนส์ VIP": ("https://dowjonespowerball.com/", "all"),
}


def scrape_vip_stock(lottery_name: str, target_date: Optional[date] = None) -> Optional[Dict[str, str]]:
    vip_info = VIP_STOCK_URLS.get(lottery_name)
    if not vip_info:
        return None
    url, session_type = vip_info
    target_date = target_date or datetime.now(TZ).date()

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return None

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            )
            page.goto(url, wait_until="networkidle", timeout=12000)
            html = page.content()
            browser.close()

        soup = BeautifulSoup(html, "lxml")
        text = soup.get_text(" ", strip=True)

        if not verify_date_guardrail(text, target_date):
            logger.debug("VIP stock %s (%s): target date %s not published yet on site", lottery_name, url, target_date)
            return None

        if lottery_name == "หวยดาวโจนส์ VIP":
            m5 = re.findall(r"(\d{5})", text)
            if m5:
                top5 = m5[0]
                bot2 = m5[1][-2:] if len(m5) > 1 else top5[:2]
                return {
                    "name": lottery_name,
                    "top3": top5[-3:],
                    "bottom2": bot2,
                    "full": top5,
                }
            return None

        if lottery_name == "เกาหลี VIP":
            try:
                r_kr = requests.get("https://api.ktopvipindex.com/api/kr", headers=HEADERS, timeout=5)
                if r_kr.status_code == 200:
                    kr_data = r_kr.json().get("data", {})
                    kr_date = kr_data.get("date")
                    if not kr_date or kr_date == target_date.strftime("%Y-%m-%d"):
                        kr_prices = kr_data.get("prices", {})
                        if kr_prices.get("available") and kr_prices.get("note") == "Close":
                            p_val = kr_prices.get("price", 0)
                            d_val = str(kr_prices.get("diff", ""))
                            p_str = f"{p_val:.2f}"
                            top3 = p_str.split(".")[0][-1] + p_str.split(".")[1]
                            bot2 = d_val.split(".")[1] if "." in d_val else d_val[-2:]
                            if len(top3) == 3 and len(bot2) == 2:
                                return {
                                    "name": lottery_name,
                                    "top3": top3,
                                    "bottom2": bot2,
                                    "full": f"{p_str} | {d_val}",
                                }
            except Exception as e:
                logger.debug("Korea VIP API error: %s", e)

            m_korea = re.search(r"(\d{3})\s*\|\s*(\d{2})", text)
            if m_korea:
                return {
                    "name": lottery_name,
                    "top3": m_korea.group(1),
                    "bottom2": m_korea.group(2),
                    "full": m_korea.group(1) + m_korea.group(2),
                }

        # Strict keyword matching for each VIP session
        # Nikkei uses 'afternoon', HSI & Shenzhen use 'evening', Taiwan uses 'closed' / 'close'
        patterns = []
        if session_type == "morning":
            patterns = [r"morning\s+top\s+(\d{3})\s+bottom\s+(\d{2})"]
        elif session_type == "afternoon":
            patterns = [
                r"afternoon\s+top\s+(\d{3})\s+bottom\s+(\d{2})",
                r"evening\s+top\s+(\d{3})\s+bottom\s+(\d{2})"
            ]
        elif session_type == "all":
            patterns = [
                r"closed?\s+top\s+(\d{3})\s+bottom\s+(\d{2})",
                r"top\s+(\d{3})\s+bottom\s+(\d{2})"
            ]

        for pat in patterns:
            m_exp = re.search(pat, text, re.IGNORECASE)
            if m_exp:
                return {
                    "name": lottery_name,
                    "top3": m_exp.group(1),
                    "bottom2": m_exp.group(2),
                    "full": m_exp.group(1) + m_exp.group(2),
                }

        # If not drawn yet (e.g. 'Evening Top - Bottom -' or placeholder), return None!
        # NEVER guess from chart numbers!
        return None
    except Exception as exc:
        logger.debug("VIP Stock scrape error for %s: %s", lottery_name, exc)

    return None


# ---------------------------------------------------------
# Master Direct Scraper Dispatcher
# ---------------------------------------------------------
def scrape_direct_official(lottery_name: str, target_date: Optional[date] = None) -> Optional[Dict[str, str]]:
    target_date = target_date or datetime.now(TZ).date()

    # 1. Hanoi Fast JSON APIs
    if lottery_name in HANOI_API_MAP:
        res = scrape_hanoi_api(lottery_name, target_date=target_date)
        if res:
            logger.info("⚡ Fast Direct scrape SUCCESS for '%s' (Hanoi API): %s-%s", lottery_name, res["top3"], res["bottom2"])
            return res

    # 2. Lao Fast JSON APIs
    if lottery_name in LAO_API_MAP:
        res = scrape_lao_api(lottery_name, target_date=target_date)
        if res:
            logger.info("⚡ Fast Direct scrape SUCCESS for '%s' (Lao API): %s-%s", lottery_name, res["top3"], res["bottom2"])
            return res

    # 3. Lao Union (ลาวสามัคคี)
    if lottery_name == "ลาวสามัคคี":
        res = scrape_lao_union(target_date=target_date)
        if res:
            logger.info("⚡ Fast Direct scrape SUCCESS for '%s' (Lao Union): %s-%s", lottery_name, res["top3"], res["bottom2"])
            return res

    # 4. Superrich 3 Rath VIP
    if lottery_name in ("อังกฤษVIP", "เยอรมันVIP", "รัสเซียVIP"):
        res = scrape_superrich_vip(lottery_name, target_date=target_date)
        if res:
            logger.info("⚡ Fast Direct scrape SUCCESS for '%s' (Superrich VIP): %s-%s", lottery_name, res["top3"], res["bottom2"])
            return res

    # 5. Fast VIP REST APIs (Dow Jones VIP & Korea VIP)
    if lottery_name == "หวยดาวโจนส์ VIP":
        res = scrape_dowjones_powerball_vip(target_date=target_date)
        if res:
            logger.info("⚡ Fast Direct scrape SUCCESS for '%s' (Dow Jones VIP API): %s-%s", lottery_name, res["top3"], res["bottom2"])
            return res

    if lottery_name == "เกาหลี VIP":
        res = scrape_korea_vip_api(target_date=target_date)
        if res:
            logger.info("⚡ Fast Direct scrape SUCCESS for '%s' (Korea VIP API): %s-%s", lottery_name, res["top3"], res["bottom2"])
            return res

    # 6. VIP Stocks (Playwright scraper)
    if lottery_name in VIP_STOCK_URLS:
        res = scrape_vip_stock(lottery_name, target_date=target_date)
        if res:
            logger.info("⚡ Fast Direct scrape SUCCESS for '%s' (VIP Stock): %s-%s", lottery_name, res["top3"], res["bottom2"])
            return res

    # 7. Main Hanoi lotteries (Press Hanoi Parser)
    clean_lotto = lottery_name.replace("หวย", "").replace(" ", "").strip()
    if clean_lotto in ("ฮานอยพิเศษ", "ฮานอย", "ฮานอยปกติ", "ฮานอยVIP", "ฮานอยvip"):
        try:
            from parsers.press_hanoi import PressHanoiParser
            parser = PressHanoiParser(lotto_name=lottery_name)
            p_res = parser.parse()
            if p_res and len(p_res.get("top3", "")) == 3 and len(p_res.get("bottom2", "")) == 2:
                logger.info("⚡ Fast Direct scrape SUCCESS for '%s' (Press Hanoi): %s-%s", lottery_name, p_res["top3"], p_res["bottom2"])
                return p_res
        except Exception as pe:
            logger.debug("Press Hanoi check for %s: %s", lottery_name, pe)

    return None
