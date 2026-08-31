# -*- coding: utf-8 -*-
"""Parser for direct Lao official lottery result portals with SMLOT fallback."""

from __future__ import annotations

import re
import requests
from bs4 import BeautifulSoup

from parsers.base import BaseParser, ParseError
from parsers.smlot_reward import SmlotRewardParser
from utils import setup_logging

logger = setup_logging()

# Direct URLs for Lao lottery draws
LAO_PORTAL_MAP: dict[str, str] = {
    "ลาว Extra": "https://www.lao-extra.com/",
    "หวยลาวExtra": "https://www.lao-extra.com/",
    "ลาว TV": "https://www.laostv.com/",
    "หวยลาว TV": "https://www.laostv.com/",
    "ลาว HD": "https://www.laohd.com/",
    "ลาว Star": "https://laostar.la/",
    "หวยลาวสตาร์": "https://laostar.la/",
    "หวยลาวSTAR VIP": "https://laostar.la/",
    "ลาวสามัคคี": "https://laosamakkhi.com/",
    "ลาวอาเซียน": "https://laoasean.com/",
    "หวยลาว กาชาด": "https://laogachad.com/",
}


class LaoDirectParser(BaseParser):
    """Scrapes Lao official portals directly for zero-delay instant results."""

    def __init__(self, url: str | None = None, lotto_name: str | None = None) -> None:
        super().__init__(url=url or "")
        self.lotto_name = lotto_name or ""

    def parse(self) -> dict[str, str]:
        portal_url = LAO_PORTAL_MAP.get(self.lotto_name) or self.url
        if portal_url:
            try:
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                }
                resp = requests.get(portal_url, headers=headers, timeout=6)
                if resp.status_code == 200:
                    text = resp.text
                    # Search for 3-digit top and 2-digit bottom patterns in Lao text
                    # Example: "ເລກ 3 ໂຕ 208" and "ເລກ 2 ໂຕລຸ່ມ 22" or "3 ตัวบน 208"
                    top3_m = re.search(r"(?:ເລກ\s*3\s*ໂຕ|3\s*ตัวบน)\s*[:\-]?\s*(\d{3})", text)
                    bot2_m = re.search(r"(?:ເລກ\s*2\s*ໂຕລຸ່ມ|2\s*ตัวล่าง)\s*[:\-]?\s*(\d{2})", text)
                    
                    if top3_m and bot2_m:
                        top3 = top3_m.group(1)
                        bottom2 = bot2_m.group(1)
                        logger.info(
                            "⚡ LaoDirectParser scraped instant result for %s: top3=%s bottom2=%s from %s",
                            self.lotto_name,
                            top3,
                            bottom2,
                            portal_url,
                        )
                        return {
                            "name": self.lotto_name,
                            "top3": top3,
                            "bottom2": bottom2,
                            "full": top3 + bottom2,
                        }
            except Exception as exc:
                logger.debug("LaoDirectParser exception for %s: %s", self.lotto_name, exc)

        # Fallback to SMLOT
        logger.info("LaoDirectParser falling back to SMLOT parser for '%s'...", self.lotto_name)
        smlot_p = SmlotRewardParser(lotto_name=self.lotto_name)
        return smlot_p.parse()
