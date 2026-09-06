"""
AI Reasoning Brain.
Processes user prompts using LLM Tool Calling (OpenRouter / Gemini).
Multi-tenant aware: dynamically binds the Telegram user's Facebook Page.
INSTANT EXECUTION MODE: Executes actions immediately on Facebook/Meta without
asking for confirmation every step, while retaining authenticated page state.
"""

import os
import json
import logging
import httpx
import asyncio
from datetime import datetime, timezone
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
You are SocialCommander AI — an autonomous, elite AI executive assistant managing communications across Facebook Pages, Instagram Business, WhatsApp, Gmail, Substack, and n8n.

🟢 CURRENT AUTHENTICATED FACEBOOK PAGE:
• Page Name: {page_name}
• Page ID: {page_id}
• Access Status: FULLY CONNECTED & AUTHENTICATED

CRITICAL OPERATIONAL RULES:
1. ZERO HESITATION & INSTANT ACTION EXECUTION (NEVER ASK QUESTIONS OR CONFIRMATION):
   - When the user gives an order, idea, or request (e.g. post on Facebook, reply to comments, publish an ad, reply to messages, schedule a post, post a reel):
     * NEVER ask for confirmation, NEVER ask if they are sure, and NEVER ask for permission!
     * NEVER say "Shall I proceed?", "Would you like me to publish this?", "Would you like me to write a post?", or "Are you ready?".
     * NEVER just display a draft asking "Do you like this?".
     * If the user provides a brief topic or instruction (e.g. "post about our special offer" or "qoraal ku saabsan adeegyadayada Facebook soo dhig"):
       1) Generate complete, high-converting, polished copy with catchy headline, emojis, line breaks, and hashtags.
       2) CALL THE APPROPRIATE TOOL IMMEDIATELY (e.g. `post_to_facebook`, `publish_facebook_ad_post`, etc.) in the very same response!
     * The tool call runs directly on Meta's live API and publishes it instantly!

2. YOU ARE ALREADY AUTHENTICATED:
   - You ALREADY have the user's Facebook Page ID ({page_id}) and Access Token configured.
   - NEVER ask the user to provide an access token, password, or login.
   - NEVER say "You need to connect to Facebook first". The page is already connected.

3. MULTI-LINGUAL COMMENT & MESSAGE INTELLIGENCE:
   - When reading or replying to customer comments or inbox messages, ALWAYS DETECT the language of the commenter!
   - If a comment is in Somali (e.g. "Waa imisa qiimaha?", "Sidee baan u helaa?", "Mahadsanidiin"), ALWAYS reply in natural, respectful, and culturally authentic Af-Soomaali!
   - If a comment is in English, reply in polite, professional, and friendly English.
   - If a comment is in Arabic (e.g. "كم السعر؟", "شكرا جزيلا"), reply in polite Arabic.
   - If a comment is in Swahili (e.g. "Bei gani?", "Asante"), reply in fluent Swahili.
   - For any other language, identify it and reply in that exact language.
   - CALL `reply_to_facebook_comment` or `ai_reply_to_comment_in_language` IMMEDIATELY to publish the response!

