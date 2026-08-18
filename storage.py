# -*- coding: utf-8 -*-
"""
storage.py
ระบบกันส่งซ้ำ: เก็บผลล่าสุดที่เคยส่งไปแล้วของแต่ละหวย ลงไฟล์ JSON
เพื่อไม่ให้ push ข้อความเดิมซ้ำเข้ากลุ่ม LINE
"""
import json
import os
import threading
from datetime import date

from config import SENT_LOG_PATH

_lock = threading.Lock()


def _ensure_dir():
    d = os.path.dirname(SENT_LOG_PATH)
    if d and not os.path.exists(d):
        os.makedirs(d, exist_ok=True)


def _load() -> dict:
    _ensure_dir()
    if not os.path.exists(SENT_LOG_PATH):
        return {}
    try:
        with open(SENT_LOG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        # ไฟล์เสียหรืออ่านไม่ได้ -> เริ่มใหม่แบบปลอดภัย (ไม่ทำโปรแกรมล้ม)
        return {}


def _save(data: dict):
    _ensure_dir()
    tmp_path = SENT_LOG_PATH + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp_path, SENT_LOG_PATH)


def _today_key() -> str:
    return date.today().isoformat()


def already_sent(lotto_key: str, result_number: str) -> bool:
    """เช็คว่าผลของหวยตัวนี้ (วันนี้) เคยถูกส่งไปแล้วหรือยัง"""
    with _lock:
        data = _load()
        today = _today_key()
        record = data.get(today, {}).get(lotto_key)
        return record == result_number


def mark_sent(lotto_key: str, result_number: str):
    """บันทึกว่าผลนี้ถูกส่งไปแล้ว"""
    with _lock:
        data = _load()
        today = _today_key()
        data.setdefault(today, {})[lotto_key] = result_number
        # เก็บย้อนหลังไม่เกิน 14 วัน กันไฟล์บวม
        if len(data) > 14:
            oldest_keys = sorted(data.keys())[: len(data) - 14]
            for k in oldest_keys:
                data.pop(k, None)
        _save(data)
