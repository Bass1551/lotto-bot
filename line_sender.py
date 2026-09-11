# -*- coding: utf-8 -*-
"""LINE Messaging API sender module with multi-bot automatic failover chain."""

from __future__ import annotations

import json
import os
import urllib.parse
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import requests
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
from linebot.v3.messaging.exceptions import ApiException

from card_generator import generate_card_image, upload_card_image
from utils import setup_logging

load_dotenv()
logger = setup_logging()


class LineSender:
    """Send text, Flex, and Image messages to LINE groups with multi-bot automatic failover."""

    def __init__(
        self,
        channel_access_token: Optional[str] = None,
        group_id: Optional[str] = None,
        bot_chain_file: Optional[str | Path] = None,
    ) -> None:
        base_dir = Path(__file__).parent
        self.bot_chain_file = Path(bot_chain_file) if bot_chain_file else base_dir / "data" / "bot_chain.json"
        self.active_index_file = base_dir / "data" / "active_bot_index.json"

        self.bot_chain: list[dict[str, Any]] = []

        # If explicit token and group_id are passed, prioritize them (e.g. for custom/isolated testing)
        if channel_access_token and group_id:
            self.bot_chain = [
                {
                    "name": "Custom",
                    "token": channel_access_token,
                    "group_id": group_id,
                    "channel_id": "",
                    "channel_secret": "",
                }
            ]
        elif self.bot_chain_file.exists():
            try:
                with open(self.bot_chain_file, "r", encoding="utf-8") as f:
                    self.bot_chain = json.load(f)
                logger.info("Loaded %d bots in failover chain from %s", len(self.bot_chain), self.bot_chain_file)
            except Exception as e:
                logger.error("Failed to load bot chain from %s: %s", self.bot_chain_file, e)

        # Fallback if bot_chain is empty
        if not self.bot_chain:
            default_token = (
                channel_access_token
                or os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
                or "8DQnOegmnlRDph8ZOFt2syPeOqmyN5fyDhucInkI937OfmXmUqBJ91KbfoERyw9R6Q5I9jdRtB3aGLLf14r4jlMwJaae6KUoyfFb/bhyouwhllNgHoAJM74hA7kULAsLAlwxY/QUOzHz470fUPsCwgdB04t89/1O/w1cDnyilFU="
            )
            default_group = group_id or os.getenv("LINE_GROUP_ID") or "C3da8f4cbb066d77d4ed40ec4fce4f959"
            self.bot_chain = [
                {
                    "name": "ผลหวย",
                    "token": default_token,
                    "group_id": default_group,
                    "channel_id": "",
                    "channel_secret": "",
                }
            ]

        active_idx = self._get_active_index()
        active_bot = self.bot_chain[active_idx] if active_idx < len(self.bot_chain) else self.bot_chain[0]
        logger.info(
            "LineSender initialized with %d bots. Active bot: [%s] (index %d, group: %s...)",
            len(self.bot_chain),
            active_bot.get("name"),
            active_idx,
            active_bot.get("group_id", "")[:8],
        )

    @property
    def current_bot(self) -> dict[str, Any]:
        idx = self._get_active_index()
        if 0 <= idx < len(self.bot_chain):
            return self.bot_chain[idx]
        return self.bot_chain[0]

    @property
    def token(self) -> str:
        return self.current_bot.get("token", "")

    @property
    def group_id(self) -> str:
        return self.current_bot.get("group_id", "")

    @property
    def configuration(self) -> Configuration:
        return Configuration(access_token=self.token)

    def _get_active_index(self) -> int:
        """Get the currently active bot index. Resets on new month."""
        current_month = datetime.now().strftime("%Y-%m")
        if self.active_index_file.exists():
            try:
                with open(self.active_index_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if data.get("month") == current_month:
                    idx = data.get("active_index", 0)
                    return min(max(0, idx), len(self.bot_chain) - 1)
                else:
                    logger.info("New month detected (%s). Resetting bot failover chain to index 0.", current_month)
                    self._save_active_index(0)
                    return 0
            except Exception as err:
                logger.warning("Could not read active_bot_index.json: %s. Defaulting to 0.", err)
        return 0

    def _save_active_index(self, index: int) -> None:
        """Save the active bot index and current month."""
        current_month = datetime.now().strftime("%Y-%m")
        try:
            self.active_index_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.active_index_file, "w", encoding="utf-8") as f:
                json.dump({"month": current_month, "active_index": index}, f, indent=2)
        except Exception as err:
            logger.error("Failed to save active bot index: %s", err)

    def _save_bot_chain(self) -> None:
        """Persist current bot_chain list (with refreshed tokens) to file."""
        try:
            self.bot_chain_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.bot_chain_file, "w", encoding="utf-8") as f:
                json.dump(self.bot_chain, f, ensure_ascii=False, indent=2)
        except Exception as err:
            logger.error("Failed to save bot chain: %s", err)

    def _refresh_token(self, bot: dict[str, Any]) -> str:
        """Fetch fresh Channel Access Token via OAuth client credentials."""
        cid = bot.get("channel_id")
        sec = bot.get("channel_secret")
        if not cid or not sec:
            return bot.get("token", "")

        try:
            res = requests.post(
                "https://api.line.me/v2/oauth/accessToken",
                data={
                    "grant_type": "client_credentials",
                    "client_id": cid,
                    "client_secret": sec,
                },
                timeout=15,
            ).json()
            new_token = res.get("access_token")
            if new_token:
                bot["token"] = new_token
                self._save_bot_chain()
                logger.info("Successfully refreshed access token for [%s]", bot.get("name"))
                return new_token
            else:
                logger.error("Failed to refresh token for [%s]: %s", bot.get("name"), res)
        except Exception as err:
            logger.error("Error refreshing token for [%s]: %s", bot.get("name"), err)
        return bot.get("token", "")

    def _get_valid_token(self, bot: dict[str, Any]) -> str:
        """Return cached token or fetch new one if missing."""
        token = bot.get("token")
        if token:
            return token
        return self._refresh_token(bot)

    def _push_messages(self, messages: list[Any]) -> bool:
        """Push messages with automatic sequential failover across the bot chain."""
        start_idx = self._get_active_index()
        total_bots = len(self.bot_chain)

        for idx in range(start_idx, total_bots):
            bot = self.bot_chain[idx]
            bot_name = bot.get("name", f"Bot-{idx}")
            token = self._get_valid_token(bot)
            group_id = bot.get("group_id", "")

            if not group_id or not token:
                logger.warning("Bot [%s] is missing group_id or token – skipping", bot_name)
                continue

            try:
                config = Configuration(access_token=token)
                with ApiClient(config) as api_client:
                    api = MessagingApi(api_client)
                    api.push_message(PushMessageRequest(to=group_id, messages=messages))

                logger.info(
                    "LINE message delivered successfully via [%s] (index: %d, group: %s...)",
                    bot_name,
                    idx,
                    group_id[:8],
                )
                if idx != start_idx:
                    self._save_active_index(idx)
                return True

            except ApiException as exc:
                body_str = str(exc.body) if exc.body else ""
                # Quota exceeded HTTP 429
                if exc.status == 429 or "monthly limit" in body_str.lower():
                    logger.warning(
                        "Quota limit reached for [%s] (HTTP 429: %s). Auto-failing over to next bot in chain...",
                        bot_name,
                        body_str,
                    )
                    next_idx = min(idx + 1, total_bots - 1)
                    self._save_active_index(next_idx)
                    continue

                # Token unauthorized HTTP 401
                elif exc.status == 401 and bot.get("channel_id") and bot.get("channel_secret"):
                    logger.warning("Token unauthorized/expired for [%s] (HTTP 401). Refreshing token...", bot_name)
                    new_token = self._refresh_token(bot)
                    if new_token:
                        try:
                            config = Configuration(access_token=new_token)
                            with ApiClient(config) as api_client:
                                api = MessagingApi(api_client)
                                api.push_message(PushMessageRequest(to=group_id, messages=messages))
                            logger.info("LINE message delivered successfully via [%s] after token refresh", bot_name)
                            if idx != start_idx:
                                self._save_active_index(idx)
                            return True
                        except Exception as retry_err:
                            logger.error("Retry failed for [%s] after token refresh: %s", bot_name, retry_err)
                            continue
                else:
                    logger.error("ApiException while sending via [%s]: status=%s body=%s", bot_name, exc.status, body_str)
                    return False

            except Exception as exc:
                logger.error("Unexpected error sending via [%s]: %s", bot_name, exc, exc_info=True)
                return False

        logger.error("All %d bots in the failover chain have exceeded quota or failed to send!", total_bots)
        return False

    def send_result_image(
        self, name: str, top3: str, bottom2: str, flag: str = "🎯"
    ) -> bool:
        """Generate high-res PNG card, upload to HTTPS host, and push ImageMessage."""
        try:
            image_path = generate_card_image(name, top3, bottom2, flag=flag)
            image_url = upload_card_image(image_path)
            messages = [
                ImageMessage(
                    original_content_url=image_url,
                    preview_image_url=image_url,
                )
            ]
            ok = self._push_messages(messages)
            if ok:
                logger.info("LINE Card ImageMessage sent successfully for %s", name)
                return True
            else:
                logger.warning("Failed to send LINE ImageMessage for %s, falling back to emoji text", name)
                return self.send_result_emoji_text(name, top3, bottom2, flag=flag)
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

            ok = self._push_messages([FlexMessage(alt_text=alt_text, contents=container)])
            if ok:
                logger.info("LINE Combined Flex Message sent successfully for: %s", names_title)
                return True
            return False
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

            ok = self._push_messages([FlexMessage(alt_text=alt_text, contents=container)])
            if ok:
                logger.info("LINE Flex Message sent successfully for %s", name)
                return True
            else:
                fallback_text = f"{flag} {name}\n🔺 3บน: {top3}\n🔻 2ล่าง: {bottom2}"
                return self.send_text(fallback_text)
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
            ok = self._push_messages([TextMessage(text=message)])
            if ok:
                logger.info("LINE text message sent successfully (%d chars)", len(message))
                return True
            return False
        except Exception as exc:
            logger.error("Failed to send LINE text message: %s", exc, exc_info=True)
            return False
