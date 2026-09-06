# -*- coding: utf-8 -*-
"""Edaylotto parser and history extractor for Vietnam & Lao development lotteries."""

from __future__ import annotations

import json
import logging
import os
import re
import time
from datetime import date, datetime
from pathlib import Path
from typing import Optional

import requests

from parsers.base import BaseParser, ParseError

logger = logging.getLogger("lottery_bot.parsers.edaylotto")

EDAYLOTTO_SESSION_FILE = Path("data/edaylotto_session.json")
EDAYLOTTO_LOGIN_URL = "https://edaylotto.com/#/auth/login"
EDAYLOTTO_API_BASE = "https://api.edaylotto.com"

# Product code mapping for the 4 lotteries requested by user
EDAYLOTTO_CODE_MAP = {
    # Hanoi Special (17:30)
    "หวยฮานอย พิเศษ": "HC",
    "ฮานอยพิเศษ": "HC",
    "ฮานอย พิเศษ": "HC",
    # Hanoi Regular (18:30)
    "หวยฮานอย": "VN",
    "ฮานอยปกติ": "VN",
    "ฮานอย": "VN",
    # Hanoi VIP (19:30)
    "หวยฮานอย VIP": "HC2",
    "ฮานอย VIP": "HC2",
    "ฮานอยVIP": "HC2",
    # Lao Phattana (20:30)
    "หวยลาวพัฒนา (จ-ศ)": "LA",
    "หวยลาวพัฒนา": "LA",
    "ลาวพัฒนา": "LA",
    "ลาวพัฒนา (จ-ศ)": "LA",
}


def get_product_code(lottery_name: str) -> Optional[str]:
    """Map lottery name to edaylotto product code."""
    cleaned = lottery_name.strip()
    if cleaned in EDAYLOTTO_CODE_MAP:
        return EDAYLOTTO_CODE_MAP[cleaned]
    for k, v in EDAYLOTTO_CODE_MAP.items():
        if k in cleaned or cleaned in k:
            return v
    return None


