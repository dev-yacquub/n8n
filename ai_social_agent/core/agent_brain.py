"""
AI Reasoning Brain.
Processes user prompts using LLM Tool Calling (OpenRouter / Gemini).
Multi-tenant aware: dynamically binds the Telegram user's Facebook Page,
coordinates between Read-Tools (instant response) and Write-Tools (staged for Telegram confirmation).
"""

import os
import json
import logging
import httpx
import asyncio
from typing import Dict, Any, List, Optional, Tuple

from ..config.config import config
from ..tools.registry import TOOLS_SCHEMA
from .confirmation_mgr import confirmation_mgr, PendingAction
from .user_db import user_db
from ..connectors import (
    FacebookConnector,
    get_facebook_connector_for_user,
    InstagramConnector,
    WhatsAppConnector,
    GmailConnector,
    SubstackConnector,
    N8NBridge
)

logger = logging.getLogger("SocialCommander.Brain")

SYSTEM_PROMPT_TEMPLATE = """
You are SocialCommander AI — an elite, personal AI executive assistant managing the user's communications across:
1. Facebook Pages (Full management, publishing, post metrics & insights, ads, inbox customer replies, and comment replies)
2. Instagram Business
3. WhatsApp (Personal Linked Device & Cloud API)
4. Gmail (Read, Draft, Send)
5. Substack Newsletters & Notes
6. n8n Automation Engine

Current Active Facebook Page:
• Page Name: {page_name}
• Page ID: {page_id}

Key Guidelines:
- You speak fluent English and Somali (Af-Soomaali). Always match the language the user speaks.
- CRITICAL: MULTI-LINGUAL COMMENT & MESSAGE INTELLIGENCE:
  * When reading or replying to customer comments or inbox messages, ALWAYS DETECT the language of the commenter!
  * If a comment is in Somali (e.g. "Waa imisa qiimaha?", "Sidee baan u helaa?", "Mahadsanidiin"), ALWAYS reply in natural, respectful, and culturally authentic Af-Soomaali!
  * If a comment is in English, reply in polite, professional, and friendly English.
  * If a comment is in Arabic (e.g. "كم السعر؟", "شكرا جزيلا"), reply in polite Arabic.
  * If a comment is in Swahili (e.g. "Bei gani?", "Asante"), reply in fluent Swahili.
  * For any other language, identify it and reply in that exact language.
  * Always use `ai_reply_to_comment_in_language` or `reply_to_facebook_comment` to craft the perfect native response.
- BE PROACTIVE, CREATIVE, AND ACTION-ORIENTED:
  When the user asks you to:
  1. Post to Facebook: Generate engaging copy with a catchy hook, line breaks, emojis, and hashtags, then CALL `post_to_facebook` immediately.
  2. Publish an Ad: Generate compelling marketing ad copy with a clear value proposition, select the most relevant CTA button (e.g. LEARN_MORE, SHOP_NOW, SIGN_UP, CONTACT_US), and CALL `publish_facebook_ad_post` immediately.
  3. Schedule a Post: Calculate the future Unix timestamp and CALL `schedule_facebook_post`.
  4. Post a Video/Reel: Call `post_video_to_facebook` with title and description.
  5. Check Comments & Insights: Call `get_recent_page_comments`, `get_facebook_posts_and_insights`, or `get_facebook_page_analytics`.
  6. Moderate Comments: Call `moderate_facebook_comment` to hide or delete spam/inappropriate comments.
- Confirmation Safety:
  Every publishing, scheduling, or sending action will automatically present a Telegram confirmation card with [Confirm], [Cancel], and [Revise] buttons, allowing the user to review before execution.
- When attached media is provided in the prompt, ALWAYS include it in your tool call parameters.
"""



