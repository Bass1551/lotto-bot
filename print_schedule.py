# -*- coding: utf-8 -*-
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

with open("config.json", "r", encoding="utf-8") as f:
    items = json.load(f)

items.sort(key=lambda x: x["time"])

print(f"Total: {len(items)}")
for item in items:
    print(f"{item['time']} น. | {item['flag']} {item['name']}")
