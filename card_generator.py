# -*- coding: utf-8 -*-
"""Generate high-resolution lottery result card images using PIL and host them for LINE."""

from __future__ import annotations

import os
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import requests

from utils import setup_logging

logger = setup_logging()

# Load fonts once
FONT_TITLE = ImageFont.truetype("C:/Windows/Fonts/LeelaUIb.ttf", 44)
FONT_LABEL = ImageFont.truetype("C:/Windows/Fonts/LeelaUIb.ttf", 28)
FONT_NUM = ImageFont.truetype("C:/Windows/Fonts/LeelaUIb.ttf", 76)


def generate_card_image(
    name: str,
    top3: str,
    bottom2: str,
    flag: str = "🎯",
    output_dir: str = "cards",
) -> str:
    """Generate a PNG card image for lottery result."""
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    file_path = os.path.join(output_dir, f"{name}.png")

    width, height = 700, 580
    img = Image.new("RGBA", (width, height), (24, 26, 32, 255))
    draw = ImageDraw.Draw(img)

    # Header Box (#1E222D)
    draw.rectangle([0, 0, width, 100], fill=(30, 34, 45, 255))
    header_text = f"{flag}  {name}"
    draw.text((35, 25), header_text, font=FONT_TITLE, fill=(255, 255, 255, 255))

    # Top 3 Red Container (#2A181A)
    draw.rounded_rectangle([30, 125, width - 30, 325], radius=18, fill=(42, 24, 26, 255))
    draw.text((55, 140), "🔺 3 ตัวบน", font=FONT_LABEL, fill=(255, 107, 107, 255))
    top3_formatted = "   ".join(top3.zfill(3)[-3:])
    bbox3 = FONT_NUM.getbbox(top3_formatted)
    w3 = bbox3[2] - bbox3[0]
    draw.text(((width - w3) // 2, 198), top3_formatted, font=FONT_NUM, fill=(255, 77, 77, 255))

    # Bottom 2 Blue Container (#142438)
    draw.rounded_rectangle([30, 345, width - 30, 545], radius=18, fill=(20, 36, 56, 255))
    draw.text((55, 360), "🔻 2 ตัวล่าง", font=FONT_LABEL, fill=(48, 171, 255, 255))
    bottom2_formatted = "   ".join(bottom2.zfill(2)[-2:])
    bbox2 = FONT_NUM.getbbox(bottom2_formatted)
    w2 = bbox2[2] - bbox2[0]
    draw.text(((width - w2) // 2, 418), bottom2_formatted, font=FONT_NUM, fill=(0, 210, 255, 255))

    img.save(file_path, "PNG")
    return file_path


def upload_card_image(image_path: str) -> str:
    """Upload image to Catbox.moe and return public HTTPS URL."""
    try:
        with open(image_path, "rb") as f:
            files = {"fileToUpload": f}
            data = {"reqtype": "fileupload"}
            response = requests.post(
                "https://catbox.moe/user/api.php",
                files=files,
                data=data,
                timeout=15,
            )
            if response.status_code == 200 and response.text.startswith("http"):
                url = response.text.strip()
                logger.info("Card image uploaded to %s", url)
                return url
    except Exception as exc:
        logger.error("Failed to upload card image to catbox: %s", exc)

    # Fallback to tmpfiles.org
    try:
        with open(image_path, "rb") as f:
            r = requests.post(
                "https://tmpfiles.org/api/v1/upload",
                files={"file": f},
                timeout=15,
            )
            if r.status_code == 200:
                data = r.json()
                url = data.get("data", {}).get("url", "")
                if url:
                    direct_url = url.replace("tmpfiles.org/", "tmpfiles.org/dl/")
                    logger.info("Card image uploaded to fallback %s", direct_url)
                    return direct_url
    except Exception as exc:
        logger.error("Failed to upload card image to fallback: %s", exc)

    raise RuntimeError("Could not upload card image to any image host")
