"""
Telegram Bot Application for Multi-Tenant Facebook Page AI Agent.
Enables every Telegram user to independently connect their Facebook account,
manage their Facebook Page, collect post insights, respond to customer messages,
and publish ad posts or campaigns.
Uses python-telegram-bot v21+ async architecture.
"""

import os
import logging
import asyncio
from pathlib import Path
from typing import Optional, List
from telegram import Update, BotCommand, InlineKeyboardButton, InlineKeyboardMarkup
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
from .user_db import user_db
from ..connectors import FacebookConnector, get_facebook_connector_for_user

logger = logging.getLogger("SocialCommander.Bot")
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")


async def safe_reply_text(message, text: str, reply_markup=None):
    """Safely replies with Markdown, falling back to plain text if markdown formatting fails."""
    try:
        return await message.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
    except Exception as e:
        logger.warning(f"Markdown reply failed ({e}), falling back to plain text")
        return await message.reply_text(text, reply_markup=reply_markup)


async def safe_edit_text(query, text: str, reply_markup=None):
    """Safely edits message with Markdown, falling back to plain text if markdown formatting fails."""
    try:
        return await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
    except Exception as e:
        logger.warning(f"Markdown edit failed ({e}), falling back to plain text")
        return await query.edit_message_text(text, reply_markup=reply_markup)


def is_user_authorized(update: Update) -> bool:
    """Checks if Telegram user is allowed. If TELEGRAM_ALLOWED_USER_ID is unset, all users are allowed."""
    if not config.TELEGRAM_ALLOWED_USER_ID:
        return True
    user_id = update.effective_user.id if update.effective_user else None
    return user_id == config.TELEGRAM_ALLOWED_USER_ID


def build_main_dashboard_keyboard(is_connected: bool) -> InlineKeyboardMarkup:
    """Builds interactive quick-action buttons for the main dashboard."""
    if is_connected:
        keyboard = [
            [
                InlineKeyboardButton("📊 Page Profile", callback_data="btn_overview"),
                InlineKeyboardButton("📝 Create Post", callback_data="btn_create_post")
            ],
            [
                InlineKeyboardButton("📬 Inbox Messages", callback_data="btn_inbox"),
                InlineKeyboardButton("🚀 Publish Ad", callback_data="btn_ad")
            ],
            [
                InlineKeyboardButton("📈 Post Insights", callback_data="btn_insights"),
                InlineKeyboardButton("🔄 Switch Page", callback_data="btn_pages")
            ],
            [
                InlineKeyboardButton("🔍 Connectivity Check", callback_data="btn_status")
            ]
        ]
    else:
        keyboard = [
            [
                InlineKeyboardButton("🔑 Connect Facebook Page", callback_data="btn_connect")
            ],
            [
                InlineKeyboardButton("📖 Help & Setup Guide", callback_data="btn_help"),
                InlineKeyboardButton("🔍 Connectivity Check", callback_data="btn_status")
            ]
        ]
    return InlineKeyboardMarkup(keyboard)


