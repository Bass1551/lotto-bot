# -*- coding: utf-8 -*-
"""Base parser class and common helpers for lottery result scraping."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Optional

import requests
import urllib3
from bs4 import BeautifulSoup
from tenacity import retry, stop_after_attempt, wait_fixed, retry_if_exception_type

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger("lottery_bot.parsers")


class ParseError(Exception):
    """Raised when a parser cannot extract a valid result."""


class BaseParser(ABC):
    """Abstract base class for all lottery parsers.

    Every concrete parser must implement `parse()` and return a dict:
        {
            "name": str,
            "top3": str,      # 3 digits
            "bottom2": str,   # 2 digits
            "full": str,      # optional full number string
        }
    """

    name: str = "Unknown"
    url: str = ""
    use_playwright: bool = False  # Override in subclass if site needs JS

    def __init__(self, url: Optional[str] = None) -> None:
        if url:
            self.url = url
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                "Accept-Language": "th-TH,th;q=0.9,en-US;q=0.8,en;q=0.7",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            }
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_fixed(2),
        retry=retry_if_exception_type((requests.RequestException, ParseError)),
        reraise=True,
    )
    def fetch_html(self, url: Optional[str] = None) -> BeautifulSoup:
        """Fetch page and return BeautifulSoup object. Retries 3 times."""
        target = url or self.url
        logger.info("Fetching %s", target)
        resp = self.session.get(target, timeout=20, verify=False)
        resp.raise_for_status()
        resp.encoding = resp.apparent_encoding or "utf-8"
        return BeautifulSoup(resp.text, "lxml")

    def fetch_with_playwright(self, url: Optional[str] = None) -> str:
        """Fetch fully rendered HTML using Playwright (for JS-heavy sites)."""
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise ParseError(
                "Playwright is required for this site. "
                "Run: pip install playwright && playwright install chromium"
            ) from exc

        target = url or self.url
        logger.info("Fetching with Playwright: %s", target)

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                )
            )
            page.goto(target, wait_until="networkidle", timeout=30000)
            content = page.content()
            browser.close()
        return content

    def fetch_soup(self, url: Optional[str] = None) -> BeautifulSoup:
        """Fetch page as BeautifulSoup with automatic Playwright fallback."""
        target = url or self.url
        if self.use_playwright:
            try:
                html = self.fetch_with_playwright(target)
                return BeautifulSoup(html, "lxml")
            except Exception as e:
                logger.warning("%s Playwright fetch failed (%s), trying HTTP fetch", self.name, e)
                return self.fetch_html(target)
        else:
            try:
                soup = self.fetch_html(target)
                text = soup.get_text(strip=True)
                if "JavaScript" in text or len(text) < 100:
                    logger.info("%s HTTP text indicates JS SPA (len=%d), using Playwright", self.name, len(text))
                    html = self.fetch_with_playwright(target)
                    return BeautifulSoup(html, "lxml")
                return soup
            except Exception as e:
                logger.info("%s HTTP fetch failed (%s), trying Playwright", self.name, e)
                html = self.fetch_with_playwright(target)
                return BeautifulSoup(html, "lxml")

    @abstractmethod
    def parse(self) -> dict[str, str]:
        """Parse the page and return result dict.

        Must return:
            {
                "name": self.name,
                "top3": "xxx",
                "bottom2": "xx",
                "full": "xxxxx"   # optional
            }
        """
        ...

    def _validate(self, top3: str, bottom2: str) -> None:
        """Raise ParseError if digits are not the expected length."""
        if not (top3.isdigit() and len(top3) == 3):
            raise ParseError(f"Invalid top3: '{top3}' (expected 3 digits)")
        if not (bottom2.isdigit() and len(bottom2) == 2):
            raise ParseError(f"Invalid bottom2: '{bottom2}' (expected 2 digits)")

    def run(self) -> dict[str, str]:
        """Public entry point with logging."""
        try:
            result = self.parse()
            self._validate(result["top3"], result["bottom2"])
            logger.info(
                "Parsed %s → top3=%s bottom2=%s",
                self.name,
                result["top3"],
                result["bottom2"],
            )
            return result
        except Exception as exc:
            logger.error("Parser %s failed: %s", self.name, exc)
            raise
