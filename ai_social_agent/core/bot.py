"""
Telegram Bot Application.
Interface for controlling Facebook, Instagram, WhatsApp, Gmail, Substack, and n8n.
Uses python-telegram-bot v20+ async architecture.
"""

import os
import logging
import asyncio
from pathlib import Path
from typing import Optional
from telegram import Update, BotCommand
from telegram.constants import ParseMode, ChatAction
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters
)

from ..config.config import config
from .agent_brain import agent_brain
from .confirmation_mgr import confirmation_mgr

logger = logging.getLogger("SocialCommander")
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")


async def safe_reply_text(message, text: str, reply_markup=None):
    """Safely replies with Markdown, automatically falling back to plain text if parsing fails."""
    try:
        return await message.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
    except Exception as e:
        logger.warning(f"Markdown reply failed ({e}), falling back to plain text")
        return await message.reply_text(text, reply_markup=reply_markup)


async def safe_edit_text(query, text: str, reply_markup=None):
    """Safely edits message with Markdown, automatically falling back to plain text if parsing fails."""
    try:
        return await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
    except Exception as e:
        logger.warning(f"Markdown edit failed ({e}), falling back to plain text")
        return await query.edit_message_text(text, reply_markup=reply_markup)


def is_user_authorized(update: Update) -> bool:
    """Restricts bot usage to the configured Telegram user ID if set."""
    if not config.TELEGRAM_ALLOWED_USER_ID:
        return True
    user_id = update.effective_user.id if update.effective_user else None
    return user_id == config.TELEGRAM_ALLOWED_USER_ID


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sends welcome message and platform readiness overview."""
    if not is_user_authorized(update):
        await update.message.reply_text("⛔ Unauthorized access.")
        return

    user_name = update.effective_user.first_name if update.effective_user else "Commander"
    summary = config.get_status_summary()

    def badge(ok: bool) -> str:
        return "🟢 Active" if ok else "⚪ Config Required"

    welcome_text = (
        f"👋 *Salaam {user_name}! Welcome to SocialCommander AI.*\n\n"
        f"I am your autonomous personal assistant controlling your social media, messaging, and newsletters.\n\n"
        f"📡 *Connected Platforms Status:*\n"
        f"• *Facebook Pages:* {badge(summary['facebook'])}\n"
        f"• *Instagram Business:* {badge(summary['instagram'])}\n"
        f"• *WhatsApp Cloud:* {badge(summary['whatsapp'])}\n"
        f"• *Gmail (Read/Send):* {badge(summary['gmail'])}\n"
        f"• *Substack Newsletter:* {badge(summary['substack'])}\n"
        f"• *n8n Automation:* {badge(summary['n8n'])}\n"
        f"• *AI Brain:* {badge(summary['ai_brain'])}\n\n"
        f"💡 *How to use me:*\n"
        f"Simply talk to me in English or Somali!\n\n"
        f"• _\"Post this photo to Instagram and Facebook with a caption about new tech trends\"_\n"
        f"• _\"Summarize my unread Gmail messages\"_\n"
        f"• _\"Send a WhatsApp message to +252... saying the contract is signed\"_\n"
        f"• _\"Draft a Substack newsletter post about AI agents\"_\n\n"
        f"Use /status to re-check connections or /help for more commands."
    )
    await update.message.reply_text(welcome_text, parse_mode=ParseMode.MARKDOWN)


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Runs live connectivity diagnostics across all platform connectors concurrently."""
    if not is_user_authorized(update):
        return

    msg = await safe_reply_text(update.message, "🔍 *Diagnosing all platform connections...*")
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)

    # Perform live checks concurrently
    fb_res, ig_res, wa_res, gm_res, sub_res, n8n_res = await asyncio.gather(
        agent_brain.fb.test_connection(),
        agent_brain.ig.test_connection(),
        agent_brain.wa.test_connection(),
        agent_brain.gmail.test_connection(),
        agent_brain.substack.test_connection(),
        agent_brain.n8n.test_connection()
    )

    report = (
        f"📊 *Platform Connectivity Diagnostic*\n\n"
        f"{fb_res.format_summary()}\n\n"
        f"{ig_res.format_summary()}\n\n"
        f"{wa_res.format_summary()}\n\n"
        f"{gm_res.format_summary()}\n\n"
        f"{sub_res.format_summary()}\n\n"
        f"{n8n_res.format_summary()}"
    )
    if msg:
        await safe_edit_text(msg, report)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Displays command manual and usage examples."""
    if not is_user_authorized(update):
        return

    help_text = (
        f"📖 *SocialCommander Command Manual*\n\n"
        f"🔹 `/start` - Launch or refresh main menu\n"
        f"🔹 `/status` - Live diagnostic test of all platforms (parallel)\n"
        f"🔹 `/clear` - Reset current conversation context\n"
        f"🔹 `/help` - Show this guidance\n\n"
        f"💬 *Example Prompts:*\n"
        f"• *Social Media:* \"Waxaad Facebook iyo Instagram ku qortaa maqaal ku saabsan barashada cilmiga data science\"\n"
        f"• *Photo Posting:* Send an image with caption: \"Publish this to Facebook with an inspiring quote\"\n"
        f"• *Email Management:* \"Check unread emails from the last 24 hours\"\n"
        f"• *Email Sending:* \"Send email to ahmed@example.com with subject Meeting and body See you at 3pm\"\n"
        f"• *Substack:* \"Draft a Substack newsletter post comparing deep learning frameworks\"\n"
        f"• *WhatsApp:* \"Send WhatsApp message to +252615123456 saying I received the invoice\""
    )
    await safe_reply_text(update.message, help_text)


async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Resets chat history with the AI Brain."""
    if not is_user_authorized(update):
        return
    agent_brain.reset_history(update.effective_chat.id)
    await safe_reply_text(update.message, "🧹 *Conversation memory cleared.* Let's start fresh!")


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Routes general user messages to the AI Agent Brain."""
    if not is_user_authorized(update) or not update.message or not update.message.text:
        return

    chat_id = update.effective_chat.id
    user_text = update.message.text.strip()
    await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)

    reply_text, pending_action = await agent_brain.process_user_message(chat_id, user_text)

    if pending_action:
        keyboard = confirmation_mgr.build_keyboard(pending_action.action_id)
        await safe_reply_text(update.message, reply_text, reply_markup=keyboard)
    else:
        await safe_reply_text(update.message, reply_text)


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles incoming photos, caches them locally, and routes to AI Brain."""
    if not is_user_authorized(update) or not update.message or not update.message.photo:
        return

    chat_id = update.effective_chat.id
    caption = update.message.caption or "Publish this photo to Instagram and Facebook"
    await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)

    # Get the highest resolution photo
    photo_file = await update.message.photo[-1].get_file()
    image_url = photo_file.file_path

    # Cache locally in uploads/ for direct binary upload to Facebook
    uploads_dir = Path("uploads")
    uploads_dir.mkdir(exist_ok=True)
    local_path = uploads_dir / f"{update.message.message_id}_{photo_file.file_unique_id}.jpg"
    media_path = None
    try:
        await photo_file.download_to_drive(custom_path=local_path)
        media_path = str(local_path.resolve())
        logger.info(f"Cached Telegram photo locally at: {media_path}")
    except Exception as e:
        logger.warning(f"Could not download photo to local disk: {e}")

    # Public URL for Instagram container ingest if hosted on Render
    public_base = os.getenv("RENDER_EXTERNAL_URL", "https://yacquub-social-commander-agent.onrender.com").rstrip("/")
    public_media_url = f"{public_base}/media/{local_path.name}" if media_path else image_url

    reply_text, pending_action = await agent_brain.process_user_message(
        chat_id=chat_id,
        user_text=caption,
        media_url=public_media_url,
        media_path=media_path
    )

    if pending_action:
        keyboard = confirmation_mgr.build_keyboard(pending_action.action_id)
        await safe_reply_text(update.message, reply_text, reply_markup=keyboard)
    else:
        await safe_reply_text(update.message, reply_text)


