# -*- coding: utf-8 -*-
"""Utility functions for lottery bot."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Optional

# Emoji mapping for digits 0-9
DIGIT_EMOJI: dict[str, str] = {
    "0": "0️⃣",
    "1": "1️⃣",
    "2": "2️⃣",
    "3": "3️⃣",
    "4": "4️⃣",
    "5": "5️⃣",
    "6": "6️⃣",
    "7": "7️⃣",
    "8": "8️⃣",
    "9": "9️⃣",
}


def setup_logging(log_dir: str = "logs") -> logging.Logger:
    """Configure root logger with file and console handlers.

    Args:
        log_dir: Directory to store log files.

    Returns:
        Configured logger instance.
    """
    Path(log_dir).mkdir(parents=True, exist_ok=True)
    log_file = Path(log_dir) / "lottery_bot.log"

    logger = logging.getLogger("lottery_bot")
    logger.setLevel(logging.INFO)

    # Avoid duplicate handlers if called multiple times
    if logger.handlers:
        return logger

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # File handler
    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setLevel(logging.INFO)
    fh.setFormatter(formatter)
    logger.addHandler(fh)

    import sys

    if sys.stdout and hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    if sys.stderr and hasattr(sys.stderr, "reconfigure"):
        try:
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    # Console handler
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch.setFormatter(formatter)
    logger.addHandler(ch)

    return logger


def digits_to_emoji(digits: str) -> str:
    """Convert a string of digits to emoji representation.

    Args:
        digits: String containing only digits (e.g. "344").

    Returns:
        Emoji string (e.g. "3️⃣ 4️⃣ 4️⃣").
    """
    return " ".join(DIGIT_EMOJI.get(d, d) for d in digits if d.isdigit())


def extract_digits(text: str, length: Optional[int] = None) -> str:
    """Extract consecutive digits from text.

    Args:
        text: Raw text that may contain numbers.
        length: If provided, return only the first `length` digits found.

    Returns:
        String of digits only.
    """
    digits = re.sub(r"\D", "", text or "")
    if length is not None and len(digits) >= length:
        return digits[:length]
    return digits


def format_result_message(
    name: str,
    top3: str,
    bottom2: str,
    flag: str = "🎯",
) -> str:
    """Format the LINE message according to specification.

    Example output:
        🇻🇳 ฮานอย HD
        🔺 3️⃣ 4️⃣ 4️⃣
        🔻 0️⃣ 3️⃣

    Args:
        name: Lottery name.
        top3: 3-digit top result.
        bottom2: 2-digit bottom result.
        flag: Country / lottery flag emoji.

    Returns:
        Formatted message string.
    """
    top_emoji = digits_to_emoji(top3.zfill(3)[-3:])
    bottom_emoji = digits_to_emoji(bottom2.zfill(2)[-2:])

    return (
        f"{flag} {name}\n"
        f"🔺 {top_emoji}\n"
        f"🔻 {bottom_emoji}"
    )


def safe_int(value: str, default: int = 0) -> int:
    """Convert string to int safely."""
    try:
        return int(re.sub(r"\D", "", value) or default)
    except (ValueError, TypeError):
        return default


THAI_DAYS = ["จันทร์", "อังคาร", "พุธ", "พฤหัสบดี", "ศุกร์", "เสาร์", "อาทิตย์"]

def generate_summary_report(results: list[dict], target_date: Optional[date] = None) -> str:
    """Format daily results in clean text template format matching user's specification."""
    from datetime import date as dt_date
    if target_date is None:
        target_date = dt_date.today()

    day_name = THAI_DAYS[target_date.weekday()]
    date_str = target_date.strftime("%d-%m-%y")

    lines = [
        f"สรุปผลวัน{day_name} {date_str}",
        "",
        "┅┅┅┅┅┅┅┅┅┅┅┅┅┅"
    ]

    for item in results:
        name = item.get("lottery_name", item.get("name", ""))
        top3 = str(item.get("top3", "")).zfill(3)[-3:]
        bot2 = str(item.get("bottom2", "")).zfill(2)[-2:]
        flag = item.get("flag", "")
        
        flag_prefix = f" {flag}" if flag else ""
        lines.append(f"{top3}-{bot2}{flag_prefix} {name}")

    lines.append("┅┅┅┅┅┅┅┅┅┅┅┅┅┅")
    return "\n".join(lines)


THAI_MONTHS_SHORT = ["", "ม.ค.", "ก.พ.", "มี.ค.", "เม.ย.", "พ.ค.", "มิ.ย.", "ก.ค.", "ส.ค.", "ก.ย.", "ต.ค.", "พ.ย.", "ธ.ค."]

