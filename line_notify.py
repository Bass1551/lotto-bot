# -*- coding: utf-8 -*-
"""
line_notify.py
ส่งข้อความเข้า LINE Group ด้วย LINE Messaging API (Push Message)
"""
import logging
import requests

from config import LINE_CHANNEL_ACCESS_TOKEN, LINE_GROUP_ID, REQUEST_TIMEOUT

LINE_PUSH_URL = "https://api.line.me/v2/bot/message/push"

logger = logging.getLogger("line_notify")


def push_message(text: str) -> bool:
    """
    ส่งข้อความ text เข้ากลุ่ม LINE ที่กำหนดไว้ใน .env (LINE_GROUP_ID)
    คืนค่า True ถ้าส่งสำเร็จ, False ถ้าล้มเหลว (จะไม่ raise exception เพื่อไม่ให้โปรแกรมหลักล้ม)
    """
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}",
    }
    payload = {
        "to": LINE_GROUP_ID,
        "messages": [{"type": "text", "text": text}],
    }

    try:
        resp = requests.post(
            LINE_PUSH_URL, headers=headers, json=payload, timeout=REQUEST_TIMEOUT
        )
        if resp.status_code == 200:
            logger.info("ส่งข้อความสำเร็จ")
            return True
        else:
            logger.error(
                "ส่งข้อความล้มเหลว status=%s body=%s", resp.status_code, resp.text
            )
            return False
    except requests.RequestException as e:
        logger.error("เกิดข้อผิดพลาดขณะเชื่อมต่อ LINE API: %s", e)
        return False


def format_lotto_message(flag: str, name: str, number: str) -> str:
    """
    จัดรูปแบบข้อความให้ตรงตามตัวอย่างที่ต้องการ:

    🇱🇦 ลาว Extra 🇱🇦
    ✅ ผลออกแล้ว
    76734
    3 บน : 767
    2 ล่าง : 34
    """
    number = number.strip()
    if len(number) != 5 or not number.isdigit():
        # เผื่อบางหวยผลไม่ใช่ 5 หลักมาตรฐาน ก็ยังส่งเลขดิบไปโดยไม่ตัด บน/ล่าง
        return (
            f"{flag} {name} {flag}\n"
            f"✅ ผลออกแล้ว\n"
            f"{number}"
        )

    three_top = number[:3]
    two_bottom = number[-2:]

    return (
        f"{flag} {name} {flag}\n"
        f"✅ ผลออกแล้ว\n"
        f"{number}\n"
        f"3 บน : {three_top}\n"
        f"2 ล่าง : {two_bottom}"
    )