# =============================================================================
# COMMAND HANDLERS
# =============================================================================

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sends welcome message, connection status, and interactive dashboard."""
    if not is_user_authorized(update):
        await update.message.reply_text("⛔ Unauthorized access.")
        return

    user = update.effective_user
    telegram_id = user.id
    user_name = user.first_name or "Commander"
    username = user.username

    # Ensure user is recorded in SQLite
    user_db.register_or_update_user(telegram_id, username, user_name)

    creds = user_db.get_user_credentials(telegram_id)
    is_connected = bool(creds and creds.get("page_id"))

    if is_connected:
        page_name = creds.get("page_name", "Connected Page")
        page_id = creds.get("page_id", "N/A")
        welcome_text = (
            f"👋 *Salaam {user_name}! Welcome back to SocialCommander AI.*\n\n"
            f"🟢 *Active Facebook Page:* `{page_name}`\n"
            f"🆔 *Page ID:* `{page_id}`\n\n"
            f"💡 *What can I do for you today?*\n"
            f"• _\"Qoraal cusub Facebook iigu daabac oo ku saabsan barnaamijyadayada cusub\"_\n"
            f"• _\"Show my Facebook inbox messages and customer inquiries\"_\n"
            f"• _\"Create an ad post with a Learn More button linking to https://mysite.com\"_\n"
            f"• _\"How did my latest 3 posts perform?\"_\n\n"
            f"Use the buttons below or simply type in English or Somali!"
        )
    else:
        welcome_text = (
            f"👋 *Salaam {user_name}! Welcome to SocialCommander AI.*\n\n"
            f"I am your autonomous personal AI assistant that manages your **Facebook Page**, "
            f"responds to customer messages, gathers post metrics, and publishes ads.\n\n"
            f"⚠️ *No Facebook Page Connected Yet.*\n"
            f"Every Telegram user can independently connect their own Facebook account!\n\n"
            f"👉 Tap *Connect Facebook Page* below or type `/connect` to link your page in 30 seconds."
        )

    await safe_reply_text(update.message, welcome_text, reply_markup=build_main_dashboard_keyboard(is_connected))


async def connect_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Initiates interactive Facebook Token connection wizard."""
    if not is_user_authorized(update):
        return

    context.user_data["waiting_for_fb_token"] = True

    msg = (
        f"🔑 *Connect Your Facebook Page*\n\n"
        f"Please send your **Facebook Access Token**.\n\n"
        f"📌 *Supported Tokens:*\n"
        f"1. **User Access Token**: I will automatically detect all Facebook Pages you manage and let you choose which one to manage.\n"
        f"2. **Page Access Token**: Directly connects that specific Facebook Page.\n\n"
        f"🛠 *How to get your token:* [Meta Graph API Explorer](https://developers.facebook.com/tools/explorer/)\n"
        f"Recommended permissions:\n"
        f"`pages_manage_posts`, `pages_read_engagement`, `pages_show_list`, `pages_messaging`, `pages_read_user_content`\n\n"
        f"👇 _Paste your access token below (or type /cancel to abort):_"
    )
    await safe_reply_text(update.message, msg)


async def pages_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lists all Facebook Pages connected by this user and allows switching."""
    if not is_user_authorized(update):
        return

    telegram_id = update.effective_user.id
    pages = user_db.list_user_pages(telegram_id)

    if not pages:
        await safe_reply_text(
            update.message,
            "⚠️ *No Facebook Pages found for your account.*\nUse `/connect` to link your Facebook Page first."
        )
        return

    buttons = []
    lines = ["📄 *Your Connected Facebook Pages:*\n"]
    for p in pages:
        p_id = p["page_id"]
        p_name = p["page_name"]
        is_active = bool(p.get("is_active"))
        badge = "🟢 (Active)" if is_active else "⚪"
        lines.append(f"{badge} *{p_name}* (`{p_id}`)")
        btn_text = f"{'✅ ' if is_active else '👉 '} {p_name}"
        buttons.append([InlineKeyboardButton(btn_text, callback_data=f"select_page:{p_id}")])

    lines.append("\n_Tap any page below to switch active management:_")
    keyboard = InlineKeyboardMarkup(buttons)
    await safe_reply_text(update.message, "\n".join(lines), reply_markup=keyboard)


async def inbox_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Fetches Facebook Page Inbox customer conversations."""
    if not is_user_authorized(update):
        return

    telegram_id = update.effective_user.id
    fb = get_facebook_connector_for_user(telegram_id)
    if not fb.is_configured():
        await safe_reply_text(
            update.message,
            "⚠️ *Facebook Page not connected.* Please run `/connect` first."
        )
        return

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
    res = await fb.get_conversations(limit=5)
    await safe_reply_text(update.message, res.message)