class AgentBrain:
    def __init__(self):
        self.provider = config.LLM_PROVIDER
        self.openrouter_key = config.OPENROUTER_API_KEY
        self.gemini_key = config.GEMINI_API_KEY
        self.model = config.LLM_MODEL
        self.chat_histories: Dict[int, List[Dict[str, Any]]] = {}
        self._chat_locks: Dict[int, asyncio.Lock] = {}

        # Default platform connectors
        self.ig = InstagramConnector()
        self.wa = WhatsAppConnector()
        self.gmail = GmailConnector()
        self.substack = SubstackConnector()
        self.n8n = N8NBridge()

    def _get_lock(self, chat_id: int) -> asyncio.Lock:
        if chat_id not in self._chat_locks:
            self._chat_locks[chat_id] = asyncio.Lock()
        return self._chat_locks[chat_id]

    def _build_system_prompt(self, chat_id: int) -> str:
        creds = user_db.get_user_credentials(chat_id)
        page_name = creds.get("page_name", "Not Connected") if creds else "Not Connected"
        page_id = creds.get("page_id", "N/A") if creds else "N/A"
        return SYSTEM_PROMPT_TEMPLATE.format(page_name=page_name, page_id=page_id)

    def get_history(self, chat_id: int) -> List[Dict[str, Any]]:
        if chat_id not in self.chat_histories:
            self.chat_histories[chat_id] = [
                {"role": "system", "content": self._build_system_prompt(chat_id)}
            ]
        return self.chat_histories[chat_id]

    def reset_history(self, chat_id: int):
        self.chat_histories[chat_id] = [
            {"role": "system", "content": self._build_system_prompt(chat_id)}
        ]

    async def _call_llm(self, messages: List[Dict[str, Any]], use_tools: bool = True) -> Dict[str, Any]:
        """Calls OpenRouter or Gemini Chat Completion endpoint with exponential backoff."""
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
        Dynamically binds the user's Facebook Page.
        """
        lock = self._get_lock(chat_id)
        async with lock:
            history = self.get_history(chat_id)

            # Update system prompt with active page
            if history and history[0].get("role") == "system":
                history[0]["content"] = self._build_system_prompt(chat_id)

            prompt = user_text
            if media_url:
                prompt += f"\n[Attached Media URL: {media_url}]"

            history.append({"role": "user", "content": prompt})

            # User-specific Facebook connector
            fb = get_facebook_connector_for_user(chat_id)

            try:
                response = await self._call_llm(history)
                choice = response["choices"][0]
                msg = choice.get("message", {})

                tool_calls = msg.get("tool_calls", [])
                if not tool_calls:
                    content = msg.get("content", "I am ready to assist you.")
                    history.append({"role": "assistant", "content": content})
                    return content, None

                # Handle tool call
                tool_call = tool_calls[0]
                func_name = tool_call["function"]["name"]
                arguments_raw = tool_call["function"]["arguments"]
                try:
                    args = json.loads(arguments_raw) if isinstance(arguments_raw, str) else arguments_raw
                except Exception:
                    args = {}

                history.append(msg)

                # =========================================================================
                # READ-ONLY ACTIONS (Executed instantly and fed back to LLM)
                # =========================================================================
                if func_name == "get_facebook_page_overview":
                    res = await fb.get_page_overview()
                    history.append({
                        "role": "tool",
                        "tool_call_id": tool_call.get("id", "call_fb_overview"),
                        "name": func_name,
                        "content": json.dumps(res.model_dump())
                    })
                    second_res = await self._call_llm(history, use_tools=False)
                    final_content = second_res["choices"][0]["message"]["content"]
                    history.append({"role": "assistant", "content": final_content})
                    return final_content, None

                elif func_name == "get_facebook_posts_and_insights":
                    lim = args.get("limit", 5)
                    res = await fb.get_posts_with_insights(limit=lim)
                    history.append({
                        "role": "tool",
                        "tool_call_id": tool_call.get("id", "call_fb_insights"),
                        "name": func_name,
                        "content": json.dumps(res.model_dump())
                    })
                    second_res = await self._call_llm(history, use_tools=False)
                    final_content = second_res["choices"][0]["message"]["content"]
                    history.append({"role": "assistant", "content": final_content})
                    return final_content, None

                elif func_name == "get_facebook_inbox":
                    lim = args.get("limit", 10)
                    unread_only = args.get("unread_only", False)
                    res = await fb.get_conversations(limit=lim, unread_only=unread_only)
                    history.append({
                        "role": "tool",
                        "tool_call_id": tool_call.get("id", "call_fb_inbox"),
                        "name": func_name,
                        "content": json.dumps(res.model_dump())
                    })
                    second_res = await self._call_llm(history, use_tools=False)
                    final_content = second_res["choices"][0]["message"]["content"]
                    history.append({"role": "assistant", "content": final_content})
                    return final_content, None

                elif func_name == "get_conversation_messages":
                    conv_id = args.get("conversation_id", "")
                    lim = args.get("limit", 10)
                    res = await fb.get_conversation_messages(conversation_id=conv_id, limit=lim)
                    history.append({
                        "role": "tool",
                        "tool_call_id": tool_call.get("id", "call_fb_msgs"),
                        "name": func_name,
                        "content": json.dumps(res.model_dump())
                    })
                    second_res = await self._call_llm(history, use_tools=False)
                    final_content = second_res["choices"][0]["message"]["content"]
                    history.append({"role": "assistant", "content": final_content})
                    return final_content, None

                elif func_name == "get_facebook_post_comments":
                    post_id = args.get("post_id", "")
                    lim = args.get("limit", 20)
                    res = await fb.get_post_comments(post_id=post_id, limit=lim)
                    history.append({
                        "role": "tool",
                        "tool_call_id": tool_call.get("id", "call_fb_comments"),
                        "name": func_name,
                        "content": json.dumps(res.model_dump())
                    })
                    second_res = await self._call_llm(history, use_tools=False)
                    final_content = second_res["choices"][0]["message"]["content"]
                    history.append({"role": "assistant", "content": final_content})
                    return final_content, None

                elif func_name == "get_recent_page_comments":
                    lim = args.get("limit", 15)
                    res = await fb.get_recent_page_comments(limit=lim)
                    history.append({
                        "role": "tool",
                        "tool_call_id": tool_call.get("id", "call_fb_recent_comments"),
                        "name": func_name,
                        "content": json.dumps(res.model_dump())
                    })
                    second_res = await self._call_llm(history, use_tools=False)
                    final_content = second_res["choices"][0]["message"]["content"]
                    history.append({"role": "assistant", "content": final_content})
                    return final_content, None

                elif func_name == "get_facebook_page_analytics":
                    period = args.get("period", "day")
                    res = await fb.get_page_insights_summary(period=period)
                    history.append({
                        "role": "tool",
                        "tool_call_id": tool_call.get("id", "call_fb_analytics"),
                        "name": func_name,
                        "content": json.dumps(res.model_dump())
                    })
                    second_res = await self._call_llm(history, use_tools=False)
                    final_content = second_res["choices"][0]["message"]["content"]
                    history.append({"role": "assistant", "content": final_content})
                    return final_content, None

                elif func_name == "read_unread_emails":
                    max_res = args.get("max_results", 5)
                    res = await self.gmail.list_unread(max_res)
                    history.append({
                        "role": "tool",
                        "tool_call_id": tool_call.get("id", "call_gmail"),
                        "name": func_name,
                        "content": json.dumps(res.model_dump())
                    })
                    second_res = await self._call_llm(history, use_tools=False)
                    final_content = second_res["choices"][0]["message"]["content"]
                    history.append({"role": "assistant", "content": final_content})
                    return final_content, None

                elif func_name == "get_social_overview":
                    fb_res = await fb.get_recent_posts(3) if fb.is_configured() else None
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

                # =========================================================================
                # WRITE ACTIONS (Require Telegram Confirmation, Attached with telegram_id)
                # =========================================================================
                target_media = (media_path if media_path and os.path.exists(media_path) else None) or media_url or args.get("image_url")

                if func_name == "post_to_facebook":
                    msg_content = args.get("message", "")
                    has_media = bool(target_media or media_path)
                    preview = (
                        f"📢 *Preview: Facebook Page Post*\n\n"
                        f"{msg_content}\n\n"
                        f"🖼 *Image Attached:* {'Yes' if has_media else 'No (Text-only)'}\n\n"
                        f"_Tap below to confirm and publish._"
                    )
                    action_type = "post_photo" if has_media else "post_text"
                    pending = confirmation_mgr.create_pending_action(
                        platform="facebook",
                        action_type=action_type,
                        payload={"message": msg_content, "caption": msg_content, "image_url": target_media, "media_path": media_path},
                        preview_text=preview,
                        media_url=target_media,
                        media_path=media_path,
                        telegram_id=chat_id
                    )
                    return preview, pending

                elif func_name == "publish_facebook_ad_post":
                    msg_content = args.get("message", "")
                    link = args.get("link", "")
                    cta = args.get("cta_type", "LEARN_MORE").upper()
                    preview = (
                        f"🚀 *Preview: Facebook Call-To-Action Ad Post*\n\n"
                        f"📝 *Ad Copy:*\n{msg_content}\n\n"
                        f"🔗 *Destination Link:* {link}\n"
                        f"🔘 *Action Button:* `[{cta}]`\n"
                        f"🖼 *Image:* {'Attached' if target_media else 'Default Preview'}\n\n"
                        f"_Confirm to publish this ad post to your page feed._"
                    )
                    pending = confirmation_mgr.create_pending_action(
                        platform="facebook",
                        action_type="publish_cta_ad_post",
                        payload={"message": msg_content, "link": link, "cta_type": cta, "image_url": target_media},
                        preview_text=preview,
                        media_url=target_media,
                        telegram_id=chat_id
                    )
                    return preview, pending

                elif func_name == "create_facebook_ad_campaign":
                    c_name = args.get("name", "New Ad Campaign")
                    obj = args.get("objective", "OUTCOME_TRAFFIC")
                    budget = args.get("daily_budget")
                    budget_str = f"${budget}/day" if budget else "Default"
                    preview = (
                        f"📢 *Preview: Meta Ads Marketing Campaign*\n\n"
                        f"🏷 *Campaign Name:* {c_name}\n"
                        f"🎯 *Objective:* `{obj}`\n"
                        f"💰 *Budget:* {budget_str}\n"
                        f"⚙️ *Initial Status:* `PAUSED` (Safe draft)\n\n"
                        f"_Confirm to create this campaign in your Ad Account._"
                    )
                    pending = confirmation_mgr.create_pending_action(
                        platform="facebook",
                        action_type="create_ad_campaign",
                        payload={"name": c_name, "objective": obj, "daily_budget": budget},
                        preview_text=preview,
                        telegram_id=chat_id
                    )
                    return preview, pending

                elif func_name == "reply_to_facebook_message":
                    conv_id = args.get("conversation_id", "")
                    reply_text = args.get("message", "")
                    preview = (
                        f"💬 *Preview: Facebook Customer Message Reply*\n\n"
                        f"🆔 *Conversation Thread:* `{conv_id}`\n"
                        f"📝 *Your Reply:*\n\"{reply_text}\"\n\n"
                        f"_Ready to deliver to the customer. Confirm below:_"
                    )
                    pending = confirmation_mgr.create_pending_action(
                        platform="facebook",
                        action_type="send_inbox_reply",
                        payload={"conversation_id": conv_id, "message": reply_text},
                        preview_text=preview,
                        telegram_id=chat_id
                    )
                    return preview, pending

                elif func_name == "reply_to_facebook_comment":
                    comment_id = args.get("comment_id", "")
                    reply_text = args.get("message", "")
                    preview = (
                        f"💬 *Preview: Reply to Facebook Comment*\n\n"
                        f"🆔 *Comment ID:* `{comment_id}`\n"
                        f"📝 *Your Response:*\n\"{reply_text}\"\n\n"
                        f"_Publish this reply to the comment thread?_"
                    )
                    pending = confirmation_mgr.create_pending_action(
                        platform="facebook",
                        action_type="reply_to_comment",
                        payload={"comment_id": comment_id, "message": reply_text},
                        preview_text=preview,
                        telegram_id=chat_id
                    )
                    return preview, pending

                elif func_name == "ai_reply_to_comment_in_language":
                    comment_id = args.get("comment_id", "")
                    c_text = args.get("comment_text", "")
                    lang = args.get("detected_language", "Auto-detected")
                    reply_msg = args.get("reply_message", "")
                    preview = (
                        f"💬 *Preview: Native Comment Reply*\n\n"
                        f"🗣 *Original Comment:* \"_{c_text}_\n"
                        f"🌐 *Detected Language:* `{lang}`\n"
                        f"📝 *Drafted Response:*\n\"{reply_msg}\"\n\n"
                        f"_Publish this response in the commenter's language?_"
                    )
                    pending = confirmation_mgr.create_pending_action(
                        platform="facebook",
                        action_type="reply_to_comment",
                        payload={"comment_id": comment_id, "message": reply_msg},
                        preview_text=preview,
                        telegram_id=chat_id
                    )
                    return preview, pending

                elif func_name == "schedule_facebook_post":
                    msg_content = args.get("message", "")
                    ts = args.get("publish_timestamp", 0)
                    from datetime import datetime, timezone
                    try:
                        time_str = datetime.fromtimestamp(ts, tz=timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
                    except Exception:
                        time_str = str(ts)
                    preview = (
                        f"⏰ *Preview: Scheduled Facebook Post*\n\n"
                        f"📅 *Scheduled Publish Time:* `{time_str}`\n"
                        f"📝 *Content:*\n{msg_content}\n\n"
                        f"_Confirm scheduling this post on your Facebook Page?_"
                    )
                    pending = confirmation_mgr.create_pending_action(
                        platform="facebook",
                        action_type="schedule_post",
                        payload={"message": msg_content, "publish_timestamp": ts, "image_url": target_media},
                        preview_text=preview,
                        media_url=target_media,
                        telegram_id=chat_id
                    )
                    return preview, pending

                elif func_name == "post_video_to_facebook":
                    v_url = args.get("video_url") or target_media
                    v_title = args.get("title", "Video Post")
                    v_desc = args.get("description", "")
                    preview = (
                        f"🎬 *Preview: Facebook Video / Reel Upload*\n\n"
                        f"🏷 *Title:* {v_title}\n"
                        f"📝 *Description:*\n{v_desc}\n"
                        f"🎥 *Source:* `{v_url}`\n\n"
                        f"_Confirm to upload and publish this video to your page._"
                    )
                    pending = confirmation_mgr.create_pending_action(
                        platform="facebook",
                        action_type="post_video",
                        payload={"video_url": v_url, "title": v_title, "description": v_desc},
                        preview_text=preview,
                        media_url=v_url,
                        media_path=media_path,
                        telegram_id=chat_id
                    )
                    return preview, pending

                elif func_name == "moderate_facebook_comment":
                    c_id = args.get("comment_id", "")
                    act = args.get("action", "hide").lower()
                    action_emoji = "🙈 Hide" if act == "hide" else ("👀 Unhide" if act == "unhide" else "🗑 Delete")
                    preview = (
                        f"🛡 *Preview: Facebook Comment Moderation*\n\n"
                        f"🆔 *Comment ID:* `{c_id}`\n"
                        f"⚡ *Action:* {action_emoji}\n\n"
                        f"_Confirm to execute this moderation action on Facebook?_"
                    )
                    pending = confirmation_mgr.create_pending_action(
                        platform="facebook",
                        action_type="moderate_comment",
                        payload={"comment_id": c_id, "action": act},
                        preview_text=preview,
                        telegram_id=chat_id
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
                        media_path=media_path,
                        telegram_id=chat_id
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
                        media_path=media_path,
                        telegram_id=chat_id
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
                        preview_text=preview,
                        telegram_id=chat_id
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
                        preview_text=preview,
                        telegram_id=chat_id
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
                        preview_text=preview,
                        telegram_id=chat_id
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
                        preview_text=preview,
                        telegram_id=chat_id
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
                        preview_text=preview,
                        telegram_id=chat_id
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
                        preview_text=preview,
                        telegram_id=chat_id
                    )
                    return preview, pending

                return f"Action `{func_name}` requested with parameters: {json.dumps(args)}", None

            except Exception as e:
                logger.error(f"Error in AI Brain: {e}", exc_info=True)
                return f"⚠️ Error in AI Brain processing: {str(e)}", None


agent_brain = AgentBrain()
