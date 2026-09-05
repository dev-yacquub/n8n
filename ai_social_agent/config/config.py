"""
Configuration management for AI Social Media & Communications Master Agent.
Loads environment variables and validates platform connection parameters.
"""

import os
from pathlib import Path
from typing import Optional, Dict, Any
from dotenv import load_dotenv

# Ensure .env in the ai_social_agent directory is loaded
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

UPLOADS_DIR = BASE_DIR / "uploads"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)


class Config:
    BASE_DIR = BASE_DIR
    UPLOADS_DIR = UPLOADS_DIR

    # --- Telegram Bot ---
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    TELEGRAM_ALLOWED_USER_ID: Optional[int] = (
        int(os.getenv("TELEGRAM_ALLOWED_USER_ID"))
        if os.getenv("TELEGRAM_ALLOWED_USER_ID", "").strip()
        else None
    )

    # --- AI Reasoning Engine ---
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "openrouter").lower()
    OPENROUTER_API_KEY: str = os.getenv("OPENROUTER_API_KEY", "").strip()
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "").strip()
    LLM_MODEL: str = os.getenv("LLM_MODEL", "google/gemini-2.5-flash").strip()

    # --- Facebook Graph API ---
    FACEBOOK_PAGE_ID: str = os.getenv("FACEBOOK_PAGE_ID", "").strip()
    FACEBOOK_ACCESS_TOKEN: str = os.getenv("FACEBOOK_ACCESS_TOKEN", "").strip()
    FACEBOOK_API_VERSION: str = os.getenv("FACEBOOK_API_VERSION", "v19.0").strip()

    # --- Instagram Graph API ---
    INSTAGRAM_ACCOUNT_ID: str = os.getenv("INSTAGRAM_ACCOUNT_ID", "").strip()
    INSTAGRAM_ACCESS_TOKEN: str = os.getenv("INSTAGRAM_ACCESS_TOKEN", "").strip()
    INSTAGRAM_API_VERSION: str = os.getenv("INSTAGRAM_API_VERSION", "v19.0").strip()

    # --- WhatsApp (Linked Device Bridge or Cloud API) ---
    WHATSAPP_MODE: str = os.getenv("WHATSAPP_MODE", "linked_device").strip().lower()
    WHATSAPP_BRIDGE_URL: str = os.getenv("WHATSAPP_BRIDGE_URL", "http://127.0.0.1:3001").rstrip("/")
    WHATSAPP_PHONE_NUMBER_ID: str = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "").strip()
    WHATSAPP_ACCESS_TOKEN: str = os.getenv("WHATSAPP_ACCESS_TOKEN", "").strip()
    WHATSAPP_API_VERSION: str = os.getenv("WHATSAPP_API_VERSION", "v19.0").strip()
    WHATSAPP_RECIPIENT_PHONE: str = os.getenv("WHATSAPP_RECIPIENT_PHONE", "").strip()

    # --- Gmail & Email Sending ---
    GMAIL_EMAIL: str = os.getenv("GMAIL_EMAIL", "").strip()
    GMAIL_APP_PASSWORD: str = os.getenv("GMAIL_APP_PASSWORD", "").strip()
    GMAIL_CLIENT_SECRET_FILE: str = os.getenv("GMAIL_CLIENT_SECRET_FILE", "").strip()
    RESEND_API_KEY: str = os.getenv("RESEND_API_KEY", "").strip()
    BREVO_API_KEY: str = os.getenv("BREVO_API_KEY", "").strip()
    EMAIL_FROM: str = os.getenv("EMAIL_FROM", "").strip()

    # --- Substack ---
    SUBSTACK_SUBDOMAIN: str = os.getenv("SUBSTACK_SUBDOMAIN", "").strip()
    SUBSTACK_COOKIE_SID: str = os.getenv("SUBSTACK_COOKIE_SID", "").strip()

    # --- n8n Bridge ---
    N8N_BASE_URL: str = os.getenv("N8N_BASE_URL", "").rstrip("/")
    N8N_API_KEY: str = os.getenv("N8N_API_KEY", "").strip()

    @classmethod
    def get_status_summary(cls) -> Dict[str, Any]:
        """Returns health status of configured credentials."""
        return {
            "telegram": bool(cls.TELEGRAM_BOT_TOKEN),
            "ai_brain": bool(cls.OPENROUTER_API_KEY or cls.GEMINI_API_KEY),
            "facebook": bool(cls.FACEBOOK_PAGE_ID and cls.FACEBOOK_ACCESS_TOKEN),
            "instagram": bool(cls.INSTAGRAM_ACCOUNT_ID and cls.INSTAGRAM_ACCESS_TOKEN),
            "whatsapp": (
                bool(cls.WHATSAPP_BRIDGE_URL)
                if cls.WHATSAPP_MODE == "linked_device"
                else bool(cls.WHATSAPP_PHONE_NUMBER_ID and cls.WHATSAPP_ACCESS_TOKEN)
            ),
            "gmail": bool((cls.GMAIL_EMAIL and (cls.GMAIL_APP_PASSWORD or cls.GMAIL_CLIENT_SECRET_FILE)) or cls.RESEND_API_KEY or cls.BREVO_API_KEY),
            "substack": bool(cls.SUBSTACK_SUBDOMAIN and cls.SUBSTACK_COOKIE_SID),
            "n8n": bool(cls.N8N_BASE_URL and cls.N8N_API_KEY)
        }


config = Config()
