"""
AI Reasoning Brain.
Processes user prompts using LLM Tool Calling (OpenRouter / Gemini).
Coordinates between Read-Tools (instant response) and Write-Tools (staged for Telegram confirmation).
"""

import json
import httpx
from typing import Dict, Any, List, Optional, Tuple
from ..config.config import config
from ..tools.registry import TOOLS_SCHEMA
from .confirmation_mgr import confirmation_mgr, PendingAction
from ..connectors import (
    FacebookConnector,
    InstagramConnector,
    WhatsAppConnector,
    GmailConnector,
    SubstackConnector,
    N8NBridge
)

import asyncio

SYSTEM_PROMPT = """
You are SocialCommander AI — an elite, personal AI executive assistant that manages the user's communications across:
1. Facebook Pages
2. Instagram Business
3. WhatsApp (Personal Linked Device & Cloud API)
4. Gmail (Read, Draft, Send)
5. Substack Newsletters & Notes
6. n8n Automation Engine

Key Guidelines:
- You speak fluent English and Somali (Af-Soomaali). Always match the language the user speaks.
- BE PROACTIVE, CREATIVE, AND ACTION-ORIENTED:
  When the user asks you to post to Facebook, Instagram, cross-post, send an email, or send a WhatsApp message, DO NOT ask them what to write if you can create it.
  Generate the complete, high-quality post/caption/email/message yourself and CALL THE CORRESPONDING TOOL IMMEDIATELY.
  The tool call will automatically generate a confirmation preview card on Telegram with [Confirm], [Cancel], and [Revise] buttons so the user can verify before anything is published.
- Quality standards:
  - For Facebook/Instagram: Use catchy hooks, formatted line breaks, relevant emojis, and 5-10 high-value hashtags.
  - For Gmail: Use clear, polite, and professional email structure.
  - For WhatsApp: Keep it natural, direct, and concise.
  - For Substack: Write thoughtful, engaging newsletter intros or well-crafted Substack Notes.
- Always invoke the proper tool when the user intends to publish, draft, send, or check information.
- When an attached media URL is present in the prompt, ALWAYS include it in your tool call parameters.
"""