async def insights_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Fetches recent posts and performance metrics."""
    if not is_user_authorized(update):
        return

    telegram_id = update.effective_user.id
    fb = get_facebook_connector_for_user(telegram_id)
    if not fb.is_configured():
        await safe_reply_text(
            update.message,
            "⚠️ *Facebook Page not connected.* Please run `/connect` first."
        )
        return

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
    res = await fb.get_posts_with_insights(limit=5)
    await safe_reply_text(update.message, res.message)


async def ad_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Provides guidance or templates for publishing ads and CTA posts."""
    if not is_user_authorized(update):
        return

    msg = (
        f"🚀 *Facebook Advertising & Sponsored Posts*\n\n"
        f"You can create two types of ads through this AI agent:\n\n"
        f"1️⃣ *Call-To-Action (CTA) Page Feed Ad Post:*\n"
        f"Publishes an action-driven post with official buttons like `[Shop Now]`, `[Learn More]`, `[Sign Up]`, or `[Contact Us]`.\n"
        f"👉 *Example:* _\"Create a Facebook ad post for our 50% summer discount with a Shop Now button to https://myshop.com\"_\n\n"
        f"2️⃣ *Meta Marketing API Ad Campaign:*\n"
        f"Creates an official campaign in your Ad Account (`act_XXXXXXXXX`).\n"
        f"👉 *Example:* _\"Create a traffic ad campaign named Summer Promo with a $15 daily budget\"_\n\n"
        f"Just tell me what product or offer you want to promote, and I will write the copy and build the ad for you!"
    )
    await safe_reply_text(update.message, msg)


async def disconnect_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Unlinks stored Facebook tokens and pages for this Telegram user."""
    if not is_user_authorized(update):
        return

    telegram_id = update.effective_user.id
    user_db.disconnect_user(telegram_id)
    await safe_reply_text(
        update.message,
        "🗑 *Facebook account disconnected.* All stored tokens and pages for your Telegram user have been deleted.\n"
        "Use `/connect` whenever you wish to connect again!"
    )


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Runs live connectivity diagnostics across configured platforms."""
    if not is_user_authorized(update):
        return

    telegram_id = update.effective_user.id
    fb = get_facebook_connector_for_user(telegram_id)

    msg = await safe_reply_text(update.message, "🔍 *Diagnosing connections...*")
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)

    fb_res, ig_res, wa_res, gm_res, sub_res, n8n_res = await asyncio.gather(
        fb.test_connection(),
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
        f"🔹 `/start` - Launch main menu & interactive dashboard\n"
        f"🔹 `/connect` - Connect Facebook Page with Access Token\n"
        f"🔹 `/pages` - View and switch between your managed Facebook Pages\n"
        f"🔹 `/inbox` - Check Facebook Page customer conversations\n"
        f"🔹 `/insights` - Check post metrics, likes, and reach\n"
        f"🔹 `/ad` - Guide to publishing Facebook CTA ads and campaigns\n"
        f"🔹 `/disconnect` - Unlink Facebook account\n"
        f"🔹 `/status` - Live diagnostic test\n"
        f"🔹 `/clear` - Reset chat history with AI\n\n"
        f"💬 *Natural Language Prompts (English & Somali):*\n"
        f"• *Post to Page:* \"Qoraal Facebook u samee oo ku saabsan faa'iidooyinka AI\"\n"
        f"• *Photo Posting:* Send an image with caption: \"Publish this photo to Facebook\"\n"
        f"• *Inbox Messages:* \"Check my Facebook messages and tell me who asked questions\"\n"
        f"• *Reply to Customer:* \"Reply to the message from Ahmed saying we will deliver tomorrow\"\n"
        f"• *Publish Ad:* \"Create an ad for our course with Learn More button linking to https://edu.com\"\n"
        f"• *Post Analytics:* \"How did my latest Facebook posts perform?\""
    )
    await safe_reply_text(update.message, help_text)


