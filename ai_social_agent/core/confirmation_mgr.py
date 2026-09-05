"""
Confirmation Manager for Human-In-The-Loop action execution.
Stores pending actions with UUIDs and provides Telegram Inline Keyboards.
Executes confirmed actions safely.
"""

import uuid
import time
from typing import Dict, Any, Optional, Callable
from dataclasses import dataclass, field
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from ..connectors import (
    FacebookConnector,
    InstagramConnector,
    WhatsAppConnector,
    GmailConnector,
    SubstackConnector,
    N8NBridge,
    ActionResult
)


@dataclass
class PendingAction:
    action_id: str
    platform: str
    action_type: str
    payload: Dict[str, Any]
    preview_text: str
    created_at: float = field(default_factory=time.time)
    media_url: Optional[str] = None
    media_path: Optional[str] = None


class ConfirmationManager:
    def __init__(self):
        self._pending: Dict[str, PendingAction] = {}
        # Instantiate connectors
        self.fb = FacebookConnector()
        self.ig = InstagramConnector()
        self.wa = WhatsAppConnector()
        self.gmail = GmailConnector()
        self.substack = SubstackConnector()
        self.n8n = N8NBridge()

    def create_pending_action(
        self,
        platform: str,
        action_type: str,
        payload: Dict[str, Any],
        preview_text: str,
        media_url: Optional[str] = None,
        media_path: Optional[str] = None
    ) -> PendingAction:
        """Stores a new action requiring user confirmation."""
        action_id = str(uuid.uuid4())[:8]
        pending = PendingAction(
            action_id=action_id,
            platform=platform.lower(),
            action_type=action_type,
            payload=payload,
            preview_text=preview_text,
            media_url=media_url,
            media_path=media_path
        )
        self._pending[action_id] = pending
        return pending

    def get_pending(self, action_id: str) -> Optional[PendingAction]:
        return self._pending.get(action_id)

    def cancel_action(self, action_id: str) -> bool:
        if action_id in self._pending:
            del self._pending[action_id]
            return True
        return False

    def build_keyboard(self, action_id: str) -> InlineKeyboardMarkup:
        """Constructs Telegram Inline Keyboard for the pending action."""
        keyboard = [
            [
                InlineKeyboardButton("🚀 Confirm & Publish", callback_data=f"confirm:{action_id}"),
                InlineKeyboardButton("❌ Cancel", callback_data=f"cancel:{action_id}")
            ],
            [
                InlineKeyboardButton("✏️ Revise / Edit", callback_data=f"revise:{action_id}")
            ]
        ]
        return InlineKeyboardMarkup(keyboard)

    async def execute_action(self, action_id: str) -> ActionResult:
        """Executes the confirmed action on the target platform."""
        action = self._pending.get(action_id)
        if not action:
            return ActionResult(
                success=False,
                platform="unknown",
                action="execute",
                message="Action expired or already processed.",
                error="EXPIRED"
            )

        platform = action.platform
        atype = action.action_type
        payload = action.payload

        result: ActionResult

        try:
            # 1. Facebook
            if platform == "facebook":
                if atype == "post_text":
                    result = await self.fb.post_text(payload.get("message") or payload.get("caption", ""))
                elif atype == "post_photo":
                    img = (action.media_path if action.media_path and os.path.exists(action.media_path) else None) or action.media_url or payload.get("image_url", "")
                    caption = payload.get("caption") or payload.get("message", "")
                    result = await self.fb.post_photo(
                        image_url=img,
                        caption=caption
                    )
                    # Cross-post to Instagram if flagged
                    if payload.get("cross_post_ig") and self.ig.is_configured():
                        ig_res = await self.ig.post_photo(image_url=img, caption=caption)
                        if ig_res.success:
                            result.message += f"\n📸 Instagram: {ig_res.message}"
                        else:
                            result.message += f"\n⚠️ Instagram: {ig_res.error or ig_res.message}"
                else:
                    result = ActionResult(success=False, platform="facebook", action=atype, message=f"Unknown action: {atype}")

            # 2. Instagram
            elif platform == "instagram":
                if atype == "post_photo":
                    img = (action.media_path if action.media_path and os.path.exists(action.media_path) else None) or action.media_url or payload.get("image_url", "")
                    caption = payload.get("caption") or payload.get("message", "")
                    result = await self.ig.post_photo(
                        image_url=img,
                        caption=caption
                    )
                else:
                    result = ActionResult(success=False, platform="instagram", action=atype, message=f"Unknown action: {atype}")

            # 3. WhatsApp
            elif platform == "whatsapp":
                if atype == "send_message":
                    recipient = payload.get("recipient") or payload.get("recipient_phone") or payload.get("to", "")
                    msg_text = payload.get("message") or payload.get("body") or payload.get("text", "")
                    result = await self.wa.send_message(
                        recipient_phone=recipient,
                        message=msg_text
                    )
                elif atype == "send_image":
                    recipient = payload.get("recipient") or payload.get("recipient_phone") or payload.get("to", "")
                    img = (action.media_path if action.media_path and os.path.exists(action.media_path) else None) or action.media_url or payload.get("image_url", "")
                    result = await self.wa.send_image(
                        recipient_phone=recipient,
                        image_url=img,
                        caption=payload.get("caption") or payload.get("message")
                    )
                else:
                    result = ActionResult(success=False, platform="whatsapp", action=atype, message=f"Unknown action: {atype}")

            # 4. Gmail
            elif platform == "gmail":
                to_addr = payload.get("to") or payload.get("recipient") or payload.get("email", "")
                subj = payload.get("subject") or "No Subject"
                body_text = payload.get("body") or payload.get("message") or payload.get("text", "")
                if atype == "send_email":
                    result = await self.gmail.send_email(
                        to=to_addr,
                        subject=subj,
                        body=body_text,
                        html_body=payload.get("html_body")
                    )
                elif atype == "create_draft":
                    result = await self.gmail.create_draft(
                        to=to_addr,
                        subject=subj,
                        body=body_text
                    )
                else:
                    result = ActionResult(success=False, platform="gmail", action=atype, message=f"Unknown action: {atype}")

            # 5. Substack
            elif platform == "substack":
                if atype == "create_draft":
                    result = await self.substack.create_draft(
                        title=payload.get("title", ""),
                        subtitle=payload.get("subtitle", ""),
                        body_markdown=payload.get("body", "")
                    )
                elif atype == "post_note":
                    result = await self.substack.post_note(payload.get("content", ""))
                else:
                    result = ActionResult(success=False, platform="substack", action=atype, message=f"Unknown action: {atype}")

            # 6. n8n
            elif platform == "n8n":
                result = await self.n8n.trigger_webhook(
                    webhook_path_or_url=payload.get("webhook", ""),
                    payload=payload.get("data", {})
                )

            else:
                result = ActionResult(
                    success=False,
                    platform=platform,
                    action=atype,
                    message=f"Unsupported platform: {platform}"
                )

        except Exception as e:
            result = ActionResult(
                success=False,
                platform=platform,
                action=atype,
                message=f"Error executing action: {str(e)}",
                error=str(e)
            )

        # Remove from pending on completion
        del self._pending[action_id]
        return result


confirmation_mgr = ConfirmationManager()
