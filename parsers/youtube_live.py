# -*- coding: utf-8 -*-
"""Parser for YouTube Live streams (e.g. @banmahahenglivenow)."""

from __future__ import annotations

import re
import requests

from parsers.base import BaseParser, ParseError
from utils import setup_logging

logger = setup_logging()


class YoutubeLiveParser(BaseParser):
    """Scrapes YouTube Live Stream titles and descriptions for instant lottery results."""

    def __init__(self, url: str | None = None, lotto_name: str | None = None) -> None:
        target_url = url or "https://www.youtube.com/@banmahahenglivenow/live"
        super().__init__(url=target_url)
        self.lotto_name = lotto_name or ""

    def parse(self) -> dict[str, str]:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        }
        try:
            resp = requests.get(self.url, headers=headers, timeout=15)
            resp.raise_for_status()
            resp.encoding = "utf-8"
        except Exception as exc:
            raise ParseError(f"HTTP request to YouTube {self.url} failed: {exc}") from exc

        # Extract title and description
        html = resp.text
        titles = re.findall(r"<title>(.*?)</title>", html)
        descriptions = re.findall(r'"description":\{"simpleText":"(.*?)"\}', html)

        combined_text = " ".join(titles + descriptions)
        if not combined_text:
            raise ParseError("Could not extract content from YouTube Live Stream")

        # Search for lotto_name followed by 3-digit and 2-digit patterns
        # Pattern example: "ลาว HD 123-45" or "123 45"
        if self.lotto_name:
            clean_name = re.escape(self.lotto_name)
            pattern = re.compile(
                rf"{clean_name}.*?(?P<top3>\d{{3}})[\s\-\/]+(?P<bot2>\d{{2}})",
                re.IGNORECASE | re.DOTALL,
            )
            match = pattern.search(combined_text)
            if match:
                top3 = match.group("top3")
                bot2 = match.group("bot2")
                logger.info(
                    "YoutubeLiveParser found result for %s: top3=%s bottom2=%s",
                    self.lotto_name,
                    top3,
                    bot2,
                )
                return {
                    "name": self.lotto_name,
                    "top3": top3,
                    "bottom2": bot2,
                    "full": top3 + bot2,
                }

        raise ParseError(f"Live result for '{self.lotto_name}' is not yet available in YouTube stream")
