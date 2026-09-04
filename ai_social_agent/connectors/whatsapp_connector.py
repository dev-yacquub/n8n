"""
WhatsApp Connector.
Supports:
1. Linked Device Mode (Baileys Node.js bridge) - Sends from your personal phone (+252 63 745 2784)
   to ANY phone number worldwide without template approvals or sandbox restrictions.
2. Cloud API Mode (Meta Graph API) - Official Meta Cloud API with system user access token.
"""

import httpx
from typing import Optional, Dict, Any
from .base import BaseConnector, ActionResult
from ..config.config import config


class WhatsAppConnector(BaseConnector):
    def __init__(self):
        super().__init__("whatsapp")
        self.mode = config.WHATSAPP_MODE  # "linked_device" or "cloud_api"
        self.bridge_url = config.WHATSAPP_BRIDGE_URL
        self.phone_number_id = config.WHATSAPP_PHONE_NUMBER_ID
        self.access_token = config.WHATSAPP_ACCESS_TOKEN
        self.api_version = config.WHATSAPP_API_VERSION or "v20.0"
        self.default_recipient = config.WHATSAPP_RECIPIENT_PHONE
        self.base_url = f"https://graph.facebook.com/{self.api_version}"

    def is_configured(self) -> bool:
        if self.mode == "linked_device":
            return bool(self.bridge_url)
        return bool(self.phone_number_id and self.access_token)

    async def test_connection(self) -> ActionResult:
        if self.mode == "linked_device":
            return await self._test_linked_device()
        return await self._test_cloud_api()

    async def _test_linked_device(self) -> ActionResult:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.get(f"{self.bridge_url}/status")
                data = res.json()

                if data.get("connected"):
                    user_phone = data.get("user", {}).get("phone", "Connected")
                    return ActionResult(
                        success=True,
                        platform="whatsapp",
                        action="test_connection",
                        message=f"Connected to WhatsApp Linked Device: +{user_phone} (Ready to message any number)",
                        data=data
                    )
                else:
                    qr_url = data.get("qr_url") or f"{self.bridge_url}/qr"
                    return ActionResult(
                        success=False,
                        platform="whatsapp",
                        action="test_connection",
                        message=f"WhatsApp Bridge is running but awaiting QR scan. Open in browser: {qr_url}",
                        error="NOT_LINKED",
                        data=data
                    )
        except Exception as e:
            return ActionResult(
                success=False,
                platform="whatsapp",
                action="test_connection",
                message=f"WhatsApp Bridge is offline on {self.bridge_url}. Start with start_bridge.ps1",
                error=str(e)
            )

    async def _test_cloud_api(self) -> ActionResult:
        if not (self.phone_number_id and self.access_token):
            return ActionResult(
                success=False,
                platform="whatsapp",
                action="test_connection",
                message="WhatsApp Phone Number ID or Access Token is missing.",
                error="UNCONFIGURED"
            )

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                url = f"{self.base_url}/{self.phone_number_id}"
                headers = {"Authorization": f"Bearer {self.access_token}"}
                params = {"fields": "verified_name,display_phone_number,quality_rating"}
                res = await client.get(url, headers=headers, params=params)
                data = res.json()

                if res.status_code == 200 and "id" in data:
                    phone_name = data.get("verified_name") or data.get("display_phone_number", "WhatsApp Account")
                    rating = data.get("quality_rating", "UNKNOWN")
                    return ActionResult(
                        success=True,
                        platform="whatsapp",
                        action="test_connection",
                        message=f"Connected to WhatsApp Business Cloud: {phone_name} (Quality: {rating})",
                        data=data
                    )
                else:
                    err_msg = data.get("error", {}).get("message", res.text)
                    return ActionResult(
                        success=False,
                        platform="whatsapp",
                        action="test_connection",
                        message="WhatsApp Cloud API connection failed.",
                        error=err_msg
                    )
        except Exception as e:
            return ActionResult(
                success=False,
                platform="whatsapp",
                action="test_connection",
                message=f"Exception connecting to WhatsApp Cloud API: {str(e)}",
                error=str(e)
            )

    async def send_message(self, message: str, recipient_phone: Optional[str] = None) -> ActionResult:
        """
        Sends a direct text message to a WhatsApp phone number.
        In linked_device mode: sends directly from your personal phone number to ANY recipient.
        In cloud_api mode: sends from Meta Cloud API number.
        """
        target = recipient_phone or self.default_recipient
        if not target:
            return ActionResult(
                success=False,
                platform="whatsapp",
                action="send_message",
                message="No recipient phone number provided or configured in .env.",
                error="MISSING_RECIPIENT"
            )

        clean_to = "".join(filter(str.isdigit, target))

        if self.mode == "linked_device":
            return await self._send_message_linked(clean_to, message)
        return await self._send_message_cloud(clean_to, message)

    async def _send_message_linked(self, clean_to: str, message: str) -> ActionResult:
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                res = await client.post(
                    f"{self.bridge_url}/send-message",
                    json={"to": clean_to, "message": message}
                )
                data = res.json()

                if res.status_code == 200 and data.get("success"):
                    msg_id = data.get("messageId", "sent")
                    return ActionResult(
                        success=True,
                        platform="whatsapp",
                        action="send_message",
                        message=f"WhatsApp message sent from your personal phone to +{clean_to}! (ID: {msg_id})",
                        data=data
                    )
                else:
                    err = data.get("error", res.text)
                    return ActionResult(
                        success=False,
                        platform="whatsapp",
                        action="send_message",
                        message=f"Failed to send WhatsApp message to +{clean_to}.",
                        error=err
                    )
        except Exception as e:
            return ActionResult(
                success=False,
                platform="whatsapp",
                action="send_message",
                message=f"Error reaching WhatsApp bridge at {self.bridge_url}.",
                error=str(e)
            )

    async def _send_message_cloud(self, clean_to: str, message: str) -> ActionResult:
        url = f"{self.base_url}/{self.phone_number_id}/messages"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": clean_to,
            "type": "text",
            "text": {
                "preview_url": True,
                "body": message
            }
        }

        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                res = await client.post(url, headers=headers, json=payload)
                data = res.json()

                if res.status_code in (200, 201) and "messages" in data:
                    msg_id = data["messages"][0]["id"]
                    return ActionResult(
                        success=True,
                        platform="whatsapp",
                        action="send_message",
                        message=f"WhatsApp message sent via Cloud API to +{clean_to}! (ID: {msg_id})",
                        data={"message_id": msg_id, "recipient": clean_to}
                    )
                else:
                    err_msg = data.get("error", {}).get("message", res.text)
                    return ActionResult(
                        success=False,
                        platform="whatsapp",
                        action="send_message",
                        message=f"Failed to send WhatsApp message to +{clean_to}.",
                        error=err_msg
                    )
        except Exception as e:
            return ActionResult(
                success=False,
                platform="whatsapp",
                action="send_message",
                message="Exception while sending WhatsApp message via Cloud API.",
                error=str(e)
            )

    async def send_image(self, image_url: str, caption: Optional[str] = None, recipient_phone: Optional[str] = None) -> ActionResult:
        """Sends an image via WhatsApp."""
        target = recipient_phone or self.default_recipient
        if not target:
            return ActionResult(
                success=False,
                platform="whatsapp",
                action="send_image",
                message="No recipient phone number provided or configured.",
                error="MISSING_RECIPIENT"
            )

        clean_to = "".join(filter(str.isdigit, target))

        if self.mode == "linked_device":
            try:
                async with httpx.AsyncClient(timeout=35.0) as client:
                    res = await client.post(
                        f"{self.bridge_url}/send-image",
                        json={"to": clean_to, "imageUrl": image_url, "caption": caption or ""}
                    )
                    data = res.json()
                    if res.status_code == 200 and data.get("success"):
                        return ActionResult(
                            success=True,
                            platform="whatsapp",
                            action="send_image",
                            message=f"WhatsApp image sent from your phone to +{clean_to}!",
                            data=data
                        )
                    return ActionResult(
                        success=False,
                        platform="whatsapp",
                        action="send_image",
                        message=f"Failed to send image to +{clean_to}.",
                        error=data.get("error", res.text)
                    )
            except Exception as e:
                return ActionResult(
                    success=False,
                    platform="whatsapp",
                    action="send_image",
                    message="Error connecting to WhatsApp bridge.",
                    error=str(e)
                )

        # Cloud API fallback
        url = f"{self.base_url}/{self.phone_number_id}/messages"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
        image_obj: Dict[str, Any] = {"link": image_url}
        if caption:
            image_obj["caption"] = caption

        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": clean_to,
            "type": "image",
            "image": image_obj
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                res = await client.post(url, headers=headers, json=payload)
                data = res.json()

                if res.status_code in (200, 201) and "messages" in data:
                    msg_id = data["messages"][0]["id"]
                    return ActionResult(
                        success=True,
                        platform="whatsapp",
                        action="send_image",
                        message=f"WhatsApp image sent via Cloud API to +{clean_to}! Message ID: {msg_id}",
                        data={"message_id": msg_id}
                    )
                else:
                    err_msg = data.get("error", {}).get("message", res.text)
                    return ActionResult(
                        success=False,
                        platform="whatsapp",
                        action="send_image",
                        message=f"Failed to send WhatsApp image to +{clean_to}.",
                        error=err_msg
                    )
        except Exception as e:
            return ActionResult(
                success=False,
                platform="whatsapp",
                action="send_image",
                message="Exception sending WhatsApp image.",
                error=str(e)
            )
