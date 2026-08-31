# -*- coding: utf-8 -*-
"""Real-time Global Stock Market Index Parser via Yahoo Finance with SMLOT fallback."""

from __future__ import annotations

import requests

from parsers.base import BaseParser, ParseError
from parsers.smlot_reward import SmlotRewardParser
from utils import setup_logging

logger = setup_logging()

# Map lottery names to Yahoo Finance market symbols
STOCK_SYMBOL_MAP: dict[str, str] = {
    # Japan Nikkei
    "นิเคอิเช้า": "^N225",
    "นิเคอิเช้า VIP": "^N225",
    "นิเคอิบ่าย": "^N225",
    "นิเคอิบ่าย VIP": "^N225",
    # Hong Kong Hang Seng
    "ฮั่งเส็งเช้า": "^HSI",
    "ฮั่งเส็งเช้า VIP": "^HSI",
    "ฮั่งเส็งบ่าย": "^HSI",
    "ฮั่งเส็งบ่าย VIP": "^HSI",
    # China Shanghai
    "จีนเช้า": "000001.SS",
    "จีนเช้า VIP": "000001.SS",
    "จีนบ่าย": "000001.SS",
    "จีนบ่าย VIP": "000001.SS",
    # Taiwan
    "ไต้หวัน": "^TWII",
    "ไต้หวัน VIP": "^TWII",
    # Korea
    "เกาหลี": "^KS11",
    "เกาหลี VIP": "^KS11",
    # Singapore
    "สิงคโปร์": "^STI",
    "สิงคโปร์ VIP": "^STI",
    "สิงค์โปร์ VIP": "^STI",
    # UK
    "อังกฤษ": "^FTSE",
    "อังกฤษVIP": "^FTSE",
    # Germany
    "เยอรมัน": "^GDAXI",
    "เยอรมันVIP": "^GDAXI",
    # Russia
    "รัสเซีย": "IMOEX.ME",
    "รัสเซียVIP": "IMOEX.ME",
    # USA Dow Jones
    "หวยดาวโจนส์": "^DJI",
    "หวยดาวโจนส์ VIP": "^DJI",
    "หวยดาวโจนส์ STAR": "^DJI",
    "หวยดาวโจนส์ extra": "^DJI",
    "หวยดาวโจนส์ TV": "^DJI",
    "หวยดาวโจนส์ mid night": "^DJI",
    # Egypt
    "หุ้นอียิปต์": "^EGX30",
}


class RealtimeStockParser(BaseParser):
    """Calculates top3 and bottom2 directly from real-time stock market closing data."""

    def __init__(self, url: str | None = None, lotto_name: str | None = None) -> None:
        super().__init__(url=url or "")
        self.lotto_name = lotto_name or ""

    def parse(self) -> dict[str, str]:
        symbol = STOCK_SYMBOL_MAP.get(self.lotto_name)
        if symbol:
            try:
                api_url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1m&range=1d"
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                }
                resp = requests.get(api_url, headers=headers, timeout=6)
                if resp.status_code == 200:
                    data = resp.json()
                    meta = data["chart"]["result"][0]["meta"]
                    price = float(meta["regularMarketPrice"])
                    prev_close = float(meta.get("chartPreviousClose") or meta.get("previousClose") or price)
                    change = price - prev_close

                    price_str = f"{price:.2f}"
                    top3 = price_str.replace(".", "")[-3:]

                    change_str = f"{abs(change):.2f}"
                    bottom2 = change_str.replace(".", "")[-2:]

                    logger.info(
                        "⚡ RealtimeStockParser calculated instant result for %s: price=%s (top3=%s) change=%s (bottom2=%s)",
                        self.lotto_name,
                        price_str,
                        top3,
                        change_str,
                        bottom2,
                    )
                    return {
                        "name": self.lotto_name,
                        "top3": top3,
                        "bottom2": bottom2,
                        "full": top3 + bottom2,
                    }
            except Exception as exc:
                logger.debug("RealtimeStockParser exception for %s: %s", self.lotto_name, exc)

        # Fallback to SMLOT if market API is closed or unlisted
        logger.info("Falling back to SMLOT parser for '%s'...", self.lotto_name)
        smlot_p = SmlotRewardParser(lotto_name=self.lotto_name)
        return smlot_p.parse()
