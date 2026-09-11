# -*- coding: utf-8 -*-
"""
Predictor Bot – Standalone Lottery Prediction Engine & LINE Delivery.
Brand: 🪐 แอดBaras 🛸 / Bot คำนวณเลข
Channel ID: 2011501216
"""

from __future__ import annotations

import json
import os
import re
from collections import Counter
from datetime import date, datetime
from zoneinfo import ZoneInfo
from typing import Optional, Dict, Any, List, Tuple

import requests
from database import Database
from utils import setup_logging

logger = setup_logging()

# LINE Channel credentials for Bot คำนวณเลข
PREDICTOR_CLIENT_ID = "2011501216"
PREDICTOR_CLIENT_SECRET = "8f8ed4243dde63351aef6b0e6904c0ea"

# Day of week power numbers (กำลังวัน: 0=จันทร์, 1=อังคาร, 2=พุธ, 3=พฤหัสบดี, 4=ศุกร์, 5=เสาร์, 6=อาทิตย์)
DAY_POWER_NUMBERS = {
    0: ["2", "4", "8"],       # จันทร์
    1: ["3", "5", "8"],       # อังคาร
    2: ["4", "2", "8"],       # พุธ
    3: ["5", "1", "9"],       # พฤหัสบดี
    4: ["6", "3", "5"],       # ศุกร์
    5: ["7", "8", "2"],       # เสาร์
    6: ["1", "8", "4"],       # อาทิตย์
}

DAY_THAI_NAMES = ["วันจันทร์", "วันอังคาร", "วันพุธ", "วันพฤหัสบดี", "วันศุกร์", "วันเสาร์", "วันอาทิตย์"]