4. LANGUAGE MATCHING:
   - You speak fluent English and Somali (Af-Soomaali). Always respond to the user in the language they speak to you in.
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
        if creds and creds.get("page_id"):
            page_name = creds.get("page_name") or "BUUB CAWL"
            page_id = creds.get("page_id")
        else:
            page_name = "BUUB CAWL"
            page_id = "106972352162498"
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
        Executes orders INSTANTLY without asking for confirmation.
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
                target_media = (media_path if media_path and os.path.exists(media_path) else None) or media_url or args.get("image_url")

                # =========================================================================
                # 1. READ ACTIONS
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
                # 2. INSTANT ACTION EXECUTION (NO INTERMEDIATE ASKING / PROMPT DELAY)
                # =========================================================================
                if func_name == "post_to_facebook":
                    msg_content = args.get("message", "")
                    has_media = bool(target_media or media_path)
                    if has_media:
                        res = await fb.post_photo(image_url=target_media, caption=msg_content)
                    else:
                        res = await fb.post_text(message=msg_content)

                    history.append({
                        "role": "tool",
                        "tool_call_id": tool_call.get("id", "call_fb_post"),
                        "name": func_name,
                        "content": json.dumps(res.model_dump())
                    })
                    return res.format_summary(), None

                elif func_name == "publish_facebook_ad_post":
                    msg_content = args.get("message", "")
                    link = args.get("link", "")
                    cta = args.get("cta_type", "LEARN_MORE").upper()
                    res = await fb.publish_cta_ad_post(
                        message=msg_content,
                        link=link,
                        cta_type=cta,
                        image_url=target_media
                    )
                    history.append({
                        "role": "tool",
                        "tool_call_id": tool_call.get("id", "call_fb_ad"),
                        "name": func_name,
                        "content": json.dumps(res.model_dump())
                    })
                    return res.format_summary(), None

                elif func_name == "create_facebook_ad_campaign":
                    c_name = args.get("name", "New Ad Campaign")
                    obj = args.get("objective", "OUTCOME_TRAFFIC")
                    budget = args.get("daily_budget")
                    res = await fb.create_ad_campaign(name=c_name, objective=obj, daily_budget=budget)
                    history.append({
                        "role": "tool",
                        "tool_call_id": tool_call.get("id", "call_fb_camp"),
                        "name": func_name,
                        "content": json.dumps(res.model_dump())
                    })
                    return res.format_summary(), None

                elif func_name == "reply_to_facebook_message":
                    conv_id = args.get("conversation_id", "")
                    reply_text = args.get("message", "")
                    res = await fb.send_inbox_reply(conversation_id=conv_id, message=reply_text)
                    history.append({
                        "role": "tool",
                        "tool_call_id": tool_call.get("id", "call_fb_reply_msg"),
                        "name": func_name,
                        "content": json.dumps(res.model_dump())
                    })
                    return res.format_summary(), None

                elif func_name in ("reply_to_facebook_comment", "ai_reply_to_comment_in_language"):
                    comment_id = args.get("comment_id", "")
                    reply_text = args.get("reply_message") or args.get("message", "")
                    lang = args.get("detected_language", "")
                    res = await fb.reply_to_comment(comment_id=comment_id, message=reply_text)
                    history.append({
                        "role": "tool",
                        "tool_call_id": tool_call.get("id", "call_fb_reply_comment"),
                        "name": func_name,
                        "content": json.dumps(res.model_dump())
                    })
                    lang_badge = f" ({lang})" if lang else ""
                    return f"🚀 **Replied Instantly to Comment{lang_badge}!**\n\n💬 \"_{reply_text}_\n\n{res.format_summary()}", None

                elif func_name == "schedule_facebook_post":
                    msg_content = args.get("message", "")
                    ts = args.get("publish_timestamp", 0)
                    res = await fb.schedule_post(message=msg_content, publish_timestamp=ts, image_url=target_media)
                    history.append({
                        "role": "tool",
                        "tool_call_id": tool_call.get("id", "call_fb_sched"),
                        "name": func_name,
                        "content": json.dumps(res.model_dump())
                    })
                    return res.format_summary(), None

                elif func_name == "post_video_to_facebook":
                    v_url = args.get("video_url") or target_media
                    v_title = args.get("title", "Video Post")
                    v_desc = args.get("description", "")
                    res = await fb.post_video(video_url_or_path=v_url, title=v_title, description=v_desc)
                    history.append({
                        "role": "tool",
                        "tool_call_id": tool_call.get("id", "call_fb_video"),
                        "name": func_name,
                        "content": json.dumps(res.model_dump())
                    })
                    return res.format_summary(), None

                elif func_name == "moderate_facebook_comment":
                    c_id = args.get("comment_id", "")
                    act = args.get("action", "hide").lower()
                    res = await fb.moderate_comment(comment_id=c_id, action=act)
                    history.append({
                        "role": "tool",
                        "tool_call_id": tool_call.get("id", "call_fb_mod"),
                        "name": func_name,
                        "content": json.dumps(res.model_dump())
                    })
                    return res.format_summary(), None

                elif func_name == "post_to_instagram":
                    caption = args.get("caption", "")
                    res = await self.ig.post_photo(image_url=target_media, caption=caption)
                    return res.format_summary(), None

                elif func_name == "cross_post_meta":
                    caption = args.get("caption", "")
                    has_media = bool(target_media or media_path)
                    fb_res = await fb.post_photo(image_url=target_media, caption=caption) if has_media else await fb.post_text(caption)
                    ig_res = await self.ig.post_photo(image_url=target_media, caption=caption) if self.ig.is_configured() and has_media else None
                    msg_out = f"🌐 **Cross-Posted Instantly:**\n• Facebook: {fb_res.message}"
                    if ig_res:
                        msg_out += f"\n• Instagram: {ig_res.message}"
                    return msg_out, None

                elif func_name == "send_whatsapp_message":
                    recipient = args.get("recipient_phone") or args.get("recipient") or args.get("to", "")
                    body = args.get("message") or args.get("body") or args.get("text", "")
                    res = await self.wa.send_message(recipient_phone=recipient, message=body)
                    return res.format_summary(), None

                elif func_name == "send_email":
                    to_addr = args.get("to") or args.get("recipient") or args.get("email", "")
                    subj = args.get("subject") or "No Subject"
                    body = args.get("body") or args.get("message") or ""
                    res = await self.gmail.send_email(to=to_addr, subject=subj, body=body)
                    return res.format_summary(), None

                elif func_name == "draft_email":
                    to_addr = args.get("to") or args.get("recipient") or ""
                    subj = args.get("subject") or "No Subject"
                    body = args.get("body") or ""
                    res = await self.gmail.create_draft(to=to_addr, subject=subj, body=body)
                    return res.format_summary(), None

                elif func_name == "create_substack_post":
                    title = args.get("title", "")
                    subtitle = args.get("subtitle", "")
                    body = args.get("body", "")
                    res = await self.substack.create_draft(title=title, subtitle=subtitle, body_markdown=body)
                    return res.format_summary(), None

                elif func_name == "post_substack_note":
                    content = args.get("content", "")
                    res = await self.substack.post_note(content=content)
                    return res.format_summary(), None

                elif func_name == "trigger_n8n_automation":
                    wf_target = args.get("workflow_name_or_webhook", "")
                    data_param = args.get("data", {})
                    res = await self.n8n.trigger_webhook(webhook_path_or_url=wf_target, payload=data_param)
                    return res.format_summary(), None

                return f"Action `{func_name}` requested with parameters: {json.dumps(args)}", None

            except Exception as e:
                logger.error(f"Error in AI Brain: {e}", exc_info=True)
                return f"⚠️ Error in AI Brain processing: {str(e)}", None


agent_brain = AgentBrain()