class EdaylottoClient:
    """Client for authenticating and querying edaylotto.com APIs."""

    def __init__(
        self,
        username: str = "zpy0kadbdd555",
        password: str = "123456",
        session_file: Path = EDAYLOTTO_SESSION_FILE,
    ) -> None:
        self.username = username
        self.password = password
        self.session_file = session_file
        self.session_id: Optional[str] = None
        self._load_session()

    def _load_session(self) -> None:
        if self.session_file.exists():
            try:
                with open(self.session_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.session_id = data.get("auth", {}).get("sessionId")
            except Exception as e:
                logger.warning("Could not read edaylotto session file: %s", e)

    def login(self) -> str:
        """Authenticate using Chrome with Cloudflare Turnstile and save session ID."""
        logger.info("Performing fresh login to edaylotto.com for user: %s", self.username)
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(
                channel="chrome",
                headless=False,
                args=["--disable-blink-features=AutomationControlled"],
            )
            context = browser.new_context(viewport={"width": 1280, "height": 800})
            page = context.new_page()

            auth_result = {}

            def on_response(res):
                if "api.edaylotto.com" in res.url and "auth/login" in res.url:
                    try:
                        auth_result["auth"] = res.json()
                    except Exception:
                        pass

            page.on("response", on_response)

            try:
                page.goto(EDAYLOTTO_LOGIN_URL, wait_until="domcontentloaded", timeout=45000)

                # Wait for Cloudflare Turnstile to solve
                token_found = False
                for _ in range(25):
                    val = page.evaluate(
                        """() => {
                        const input = document.querySelector('input[name="cf-turnstile-response"]');
                        return input ? input.value : null;
                    }"""
                    )
                    if val:
                        token_found = True
                        break
                    time.sleep(0.5)

                if not token_found:
                    logger.warning("Turnstile token took longer, proceeding with form fill...")

                page.fill('input[name="username"]', self.username)
                page.fill('input[name="password"]', self.password)
                time.sleep(1)

                page.click("#kt_sign_in_submit")
                time.sleep(5)

                if "auth" in auth_result:
                    sid = auth_result["auth"].get("sessionId")
                    if sid:
                        self.session_id = sid
                        self.session_file.parent.mkdir(parents=True, exist_ok=True)
                        with open(self.session_file, "w", encoding="utf-8") as f:
                            json.dump(auth_result, f, indent=2, ensure_ascii=False)
                        logger.info("Successfully authenticated to edaylotto! Session ID: %s", sid)
                        return sid

                raise ParseError("Failed to obtain session ID from edaylotto login")
            finally:
                browser.close()

    def get_valid_session_id(self, force_refresh: bool = False) -> str:
        if force_refresh or not self.session_id:
            return self.login()
        return self.session_id

    def fetch_product_awards(self, product_code: str) -> list[dict]:
        """Fetch historical award results for a product code."""
        sid = self.get_valid_session_id()
        url = f"{EDAYLOTTO_API_BASE}/api/rewardcalc/award/get_by_product/{product_code}"
        headers = {"Authorization": f"Bearer {sid}"}

        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 401:
            logger.warning("Edaylotto session expired (401). Refreshing login...")
            sid = self.login()
            headers = {"Authorization": f"Bearer {sid}"}
            resp = requests.get(url, headers=headers, timeout=10)

        if resp.status_code != 200:
            raise ParseError(f"Edaylotto API failed with status {resp.status_code}: {resp.text[:200]}")

        data = resp.json().get("data", {})
        raw_awards = data.get("awards", []) or []

        parsed_results = []
        for a in raw_awards:
            name_str = a.get("name", "")
            match = re.search(r"(\d{2})/(\d{2})/(\d{2})", name_str)
            if match:
                d, m, y = match.groups()
                full_y = 2000 + int(y) - 43  # Convert BE 69 to AD 2026
                iso_date = f"{full_y:04d}-{int(m):02d}-{int(d):02d}"
            else:
                continue

            top3 = None
            bot2 = None
            for item in a.get("set_items", []):
                th_name = item.get("names", {}).get("th", "")
                val = item.get("value", [""])[0]
                if "3 ตัวบน" in th_name:
                    top3 = val
                elif "2 ตัวล่าง" in th_name:
                    bot2 = val

            if top3 and bot2:
                parsed_results.append({
                    "result_date": iso_date,
                    "draw_name": name_str,
                    "top3": str(top3).zfill(3)[-3:],
                    "bottom2": str(bot2).zfill(2)[-2:],
                })

        return parsed_results

    def get_history(self, lottery_name: str, limit: int = 15) -> list[dict]:
        """Return history records sorted chronologically (oldest to newest)."""
        code = get_product_code(lottery_name)
        if not code:
            raise ParseError(f"Unknown edaylotto lottery: {lottery_name}")

        awards = self.fetch_product_awards(code)
        # Sort chronologically by date ascending
        awards.sort(key=lambda x: x["result_date"])
        return awards[-limit:]


_client = EdaylottoClient()


class EdaylottoParser(BaseParser):
    """Parser that fetches live draw results and history directly from edaylotto.com."""

    def __init__(self, name: str = "", url: str = EDAYLOTTO_LOGIN_URL) -> None:
        super().__init__(url=url)
        self.name = name
        self.client = _client

    def parse(self, name: Optional[str] = None, **kwargs) -> dict:
        target_name = name or self.name
        code = get_product_code(target_name)
        if not code:
            raise ParseError(f"No edaylotto mapping for: {target_name}")

        awards = self.client.fetch_product_awards(code)
        if not awards:
            raise ParseError(f"No awards returned from edaylotto for: {target_name} ({code})")

        # Most recent draw is the last in chronological order or first in raw list
        latest = awards[0]  # raw awards are sorted newest first
        today_str = date.today().isoformat()

        # Check if the latest result matches today
        if latest["result_date"] != today_str:
            raise ParseError(
                f"Edaylotto: latest draw for {target_name} is {latest['result_date']}, today {today_str} not yet available"
            )

        return {
            "name": target_name,
            "top3": latest["top3"],
            "bottom2": latest["bottom2"],
            "full": f"{latest['top3']}{latest['bottom2']}",
        }