class AgentBrain:
    def __init__(self):
        self.provider = config.LLM_PROVIDER
        self.openrouter_key = config.OPENROUTER_API_KEY
        self.gemini_key = config.GEMINI_API_KEY
        self.model = config.LLM_MODEL
        self.chat_histories: Dict[int, List[Dict[str, Any]]] = {}
        self._chat_locks: Dict[int, asyncio.Lock] = {}

        # Direct connectors for read operations
        self.fb = FacebookConnector()
        self.ig = InstagramConnector()
        self.wa = WhatsAppConnector()
        self.gmail = GmailConnector()
        self.substack = SubstackConnector()
        self.n8n = N8NBridge()

    def _get_lock(self, chat_id: int) -> asyncio.Lock:
        if chat_id not in self._chat_locks:
            self._chat_locks[chat_id] = asyncio.Lock()
        return self._chat_locks[chat_id]

    def get_history(self, chat_id: int) -> List[Dict[str, Any]]:
        if chat_id not in self.chat_histories:
            self.chat_histories[chat_id] = [
                {"role": "system", "content": SYSTEM_PROMPT}
            ]
        return self.chat_histories[chat_id]

    def reset_history(self, chat_id: int):
        self.chat_histories[chat_id] = [
            {"role": "system", "content": SYSTEM_PROMPT}
        ]

    async def _call_llm(self, messages: List[Dict[str, Any]], use_tools: bool = True) -> Dict[str, Any]:
        """Calls OpenRouter or Gemini Chat Completion endpoint."""
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.openrouter_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/socialcommander",
            "X-Title": "SocialCommander AI"
        }

        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.7
        }

        if use_tools:
            payload["tools"] = TOOLS_SCHEMA
            payload["tool_choice"] = "auto"

        last_error = None
        for attempt in range(3):
            try:
                async with httpx.AsyncClient(timeout=45.0) as client:
                    res = await client.post(url, headers=headers, json=payload)
                    if res.status_code == 200:
                        return res.json()
                    elif res.status_code in (500, 502, 503, 504, 429) and attempt < 2:
                        await asyncio.sleep(2.0 * (attempt + 1))
                        continue
                    else:
                        raise RuntimeError(f"LLM API returned error ({res.status_code}): {res.text}")
            except (httpx.ConnectError, httpx.TimeoutException) as net_err:
                last_error = net_err
                if attempt < 2:
                    await asyncio.sleep(2.0 * (attempt + 1))
                    continue
                raise net_err
            except Exception as e:
                last_error = e
                if attempt < 2:
                    await asyncio.sleep(2.0 * (attempt + 1))
                    continue
                raise e

        raise RuntimeError(f"LLM API failed after 3 attempts: {last_error}")

    async def process_user_message(
        self,
        chat_id: int,
        user_text: str,
        media_url: Optional[str] = None,
        media_path: Optional[str] = None
    ) -> Tuple[str, Optional[PendingAction]]:
        """
        Processes a user input message with AI tool calling.
        Returns:
            (reply_text, optional_pending_action)
        """
        lock = self._get_lock(chat_id)
        async with lock:
            history = self.get_history(chat_id)

            prompt = user_text
            if media_url:
                prompt += f"\n[Attached Media URL: {media_url}]"

            history.append({"role": "user", "content": prompt})

            try:
                response = await self._call_llm(history)
                choice = response["choices"][0]
                msg = choice.get("message", {})

                # Check if LLM requested tool calling
                tool_calls = msg.get("tool_calls", [])
                if not tool_calls:
                    content = msg.get("content", "I am ready to assist you.")
                    history.append({"role": "assistant", "content": content})
                    return content, None

                # Handle first tool call
                tool_call = tool_calls[0]
                func_name = tool_call["function"]["name"]
                arguments_raw = tool_call["function"]["arguments"]
                try:
                    args = json.loads(arguments_raw) if isinstance(arguments_raw, str) else arguments_raw
                except Exception:
                    args = {}

                # Append assistant message with tool call to history
                history.append(msg)

                # --- READ ACTIONS (Executed instantly and fed back to LLM) ---
                if func_name == "read_unread_emails":
                    max_res = args.get("max_results", 5)
                    res = await self.gmail.list_unread(max_res)
                    tool_output = json.dumps(res.model_dump())
                    history.append({
                        "role": "tool",
                        "tool_call_id": tool_call.get("id", "call_gmail"),
                        "name": func_name,
                        "content": tool_output
                    })
                    # Re-prompt LLM for summary
                    second_res = await self._call_llm(history, use_tools=False)
                    final_content = second_res["choices"][0]["message"]["content"]
                    history.append({"role": "assistant", "content": final_content})
                    return final_content, None

                elif func_name == "get_social_overview":
                    fb_res = await self.fb.get_recent_posts(3) if self.fb.is_configured() else None
                    ig_res = await self.ig.get_recent_media(3) if self.ig.is_configured() else None
                    sub_res = await self.substack.get_recent_posts(3) if self.substack.is_configured() else None
                    n8n_res = await self.n8n.list_workflows() if self.n8n.is_configured() else None

                    overview_data = {
                        "facebook": fb_res.data if fb_res and fb_res.success else "Unavailable",
                        "instagram": ig_res.data if ig_res and ig_res.success else "Unavailable",
                        "substack": sub_res.data if sub_res and sub_res.success else "Unavailable",
                        "n8n": n8n_res.data if n8n_res and n8n_res.success else "Unavailable"
                    }
                    history.append({
                        "role": "tool",
                        "tool_call_id": tool_call.get("id", "call_overview"),
                        "name": func_name,
                        "content": json.dumps(overview_data)
                    })
                    second_res = await self._call_llm(history, use_tools=False)
                    final_content = second_res["choices"][0]["message"]["content"]
                    history.append({"role": "assistant", "content": final_content})
                    return final_content, None

                # --- WRITE ACTIONS (Require Telegram User Confirmation) ---
                target_media = media_url or args.get("image_url")

                if func_name == "post_to_facebook":
                    msg_content = args.get("message", "")
                    has_media = bool(target_media or media_path)
                    preview = (
                        f"📢 *Preview: Facebook Page Post*\n\n"
                        f"{msg_content}\n\n"
                        f"🖼 *Image Attached:* {'Yes' if has_media else 'No (Text-only)'}\n\n"
                        f"_Tap below to confirm or revise._"
                    )
                    action_type = "post_photo" if has_media else "post_text"
                    pending = confirmation_mgr.create_pending_action(
                        platform="facebook",
                        action_type=action_type,
                        payload={"message": msg_content, "caption": msg_content, "image_url": target_media, "media_path": media_path},
                        preview_text=preview,
                        media_url=target_media,
                        media_path=media_path
                    )
                    return preview, pending

                elif func_name == "post_to_instagram":
                    caption = args.get("caption", "")
                    preview = (
                        f"📸 *Preview: Instagram Post*\n\n"
                        f"{caption}\n\n"
                        f"🖼 *Image URL:* {target_media}\n\n"
                        f"_Tap below to confirm or revise._"
                    )
                    pending = confirmation_mgr.create_pending_action(
                        platform="instagram",
                        action_type="post_photo",
                        payload={"caption": caption, "image_url": target_media, "media_path": media_path},
                        preview_text=preview,
                        media_url=target_media,
                        media_path=media_path
                    )
                    return preview, pending

                elif func_name == "cross_post_meta":
                    caption = args.get("caption", "")
                    preview = (
                        f"🌐 *Preview: Cross-Post (Facebook & Instagram)*\n\n"
                        f"{caption}\n\n"
                        f"🖼 *Media URL:* {target_media}\n\n"
                        f"_Tap below to publish simultaneously._"
                    )
                    pending = confirmation_mgr.create_pending_action(
                        platform="facebook",
                        action_type="post_photo",
                        payload={"caption": caption, "message": caption, "image_url": target_media, "media_path": media_path, "cross_post_ig": True},
                        preview_text=preview,
                        media_url=target_media,
                        media_path=media_path
                    )
                    return preview, pending

                elif func_name == "send_whatsapp_message":
                    recipient = args.get("recipient_phone") or args.get("recipient") or args.get("to", "")
                    body = args.get("message") or args.get("body") or args.get("text", "")
                    preview = (
                        f"💬 *Preview: WhatsApp Message*\n\n"
                        f"👤 *To:* `{recipient}`\n"
                        f"📝 *Message:*\n{body}\n\n"
                        f"_Ready to send. Confirm below:_"
                    )
                    pending = confirmation_mgr.create_pending_action(
                        platform="whatsapp",
                        action_type="send_message",
                        payload={"recipient": recipient, "message": body},
                        preview_text=preview
                    )
                    return preview, pending

                elif func_name == "send_email":
                    to_addr = args.get("to") or args.get("recipient") or args.get("email", "")
                    subj = args.get("subject") or args.get("title") or "No Subject"
                    body = args.get("body") or args.get("message") or args.get("content", "")
                    preview = (
                        f"📧 *Preview: Gmail Outgoing Message*\n\n"
                        f"📬 *To:* `{to_addr}`\n"
                        f"📌 *Subject:* {subj}\n\n"
                        f"📝 *Body:*\n{body}\n\n"
                        f"_Ready to send. Confirm below:_"
                    )
                    pending = confirmation_mgr.create_pending_action(
                        platform="gmail",
                        action_type="send_email",
                        payload={"to": to_addr, "subject": subj, "body": body},
                        preview_text=preview
                    )
                    return preview, pending

                elif func_name == "draft_email":
                    to_addr = args.get("to") or args.get("recipient") or args.get("email", "")
                    subj = args.get("subject") or args.get("title") or "No Subject"
                    body = args.get("body") or args.get("message") or args.get("content", "")
                    preview = (
                        f"📝 *Preview: Gmail Draft*\n\n"
                        f"📬 *To:* `{to_addr}`\n"
                        f"📌 *Subject:* {subj}\n\n"
                        f"📝 *Body:*\n{body}\n\n"
                        f"_Save as draft in Gmail?_"
                    )
                    pending = confirmation_mgr.create_pending_action(
                        platform="gmail",
                        action_type="create_draft",
                        payload={"to": to_addr, "subject": subj, "body": body},
                        preview_text=preview
                    )
                    return preview, pending

                elif func_name == "create_substack_post":
                    title = args.get("title", "")
                    subtitle = args.get("subtitle", "")
                    body = args.get("body", "")
                    preview = (
                        f"📰 *Preview: Substack Newsletter Article*\n\n"
                        f"🏷 *Title:* {title}\n"
                        f"🔹 *Subtitle:* {subtitle}\n\n"
                        f"📖 *Content Preview:*\n{body[:350]}...\n\n"
                        f"_Ready to create draft on Substack._"
                    )
                    pending = confirmation_mgr.create_pending_action(
                        platform="substack",
                        action_type="create_draft",
                        payload={"title": title, "subtitle": subtitle, "body": body},
                        preview_text=preview
                    )
                    return preview, pending

                elif func_name == "post_substack_note":
                    content = args.get("content", "")
                    preview = (
                        f"✍️ *Preview: Substack Note*\n\n"
                        f"{content}\n\n"
                        f"_Publish this Note to Substack?_"
                    )
                    pending = confirmation_mgr.create_pending_action(
                        platform="substack",
                        action_type="post_note",
                        payload={"content": content},
                        preview_text=preview
                    )
                    return preview, pending

                elif func_name == "trigger_n8n_automation":
                    wf_target = args.get("workflow_name_or_webhook", "")
                    data_param = args.get("data", {})
                    preview = (
                        f"⚙️ *Preview: n8n Workflow Trigger*\n\n"
                        f"🔗 *Target:* `{wf_target}`\n"
                        f"📦 *Payload:* `{json.dumps(data_param)}`\n\n"
                        f"_Execute automation?_"
                    )
                    pending = confirmation_mgr.create_pending_action(
                        platform="n8n",
                        action_type="trigger_webhook",
                        payload={"webhook": wf_target, "data": data_param},
                        preview_text=preview
                    )
                    return preview, pending

                # Fallback
                return f"Action `{func_name}` requested with parameters: {json.dumps(args)}", None

            except Exception as e:
                return f"⚠️ Error in AI Brain processing: {str(e)}", None


agent_brain = AgentBrain()
