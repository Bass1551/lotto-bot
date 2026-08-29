# -*- coding: utf-8 -*-
"""Parser for YouTube Live streams from channel 'บ้านมหาเฮง - LIVE NOW' (UCUZt27_J1xRgzc5kQ5YMTvA)."""

from __future__ import annotations

import re
import requests
import xml.etree.ElementTree as ET

from parsers.base import BaseParser, ParseError
from utils import setup_logging

logger = setup_logging()
CHANNEL_RSS_URL = "https://www.youtube.com/feeds/videos.xml?channel_id=UCUZt27_J1xRgzc5kQ5YMTvA"


class YoutubeLiveParser(BaseParser):
    """Scrapes YouTube Live Streams for instant lottery results from 'บ้านมหาเฮง - LIVE NOW'."""

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

        # 1. Fetch latest stream URLs from YouTube RSS feed
        video_urls = [self.url]
        try:
            r = requests.get(CHANNEL_RSS_URL, headers=headers, timeout=10)
            if r.status_code == 200:
                root = ET.fromstring(r.text)
                ns = {"atom": "http://www.w3.org/2005/Atom"}
                for entry in root.findall("atom:entry", ns)[:5]:
                    link_el = entry.find("atom:link", ns)
                    if link_el is not None and "href" in link_el.attrib:
                        video_urls.append(link_el.attrib["href"])
        except Exception as exc:
            logger.debug("Failed to fetch YouTube RSS feed: %s", exc)

        # 2. Check each video URL for lotto_name and results
        for v_url in video_urls:
            try:
                resp = requests.get(v_url, headers=headers, timeout=10)
                if resp.status_code != 200:
                    continue
                resp.encoding = "utf-8"
                html = resp.text

                titles = re.findall(r"<title>(.*?)</title>", html)
                descriptions = re.findall(r'"description":\{"simpleText":"(.*?)"\}', html)
                combined_text = " ".join(titles + descriptions)

                if self.lotto_name and combined_text:
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
                            "YoutubeLiveParser found result for %s: top3=%s bottom2=%s from %s",
                            self.lotto_name,
                            top3,
                            bot2,
                            v_url,
                        )
                        return {
                            "name": self.lotto_name,
                            "top3": top3,
                            "bottom2": bot2,
                            "full": top3 + bot2,
                        }
            except Exception as exc:
                logger.debug("Error checking video URL %s: %s", v_url, exc)

        raise ParseError(f"Live result for '{self.lotto_name}' is not yet available on YouTube Channel 'บ้านมหาเฮง - LIVE NOW'")