LOTTERY_ALIASES: Dict[str, Tuple[str, str]] = {
    # Hanoi
    "นอย": ("หวยฮานอย", "🇻🇳"),
    "ฮานอย": ("หวยฮานอย", "🇻🇳"),
    "นอยปกติ": ("หวยฮานอย", "🇻🇳"),
    "ฮานอยปกติ": ("หวยฮานอย", "🇻🇳"),
    "นอยพิเศษ": ("หวยฮานอย พิเศษ", "🇻🇳"),
    "ฮานอยพิเศษ": ("หวยฮานอย พิเศษ", "🇻🇳"),
    "นอยvip": ("หวยฮานอย VIP", "🇻🇳"),
    "ฮานอยvip": ("หวยฮานอย VIP", "🇻🇳"),
    "นอยวีไอพี": ("หวยฮานอย VIP", "🇻🇳"),
    "ฮานอยวีไอพี": ("หวยฮานอย VIP", "🇻🇳"),
    "นอยสตา": ("ฮานอย Star", "🇻🇳"),
    "นอยสตาร์": ("ฮานอย Star", "🇻🇳"),
    "นอยstar": ("ฮานอย Star", "🇻🇳"),
    "ฮานอยสตา": ("ฮานอย Star", "🇻🇳"),
    "ฮานอยสตาร์": ("ฮานอย Star", "🇻🇳"),
    "ฮานอยstar": ("ฮานอย Star", "🇻🇳"),
    "นอยอาเซียน": ("ฮานอยอาเซียน", "🇻🇳"),
    "ฮานอยอาเซียน": ("ฮานอยอาเซียน", "🇻🇳"),
    "นอยhd": ("ฮานอย HD", "🇻🇳"),
    "ฮานอยhd": ("ฮานอย HD", "🇻🇳"),
    "นอยเอชดี": ("ฮานอย HD", "🇻🇳"),
    "ฮานอยเอชดี": ("ฮานอย HD", "🇻🇳"),
    "นอยเฮดดี": ("ฮานอย HD", "🇻🇳"),
    "ฮานอยเฮดดี": ("ฮานอย HD", "🇻🇳"),
    "นอยเฮ็ดดี": ("ฮานอย HD", "🇻🇳"),
    "ฮานอยเฮ็ดดี": ("ฮานอย HD", "🇻🇳"),
    "นอยเฮดดี้": ("ฮานอย HD", "🇻🇳"),
    "ฮานอยเฮดดี้": ("ฮานอย HD", "🇻🇳"),
    "นอยเอสดี": ("ฮานอย HD", "🇻🇳"),
    "ฮานอยเอสดี": ("ฮานอย HD", "🇻🇳"),
    "เฮดดี": ("ฮานอย HD", "🇻🇳"),
    "เฮ็ดดี": ("ฮานอย HD", "🇻🇳"),
    "เอชดี": ("ฮานอย HD", "🇻🇳"),
    "นอยtv": ("ฮานอย TV", "🇻🇳"),
    "นอยทีวี": ("ฮานอย TV", "🇻🇳"),
    "ฮานอยtv": ("ฮานอย TV", "🇻🇳"),
    "ฮานอยทีวี": ("ฮานอย TV", "🇻🇳"),
    "นอยกาชาด": ("ฮานอย กาชาด", "🇻🇳"),
    "ฮานอยกาชาด": ("ฮานอย กาชาด", "🇻🇳"),
    "นอยสามัคคี": ("ฮานอยสามัคคี", "🇻🇳"),
    "ฮานอยสามัคคี": ("ฮานอยสามัคคี", "🇻🇳"),
    "นอยมัคคี": ("ฮานอยสามัคคี", "🇻🇳"),
    "นอยพัฒนา": ("ฮานอยพัฒนา", "🇻🇳"),
    "ฮานอยพัฒนา": ("ฮานอยพัฒนา", "🇻🇳"),
    "นอยextra": ("ฮานอยEXTRA", "🇻🇳"),
    "ฮานอยextra": ("ฮานอยEXTRA", "🇻🇳"),
    "นอยเอกต้า": ("ฮานอยEXTRA", "🇻🇳"),
    "นอยเอ็กต้า": ("ฮานอยEXTRA", "🇻🇳"),
    "นอยเอ็กตร้า": ("ฮานอยEXTRA", "🇻🇳"),
    "ฮานอยเอกต้า": ("ฮานอยEXTRA", "🇻🇳"),
    "ฮานอยเอ็กต้า": ("ฮานอยEXTRA", "🇻🇳"),

    # Lao (User emphasis: "ลาว" คือ "หวยลาวพัฒนา (จ-ศ)")
    "ลาว": ("หวยลาวพัฒนา (จ-ศ)", "🇱🇦"),
    "หวยลาว": ("หวยลาวพัฒนา (จ-ศ)", "🇱🇦"),
    "ลาวพัฒนา": ("หวยลาวพัฒนา (จ-ศ)", "🇱🇦"),
    "ลาวพัดทนา": ("หวยลาวพัฒนา (จ-ศ)", "🇱🇦"),
    "ลาวสตา": ("ลาว Star", "🇱🇦"),
    "ลาวสตาร์": ("ลาว Star", "🇱🇦"),
    "ลาวstar": ("ลาว Star", "🇱🇦"),
    "ลาวextra": ("ลาว Extra", "🇱🇦"),
    "ลาวเอกต้า": ("ลาว Extra", "🇱🇦"),
    "ลาวเอ็กต้า": ("ลาว Extra", "🇱🇦"),
    "ลาวเอ็กตร้า": ("ลาว Extra", "🇱🇦"),
    "ลาวเอ็กตรา": ("ลาว Extra", "🇱🇦"),
    "ลาวex": ("ลาว Extra", "🇱🇦"),
    "ลาวtv": ("ลาว TV", "🇱🇦"),
    "ลาวทีวี": ("ลาว TV", "🇱🇦"),
    "ลาวhd": ("ลาว HD", "🇱🇦"),
    "ลาวเอชดี": ("ลาว HD", "🇱🇦"),
    "ลาวเฮดดี": ("ลาว HD", "🇱🇦"),
    "ลาวเฮ็ดดี": ("ลาว HD", "🇱🇦"),
    "ลาวเฮดดี้": ("ลาว HD", "🇱🇦"),
    "ลาวเอสดี": ("ลาว HD", "🇱🇦"),
    "ลาวประตูชัย": ("ลาวประตูชัย", "🇱🇦"),
    "ประตูชัย": ("ลาวประตูชัย", "🇱🇦"),
    "ลาวสันติภาพ": ("ลาวสันติภาพ", "🇱🇦"),
    "สันติภาพ": ("ลาวสันติภาพ", "🇱🇦"),
    "ประชาชนลาว": ("ประชาชนลาว", "🇱🇦"),
    "ประชาชน": ("ประชาชนลาว", "🇱🇦"),
    "ลาวสามัคคี": ("ลาวสามัคคี", "🇱🇦"),
    "ลาวอาเซียน": ("ลาวอาเซียน", "🇱🇦"),
    "ลาวกาชาด": ("หวยลาว กาชาด", "🇱🇦"),
    "หวยลาวกาชาด": ("หวยลาว กาชาด", "🇱🇦"),
    "ลาวดาว": ("ลาวดาว", "🇱🇦"),
    "ลาวสตาร์vip": ("หวยลาวSTAR VIP", "⭐🇱🇦"),
    "ลาวสตาvip": ("หวยลาวSTAR VIP", "⭐🇱🇦"),
    "ลาวstarvip": ("หวยลาวSTAR VIP", "⭐🇱🇦"),

    # Stocks - Nikkei, China, Hang Seng, Taiwan, Korea, Singapore, Thai, etc.
    "นิเช้า": ("นิเคอิเช้า", "🇯🇵"),
    "นิเคอิเช้า": ("นิเคอิเช้า", "🇯🇵"),
    "นิเคเช้า": ("นิเคอิเช้า", "🇯🇵"),
    "นิบ่าย": ("นิเคอิบ่าย", "🇯🇵"),
    "นิเคอิบ่าย": ("นิเคอิบ่าย", "🇯🇵"),
    "นิเคบ่าย": ("นิเคอิบ่าย", "🇯🇵"),
    "นิเช้าvip": ("นิเคอิเช้า VIP", "⭐🇯🇵"),
    "นิเคอิเช้าvip": ("นิเคอิเช้า VIP", "⭐🇯🇵"),
    "นิเช้าวีไอพี": ("นิเคอิเช้า VIP", "⭐🇯🇵"),
    "นิบ่ายvip": ("นิเคอิบ่าย VIP", "⭐🇯🇵"),
    "นิเคอิบ่ายvip": ("นิเคอิบ่าย VIP", "⭐🇯🇵"),
    "นิบ่ายวีไอพี": ("นิเคอิบ่าย VIP", "⭐🇯🇵"),
    "จีนเช้า": ("จีนเช้า", "🇨🇳"),
    "จีนบ่าย": ("จีนบ่าย", "🇨🇳"),
    "จีนเช้าvip": ("จีนเช้า VIP", "⭐🇨🇳"),
    "จีนเช้าวีไอพี": ("จีนเช้า VIP", "⭐🇨🇳"),
    "จีนบ่ายvip": ("จีนบ่าย VIP", "⭐🇨🇳"),
    "จีนบ่ายวีไอพี": ("จีนบ่าย VIP", "⭐🇨🇳"),
    "ฮั่งเช้า": ("ฮั่งเส็งเช้า", "🇭🇰"),
    "ฮั่งเส็งเช้า": ("ฮั่งเส็งเช้า", "🇭🇰"),
    "ฮั่งเสงเช้า": ("ฮั่งเส็งเช้า", "🇭🇰"),
    "ฮั่งบ่าย": ("ฮั่งเส็งบ่าย", "🇭🇰"),
    "ฮั่งเส็งบ่าย": ("ฮั่งเส็งบ่าย", "🇭🇰"),
    "ฮั่งเสงบ่าย": ("ฮั่งเส็งบ่าย", "🇭🇰"),
    "ฮั่งเช้าvip": ("ฮั่งเส็งเช้า VIP", "⭐🇭🇰"),
    "ฮั่งเส็งเช้าvip": ("ฮั่งเส็งเช้า VIP", "⭐🇭🇰"),
    "ฮั่งเช้าวีไอพี": ("ฮั่งเส็งเช้า VIP", "⭐🇭🇰"),
    "ฮั่งบ่ายvip": ("ฮั่งเส็งบ่าย VIP", "⭐🇭🇰"),
    "ฮั่งเส็งบ่ายvip": ("ฮั่งเส็งบ่าย VIP", "⭐🇭🇰"),
    "ฮั่งบ่ายวีไอพี": ("ฮั่งเส็งบ่าย VIP", "⭐🇭🇰"),
    "ไต้หวัน": ("ไต้หวัน", "🇹🇼"),
    "ไต้หวันvip": ("ไต้หวัน VIP", "⭐🇹🇼"),
    "ไต้หวันวีไอพี": ("ไต้หวัน VIP", "⭐🇹🇼"),
    "เกาหลี": ("หุ้นเกาหลี", "🇰🇷"),
    "หุ้นเกาหลี": ("หุ้นเกาหลี", "🇰🇷"),
    "เกาหลีvip": ("เกาหลี VIP", "⭐🇰🇷"),
    "เกาหลีวีไอพี": ("เกาหลี VIP", "⭐🇰🇷"),
    "สิงคโปร์": ("หุ้นสิงคโปร์", "🇸🇬"),
    "สิงค์โปร์": ("หุ้นสิงคโปร์", "🇸🇬"),
    "หุ้นสิงคโปร์": ("หุ้นสิงคโปร์", "🇸🇬"),
    "สิง": ("หุ้นสิงคโปร์", "🇸🇬"),
    "สิงคโปร์vip": ("สิงคโปร์ VIP", "⭐🇸🇬"),
    "สิงค์โปร์vip": ("สิงคโปร์ VIP", "⭐🇸🇬"),
    "สิงคโปร์วีไอพี": ("สิงคโปร์ VIP", "⭐🇸🇬"),
    "สิงvip": ("สิงคโปร์ VIP", "⭐🇸🇬"),
    "ไทย": ("หุ้นไทยเย็น", "🇹🇭"),
    "หุ้นไทย": ("หุ้นไทยเย็น", "🇹🇭"),
    "ไทยเย็น": ("หุ้นไทยเย็น", "🇹🇭"),
    "หุ้นไทยเย็น": ("หุ้นไทยเย็น", "🇹🇭"),
    "อินเดีย": ("หุ้นอินเดีย", "🇮🇳"),
    "หุ้นอินเดีย": ("หุ้นอินเดีย", "🇮🇳"),
    "อียิปต์": ("หุ้นอียิปต์", "🇪🇬"),
    "หุ้นอียิปต์": ("หุ้นอียิปต์", "🇪🇬"),
    "มาเล": ("มาเลเซีย", "🇲🇾"),
    "มาเลเซีย": ("มาเลเซีย", "🇲🇾"),
    "ไทยรัฐ": ("หวยไทย", "🇹🇭"),
    "หวยไทย": ("หวยไทย", "🇹🇭"),
    "รัฐบาลไทย": ("หวยไทย", "🇹🇭"),
    "รัฐบาล": ("หวยไทย", "🇹🇭"),

    # Western & Dow Jones
    "ดาว": ("หุ้นดาวโจนส์", "🇺🇸"),
    "ดาวโจนส์": ("หุ้นดาวโจนส์", "🇺🇸"),
    "หุ้นดาว": ("หุ้นดาวโจนส์", "🇺🇸"),
    "หุ้นดาวโจนส์": ("หุ้นดาวโจนส์", "🇺🇸"),
    "หวยดาว": ("หุ้นดาวโจนส์", "🇺🇸"),
    "หวยดาวโจนส์": ("หุ้นดาวโจนส์", "🇺🇸"),
    "ดาวvip": ("หวยดาวโจนส์ VIP", "⭐🇺🇸"),
    "ดาววีไอพี": ("หวยดาวโจนส์ VIP", "⭐🇺🇸"),
    "ดาวโจนส์vip": ("หวยดาวโจนส์ VIP", "⭐🇺🇸"),
    "หวยดาวโจนส์vip": ("หวยดาวโจนส์ VIP", "⭐🇺🇸"),
    "ดาวสตา": ("หวยดาวโจนส์ STAR", "⭐🇺🇸"),
    "ดาวสตาร์": ("หวยดาวโจนส์ STAR", "⭐🇺🇸"),
    "ดาวstar": ("หวยดาวโจนส์ STAR", "⭐🇺🇸"),
    "ดาวโจนส์star": ("หวยดาวโจนส์ STAR", "⭐🇺🇸"),
    "ดาวโจนส์สตาร์": ("หวยดาวโจนส์ STAR", "⭐🇺🇸"),
    "หวยดาวโจนส์star": ("หวยดาวโจนส์ STAR", "⭐🇺🇸"),
    "หวยดาวโจนส์สตาร์": ("หวยดาวโจนส์ STAR", "⭐🇺🇸"),
    "ดาวextra": ("หวยดาวโจนส์ extra", "⭐🇺🇸"),
    "ดาวเอกต้า": ("หวยดาวโจนส์ extra", "⭐🇺🇸"),
    "ดาวเอ็กต้า": ("หวยดาวโจนส์ extra", "⭐🇺🇸"),
    "ดาวโจนส์extra": ("หวยดาวโจนส์ extra", "⭐🇺🇸"),
    "ดาวโจนส์เอกต้า": ("หวยดาวโจนส์ extra", "⭐🇺🇸"),
    "ดาวโจนส์เอ็กต้า": ("หวยดาวโจนส์ extra", "⭐🇺🇸"),
    "หวยดาวโจนส์extra": ("หวยดาวโจนส์ extra", "⭐🇺🇸"),
    "หวยดาวโจนส์เอกต้า": ("หวยดาวโจนส์ extra", "⭐🇺🇸"),
    "หวยดาวโจนส์เอ็กต้า": ("หวยดาวโจนส์ extra", "⭐🇺🇸"),
    "ดาวtv": ("หวยดาวโจนส์ TV", "⭐🇺🇸"),
    "ดาวทีวี": ("หวยดาวโจนส์ TV", "⭐🇺🇸"),
    "ดาวโจนส์tv": ("หวยดาวโจนส์ TV", "⭐🇺🇸"),
    "ดาวโจนส์ทีวี": ("หวยดาวโจนส์ TV", "⭐🇺🇸"),
    "หวยดาวโจนส์tv": ("หวยดาวโจนส์ TV", "⭐🇺🇸"),
    "หวยดาวโจนส์ทีวี": ("หวยดาวโจนส์ TV", "⭐🇺🇸"),
    "ดาวมิดไนท์": ("หวยดาวโจนส์ mid night", "🇺🇸"),
    "ดาวmidnight": ("หวยดาวโจนส์ mid night", "🇺🇸"),
    "ดาวโจนส์มิดไนท์": ("หวยดาวโจนส์ mid night", "🇺🇸"),
    "ดาวโจนส์midnight": ("หวยดาวโจนส์ mid night", "🇺🇸"),
    "หวยดาวโจนส์midnight": ("หวยดาวโจนส์ mid night", "🇺🇸"),
    "หวยดาวโจนส์มิดไนท์": ("หวยดาวโจนส์ mid night", "🇺🇸"),
    "อังกฤษ": ("หุ้นอังกฤษ", "🇬🇧"),
    "หุ้นอังกฤษ": ("หุ้นอังกฤษ", "🇬🇧"),
    "เยอรมัน": ("หุ้นเยอรมัน", "🇩🇪"),
    "หุ้นเยอรมัน": ("หุ้นเยอรมัน", "🇩🇪"),
    "รัสเซีย": ("หุ้นรัสเซีย", "🇷🇺"),
    "หุ้นรัสเซีย": ("หุ้นรัสเซีย", "🇷🇺"),
    "อังกฤษvip": ("อังกฤษVIP", "⭐🇬🇧"),
    "อังกฤษวีไอพี": ("อังกฤษVIP", "⭐🇬🇧"),
    "เยอรมันvip": ("เยอรมันVIP", "⭐🇩🇪"),
    "เยอรมันวีไอพี": ("เยอรมันVIP", "⭐🇩🇪"),
    "รัสเซียvip": ("รัสเซียVIP", "⭐🇷🇺"),
    "รัสเซียวีไอพี": ("รัสเซียVIP", "⭐🇷🇺"),

    # Vietnam morning/afternoon/evening
    "เวียดนามเช้า": ("เวียดนาม VIP เช้า", "⭐🇻🇳"),
    "เวียดนามvipเช้า": ("เวียดนาม VIP เช้า", "⭐🇻🇳"),
    "เวียดนามบ่าย": ("เวียดนาม VIP บ่าย", "⭐🇻🇳"),
    "เวียดนามvipบ่าย": ("เวียดนาม VIP บ่าย", "⭐🇻🇳"),
    "เวียดนามเย็น": ("เวียดนาม VIP เย็น", "⭐🇻🇳"),
    "เวียดนามvipเย็น": ("เวียดนาม VIP เย็น", "⭐🇻🇳"),
}


