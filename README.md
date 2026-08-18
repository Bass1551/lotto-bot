# Lottery Bot (หวย LINE Bot)

ระบบดึงผลหวยอัตโนมัติแล้วส่งเข้า LINE กลุ่มทันทีเมื่อถึงเวลาออกผล  
**ห้ามส่งซ้ำ** (ใช้ SQLite เก็บประวัติ)

## คุณสมบัติ

- เช็กเว็บไซต์เฉพาะตอนถึงเวลาออกผลเท่านั้น
- เช็กทุก 1 นาที สูงสุด 10 นาที
- พบผลแล้วหยุดเช็กทันที
- แยก parser ตามเว็บไซต์ (HTML ไม่เหมือนกัน)
- หวยลาว ดึง 3 ตัวบน / 2 ตัวล่าง จากช่องที่เว็บแสดงโดยตรง
- แปลงตัวเลขเป็น Emoji
- Retry 3 ครั้งเมื่อเว็บล่ม
- Log ครบทุกขั้นตอน
- ใช้ APScheduler + SQLite + LINE Messaging API

## โครงสร้าง

```
lottery_bot/
├── main.py
├── scheduler.py
├── database.py
├── line_sender.py
├── utils.py
├── config.json
├── requirements.txt
├── .env
├── logs/
└── parsers/
    ├── __init__.py
    ├── base.py
    ├── hanoi_hd.py
    ├── hanoi_star.py
    ├── hanoi_tv.py
    ├── hanoi_kachad.py
    ├── lao_hd.py
    ├── lao_tv.py
    ├── lao_star.py
    ├── lao_extra.py
    └── stock_generic.py
```

## การติดตั้ง

```bash
cd lottery_bot
python -m venv venv
# Windows
venv\Scripts\activate
# Linux / macOS
source venv/bin/activate

pip install -r requirements.txt
playwright install chromium   # จำเป็นสำหรับเว็บที่ใช้ JavaScript
```

## ตั้งค่า

แก้ไขไฟล์ `.env`:

```
LINE_CHANNEL_ACCESS_TOKEN=ใส่ token จริง
LINE_GROUP_ID=ใส่ group id จริง
```

วิธีหา Group ID:
1. เชิญบอทเข้ากลุ่ม
2. ส่งข้อความในกลุ่ม
3. ดู Webhook event หรือใช้ API get group id

## รัน

```bash
python main.py
```

บอทจะทำงานตลอดเวลา และเช็กเฉพาะตอนถึงเวลาที่กำหนดใน `config.json`

## เพิ่มหวยใหม่

1. สร้างไฟล์ parser ใน `parsers/` (สืบทอดจาก `BaseParser`)
2. ลงทะเบียนใน `parsers/__init__.py`
3. เพิ่มรายการใน `config.json`

## รูปแบบข้อความที่ส่ง

```
🇻🇳 ฮานอย HD
🔺 3️⃣ 4️⃣ 4️⃣
🔻 0️⃣ 3️⃣
```

## หมายเหตุ

- บางเว็บไซต์หวยมีการป้องกัน / เปลี่ยนโครงสร้างบ่อย → อาจต้องปรับ selector ใน parser
- เว็บที่ใช้ JavaScript หนัก (lao-tv, laostars, บางเว็บฮานอย) ใช้ Playwright
- แนะนำรันบน VPS หรือเครื่องที่เปิดตลอด