def generate_history_report(lottery_name: str, results: list[dict], flag: str = "") -> str:
    """Format 10-day historical statistics report matching user's exact template.
    
    Example output:
        🇱🇦 สถิติย้อนหลัง ลาว Extra 🇱🇦
        ➖➖➖➖➖➖➖➖
        🇱🇦 18 ส.ค. 69 | 968-93
        🇱🇦 19 ส.ค. 69 | 214-94
        ...
    """
    flag_str = f"{flag} " if flag else ""
    flag_suffix = f" {flag}" if flag else ""
    lines = [
        f"{flag_str}สถิติย้อนหลัง {lottery_name}{flag_suffix}".strip(),
        "🪐 แอดBaras 🛸",
        "➖➖➖➖➖➖➖➖"
    ]
    
    for r in results:
        r_date = r.get("result_date", "")
        top3 = str(r.get("top3", "")).zfill(3)[-3:]
        bot2 = str(r.get("bottom2", "")).zfill(2)[-2:]
        
        # Parse ISO date YYYY-MM-DD to Thai short date e.g. "18 ส.ค. 69"
        thai_date_str = r_date
        if r_date and len(r_date.split("-")) == 3:
            y, m, d = map(int, r_date.split("-"))
            d_str = f"{d:02d}"
            m_str = THAI_MONTHS_SHORT[m] if 1 <= m <= 12 else str(m)
            th_year_short = str((y + 543) % 100).zfill(2)
            thai_date_str = f"{d_str} {m_str} {th_year_short}"
            
        line_flag = f"{flag} " if flag else ""
        lines.append(f"{line_flag}{thai_date_str} | {top3}-{bot2}")
        
    return "\n".join(lines)


import holidays
from datetime import date, timedelta

STOCK_HOLIDAYS_MAP = {
    "นิเคอิเช้า": (holidays.Japan(), "ญี่ปุ่น (Tokyo Stock Exchange)"),
    "นิเคอิบ่าย": (holidays.Japan(), "ญี่ปุ่น (Tokyo Stock Exchange)"),
    "จีนเช้า": (holidays.China(), "จีน (Shanghai/Shenzhen Stock Exchange)"),
    "จีนบ่าย": (holidays.China(), "จีน (Shanghai/Shenzhen Stock Exchange)"),
    "ฮั่งเส็งเช้า": (holidays.HongKong(), "ฮ่องกง (Hong Kong Stock Exchange)"),
    "ฮั่งเส็งบ่าย": (holidays.HongKong(), "ฮ่องกง (Hong Kong Stock Exchange)"),
    "ไต้หวัน": (holidays.Taiwan(), "ไต้หวัน (Taiwan Stock Exchange)"),
    "หุ้นเกาหลี": (holidays.SouthKorea(), "เกาหลีใต้ (Korea Exchange)"),
    "หุ้นสิงคโปร์": (holidays.Singapore(), "สิงคโปร์ (Singapore Exchange)"),
    "หุ้นไทยเย็น": (holidays.Thailand(), "ไทย (ตลาดหลักทรัพย์แห่งประเทศไทย)"),
    "หุ้นอังกฤษ": (holidays.UnitedKingdom(), "อังกฤษ (London Stock Exchange)"),
    "หุ้นเยอรมัน": (holidays.Germany(), "เยอรมัน (Frankfurt Stock Exchange)"),
    "หุ้นรัสเซีย": (holidays.Russia(), "รัสเซีย (Moscow Exchange)"),
    "หุ้นดาวโจนส์": (holidays.UnitedStates(), "สหรัฐอเมริกา (New York Stock Exchange)"),
    "หวยดาวโจนส์": (holidays.UnitedStates(), "สหรัฐอเมริกา (New York Stock Exchange)"),
    "หุ้นอินเดีย": (holidays.India(), "อินเดีย (National Stock Exchange of India)"),
    "หุ้นอียิปต์": (holidays.Egypt(), "อียิปต์ (The Egyptian Exchange)"),
}


def check_market_closed(lottery_name: str, target_date: date) -> tuple[bool, str]:
    """Check if a stock lottery is closed on target_date due to weekend or exchange holiday.
    Returns (is_closed, reason).
    """
    if lottery_name in ("หุ้นดาวโจนส์", "หวยดาวโจนส์"):
        # US Stock Exchange (NYSE) closes Friday afternoon US time -> Sat 03:55 AM BKK is last draw.
        # BKK Sunday (03:55) and BKK Monday (03:55) have no draws!
        if target_date.weekday() in (6, 0):  # Sunday or Monday in Thailand
            return True, "ตลาดปิด (วันหยุดสุดสัปดาห์ NYSE)"
        try:
            us_cal = holidays.UnitedStates()
            trade_date = target_date - timedelta(days=1)
            if trade_date in us_cal:
                h_name = us_cal.get(trade_date)
                return True, f"ตลาดปิด (วันหยุดตลาดสหรัฐฯ: {h_name})"
        except Exception:
            pass
        return False, ""

    if lottery_name in STOCK_HOLIDAYS_MAP:
        # Weekend check: Saturday (5) or Sunday (6)
        if target_date.weekday() in (5, 6):
            return True, "ตลาดปิด (วันหยุดสุดสัปดาห์ เสาร์-อาทิตย์)"
        cal, market_name = STOCK_HOLIDAYS_MAP[lottery_name]
        try:
            if target_date in cal:
                h_name = cal.get(target_date)
                return True, f"ตลาดปิด (วันหยุดตลาด{market_name}: {h_name})"
        except Exception:
            pass
        return False, ""

    if lottery_name in ("หวยไทย", "สลากกินแบ่งรัฐบาล", "หวยรัฐบาลไทย"):
        if target_date.day not in (1, 16):
            return True, "ออกรางวัลเฉพาะวันที่ 1 และ 16 ของเดือน"
        return False, ""

    return False, ""