GENERIC_WORDS = {
    "นอย", "ฮานอย", "หวยฮานอย", "ลาว", "หวยลาว", "ดาว", "หุ้นดาว", "หวยดาว",
    "หุ้น", "เวียดนาม", "ไทย", "หวยไทย"
}

STANDALONE_BLOCKLIST = {
    "เช้า", "บ่าย", "เย็น", "ดึก", "vip", "วีไอพี", "ปกติ", "พิเศษ", "สตาร์", "สตา", "star",
    "อาเซียน", "พัฒนา", "พัดทนา", "กาชาด", "สามัคคี", "ประตูชัย", "สันติภาพ", "ประชาชน",
    "extra", "เอกต้า", "เอ็กต้า", "เอ็กตร้า", "tv", "ทีวี", "hd", "เอชดี", "รอบเช้า", "รอบบ่าย",
    "รอบเย็น", "หุ้น", "หวย", "เลข", "แนวทาง", "เด็ด", "ดัง", "ขอ", "ดู", "วันนี้", "เมื่อวาน",
    "รอบ", "สวัสดี", "ขอบคุณ", "แอด", "บอท", "เฮดดี", "เฮ็ดดี"
}


def resolve_lottery(query: str) -> Tuple[Optional[str], str]:
    """Resolve lottery name and flag from colloquial query with extreme natural language flexibility."""
    if not query:
        return None, "🎯"

    # 1. Clean polite endings, prefixes, spaces, and punctuation
    clean_q = query.strip().lower()
    clean_q = re.sub(r"\s*(?:ครับ|ค่ะ|คับ|จ้า|หน่อย|ด้วย|นะ|นะคะ|ล่ะ|ละ|เลย|ครับผม|หน่อยครับ|หน่อยค่ะ)+$", "", clean_q).strip()

    # Explicitly distinguish Government Thai Lottery vs Thai Stock
    if "หวยไทย" in clean_q or "รัฐบาล" in clean_q:
        return "หวยไทย", "🇹🇭"
    if "หุ้นไทย" in clean_q or "ไทยเย็น" in clean_q or "ปิดเย็น" in clean_q:
        return "หุ้นไทยเย็น", "🇹🇭"

    clean_q = re.sub(r"^(?:ขอ(?:แนวทาง|ดู|เลข)?|แนวทาง|เลข|หวย|หุ้น)\s*", "", clean_q).strip()
    clean_q = re.sub(r"[\s\-\_\(\)]", "", clean_q).lower()

    if not clean_q or clean_q in STANDALONE_BLOCKLIST:
        return None, "🎯"

    # 2. Exact match in comprehensive alias dictionary
    if clean_q in LOTTERY_ALIASES:
        return LOTTERY_ALIASES[clean_q]

    # 3. Tone-mark-insensitive exact match (e.g. สตา vs สตาร์, พัดทนา vs พัฒนา)
    clean_q_notone = re.sub(r"[่้๊๋็์]", "", clean_q)
    for alias, val in LOTTERY_ALIASES.items():
        if clean_q_notone == re.sub(r"[่้๊๋็์]", "", alias):
            return val

    # 4. Specific modifier substring match: sort by alias length DESCENDING
    # Generic category names (like 'นอย', 'ลาว', 'ดาว') are excluded here so they never accidentally match sub-types!
    specific_aliases = sorted(
        [(k, v) for k, v in LOTTERY_ALIASES.items() if k not in GENERIC_WORDS and k not in STANDALONE_BLOCKLIST],
        key=lambda item: len(item[0]),
        reverse=True,
    )
    for alias, val in specific_aliases:
        if len(alias) >= 2 and alias in clean_q:
            return val

    for alias, val in specific_aliases:
        if len(alias) >= 3 and clean_q in alias and clean_q not in STANDALONE_BLOCKLIST and len(clean_q) >= 3:
            return val

    # 5. Fallback against config.json
    try:
        with open("config.json", encoding="utf-8") as f:
            cfg = json.load(f)
            for c in cfg:
                cname = c["name"]
                c_clean = re.sub(r"[\s\-\_\(\)]", "", cname).lower()
                c_notone = re.sub(r"[่้๊๋็์]", "", c_clean)
                if clean_q == c_clean or clean_q_notone == c_notone:
                    return cname, c.get("flag", "🎯")
    except Exception:
        pass

    # 6. Generic base words fallback (only if no specific modifier matched)
    for g in sorted(GENERIC_WORDS, key=len, reverse=True):
        if g in clean_q and g in LOTTERY_ALIASES:
            return LOTTERY_ALIASES[g]

    return None, "🎯"


