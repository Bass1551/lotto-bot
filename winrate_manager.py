# -*- coding: utf-8 -*-
"""
WinRateManager – Manages rolling 100-bill prediction win rates,
tracks requested prediction bills, evaluates outcomes after lottery draws,
and builds LINE Flex Message cards for bill results and overall win rates.
"""

from __future__ import annotations

import json
import os
import threading
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

import requests
from utils import setup_logging

logger = setup_logging()
TZ = ZoneInfo("Asia/Bangkok")

PENDING_BILLS_FILE = Path("data/pending_prediction_bills.json")
ROLLING_BILLS_FILE = Path("data/rolling_100_bills.json")
MAX_ROLLING_BILLS = 100
LOCK = threading.Lock()


def is_same_lottery(name1: str, name2: str) -> bool:
    """Accurately check if two lottery names refer to the exact same lottery draw."""
    if not name1 or not name2:
        return False
    if name1 == name2:
        return True

    import re
    clean1 = re.sub(r"[\s\-\_\(\)]", "", name1).replace("หวย", "").replace("หุ้น", "").replace("รอบ", "").replace("จศ", "").replace("จ-ศ", "").lower()
    clean2 = re.sub(r"[\s\-\_\(\)]", "", name2).replace("หวย", "").replace("หุ้น", "").replace("รอบ", "").replace("จศ", "").replace("จ-ศ", "").lower()
    if clean1 == clean2:
        return True

    # VIP check: one has VIP, other doesn't -> definitely NOT same lottery!
    is_vip1 = "vip" in clean1 or "วีไอพี" in clean1
    is_vip2 = "vip" in clean2 or "วีไอพี" in clean2
    if is_vip1 != is_vip2:
        return False

    # Session check (เช้า, บ่าย, เย็น)
    for s in ["เช้า", "บ่าย", "เย็น"]:
        if (s in clean1) != (s in clean2):
            return False

    # Sub-type checks
    sub_types = [
        "star", "สตาร์", "สตา", "extra", "เอกต้า", "เอ็กต้า", "เอ็กตร้า", "tv", "ทีวี", "hd", "เอชดี",
        "พิเศษ", "พัฒนา", "อาเซียน", "กาชาด", "สามัคคี", "ประตูชัย", "สันติภาพ", "ประชาชน", "ดาว",
        "midnight", "mid night", "มิดไนท์"
    ]
    for st in sub_types:
        if (st in clean1) != (st in clean2):
            return False

    # Thai lotto (รัฐบาล) vs Thai Stock (หุ้นไทยเย็น)
    is_lotto_thai1 = ("หวยไทย" in name1) or (clean1 == "ไทย")
    is_stock_thai1 = ("หุ้นไทย" in name1) or ("ไทยเย็น" in name1) or ("ปิดเย็น" in name1)
    is_lotto_thai2 = ("หวยไทย" in name2) or (clean2 == "ไทย")
    is_stock_thai2 = ("หุ้นไทย" in name2) or ("ไทยเย็น" in name2) or ("ปิดเย็น" in name2)
    if (is_lotto_thai1 and is_stock_thai2) or (is_stock_thai1 and is_lotto_thai2):
        return False

    # Generic check: "ฮานอย" (normal) vs sub-lotteries
    is_plain_hanoi1 = clean1 in {"ฮานอย", "ฮานอยปกติ"}
    is_plain_hanoi2 = clean2 in {"ฮานอย", "ฮานอยปกติ"}
    if is_plain_hanoi1 != is_plain_hanoi2:
        return False

    is_plain_lao1 = clean1 in {"ลาว", "ลาวพัฒนา"}
    is_plain_lao2 = clean2 in {"ลาว", "ลาวพัฒนา"}
    if is_plain_lao1 != is_plain_lao2:
        return False

    return clean1 == clean2 or clean1 in clean2 or clean2 in clean1


