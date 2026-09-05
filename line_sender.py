# -*- coding: utf-8 -*-
"""LINE Messaging API sender module."""

from __future__ import annotations

import os
import urllib.parse
from typing import Optional

from dotenv import load_dotenv
from linebot.v3.messaging import (
    ApiClient,
    Configuration,
    FlexContainer,
    FlexMessage,
    ImageMessage,
    MessagingApi,
    PushMessageRequest,
    TextMessage,
)

from card_generator import generate_card_image, upload_card_image
from utils import setup_logging

load_dotenv()
logger = setup_logging()


class LineSender:
    """Send text, Flex, and Image messages to a LINE group via Messaging API."""

    def __init__(
        self,
        channel_access_token: Optional[str] = None,
        group_id: Optional[str] = None,
    ) -> None:
        self.token = channel_access_token or os.getenv("LINE_CHANNEL_ACCESS_TOKEN") or "8DQnOegmnlRDph8ZOFt2syPeOqmyN5fyDhucInkI937OfmXmUqBJ91KbfoERyw9R6Q5I9jdRtB3aGLLf14r4jlMwJaae6KUoyfFb/bhyouwhllNgHoAJM74hA7kULAsLAlwxY/QUOzHz470fUPsCwgdB04t89/1O/w1cDnyilFU="
        self.group_id = group_id or os.getenv("LINE_GROUP_ID") or "C3da8f4cbb066d77d4ed40ec4fce4f959"

        if not self.token:
            raise ValueError(
                "LINE_CHANNEL_ACCESS_TOKEN is not set. "
                "Please set it in .env or pass it to the constructor."
            )
        if not self.group_id:
            raise ValueError(
                "LINE_GROUP_ID is not set. "
                "Please set it in .env or pass it to the constructor."
            )

        self.configuration = Configuration(access_token=self.token)
        logger.info("LineSender initialized for group %s", self.group_id[:8] + "...")

    def send_result_image(
        self, name: str, top3: str, bottom2: str, flag: str = "🎯"
    ) -> bool:
        """Generate high-res PNG card, upload to HTTPS host, and push ImageMessage."""
        try:
            image_path = generate_card_image(name, top3, bottom2, flag=flag)
            image_url = upload_card_image(image_path)

            with ApiClient(self.configuration) as api_client:
                api = MessagingApi(api_client)
                api.push_message(
                    PushMessageRequest(
                        to=self.group_id,
                        messages=[
                            ImageMessage(
                                original_content_url=image_url,
                                preview_image_url=image_url,
                            )
                        ],
                    )
                )
            logger.info("LINE Card ImageMessage sent successfully for %s", name)
            return True
        except Exception as exc:
            logger.error("Failed to send LINE ImageMessage for %s: %s", name, exc, exc_info=True)
            return self.send_result_emoji_text(name, top3, bottom2, flag=flag)

    def create_clean_flex_message_dict(
        self, name: str, top3: str, bottom2: str, flag: str = "🎯"
    ) -> dict:
        """Create a clean Flex Message bubble (WITHOUT share button)."""
        top3_fmt = "  ".join(top3.zfill(3)[-3:])
        bottom2_fmt = "  ".join(bottom2.zfill(2)[-2:])

        return {
            "type": "bubble",
            "size": "mega",
            "header": {
                "type": "box",
                "layout": "horizontal",
                "backgroundColor": "#1E222D",
                "paddingAll": "lg",
                "alignItems": "center",
                "contents": [
                    {
                        "type": "text",
                        "text": flag,
                        "size": "xl",
                        "flex": 0,
                    },
                    {
                        "type": "text",
                        "text": f" {name}",
                        "weight": "bold",
                        "size": "xl",
                        "color": "#FFFFFF",
                        "flex": 1,
                    },
                ],
            },
            "body": {
                "type": "box",
                "layout": "vertical",
                "backgroundColor": "#181A20",
                "spacing": "md",
                "paddingAll": "lg",
                "contents": [
                    # 3 ตัวบน (Theme แดง/ส้ม)
                    {
                        "type": "box",
                        "layout": "vertical",
                        "backgroundColor": "#2A181A",
                        "cornerRadius": "md",
                        "paddingAll": "md",
                        "spacing": "xs",
                        "contents": [
                            {
                                "type": "text",
                                "text": "🔺 3 ตัวบน",
                                "size": "sm",
                                "color": "#FF6B6B",
                                "weight": "bold",
                            },
                            {
                                "type": "text",
                                "text": top3_fmt,
                                "size": "3xl",
                                "weight": "bold",
                                "color": "#FF4D4D",
                                "align": "center",
                            },
                        ],
                    },
                    # Signature Watermark (Mysterious Sci-Fi - กลางการ์ด ป้องกันการตัดรูป)
                    {
                        "type": "box",
                        "layout": "horizontal",
                        "justifyContent": "center",
                        "alignItems": "center",
                        "contents": [
                            {
                                "type": "text",
                                "text": "🪐 แอดBaras 🛸",
                                "size": "xs",
                                "color": "#00E5FF",
                                "weight": "bold",
                                "align": "center",
                            }
                        ],
                    },
                    # 2 ตัวล่าง (Theme น้ำเงิน/ฟ้า)
                    {
                        "type": "box",
                        "layout": "vertical",
                        "backgroundColor": "#142438",
                        "cornerRadius": "md",
                        "paddingAll": "md",
                        "spacing": "xs",
                        "contents": [
                            {
                                "type": "text",
                                "text": "🔻 2 ตัวล่าง",
                                "size": "sm",
                                "color": "#4DABFF",
                                "weight": "bold",
                            },
                            {
                                "type": "text",
                                "text": bottom2_fmt,
                                "size": "3xl",
                                "weight": "bold",
                                "color": "#00D2FF",
                                "align": "center",
                            },
                        ],
                    },
                ],
            },
        }

    def create_flex_message_dict(
        self, name: str, top3: str, bottom2: str, flag: str = "🎯"
    ) -> dict:
        """Create a styled LINE Flex Message bubble with LIFF share button."""
        clean_flex = self.create_clean_flex_message_dict(name, top3, bottom2, flag=flag)
        
        # Short parameter URL for LIFF Share Target Picker (< 100 chars)
        q_name = urllib.parse.quote(name)
        q_top3 = urllib.parse.quote(top3)
        q_bottom2 = urllib.parse.quote(bottom2)
        q_flag = urllib.parse.quote(flag)
        liff_share_uri = f"https://liff.line.me/2011157640-izadxULb?n={q_name}&t={q_top3}&b={q_bottom2}&f={q_flag}"

        clean_flex["footer"] = {
            "type": "box",
            "layout": "vertical",
            "backgroundColor": "#14161D",
            "paddingAll": "md",
            "contents": [
                {
                    "type": "button",
                    "style": "primary",
                    "color": "#28A745",
                    "height": "sm",
                    "action": {
                        "type": "uri",
                        "label": "📤 กดที่นี่เพื่อแชร์ผล",
                        "uri": liff_share_uri,
                    },
                }
            ],
        }
        return clean_flex

    def create_combined_clean_flex_message_dict(self, items: list) -> dict:
        """Create a clean combined Flex Message bubble for multiple lotteries."""
        body_contents = []
        for i, item in enumerate(items):
            if i > 0:
                body_contents.append({"type": "separator", "margin": "lg", "color": "#333A48"})
            
            top3_fmt = "  ".join(list(item["top3"].zfill(3)[-3:]))
            bottom2_fmt = "  ".join(list(item["bottom2"].zfill(2)[-2:]))

            body_contents.extend([
                {
                    "type": "box",
                    "layout": "horizontal",
                    "margin": "md",
                    "contents": [
                        {"type": "text", "text": item.get("flag", "🎯"), "size": "md", "flex": 0},
                        {"type": "text", "text": " " + item["name"], "weight": "bold", "size": "md", "color": "#FFFFFF", "flex": 1}
                    ]
                },
                {
                    "type": "box",
                    "layout": "vertical",
                    "backgroundColor": "#2A181A",
                    "cornerRadius": "md",
                    "paddingAll": "md",
                    "spacing": "xs",
                    "contents": [
                        {"type": "text", "text": "🔺 3 ตัวบน", "size": "xs", "color": "#FF6B6B", "weight": "bold"},
                        {"type": "text", "text": top3_fmt, "size": "xxl", "weight": "bold", "color": "#FF4D4D", "align": "center"}
                    ]
                },
                {
                    "type": "box",
                    "layout": "horizontal",
                    "justifyContent": "center",
                    "alignItems": "center",
                    "contents": [
                        {
                            "type": "text",
                            "text": "🪐 แอดBaras 🛸",
                            "size": "xs",
                            "color": "#00E5FF",
                            "weight": "bold",
                            "align": "center",
                        }
                    ],
                },
                {
                    "type": "box",
                    "layout": "vertical",
                    "backgroundColor": "#142438",
                    "cornerRadius": "md",
                    "paddingAll": "md",
                    "spacing": "xs",
                    "contents": [
                        {"type": "text", "text": "🔻 2 ตัวล่าง", "size": "xs", "color": "#4DABFF", "weight": "bold"},
                        {"type": "text", "text": bottom2_fmt, "size": "xxl", "weight": "bold", "color": "#00D2FF", "align": "center"}
                    ]
                }
            ])

        header_title = f"🎯 ผลสลากรวม ({len(items)} หวย)"
        return {
            "type": "bubble",
            "size": "mega",
            "header": {
                "type": "box",
                "layout": "horizontal",
                "backgroundColor": "#1E222D",
                "paddingAll": "lg",
                "alignItems": "center",
                "contents": [
                    {"type": "text", "text": header_title, "weight": "bold", "size": "lg", "color": "#FFFFFF", "flex": 1}
                ]
            },
            "body": {
                "type": "box",
                "layout": "vertical",
                "backgroundColor": "#181A20",
                "spacing": "md",
                "paddingAll": "lg",
                "contents": body_contents
            }
        }

    def create_combined_flex_message_dict(self, items: list) -> dict:
        """Create a styled LINE Flex Message bubble for multiple lotteries with LIFF share button."""
        clean_flex = self.create_combined_clean_flex_message_dict(items)

        names_str = "|".join([x["name"] for x in items])
        top3_str = "|".join([x["top3"] for x in items])
        bottom2_str = "|".join([x["bottom2"] for x in items])
        flags_str = "|".join([x.get("flag", "🎯") for x in items])

        q_name = urllib.parse.quote(names_str)
        q_top3 = urllib.parse.quote(top3_str)
        q_bottom2 = urllib.parse.quote(bottom2_str)
        q_flag = urllib.parse.quote(flags_str)
        liff_share_uri = f"https://liff.line.me/2011157640-izadxULb?n={q_name}&t={q_top3}&b={q_bottom2}&f={q_flag}"

        clean_flex["footer"] = {
            "type": "box",
            "layout": "vertical",
            "backgroundColor": "#14161D",
            "paddingAll": "md",
            "contents": [
                {
                    "type": "button",
                    "style": "primary",
                    "color": "#28A745",
                    "height": "sm",
                    "action": {
                        "type": "uri",
                        "label": "📤 กดที่นี่เพื่อแชร์ผลรวม",
                        "uri": liff_share_uri,
                    },
                }
            ],
        }
        return clean_flex

    def send_combined_result_flex(self, items: list) -> bool:
        """Send a combined Flex Message card containing multiple lotteries with share button."""
        try:
            flex_dict = self.create_combined_flex_message_dict(items)
            names_title = " + ".join([f"{x.get('flag', '🎯')} {x['name']}" for x in items])
            container = FlexContainer.from_dict(flex_dict)
            alt_text = f"🎯 ผลสลากรวม: {names_title}"

            with ApiClient(self.configuration) as api_client:
                api = MessagingApi(api_client)
                api.push_message(
                    PushMessageRequest(
                        to=self.group_id,
                        messages=[FlexMessage(alt_text=alt_text, contents=container)],
                    )
                )
            logger.info("LINE Combined Flex Message sent successfully for: %s", names_title)
            return True
        except Exception as err:
            logger.error("Failed to send LINE Combined Flex Message: %s", err)
            return False

    def send_result_flex(
        self, name: str, top3: str, bottom2: str, flag: str = "🎯"
    ) -> bool:
        """Push a Flex Message result card to the LINE group with share button."""
        try:
            flex_dict = self.create_flex_message_dict(
                name=name, top3=top3, bottom2=bottom2, flag=flag
            )
            container = FlexContainer.from_dict(flex_dict)
            alt_text = f"{flag} {name} | 3บน: {top3} | 2ล่าง: {bottom2}"

            with ApiClient(self.configuration) as api_client:
                api = MessagingApi(api_client)
                api.push_message(
                    PushMessageRequest(
                        to=self.group_id,
                        messages=[FlexMessage(alt_text=alt_text, contents=container)],
                    )
                )
            logger.info("LINE Flex Message sent successfully for %s", name)
            return True
        except Exception as exc:
            logger.error("Failed to send LINE Flex Message for %s: %s", name, exc, exc_info=True)
            # Fallback to Text Message if Flex fails
            fallback_text = f"{flag} {name}\n🔺 3บน: {top3}\n🔻 2ล่าง: {bottom2}"
            return self.send_text(fallback_text)

    def send_result_emoji_text(
        self, name: str, top3: str, bottom2: str, flag: str = "🎯"
    ) -> bool:
        """Send a forwardable text message with colored badges and clean digits."""
        top3_clean = "  ".join(top3.zfill(3)[-3:])
        bottom2_clean = "  ".join(bottom2.zfill(2)[-2:])

        text = (
            f"{flag} {name}\n"
            f"🔴 3 ตัวบน : {top3_clean}\n"
            f"🔵 2 ตัวล่าง : {bottom2_clean}"
        )
        return self.send_text(text)

    def send_text(self, message: str) -> bool:
        """Push a text message to the configured group."""
        try:
            with ApiClient(self.configuration) as api_client:
                api = MessagingApi(api_client)
                api.push_message(
                    PushMessageRequest(
                        to=self.group_id,
                        messages=[TextMessage(text=message)],
                    )
                )
            logger.info("LINE text message sent successfully (%d chars)", len(message))
            return True
        except Exception as exc:
            logger.error("Failed to send LINE text message: %s", exc, exc_info=True)
            return False
