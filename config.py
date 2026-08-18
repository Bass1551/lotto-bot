# -*- coding: utf-8 -*-
"""
config.py
กำหนดค่าคงที่, โหลด environment variables และรายชื่อหวยทั้งหมด
"""
import os
from dotenv import load_dotenv

load_dotenv()

# ---------- LINE Messaging API ----------
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "")
LINE_GROUP_ID = os.getenv("LINE_GROUP_ID", "")

if not LINE_CHANNEL_ACCESS_TOKEN or not LINE_GROUP_ID:
    raise RuntimeError(
        "กรุณาตั้งค่า LINE_CHANNEL_ACCESS_TOKEN และ LINE_GROUP_ID ในไฟล์ .env ก่อนรันโปรแกรม"
    )

# ---------- ไฟล์เก็บสถานะกันส่งซ้ำ ----------
SENT_LOG_PATH = os.getenv("SENT_LOG_PATH", "data/sent_log.json")

# ---------- ตั้งค่าการเช็คผลซ้ำ ----------
CHECK_INTERVAL_SECONDS = int(os.getenv("CHECK_INTERVAL_SECONDS", "30"))
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "10"))
REQUEST_RETRY = int(os.getenv("REQUEST_RETRY", "3"))

# ---------- ธง (emoji) และชื่อหวย ----------
# key: รหัสภายในของแต่ละหวย (ใช้เป็นชื่อ log / ชื่อฟังก์ชัน scraper)
# name: ชื่อที่จะแสดงในข้อความ LINE
# flag: อิโมจิหน้าชื่อ (ปรับได้ตามชอบ)
# schedule_time: เวลาที่คาดว่าผลจะออก (HH:MM) ใช้เป็นตัวช่วยตั้ง schedule เช็คถี่ช่วงใกล้เวลาออกผล
#                (ระบบยังคง poll ทุก ๆ CHECK_INTERVAL_SECONDS ตลอดวัน แต่ค่านี้ไว้ใช้ทำ log/แจ้งเตือนเพิ่มเติมได้)

DAILY_LOTTOS = [
    {"key": "laos_extra",        "name": "ลาว Extra",         "flag": "🇱🇦", "schedule_time": "08:30"},
    {"key": "hanoi_asean",       "name": "ฮานอยอาเซียน",       "flag": "🇻🇳", "schedule_time": "09:30"},
    {"key": "nikkei_morning",    "name": "นิเคอิเช้า",         "flag": "🇯🇵", "schedule_time": "09:30"},
    {"key": "china_morning",     "name": "จีนเช้า",           "flag": "🇨🇳", "schedule_time": "10:30"},
    {"key": "laos_tv",           "name": "ลาว TV",             "flag": "🇱🇦", "schedule_time": "10:30"},
    {"key": "hangseng_morning",  "name": "ฮั่งเส็งเช้า",       "flag": "🇭🇰", "schedule_time": "11:06"},
    {"key": "hanoi_hd",          "name": "ฮานอย HD",           "flag": "🇻🇳", "schedule_time": "11:30"},
    {"key": "hanoi_star",        "name": "ฮานอย Star",         "flag": "🇻🇳", "schedule_time": "12:30"},
    {"key": "taiwan",            "name": "ไต้หวัน",             "flag": "🇹🇼", "schedule_time": "12:34"},
    {"key": "korea",             "name": "หุ้นเกาหลี",          "flag": "🇰🇷", "schedule_time": "13:30"},
    {"key": "nikkei_afternoon",  "name": "นิเคอิบ่าย",         "flag": "🇯🇵", "schedule_time": "13:00"},
    {"key": "laos_hd",           "name": "ลาว HD",             "flag": "🇱🇦", "schedule_time": "13:45"},
    {"key": "china_afternoon",   "name": "จีนบ่าย",            "flag": "🇨🇳", "schedule_time": "14:00"},
    {"key": "hanoi_tv",          "name": "ฮานอย TV",           "flag": "🇻🇳", "schedule_time": "14:30"},
    {"key": "hangseng_afternoon","name": "ฮั่งเส็งบ่าย",       "flag": "🇭🇰", "schedule_time": "15:10"},
    {"key": "laos_star",         "name": "ลาว Star",           "flag": "🇱🇦", "schedule_time": "15:45"},
    {"key": "singapore",         "name": "หุ้นสิงคโปร์",        "flag": "🇸🇬", "schedule_time": "16:25"},
    {"key": "hanoi_kachad",      "name": "ฮานอย กาชาด",       "flag": "🇻🇳", "schedule_time": "16:30"},
    {"key": "thai_evening",      "name": "หุ้นไทยเย็น",       "flag": "🇹🇭", "schedule_time": "16:40"},
]

NORMAL_STOCK_LOTTOS = []  # ปัจจุบันรวมอยู่ใน DAILY_LOTTOS แล้วตามที่ระบุ (หวยรายวัน+หุ้นปกติ = list เดียวกันในวันจันทร์-ศุกร์)

VIP_STOCK_LOTTOS = [
    {"key": "nikkei_morning_vip",   "name": "นิเคอิเช้า VIP",   "flag": "🇯🇵", "schedule_time": "11:30"},
    {"key": "china_morning_vip",    "name": "จีนเช้า VIP",      "flag": "🇨🇳", "schedule_time": "11:35"},
    {"key": "hangseng_morning_vip", "name": "ฮั่งเส็งเช้า VIP",  "flag": "🇭🇰", "schedule_time": "12:15"},
    {"key": "taiwan_vip",           "name": "ไต้หวัน VIP",       "flag": "🇹🇼", "schedule_time": "14:10"},
    {"key": "korea_vip",            "name": "เกาหลี VIP",       "flag": "🇰🇷", "schedule_time": "14:30"},
    {"key": "nikkei_afternoon_vip", "name": "นิเคอิบ่าย VIP",   "flag": "🇯🇵", "schedule_time": "14:45"},
    {"key": "china_afternoon_vip",  "name": "จีนบ่าย VIP",      "flag": "🇨🇳", "schedule_time": "15:15"},
    {"key": "hangseng_afternoon_vip","name": "ฮั่งเส็งบ่าย VIP", "flag": "🇭🇰", "schedule_time": "16:00"},
]


def get_today_lotto_list(weekday: int):
    """
    weekday: 0=จันทร์ ... 5=เสาร์, 6=อาทิตย์ (ตาม datetime.weekday())
    คืนค่ารายการหวยที่ต้องเช็คผลของวันนั้น ๆ ตามกติกา:
      - จันทร์-ศุกร์ (0-4): หวยรายวัน (DAILY_LOTTOS)
      - เสาร์-อาทิตย์ (5-6): หวยรายวัน + หุ้นวีไอพี
    """
    if weekday in (5, 6):
        return DAILY_LOTTOS + VIP_STOCK_LOTTOS
    return DAILY_LOTTOS