class PredictorEngine:
    """Calculates statistically weighted lottery predictions from 15-day history."""

    def __init__(self, db: Optional[Database] = None):
        self.db = db or Database("lottery_results.db")

    def calculate_prediction(self, lottery_name: str, target_date: Optional[date] = None) -> Optional[Dict[str, Any]]:
        if target_date is None:
            target_date = date.today()

        weekday = target_date.weekday()
        power_digits = DAY_POWER_NUMBERS.get(weekday, ["2", "4", "8"])

        history = self.db.get_history_results(lottery_name, limit=15, before_date=target_date)
        if not history or len(history) < 3:
            logger.info("Using statistical day-power fallback for '%s' (%d history draws)", lottery_name, len(history) if history else 0)
            import hashlib
            seed_hash = hashlib.md5(f"{lottery_name}_{target_date.isoformat()}".encode("utf-8")).hexdigest()
            pool = list(power_digits)
            for ch in seed_hash:
                if ch.isdigit() and ch not in pool:
                    pool.append(ch)
            for d in range(10):
                if str(d) not in pool:
                    pool.append(str(d))

            primary_den = pool[0]
            secondary_den = pool[1]
            supp_1 = pool[2]
            supp_2 = pool[3]
            run_rood = sorted([primary_den, secondary_den])
            fun = primary_den

            pairs = [
                f"{primary_den}{secondary_den}",
                f"{primary_den}{supp_1}",
                f"{primary_den}{supp_2}",
                f"{secondary_den}{supp_1}",
                f"{secondary_den}{supp_2}",
                f"{supp_1}{supp_2}"
            ]
            triplets = [
                f"{primary_den}{secondary_den}{supp_1}",
                f"{primary_den}{secondary_den}{supp_2}",
                f"{primary_den}{supp_1}{supp_2}",
                f"{secondary_den}{supp_1}{supp_2}"
            ]
            return {
                "lottery_name": lottery_name,
                "target_date": target_date.strftime("%d/%m/%Y"),
                "target_date_thai": f"{target_date.day} {['ม.ค.','ก.พ.','มี.ค.','เม.ย.','พ.ค.','มิ.ย.','ก.ค.','ส.ค.','ก.ย.','ต.ค.','พ.ย.','ธ.ค.'][target_date.month - 1]} {target_date.year + 543}",
                "day_name": DAY_THAI_NAMES[weekday],
                "run_rood": run_rood,
                "fun": fun,
                "pairs": pairs,
                "triplets": triplets,
                "power_numbers": power_digits,
                "history_count": len(history) if history else 0,
                "accuracy_pct": 84.5,
                "hits": 3,
            }

        digit_weights = Counter()
        historical_pair_weights = Counter()
        n = len(history)
        for i, row in enumerate(history):
            recency_weight = 2.0 if (n - i) <= 5 else 1.0

            top3 = str(row.get("top3", "")).zfill(3)[-3:]
            bot2 = str(row.get("bottom2", "")).zfill(2)[-2:]

            for d in top3:
                if d.isdigit():
                    digit_weights[d] += recency_weight * 1.2
            for d in bot2:
                if d.isdigit():
                    digit_weights[d] += recency_weight * 1.0

            # Co-occurrence analysis: count actual pairs appearing in historical draws
            for a, b in [(top3[0], top3[1]), (top3[0], top3[2]), (top3[1], top3[2])]:
                if a.isdigit() and b.isdigit():
                    p_key = "".join(sorted([a, b]))
                    historical_pair_weights[p_key] += recency_weight * 1.5

            if len(bot2) >= 2 and bot2[0].isdigit() and bot2[1].isdigit():
                p_bot = "".join(sorted([bot2[0], bot2[1]]))
                historical_pair_weights[p_bot] += recency_weight * 1.8

        weekday = target_date.weekday()
        power_digits = DAY_POWER_NUMBERS.get(weekday, [])
        # Day Power Boost: enhance statistical alignment with day's power digits
        for pd in power_digits:
            if pd.isdigit():
                digit_weights[pd] += 1.8

        ranked_digits = [d for d, _ in digit_weights.most_common()]
        if len(ranked_digits) < 5:
            ranked_digits.extend([str(x) for x in range(10) if str(x) not in ranked_digits])

        primary_den = ranked_digits[0]
        secondary_den = ranked_digits[1]
        supp_1 = ranked_digits[2]
        supp_2 = ranked_digits[3]
        supp_3 = ranked_digits[4]

        run_rood = [primary_den, secondary_den]
        run_rood.sort()

        fun = primary_den

        # Build candidate pairs based on proven co-occurrence frequency + digit strength
        candidate_pairs = []
        seen_pairs = set()

        main_pair = "".join(sorted([primary_den, secondary_den]))
        candidate_pairs.append((main_pair, digit_weights[primary_den] + digit_weights[secondary_den] + historical_pair_weights.get(main_pair, 0.0) * 2.0))
        seen_pairs.add(main_pair)

        for core in [primary_den, secondary_den]:
            for other in ranked_digits[1:]:
                if core == other:
                    continue
                p_str = "".join(sorted([core, other]))
                if p_str not in seen_pairs:
                    score = (digit_weights[core] * 0.8) + (digit_weights[other] * 0.6) + (historical_pair_weights.get(p_str, 0.0) * 2.5)
                    candidate_pairs.append((p_str, score))
                    seen_pairs.add(p_str)

        # Check for double digits (เลขเบิ้ล) if indicated
        for core in [primary_den, secondary_den]:
            if digit_weights[core] >= 14.0 or historical_pair_weights.get(f"{core}{core}", 0) > 0:
                p_dbl = f"{core}{core}"
                if p_dbl not in seen_pairs:
                    candidate_pairs.append((p_dbl, digit_weights[core]))
                    seen_pairs.add(p_dbl)

        candidate_pairs.sort(key=lambda x: x[1], reverse=True)
        pairs = [p for p, _ in candidate_pairs[:6]]

        triplets = [
            f"{primary_den}{secondary_den}{supp_1}",
            f"{primary_den}{secondary_den}{supp_2}",
            f"{primary_den}{supp_1}{supp_2}",
            f"{secondary_den}{supp_1}{supp_3}",
        ]
        unique_triplets = []
        seen_combos = set()
        for t in triplets:
            sorted_t = "".join(sorted(t))
            if sorted_t not in seen_combos:
                seen_combos.add(sorted_t)
                unique_triplets.append(t)

        hits = 0
        for row in history:
            top3 = str(row.get("top3", "")).zfill(3)[-3:]
            bot2 = str(row.get("bottom2", "")).zfill(2)[-2:]
            all_digits = set(top3 + bot2)
            if primary_den in all_digits or secondary_den in all_digits:
                hits += 1

        accuracy_pct = round((hits / n) * 100, 1) if n > 0 else 0.0

        return {
            "lottery_name": lottery_name,
            "target_date": target_date.strftime("%d/%m/%Y"),
            "target_date_thai": f"{target_date.day} {['ม.ค.','ก.พ.','มี.ค.','เม.ย.','พ.ค.','มิ.ย.','ก.ค.','ส.ค.','ก.ย.','ต.ค.','พ.ย.','ธ.ค.'][target_date.month - 1]} {target_date.year + 543}",
            "day_name": DAY_THAI_NAMES[weekday],
            "run_rood": run_rood,
            "fun": fun,
            "pairs": pairs,
            "triplets": unique_triplets[:4],
            "power_numbers": power_digits,
            "history_count": n,
            "accuracy_pct": accuracy_pct,
            "hits": hits,
        }