async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles interactive confirmation buttons [🚀 Confirm], [❌ Cancel], [✏️ Revise]."""
    query = update.callback_query
    await query.answer()

    data = query.data or ""
    if ":" not in data:
        return

    action_cmd, action_id = data.split(":", 1)

    if action_cmd == "cancel":
        confirmation_mgr.cancel_action(action_id)
        original = query.message.text if query.message else ""
        await safe_edit_text(
            query,
            f"{original}\n\n❌ *Action cancelled by user.*"
        )

    elif action_cmd == "revise":
        original = query.message.text if query.message else ""
        await safe_edit_text(
            query,
            f"{original}\n\n✏️ *Ready for revisions.* Reply with your updated prompt or specific changes."
        )

    elif action_cmd == "confirm":
        original = query.message.text if query.message else ""
        await safe_edit_text(
            query,
            f"{original}\n\n⏳ *Executing action on platform... Please wait.*"
        )
        try:
            result = await confirmation_mgr.execute_action(action_id)
            if query.message:
                await safe_reply_text(query.message, result.format_summary())
        except Exception as e:
            logger.error(f"Error executing action {action_id}: {e}", exc_info=True)
            if query.message:
                await safe_reply_text(query.message, f"❌ *Error executing action:*\n`{str(e)}`")


def build_application() -> Application:
    """Builds and configures the Telegram Application with full concurrent update processing."""
    token = config.TELEGRAM_BOT_TOKEN
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN is not set in configuration or .env")

    # concurrent_updates=True enables asynchronous, non-blocking execution of multiple tasks simultaneously
    app = Application.builder().token(token).concurrent_updates(True).build()

    # Commands
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("platforms", status_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("clear", clear_command))

    # Interactive buttons
    app.add_handler(CallbackQueryHandler(handle_callback_query))

    # Messages
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    return app