async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Resets chat history with the AI Brain."""
    if not is_user_authorized(update):
        return
    agent_brain.reset_history(update.effective_chat.id)
    await safe_reply_text(update.message, "🧹 *Conversation memory cleared.* Let's start fresh!")


# =============================================================================
# MESSAGE & PHOTO HANDLERS
# =============================================================================

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Routes incoming text: token wizard or AI reasoning brain."""
    if not is_user_authorized(update) or not update.message or not update.message.text:
        return

    chat_id = update.effective_chat.id
    user_text = update.message.text.strip()
    user = update.effective_user

    # 1. Handle Facebook Token Connection Wizard
    if context.user_data.get("waiting_for_fb_token"):
        if user_text.lower() in ("/cancel", "cancel"):
            context.user_data["waiting_for_fb_token"] = False
            await safe_reply_text(update.message, "❌ Token setup cancelled.")
            return

        # User submitted token
        await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
        validation = await FacebookConnector.validate_token(user_text)

        if not validation.success:
            await safe_reply_text(
                update.message,
                f"❌ *Token Validation Failed:*\n{validation.error or validation.message}\n\n"
                f"Please ensure your token is active and has required permissions, then try again or type `/cancel`."
            )
            return

        context.user_data["waiting_for_fb_token"] = False
        data = validation.data or {}
        pages = data.get("pages", [])

        if not pages and data.get("token_type") == "user_no_pages":
            await safe_reply_text(
                update.message,
                "⚠️ Valid Facebook user token, but no managed Facebook Pages were found for this account.\n"
                "Please create a Facebook Page first or use a Page Access Token."
            )
            return

        # Save pages to database
        active_page = user_db.save_user_token_and_pages(
            telegram_id=chat_id,
            user_token=user_text,
            pages=pages,
            username=user.username,
            first_name=user.first_name
        )

        if len(pages) > 1:
            buttons = [
                [InlineKeyboardButton(f"📄 {p.get('name')}", callback_data=f"select_page:{p.get('id')}")]
                for p in pages
            ]
            keyboard = InlineKeyboardMarkup(buttons)
            await safe_reply_text(
                update.message,
                f"✅ *Facebook Token Validated!*\n"
                f"Found {len(pages)} managed Facebook Pages.\n\n"
                f"👉 Tap the page you want to manage:",
                reply_markup=keyboard
            )
        else:
            p_name = active_page.get("name") if active_page else "Facebook Page"
            p_id = active_page.get("id") if active_page else "N/A"
            p_cat = active_page.get("category") if active_page else "General"
            await safe_reply_text(
                update.message,
                f"🎉 *Facebook Page Connected Successfully!*\n\n"
                f"📄 *Page:* {p_name}\n"
                f"🆔 *Page ID:* `{p_id}`\n"
                f"🏷 *Category:* {p_cat}\n\n"
                f"Your AI agent is now ready to manage your page, publish posts, reply to messages, and run ads!",
                reply_markup=build_main_dashboard_keyboard(True)
            )
        return

    # 2. General AI Agent Message Processing
    await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
    reply_text, pending_action = await agent_brain.process_user_message(chat_id, user_text)

    if pending_action:
        keyboard = confirmation_mgr.build_keyboard(pending_action.action_id)
        await safe_reply_text(update.message, reply_text, reply_markup=keyboard)
    else:
        await safe_reply_text(update.message, reply_text)


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles incoming photos, caches locally, and routes to AI Brain."""
    if not is_user_authorized(update) or not update.message or not update.message.photo:
        return

    chat_id = update.effective_chat.id
    caption = update.message.caption or "Publish this photo to Facebook Page"
    await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)

    # Get highest resolution photo
    photo_file = await update.message.photo[-1].get_file()
    image_url = photo_file.file_path

    # Cache locally in config.UPLOADS_DIR
    uploads_dir = config.UPLOADS_DIR
    local_path = uploads_dir / f"{update.message.message_id}_{photo_file.file_unique_id}.jpg"
    media_path = None
    try:
        await photo_file.download_to_drive(custom_path=local_path)
        media_path = str(local_path.resolve())
        logger.info(f"Cached Telegram photo locally at: {media_path}")
    except Exception as e:
        logger.warning(f"Could not download photo to local disk: {e}")

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


# =============================================================================
# CALLBACK QUERY HANDLER
# =============================================================================

async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles inline buttons for confirmations, page switching, and quick actions."""
    query = update.callback_query
    await query.answer()

    data = query.data or ""
    chat_id = update.effective_chat.id

    # 1. Page Selection
    if data.startswith("select_page:"):
        page_id = data.split(":", 1)[1]
        ok = user_db.set_active_page(chat_id, page_id)
        if ok:
            creds = user_db.get_user_credentials(chat_id)
            page_name = creds.get("page_name", "Selected Page") if creds else "Selected Page"
            await safe_edit_text(
                query,
                f"✅ *Active Facebook Page Updated!*\n\n"
                f"📄 *Page:* {page_name}\n"
                f"🆔 *ID:* `{page_id}`\n\n"
                f"You can now manage this page!",
                reply_markup=build_main_dashboard_keyboard(True)
            )
        else:
            await safe_edit_text(query, "❌ Could not activate selected page.")
        return

    # 2. Quick Dashboard Buttons
    if data == "btn_connect":
        context.user_data["waiting_for_fb_token"] = True
        await safe_reply_text(
            query.message,
            "🔑 *Paste your Facebook Access Token below (or /cancel):*"
        )
        return

    elif data == "btn_overview":
        fb = get_facebook_connector_for_user(chat_id)
        await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
        res = await fb.get_page_overview()
        await safe_reply_text(query.message, res.message)
        return

    elif data == "btn_inbox":
        fb = get_facebook_connector_for_user(chat_id)
        await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
        res = await fb.get_conversations(limit=5)
        await safe_reply_text(query.message, res.message)
        return

    elif data == "btn_insights":
        fb = get_facebook_connector_for_user(chat_id)
        await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
        res = await fb.get_posts_with_insights(limit=5)
        await safe_reply_text(query.message, res.message)
        return

    elif data == "btn_create_post":
        await safe_reply_text(
            query.message,
            "✍️ *Ready to post!*\nSimply type your post idea or attach an image with a caption.\n"
            "_Example:_ \"Write a post announcing our special weekend offers!\""
        )
        return

    elif data == "btn_ad":
        await ad_command(update, context)
        return

    elif data == "btn_pages":
        await pages_command(update, context)
        return

    elif data == "btn_status":
        await status_command(update, context)
        return

    elif data == "btn_help":
        await help_command(update, context)
        return

    # 3. Action Confirmations
    if ":" in data:
        action_cmd, action_id = data.split(":", 1)

        if action_cmd == "cancel":
            confirmation_mgr.cancel_action(action_id)
            original = query.message.text if query.message else ""
            await safe_edit_text(query, f"{original}\n\n❌ *Action cancelled by user.*")

        elif action_cmd == "revise":
            original = query.message.text if query.message else ""
            await safe_edit_text(query, f"{original}\n\n✏️ *Ready for revisions.* Reply with your requested edits.")

        elif action_cmd == "confirm":
            original = query.message.text if query.message else ""
            await safe_edit_text(query, f"{original}\n\n⏳ *Executing action... Please wait.*")
            try:
                result = await confirmation_mgr.execute_action(action_id)
                if query.message:
                    await safe_reply_text(query.message, result.format_summary())
            except Exception as e:
                logger.error(f"Error executing action {action_id}: {e}", exc_info=True)
                if query.message:
                    await safe_reply_text(query.message, f"❌ *Error executing action:*\n`{str(e)}`")


# =============================================================================
# APPLICATION BUILDER
# =============================================================================

def build_application() -> Application:
    """Builds and configures Telegram Application with full concurrent update processing."""
    token = config.TELEGRAM_BOT_TOKEN
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN is not set in configuration or .env")

    app = Application.builder().token(token).concurrent_updates(True).build()

    # Commands
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("connect", connect_command))
    app.add_handler(CommandHandler("pages", pages_command))
    app.add_handler(CommandHandler("inbox", inbox_command))
    app.add_handler(CommandHandler("insights", insights_command))
    app.add_handler(CommandHandler("ad", ad_command))
    app.add_handler(CommandHandler("disconnect", disconnect_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("clear", clear_command))

    # Interactive buttons
    app.add_handler(CallbackQueryHandler(handle_callback_query))

    # Messages
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    return app