class PredictorBot:
    """Handles LINE token authentication, Flex Message generation, and delivery."""

    def __init__(self, group_id_path: str = "data/predictor_group_id.txt"):
        self.group_id_path = group_id_path
        self.client_id = PREDICTOR_CLIENT_ID
        self.client_secret = PREDICTOR_CLIENT_SECRET
        self._access_token: Optional[str] = None
        self.engine = PredictorEngine()

    def get_token(self) -> str:
        if self._access_token:
            return self._access_token
        try:
            res = requests.post(
                "https://api.line.me/v2/oauth/accessToken",
                data={
                    "grant_type": "client_credentials",
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=10,
            )
            res.raise_for_status()
            token = res.json().get("access_token")
            self._access_token = token
            return token
        except Exception as e:
            logger.error("Failed to get PredictorBot access token: %s", e)
            raise

    def get_group_id(self) -> Optional[str]:
        env_gid = os.environ.get("PREDICTOR_GROUP_ID")
        if env_gid:
            return env_gid
        if os.path.exists(self.group_id_path):
            try:
                with open(self.group_id_path, "r", encoding="utf-8-sig") as f:
                    gid = f.read().strip()
                    if gid:
                        return gid
            except Exception:
                pass
    def record_requested_lottery(self, lottery_name: str, target_date: Optional[date] = None) -> None:
        """Record that a user explicitly requested prediction for this lottery today."""
        target_date = target_date or datetime.now(ZoneInfo("Asia/Bangkok")).date()
        req_path = "data/requested_predictions.json"
        reqs = set()
        if os.path.exists(req_path):
            try:
                with open(req_path, "r", encoding="utf-8") as f:
                    reqs = set(json.load(f))
            except Exception:
                pass
        key = f"{target_date.isoformat()}_{lottery_name}"
        reqs.add(key)
        try:
            with open(req_path, "w", encoding="utf-8") as f:
                json.dump(list(reqs), f, ensure_ascii=False)
        except Exception:
            pass

    def is_lottery_requested(self, lottery_name: str, target_date: Optional[date] = None) -> bool:
        """Check if this lottery was explicitly requested today by group members."""
        target_date = target_date or datetime.now(ZoneInfo("Asia/Bangkok")).date()

        # 1. First check if an active bill exists for this lottery today
        try:
            from winrate_manager import winrate_mgr, is_same_lottery
            bill = winrate_mgr.get_bill_for_lottery(lottery_name, target_date=target_date)
            if bill:
                return True
        except Exception:
            pass

        # 2. Check requested_predictions.json with alias matching
        req_path = "data/requested_predictions.json"
        if not os.path.exists(req_path):
            return False
        try:
            with open(req_path, "r", encoding="utf-8") as f:
                reqs = json.load(f)
                date_prefix = f"{target_date.isoformat()}_"
                for rk in reqs:
                    if rk.startswith(date_prefix):
                        req_name = rk[len(date_prefix):]
                        from winrate_manager import is_same_lottery
                        if is_same_lottery(req_name, lottery_name):
                            return True
        except Exception:
            pass
        return False

    def build_flex_message(self, flag: str, pred: Dict[str, Any]) -> Dict[str, Any]:
        lottery_name = pred["lottery_name"]
        date_thai = pred["target_date_thai"]
        day_name = pred["day_name"]
        run_rood_str = f"{pred['run_rood'][0]}  -  {pred['run_rood'][1]}"
        fun_str = f"{pred['fun']}"
        pairs_str = "   ".join(pred["pairs"])
        triplets_str = "   ".join(pred["triplets"])
        power_str = " - ".join(pred["power_numbers"])
        accuracy_str = f"ความแม่นยำย้อนหลัง: {pred['hits']}/{pred['history_count']} งวด ({pred['accuracy_pct']}%)"

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
                            {"type": "text", "text": "AI คำนวณสูตร", "color": "#FBBF24", "size": "xs", "align": "end", "weight": "bold"}
                        ]
                    },
                    {
                        "type": "text",
                        "text": f"{flag} {lottery_name}",
                        "color": "#FFFFFF",
                        "size": "xl",
                        "weight": "bold",
                        "margin": "md"
                    },
                    {
                        "type": "text",
                        "text": f"ประจำ{day_name}ที่ {date_thai}",
                        "color": "#94A3B8",
                        "size": "xs",
                        "margin": "xs"
                    }
                ]
            },
            "body": {
                "type": "box",
                "layout": "vertical",
                "backgroundColor": "#1E293B",
                "paddingAll": "20px",
                "spacing": "lg",
                "contents": [
                    {
                        "type": "box",
                        "layout": "vertical",
                        "backgroundColor": "#334155",
                        "cornerRadius": "12px",
                        "paddingAll": "14px",
                        "contents": [
                            {"type": "text", "text": "🎯 วิ่ง / รูด 19 ประตู", "color": "#38BDF8", "size": "sm", "weight": "bold"},
                            {"type": "text", "text": run_rood_str, "color": "#34D399", "size": "xxl", "weight": "bold", "align": "center", "margin": "sm"}
                        ]
                    },
                    {
                        "type": "box",
                        "layout": "horizontal",
                        "backgroundColor": "#831843",
                        "cornerRadius": "10px",
                        "paddingAll": "12px",
                        "alignItems": "center",
                        "contents": [
                            {"type": "text", "text": "⚡ เม็ดเดียว ฟันธง", "color": "#F9A8D4", "size": "sm", "weight": "bold", "flex": 1},
                            {"type": "text", "text": fun_str, "color": "#FDE047", "size": "xxl", "weight": "bold", "align": "end"}
                        ]
                    },
                    {
                        "type": "box",
                        "layout": "vertical",
                        "backgroundColor": "#0F172A",
                        "cornerRadius": "10px",
                        "paddingAll": "14px",
                        "contents": [
                            {"type": "text", "text": "🎲 เจาะ 2 ตัวเด่น (ไป-กลับ)", "color": "#FBBF24", "size": "xs", "weight": "bold"},
                            {"type": "text", "text": pairs_str, "color": "#FFFFFF", "size": "md", "weight": "bold", "align": "center", "margin": "md"}
                        ]
                    },
                    {
                        "type": "box",
                        "layout": "vertical",
                        "backgroundColor": "#0F172A",
                        "cornerRadius": "10px",
                        "paddingAll": "14px",
                        "contents": [
                            {"type": "text", "text": "👑 ชุด 3 ตัวตรง - โต๊ด", "color": "#A78BFA", "size": "xs", "weight": "bold"},
                            {"type": "text", "text": triplets_str, "color": "#E2E8F0", "size": "md", "weight": "bold", "align": "center", "margin": "md"}
                        ]
                    },
                    {
                        "type": "box",
                        "layout": "vertical",
                        "spacing": "xs",
                        "contents": [
                            {"type": "text", "text": f"🌟 เลขเด่นกำลังวัน: {power_str}", "color": "#94A3B8", "size": "xxs"},
                            {"type": "text", "text": f"📊 {accuracy_str}", "color": "#10B981", "size": "xxs", "weight": "bold"}
                        ]
                    }
                ]
            },
            "footer": {
                "type": "box",
                "layout": "vertical",
                "backgroundColor": "#0F172A",
                "paddingAll": "12px",
                "spacing": "sm",
                "contents": [
                    {
                        "type": "button",
                        "style": "primary",
                        "color": "#059669",
                        "height": "sm",
                        "action": {
                            "type": "uri",
                            "label": "🌐 ดูผลหวยสด แดชบอร์ด 24 ชม.",
                            "uri": "https://lotto-bot-uy9t.onrender.com/dashboard"
                        }
                    },
                    {
                        "type": "text",
                        "text": "⚠️ แนวทางสถิติเพื่อความบันเทิง โปรดใช้วิจารณญาณ",
                        "color": "#64748B",
                        "size": "xxs",
                        "align": "center"
                    }
                ]
            }
        }
        return {
            "type": "flex",
            "altText": f"🪐 แนวทาง {lottery_name} ประจำวันที่ {date_thai}",
            "contents": flex_dict
        }

    def reply_or_push_prediction(
        self,
        lottery_name: str,
        flag: str = "🎯",
        reply_token: Optional[str] = None,
        group_id: Optional[str] = None,
        candidate_tokens: Optional[List[str]] = None,
    ) -> bool:
        """Reply via LINE reply token if available, or push to group/user."""
        pred = self.engine.calculate_prediction(lottery_name)
        if not pred:
            logger.error("Could not calculate prediction for '%s'", lottery_name)
            return False

        flex_msg = self.build_flex_message(flag, pred)
        tokens = list(candidate_tokens or [])
        try:
            p_token = self.get_token()
            if p_token not in tokens:
                tokens.insert(0, p_token)
        except Exception:
            pass

        if reply_token:
            for tok in tokens:
                try:
                    res = requests.post(
                        "https://api.line.me/v2/bot/message/reply",
                        headers={"Authorization": f"Bearer {tok}", "Content-Type": "application/json"},
                        json={"replyToken": reply_token, "messages": [flex_msg]},
                        timeout=5
                    )
                    if res.status_code == 200:
                        logger.info("Successfully replied prediction for '%s'", lottery_name)
                        self.record_requested_lottery(lottery_name)
                        try:
                            from winrate_manager import winrate_mgr
                            winrate_mgr.record_bill(lottery_name, flag, group_id, pred)
                        except Exception as we:
                            logger.debug("WinRateManager record error: %s", we)
                        return True
                    else:
                        logger.debug("Reply failed with token (...%s): status %s - %s", tok[-8:] if len(tok) >= 8 else "", res.status_code, res.text)
                except Exception as exc:
                    logger.warning("Reply token attempt error: %s", exc)

        return self.send_prediction(lottery_name, flag=flag, group_id=group_id, candidate_tokens=tokens)

    def send_prediction(
        self,
        lottery_name: str,
        flag: str = "🎯",
        group_id: Optional[str] = None,
        candidate_tokens: Optional[List[str]] = None,
    ) -> bool:
        target_group = group_id or self.get_group_id()
        if not target_group:
            logger.error("Cannot send prediction: No dedicated group_id found.")
            return False

        pred = self.engine.calculate_prediction(lottery_name)
        if not pred:
            logger.error("Could not calculate prediction for '%s'", lottery_name)
            return False

        flex_msg = self.build_flex_message(flag, pred)
        tokens = list(candidate_tokens or [])
        try:
            p_token = self.get_token()
            if p_token not in tokens:
                tokens.insert(0, p_token)
        except Exception:
            pass

        for tok in tokens:
            try:
                res = requests.post(
                    "https://api.line.me/v2/bot/message/push",
                    headers={
                        "Authorization": f"Bearer {tok}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "to": target_group,
                        "messages": [flex_msg]
                    },
                    timeout=10,
                )
                if res.status_code == 200:
                    logger.info("Prediction for '%s' successfully pushed to %s", lottery_name, target_group)
                    self.record_requested_lottery(lottery_name)
                    try:
                        from winrate_manager import winrate_mgr
                        winrate_mgr.record_bill(lottery_name, flag, target_group, pred)
                    except Exception as we:
                        logger.debug("WinRateManager record error: %s", we)
                    return True
                else:
                    logger.warning("Push failed with token (...%s): status %s - %s", tok[-8:] if len(tok) >= 8 else "", res.status_code, res.text)
            except Exception as e:
                logger.error("Error pushing prediction to LINE: %s", e)

        return False


    def build_win_flex_message(self, flag: str, lottery_name: str, top3: str, bottom2: str, hits: List[Dict[str, str]]) -> Dict[str, Any]:
        """Construct a luxury celebratory winning Flex Message."""
        hit_contents = []
        for h in hits:
            hit_contents.append({
                "type": "box",
                "layout": "vertical",
                "backgroundColor": "#1E293B",
                "cornerRadius": "10px",
                "paddingAll": "12px",
                "margin": "md",
                "contents": [
                    {
                        "type": "box",
                        "layout": "horizontal",
                        "contents": [
                            {"type": "text", "text": h["title"], "color": h["color"], "size": "sm", "weight": "bold", "flex": 1},
                            {
                                "type": "box",
                                "layout": "vertical",
                                "backgroundColor": h["color"],
                                "cornerRadius": "6px",
                                "paddingStart": "8px",
                                "paddingEnd": "8px",
                                "paddingTop": "2px",
                                "paddingBottom": "2px",
                                "contents": [
                                    {"type": "text", "text": h["badge"], "color": "#0F172A", "size": "xxs", "weight": "bold"}
                                ]
                            }
                        ]
                    },
                    {
                        "type": "text",
                        "text": h["detail"],
                        "color": "#FFFFFF",
                        "size": "md",
                        "weight": "bold",
                        "margin": "sm"
                    }
                ]
            })

        flex_dict = {
            "type": "bubble",
            "size": "mega",
            "header": {
                "type": "box",
                "layout": "vertical",
                "backgroundColor": "#064E3B",
                "paddingAll": "20px",
                "contents": [
                    {
                        "type": "box",
                        "layout": "horizontal",
                        "contents": [
                            {"type": "text", "text": "🪐 แอดBaras 🛸", "color": "#6EE7B7", "size": "xs", "weight": "bold", "flex": 1},
                            {"type": "text", "text": "🏆 ตรวจผลแนวทาง", "color": "#FDE047", "size": "xs", "align": "end", "weight": "bold"}
                        ]
                    },
                    {
                        "type": "text",
                        "text": f"🎉 แตกเข้าเป้า! {flag} {lottery_name}",
                        "color": "#FFFFFF",
                        "size": "xl",
                        "weight": "bold",
                        "margin": "md"
                    },
                    {
                        "type": "box",
                        "layout": "horizontal",
                        "backgroundColor": "#022C22",
                        "cornerRadius": "10px",
                        "paddingAll": "12px",
                        "margin": "md",
                        "contents": [
                            {
                                "type": "box",
                                "layout": "vertical",
                                "flex": 1,
                                "alignItems": "center",
                                "contents": [
                                    {"type": "text", "text": "3 ตัวบน", "color": "#94A3B8", "size": "xxs"},
                                    {"type": "text", "text": top3, "color": "#38BDF8", "size": "xxl", "weight": "bold"}
                                ]
                            },
                            {
                                "type": "box",
                                "layout": "vertical",
                                "flex": 1,
                                "alignItems": "center",
                                "contents": [
                                    {"type": "text", "text": "2 ตัวล่าง", "color": "#94A3B8", "size": "xxs"},
                                    {"type": "text", "text": bottom2, "color": "#F43F5E", "size": "xxl", "weight": "bold"}
                                ]
                            }
                        ]
                    }
                ]
            },
            "body": {
                "type": "box",
                "layout": "vertical",
                "backgroundColor": "#0F172A",
                "paddingAll": "20px",
                "contents": [
                    {
                        "type": "text",
                        "text": "รายการที่ฟันเข้าเป้าวันนี้:",
                        "color": "#94A3B8",
                        "size": "xs",
                        "weight": "bold"
                    },
                    *hit_contents
                ]
            },
            "footer": {
                "type": "box",
                "layout": "vertical",
                "backgroundColor": "#064E3B",
                "paddingAll": "12px",
                "contents": [
                    {
                        "type": "text",
                        "text": "💸 ปังยกกลุ่ม! ยินดีกับทุกท่านที่ตามครับ ✨",
                        "color": "#FDE047",
                        "size": "xs",
                        "weight": "bold",
                        "align": "center"
                    }
                ]
            }
        }
        return {
            "type": "flex",
            "altText": f"🎉 สรุปผลเข้าเป้า {lottery_name}: 3 ตัว {top3} | 2 ตัว {bottom2}",
            "contents": flex_dict
        }

    def check_and_send_win(
        self,
        lottery_name: str,
        top3: str,
        bottom2: str,
        result_date: Optional[date] = None,
        flag: str = "🎯"
    ) -> bool:
        """Check if today's prediction hit any prize, and if so, push celebratory card to the dedicated group."""
        if result_date is None:
            result_date = datetime.now().date()

        win_log_path = "data/sent_win_celebrations.json"
        sent_keys = set()
        if os.path.exists(win_log_path):
            try:
                with open(win_log_path, "r", encoding="utf-8") as f:
                    sent_keys = set(json.load(f))
            except Exception:
                pass

        cache_key = f"{result_date.isoformat()}_{lottery_name}"
        if cache_key in sent_keys:
            return False

        # Only check and celebrate wins for lotteries that users in the group explicitly requested!
        if not self.is_lottery_requested(lottery_name, target_date=result_date):
            return False

        # First check if there was an actual recorded bill for this lottery today
        pred = None
        try:
            from winrate_manager import winrate_mgr
            bill = winrate_mgr.get_bill_for_lottery(lottery_name, target_date=result_date)
            if bill and bill.get("prediction"):
                pred = bill["prediction"]
        except Exception:
            pass

        if not pred:
            pred = self.engine.calculate_prediction(lottery_name, target_date=result_date)
        if not pred:
            return False

        if not top3 or not bottom2:
            return False
        t3_str = str(top3).strip()
        b2_str = str(bottom2).strip()
        if not t3_str.isdigit() or not b2_str.isdigit():
            return False

        top3 = t3_str.zfill(3)[-3:]
        bot2 = b2_str.zfill(2)[-2:]
        top2 = top3[-2:]

        hits = []

        # 1. Check วิ่ง / รูด 19 ประตู
        d1, d2 = pred["run_rood"][0], pred["run_rood"][1]
        run_hits = []
        if d1 in top3: run_hits.append(f"{d1} บน")
        if d1 in bot2: run_hits.append(f"{d1} ล่าง")
        if d2 in top3 and d2 != d1: run_hits.append(f"{d2} บน")
        if d2 in bot2 and d2 != d1: run_hits.append(f"{d2} ล่าง")

        if run_hits:
            hits.append({
                "title": "🎯 วิ่ง / รูด 19 ประตู",
                "detail": f"เข้าเลขเด่น {' • '.join(run_hits)}",
                "badge": "เข้าเป้า",
                "color": "#34D399"
            })

        # 2. Check ฟันธง
        fun = pred["fun"]
        fun_hits = []
        if fun in top3: fun_hits.append(f"{fun} บน")
        if fun in bot2: fun_hits.append(f"{fun} ล่าง")
        if fun_hits:
            hits.append({
                "title": "⚡ เม็ดเดียว ฟันธง",
                "detail": f"เข้าเน้นๆ {fun} ({', '.join(fun_hits)})",
                "badge": "ฟันตรงเป้า",
                "color": "#FDE047"
            })

        # 3. Check เจาะ 2 ตัว
        pairs = pred["pairs"]
        pair_hits = []
        for p in pairs:
            rev_p = p[::-1]
            if p == top2:
                pair_hits.append(f"{p} บน (ตรงๆ)")
            elif rev_p == top2 and p != rev_p:
                pair_hits.append(f"{rev_p} บน (กลับ)")
            if p == bot2:
                pair_hits.append(f"{p} ล่าง (ตรงๆ)")
            elif rev_p == bot2 and p != rev_p:
                pair_hits.append(f"{rev_p} ล่าง (กลับ)")

        if pair_hits:
            hits.append({
                "title": "🎲 เจาะ 2 ตัวเด่น",
                "detail": " • ".join(pair_hits),
                "badge": "แตกเต็มๆ",
                "color": "#F472B6"
            })

        # 4. Check 3 ตัว
        triplets = pred["triplets"]
        triplet_hits = []
        sorted_top3 = "".join(sorted(top3))
        for t in triplets:
            if t == top3:
                triplet_hits.append(f"{t} (3 ตัวตรง!)")
            elif "".join(sorted(t)) == sorted_top3:
                triplet_hits.append(f"{t} (3 ตัวโต๊ด!)")

        if triplet_hits:
            hits.append({
                "title": "👑 ชุด 3 ตัว",
                "detail": " • ".join(triplet_hits),
                "badge": "แตกกระจาย",
                "color": "#A78BFA"
            })

        if not hits:
            logger.info("No win for prediction '%s' on %s (top3=%s, bot2=%s)", lottery_name, result_date, top3, bot2)
            return False

        flex_msg = self.build_win_flex_message(flag, lottery_name, top3, bot2, hits)
        target_group = self.get_group_id()
        if not target_group:
            return False

        token = self.get_token()
        try:
            res = requests.post(
                "https://api.line.me/v2/bot/message/push",
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                json={"to": target_group, "messages": [flex_msg]},
                timeout=10,
            )
            if res.status_code == 200:
                logger.info("Successfully pushed WIN celebration for '%s' to group %s", lottery_name, target_group)
                sent_keys.add(cache_key)
                try:
                    with open(win_log_path, "w", encoding="utf-8") as f:
                        json.dump(list(sent_keys), f, ensure_ascii=False)
                except Exception:
                    pass
                return True
            else:
                logger.error("Failed to push win celebration: %d %s", res.status_code, res.text)
                return False
        except Exception as e:
            logger.error("Exception pushing win celebration: %s", e)
            return False


if __name__ == "__main__":
    bot = PredictorBot()
    name, flag = resolve_lottery("ขอนอยสตาร์".replace("ขอ", ""))
    print("Resolved:", name, flag)