class WinRateManager:
    def __init__(self):
        PENDING_BILLS_FILE.parent.mkdir(parents=True, exist_ok=True)

    def load_pending_bills(self) -> List[Dict[str, Any]]:
        with LOCK:
            if not PENDING_BILLS_FILE.exists():
                return []
            try:
                with open(PENDING_BILLS_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error("Failed to load pending bills: %s", e)
                return []

    def save_pending_bills(self, bills: List[Dict[str, Any]]) -> None:
        with LOCK:
            try:
                with open(PENDING_BILLS_FILE, "w", encoding="utf-8") as f:
                    json.dump(bills, f, ensure_ascii=False, indent=2)
            except Exception as e:
                logger.error("Failed to save pending bills: %s", e)

    def record_bill(
        self,
        lottery_name: str,
        flag: str,
        group_id: Optional[str],
        prediction: Dict[str, Any],
        target_date: Optional[date] = None,
    ) -> Dict[str, Any]:
        """Record a newly requested prediction bill."""
        now_dt = datetime.now(TZ)
        t_date = target_date or now_dt.date()

        bills = self.load_pending_bills()

        # Avoid duplicate pending bills for the same lottery on the same date
        for b in bills:
            if b.get("lottery_name") == lottery_name and b.get("date") == t_date.isoformat():
                return b

        bill = {
            "id": f"BILL_{int(now_dt.timestamp())}_{lottery_name}",
            "lottery_name": lottery_name,
            "flag": flag,
            "group_id": group_id,
            "date": t_date.isoformat(),
            "created_at": now_dt.strftime("%H:%M:%S"),
            "prediction": {
                "run_rood": prediction.get("run_rood", []),
                "fun": prediction.get("fun", ""),
                "pairs": prediction.get("pairs", []),
                "triplets": prediction.get("triplets", []),
                "power_numbers": prediction.get("power_numbers", []),
            },
            "status": "pending",
        }
        bills.append(bill)
        self.save_pending_bills(bills)
        logger.info("Recorded new prediction bill: %s (%s)", lottery_name, bill["id"])
        return bill

    def load_rolling_bills(self) -> List[Dict[str, Any]]:
        with LOCK:
            if not ROLLING_BILLS_FILE.exists():
                return []
            try:
                with open(ROLLING_BILLS_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error("Failed to load rolling bills: %s", e)
                return []

    def save_rolling_bills(self, history: List[Dict[str, Any]]) -> None:
        with LOCK:
            try:
                with open(ROLLING_BILLS_FILE, "w", encoding="utf-8") as f:
                    json.dump(history, f, ensure_ascii=False, indent=2)
            except Exception as e:
                logger.error("Failed to save rolling bills: %s", e)

    def get_winrate_stats(self) -> Dict[str, Any]:
        """Calculate live win rate from the rolling window (up to 100 bills)."""
        history = self.load_rolling_bills()
        total = len(history)
        if total == 0:
            return {
                "total": 0,
                "wins": 0,
                "losses": 0,
                "winrate_pct": 0.0,
                "history": [],
                "streak": 0,
            }

        wins = sum(1 for b in history if b.get("is_win"))
        losses = total - wins
        winrate_pct = round((wins / total) * 100, 1)

        streak = 0
        for b in reversed(history):
            if b.get("is_win"):
                streak += 1
            else:
                break

        return {
            "total": total,
            "wins": wins,
            "losses": losses,
            "winrate_pct": winrate_pct,
            "history": history[-10:],
            "streak": streak,
        }

    def evaluate_bill(
        self,
        bill: Dict[str, Any],
        top3: str,
        bottom2: str,
    ) -> Tuple[bool, List[Dict[str, str]]]:
        """Evaluate if the bill hit any prize."""
        pred = bill.get("prediction", {})
        top3 = str(top3).zfill(3)[-3:]
        bot2 = str(bottom2).zfill(2)[-2:]
        top2 = top3[-2:]

        hits: List[Dict[str, str]] = []

        # 1. Check วิ่ง / รูด 19 ประตู
        run_rood = pred.get("run_rood", [])
        run_hits = []
        for digit in run_rood:
            if not digit:
                continue
            if digit in top3:
                run_hits.append(f"{digit} บน")
            if digit in bot2:
                run_hits.append(f"{digit} ล่าง")
        if run_hits:
            hits.append({
                "category": "🎯 วิ่ง / รูด 19 ประตู",
                "detail": f"เข้าเลขเด่น {' • '.join(run_hits)}",
                "is_hit": True,
            })

        # 2. Check เม็ดเดียว ฟันธง
        fun = pred.get("fun", "")
        if fun:
            fun_hits = []
            if fun in top3:
                fun_hits.append(f"{fun} บน")
            if fun in bot2:
                fun_hits.append(f"{fun} ล่าง")
            if fun_hits:
                hits.append({
                    "category": "⚡ เม็ดเดียว ฟันธง",
                    "detail": f"ฟันตรงเป้า {fun} ({' • '.join(fun_hits)})",
                    "is_hit": True,
                })

        # 3. Check เจาะ 2 ตัวเด่น (ไป-กลับ)
        pairs = pred.get("pairs", [])
        pair_hits = []
        for p in pairs:
            p_clean = p.strip()
            if len(p_clean) != 2:
                continue
            rev_p = p_clean[::-1]
            if top2 in (p_clean, rev_p):
                pair_hits.append(f"{p_clean} บน (ออก {top2})")
            if bot2 in (p_clean, rev_p):
                pair_hits.append(f"{p_clean} ล่าง (ออก {bot2})")
        if pair_hits:
            hits.append({
                "category": "🎲 เจาะ 2 ตัวเด่น",
                "detail": f"เจาะแตก {' • '.join(pair_hits)}",
                "is_hit": True,
            })

        # 4. Check ชุด 3 ตัวตรง - โต๊ด
        triplets = pred.get("triplets", [])
        triplet_hits = []
        top3_sorted = "".join(sorted(top3))
        for t in triplets:
            t_clean = t.strip()
            if len(t_clean) != 3:
                continue
            if t_clean == top3:
                triplet_hits.append(f"{t_clean} 👑 ตรงๆ เต็มคาราเบล!")
            elif "".join(sorted(t_clean)) == top3_sorted:
                triplet_hits.append(f"{t_clean} ⭐ โต๊ดแตก!")
        if triplet_hits:
            hits.append({
                "category": "👑 ชุด 3 ตัวตรง-โต๊ด",
                "detail": " • ".join(triplet_hits),
                "is_hit": True,
            })

        is_win = len(hits) > 0
        return is_win, hits

    def resolve_pending_bills(
        self,
        lottery_name: str,
        top3: str,
        bottom2: str,
        target_date: Optional[date] = None,
    ) -> List[Dict[str, Any]]:
        """Find pending bills for this lottery, evaluate them, update 100-bill rolling FIFO, and return outcomes."""
        t_date = target_date or datetime.now(TZ).date()
        date_str = t_date.isoformat()

        all_bills = self.load_pending_bills()
        remaining_bills = []
        matched_outcomes = []

        rolling_history = self.load_rolling_bills()

        for b in all_bills:
            b_name = b.get("lottery_name", "")
            b_date = b.get("date", "")
            name_match = is_same_lottery(b_name, lottery_name)
            if name_match and b_date == date_str and b.get("status") == "pending":
                is_win, hits = self.evaluate_bill(b, top3, bottom2)
                b["status"] = "resolved"
                b["is_win"] = is_win
                b["top3"] = top3
                b["bottom2"] = bottom2
                b["resolved_at"] = datetime.now(TZ).strftime("%H:%M:%S")
                b["hits"] = hits

                # Add to rolling window (FIFO max 100)
                record_item = {
                    "bill_id": b.get("id"),
                    "lottery_name": b_name,
                    "flag": b.get("flag", "🎯"),
                    "date": b_date,
                    "time": b["resolved_at"],
                    "is_win": is_win,
                    "top3": top3,
                    "bottom2": bottom2,
                    "hits_summary": [h["detail"] for h in hits] if is_win else ["ไม่เข้าเป้า"],
                }
                rolling_history.append(record_item)
                if len(rolling_history) > MAX_ROLLING_BILLS:
                    popped = rolling_history.pop(0)
                    logger.info("Rolling 100 window full: dropped oldest bill %s", popped.get("bill_id"))

                matched_outcomes.append(b)
            else:
                remaining_bills.append(b)

        if matched_outcomes:
            self.save_pending_bills(remaining_bills)
            self.save_rolling_bills(rolling_history)
            logger.info("Resolved %d bills for '%s' (WinRate updated)", len(matched_outcomes), lottery_name)

        return matched_outcomes

    def build_bill_result_flex(
        self,
        bill: Dict[str, Any],
        stats: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Build Flex Message announcing the evaluation of a requested bill."""
        lottery_name = bill.get("lottery_name", "")
        flag = bill.get("flag", "🎯")
        top3 = bill.get("top3", "")
        bottom2 = bill.get("bottom2", "")
        is_win = bill.get("is_win", False)
        hits = bill.get("hits", [])

        badge_text = "🎉 บิลนี้เข้าเป้า (WIN)" if is_win else "❌ บิลนี้หลุด (LOSE)"

        hit_box_contents = []
        if is_win:
            for h in hits:
                hit_box_contents.append({
                    "type": "box",
                    "layout": "vertical",
                    "backgroundColor": "#1E293B",
                    "cornerRadius": "10px",
                    "paddingAll": "10px",
                    "margin": "sm",
                    "contents": [
                        {"type": "text", "text": h["category"], "color": "#FBBF24", "size": "xs", "weight": "bold"},
                        {"type": "text", "text": f"✅ {h['detail']}", "color": "#34D399", "size": "sm", "weight": "bold", "wrap": True, "margin": "xs"}
                    ]
                })
        else:
            hit_box_contents.append({
                "type": "box",
                "layout": "vertical",
                "backgroundColor": "#1E293B",
                "cornerRadius": "10px",
                "paddingAll": "10px",
                "margin": "sm",
                "contents": [
                    {"type": "text", "text": "ผลการคำนวณบิลนี้", "color": "#94A3B8", "size": "xs"},
                    {"type": "text", "text": "⚠️ งวดนี้เลขหลุด ไม่ตรงกับผลรางวัล", "color": "#F87171", "size": "sm", "weight": "bold", "margin": "xs"}
                ]
            })

        flex_dict = {
            "type": "bubble",
            "size": "mega",
            "header": {
                "type": "box",
                "layout": "vertical",
                "backgroundColor": "#0F172A",
                "paddingAll": "16px",
                "contents": [
                    {
                        "type": "box",
                        "layout": "horizontal",
                        "contents": [
                            {"type": "text", "text": "📋 สรุปผลบิลที่ขอ", "color": "#38BDF8", "size": "sm", "weight": "bold", "flex": 1},
                            {"type": "text", "text": badge_text, "color": "#34D399" if is_win else "#F87171", "size": "xs", "weight": "bold", "align": "end"}
                        ]
                    },
                    {
                        "type": "text",
                        "text": f"{flag} {lottery_name}",
                        "weight": "bold",
                        "size": "xl",
                        "color": "#FFFFFF",
                        "margin": "sm"
                    }
                ]
            },
            "body": {
                "type": "box",
                "layout": "vertical",
                "backgroundColor": "#0F172A",
                "paddingAll": "16px",
                "paddingTop": "0px",
                "contents": [
                    {
                        "type": "box",
                        "layout": "horizontal",
                        "backgroundColor": "#1E293B",
                        "cornerRadius": "12px",
                        "paddingAll": "12px",
                        "contents": [
                            {
                                "type": "box",
                                "layout": "vertical",
                                "alignItems": "center",
                                "contents": [
                                    {"type": "text", "text": "3 ตัวบน", "color": "#94A3B8", "size": "xs"},
                                    {"type": "text", "text": top3, "color": "#F8FAFC", "size": "xl", "weight": "bold", "margin": "xs"}
                                ]
                            },
                            {
                                "type": "separator",
                                "color": "#334155"
                            },
                            {
                                "type": "box",
                                "layout": "vertical",
                                "alignItems": "center",
                                "contents": [
                                    {"type": "text", "text": "2 ตัวล่าง", "color": "#94A3B8", "size": "xs"},
                                    {"type": "text", "text": bottom2, "color": "#38BDF8", "size": "xl", "weight": "bold", "margin": "xs"}
                                ]
                            }
                        ]
                    },
                    {
                        "type": "box",
                        "layout": "vertical",
                        "margin": "md",
                        "contents": hit_box_contents
                    },
                    {
                        "type": "box",
                        "layout": "horizontal",
                        "backgroundColor": "#1E1B4B",
                        "borderColor": "#6366F1",
                        "borderWidth": "1px",
                        "cornerRadius": "10px",
                        "paddingAll": "10px",
                        "margin": "md",
                        "contents": [
                            {"type": "text", "text": "📊 วินเรทบอทสะสม (100 ใบล่าสุด)", "color": "#C7D2FE", "size": "xs", "weight": "bold", "flex": 1},
                            {"type": "text", "text": f"{stats['winrate_pct']}% ({stats['wins']}/{stats['total']})", "color": "#38BDF8", "size": "xs", "weight": "bold", "align": "end"}
                        ]
                    }
                ]
            }
        }

        return {
            "type": "flex",
            "altText": f"📋 สรุปผลบิลที่ขอ {lottery_name}: {badge_text} (บน {top3} ล่าง {bottom2})",
            "contents": flex_dict
        }

    def build_winrate_flex(self) -> Dict[str, Any]:
        """Build dedicated Win Rate summary card when user asks for 'ขอวินเรท'."""
        stats = self.get_winrate_stats()
        total = stats["total"]
        wins = stats["wins"]
        losses = stats["losses"]
        pct = stats["winrate_pct"]
        streak = stats["streak"]
        history = stats["history"]

        if pct >= 80:
            status_desc = "🔥 ฟอร์มกำลังร้อนแรง แม่นยำสูงมาก"
        elif pct >= 60:
            status_desc = "⚡ ผลงานมาตรฐาน สถิติดีต่อเนื่อง"
        else:
            status_desc = "📈 กำลังสะสมสถิติเพิ่มเติม"

        history_items = []
        if history:
            for b in reversed(history[:6]):
                is_w = b.get("is_win", False)
                icon = "✅ เข้า" if is_w else "❌ หลุด"
                color = "#34D399" if is_w else "#F87171"
                history_items.append({
                    "type": "box",
                    "layout": "horizontal",
                    "margin": "sm",
                    "contents": [
                        {"type": "text", "text": f"{b.get('flag', '')} {b.get('lottery_name', '')}", "color": "#CBD5E1", "size": "xs", "flex": 3},
                        {"type": "text", "text": f"{b.get('top3', '')}-{b.get('bottom2', '')}", "color": "#94A3B8", "size": "xs", "flex": 2},
                        {"type": "text", "text": icon, "color": color, "size": "xs", "weight": "bold", "align": "end", "flex": 2}
                    ]
                })
        else:
            history_items.append({
                "type": "text",
                "text": "เริ่มนับบิลแรกเมื่อมีสมาชิกขอแนวทางและหวยออกผลครับ",
                "color": "#94A3B8",
                "size": "xs",
                "wrap": True
            })

        flex_dict = {
            "type": "bubble",
            "size": "mega",
            "header": {
                "type": "box",
                "layout": "vertical",
                "backgroundColor": "#0F172A",
                "paddingAll": "20px",
                "contents": [
                    {
                        "type": "box",
                        "layout": "horizontal",
                        "contents": [
                            {"type": "text", "text": "🪐 แอดBaras 🛸", "color": "#38BDF8", "size": "sm", "weight": "bold", "flex": 1},
                            {"type": "text", "text": "ระบบตรวจผล 100 ใบ", "color": "#FBBF24", "size": "xs", "align": "end", "weight": "bold"}
                        ]
                    },
                    {
                        "type": "text",
                        "text": "📊 สถิติวินเรทบอท (Win Rate)",
                        "weight": "bold",
                        "size": "xl",
                        "color": "#FFFFFF",
                        "margin": "md"
                    },
                    {
                        "type": "text",
                        "text": status_desc,
                        "color": "#94A3B8",
                        "size": "xs",
                        "margin": "xs"
                    }
                ]
            },
            "body": {
                "type": "box",
                "layout": "vertical",
                "backgroundColor": "#0F172A",
                "paddingAll": "20px",
                "paddingTop": "0px",
                "contents": [
                    {
                        "type": "box",
                        "layout": "vertical",
                        "backgroundColor": "#1E293B",
                        "cornerRadius": "16px",
                        "paddingAll": "16px",
                        "alignItems": "center",
                        "contents": [
                            {"type": "text", "text": "อัตราการเข้าเป้าสะสม (Rolling Window)", "color": "#94A3B8", "size": "xs"},
                            {
                                "type": "box",
                                "layout": "horizontal",
                                "alignItems": "baseline",
                                "margin": "sm",
                                "contents": [
                                    {"type": "text", "text": f"{pct}", "color": "#38BDF8", "size": "4xl", "weight": "bold"},
                                    {"type": "text", "text": "%", "color": "#38BDF8", "size": "xl", "weight": "bold", "margin": "xs"}
                                ]
                            },
                            {"type": "text", "text": f"คิดจาก {total} ใบล่าสุด (สูงสุด {MAX_ROLLING_BILLS} ใบ)", "color": "#CBD5E1", "size": "xs", "margin": "xs"}
                        ]
                    },
                    {
                        "type": "box",
                        "layout": "horizontal",
                        "margin": "md",
                        "spacing": "md",
                        "contents": [
                            {
                                "type": "box",
                                "layout": "vertical",
                                "backgroundColor": "#064E3B",
                                "cornerRadius": "12px",
                                "paddingAll": "12px",
                                "alignItems": "center",
                                "flex": 1,
                                "contents": [
                                    {"type": "text", "text": "🏆 ชนะ (เข้าเป้า)", "color": "#6EE7B7", "size": "xxs"},
                                    {"type": "text", "text": f"{wins} ใบ", "color": "#A7F3D0", "size": "lg", "weight": "bold", "margin": "xs"}
                                ]
                            },
                            {
                                "type": "box",
                                "layout": "vertical",
                                "backgroundColor": "#7F1D1D",
                                "cornerRadius": "12px",
                                "paddingAll": "12px",
                                "alignItems": "center",
                                "flex": 1,
                                "contents": [
                                    {"type": "text", "text": "❌ แพ้ (หลุด)", "color": "#FCA5A5", "size": "xxs"},
                                    {"type": "text", "text": f"{losses} ใบ", "color": "#FECACA", "size": "lg", "weight": "bold", "margin": "xs"}
                                ]
                            },
                            {
                                "type": "box",
                                "layout": "vertical",
                                "backgroundColor": "#1E1B4B",
                                "cornerRadius": "12px",
                                "paddingAll": "12px",
                                "alignItems": "center",
                                "flex": 1,
                                "contents": [
                                    {"type": "text", "text": "🔥 ชนะติดกัน", "color": "#C7D2FE", "size": "xxs"},
                                    {"type": "text", "text": f"{streak} นัด", "color": "#E0E7FF", "size": "lg", "weight": "bold", "margin": "xs"}
                                ]
                            }
                        ]
                    },
                    {
                        "type": "box",
                        "layout": "vertical",
                        "backgroundColor": "#1E293B",
                        "cornerRadius": "12px",
                        "paddingAll": "12px",
                        "margin": "md",
                        "contents": [
                            {"type": "text", "text": "📜 บิลที่สมาชิกล่าสุด", "color": "#FBBF24", "size": "xs", "weight": "bold", "margin": "none"},
                            {"type": "separator", "color": "#334155", "margin": "sm"},
                            *history_items
                        ]
                    }
                ]
            }
        }

        return {
            "type": "flex",
            "altText": f"📊 สถิติวินเรทบอทปัจจุบัน: {pct}% (ชนะ {wins} / แพ้ {losses} จาก {total} ใบล่าสุด)",
            "contents": flex_dict
        }

    def check_and_send_bill_outcomes(
        self,
        lottery_name: str,
        top3: str,
        bottom2: str,
        sender: Any = None,
        target_date: Optional[date] = None,
    ) -> List[Dict[str, Any]]:
        """Evaluate any pending bills for this lottery and push outcome Flex card to LINE group."""
        try:
            resolved_bills = self.resolve_pending_bills(lottery_name, top3, bottom2, target_date=target_date)
            if not resolved_bills:
                return []

            stats = self.get_winrate_stats()
            from predictor_bot import PredictorBot
            pbot = PredictorBot(group_id_path="data/predictor_group_id.txt")
            candidate_tokens = []
            try:
                candidate_tokens.append(pbot.get_token())
            except Exception:
                pass
            if sender and hasattr(sender, "bot_chain"):
                for b in sender.bot_chain:
                    tok = b.get("token")
                    if tok and tok not in candidate_tokens:
                        candidate_tokens.append(tok)

            for b in resolved_bills:
                flex_card = self.build_bill_result_flex(b, stats)
                target_gid = b.get("group_id") or pbot.get_group_id()
                if not target_gid:
                    try:
                        with open("data/last_captured_group.txt", "r", encoding="utf-8") as f:
                            target_gid = f.read().strip()
                    except Exception:
                        pass

                if target_gid and candidate_tokens:
                    for tok in candidate_tokens:
                        try:
                            res = requests.post(
                                "https://api.line.me/v2/bot/message/push",
                                headers={"Authorization": f"Bearer {tok}", "Content-Type": "application/json"},
                                json={"to": target_gid, "messages": [flex_card]},
                                timeout=10
                            )
                            if res.status_code == 200:
                                logger.info("Successfully pushed bill result card for %s to %s", lottery_name, target_gid)
                                break
                        except Exception as pe:
                            logger.warning("Failed pushing bill outcome: %s", pe)

            return resolved_bills
        except Exception as exc:
            logger.warning("Error in check_and_send_bill_outcomes for %s: %s", lottery_name, exc)
            return []


winrate_mgr = WinRateManager()
