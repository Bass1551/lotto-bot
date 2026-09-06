# -*- coding: utf-8 -*-
"""Parser registry – map config "parser" key to concrete class factory."""

from __future__ import annotations

from typing import Type

from parsers.base import BaseParser
from parsers.hanoi_hd import HanoiHdParser
from parsers.hanoi_star import HanoiStarParser
from parsers.hanoi_tv import HanoiTvParser
from parsers.hanoi_kachad import HanoiKachadParser
from parsers.hanoi_asean import HanoiAseanParser
from parsers.lao_hd import LaoHdParser
from parsers.lao_tv import LaoTvParser
from parsers.lao_star import LaoStarParser
from parsers.lao_extra import LaoExtraParser
from parsers.stock_generic import (
    NikkeiMorningParser,
    NikkeiAfternoonParser,
    ChinaMorningParser,
    ChinaAfternoonParser,
    HangsengMorningParser,
    HangsengAfternoonParser,
    TaiwanParser,
    KoreaParser,
    SingaporeParser,
    ThaiEveningParser,
)
from parsers.vip_stock import (
    NikkeiMorningVipParser,
    NikkeiAfternoonVipParser,
    ChinaMorningVipParser,
    ChinaAfternoonVipParser,
    HangsengMorningVipParser,
    HangsengAfternoonVipParser,
    TaiwanVipParser,
    KoreaVipParser,
)

from parsers.smlot_reward import SmlotRewardParser
from parsers.edaylotto import EdaylottoParser

from parsers.press_hanoi import PressHanoiParser
from parsers.youtube_live import YoutubeLiveParser
from parsers.realtime_stock import RealtimeStockParser
from parsers.lao_direct import LaoDirectParser

PARSER_MAP: dict[str, Type[BaseParser]] = {
    # Central SMLOT Report Parser
    "smlot_reward": SmlotRewardParser,
    "edaylotto": EdaylottoParser,
    "press_hanoi": PressHanoiParser,
    "youtube_live": YoutubeLiveParser,
    "realtime_stock": RealtimeStockParser,
    "lao_direct": LaoDirectParser,
    # Hanoi
    "hanoi_hd": HanoiHdParser,
    "hanoi_star": HanoiStarParser,
    "hanoi_tv": HanoiTvParser,
    "hanoi_kachad": HanoiKachadParser,
    "hanoi_asean": HanoiAseanParser,
    # Laos
    "lao_hd": LaoHdParser,
    "lao_tv": LaoTvParser,
    "lao_star": LaoStarParser,
    "lao_extra": LaoExtraParser,
    # Normal stock
    "nikkei_morning": NikkeiMorningParser,
    "nikkei_afternoon": NikkeiAfternoonParser,
    "china_morning": ChinaMorningParser,
    "china_afternoon": ChinaAfternoonParser,
    "hangseng_morning": HangsengMorningParser,
    "hangseng_afternoon": HangsengAfternoonParser,
    "taiwan": TaiwanParser,
    "korea": KoreaParser,
    "singapore": SingaporeParser,
    "thai_evening": ThaiEveningParser,
    # VIP stock
    "nikkei_morning_vip": NikkeiMorningVipParser,
    "nikkei_afternoon_vip": NikkeiAfternoonVipParser,
    "china_morning_vip": ChinaMorningVipParser,
    "china_afternoon_vip": ChinaAfternoonVipParser,
    "hangseng_morning_vip": HangsengMorningVipParser,
    "hangseng_afternoon_vip": HangsengAfternoonVipParser,
    "taiwan_vip": TaiwanVipParser,
    "korea_vip": KoreaVipParser,
}


def get_parser(parser_key: str, url: str | None = None, lotto_name: str | None = None) -> BaseParser:
    """Instantiate the correct parser by key from config.json."""
    cls = PARSER_MAP.get(parser_key)
    if cls is None:
        raise KeyError(
            f"Unknown parser key '{parser_key}'. "
            f"Available: {list(PARSER_MAP.keys())}"
        )
    if cls is SmlotRewardParser:
        return SmlotRewardParser(url=url, lotto_name=lotto_name)
    if cls is PressHanoiParser:
        return PressHanoiParser(url=url, lotto_name=lotto_name)
    if cls is YoutubeLiveParser:
        return YoutubeLiveParser(url=url, lotto_name=lotto_name)
    if cls is RealtimeStockParser:
        return RealtimeStockParser(url=url, lotto_name=lotto_name)
    if cls is LaoDirectParser:
        return LaoDirectParser(url=url, lotto_name=lotto_name)
    return cls(url=url)
