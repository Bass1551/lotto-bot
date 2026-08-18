# -*- coding: utf-8 -*-
"""
scrapers/base.py
ฟังก์ชันช่วยเหลือส่วนกลางสำหรับ scraper ทุกตัว
- fetch_html: ดึงหน้าเว็บพร้อม retry และ timeout
- extract_digits: ดึงเฉพาะตัวเลขจากข้อความที่ scrape มา
"""
import logging
import re
import time

import requests
from bs4 import BeautifulSoup

from config import REQUEST_TIMEOUT, REQUEST_RETRY

logger = logging.getLogger("scraper")

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}


class ScrapeError(Exception):
    """เกิดข้อผิดพลาดระหว่างดึง/แปลผลข้อมูลจากเว็บ"""


def fetch_html(url: str, params: dict = None) -> BeautifulSoup:
    """
    ดึง HTML จาก url ที่กำหนด พร้อม retry ตาม REQUEST_RETRY
    คืนค่าเป็น BeautifulSoup object; ถ้าล้มเหลวทุกครั้ง จะ raise ScrapeError
    """
    last_error = None
    for attempt in range(1, REQUEST_RETRY + 1):
        try:
            resp = requests.get(
                url,
                params=params,
                headers=DEFAULT_HEADERS,
                timeout=REQUEST_TIMEOUT,
            )
            resp.raise_for_status()
            resp.encoding = resp.apparent_encoding or "utf-8"
            return BeautifulSoup(resp.text, "html.parser")
        except requests.RequestException as e:
            last_error = e
            logger.warning(
                "ดึงข้อมูลจาก %s ล้มเหลว (ครั้งที่ %s/%s): %s",
                url, attempt, REQUEST_RETRY, e,
            )
            time.sleep(1.5 * attempt)  # เว้นช่วงก่อน retry
    raise ScrapeError(f"ไม่สามารถดึงข้อมูลจาก {url} ได้หลังลองครบ {REQUEST_RETRY} ครั้ง") from last_error


def extract_digits(text: str, expected_length: int = 5) -> str:
    """
    ดึงเฉพาะตัวเลขจากสตริง แล้วตรวจสอบความยาวให้ตรงตามที่คาดหวัง (ปกติ 5 หลัก)
    ถ้าความยาวไม่ตรง จะ raise ScrapeError เพื่อให้ caller รู้ว่าผลยังไม่ออก/รูปแบบเปลี่ยน
    """
    digits = re.sub(r"\D", "", text or "")
    if expected_length and len(digits) != expected_length:
        raise ScrapeError(
            f"รูปแบบเลขที่ดึงได้ไม่ตรงตามคาด (ได้ '{digits}' ยาว {len(digits)} ต้องการ {expected_length} หลัก)"
        )
    return digits
