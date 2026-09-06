"""
Configuration management for AI Social Media & Communications Master Agent.
Loads environment variables and validates platform connection parameters.
"""

import os
import base64
from pathlib import Path
from typing import Optional, Dict, Any
from dotenv import load_dotenv

# Ensure .env in the ai_social_agent directory is loaded
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

UPLOADS_DIR = BASE_DIR / "uploads"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)


def _get_env_or_b64(env_key: str, b64_fallback: str) -> str:
    val = os.getenv(env_key, "").strip()
    if val:
        return val
    if b64_fallback:
        try:
            return base64.b64decode(b64_fallback.encode()).decode().strip()
        except Exception:
            return ""
    return ""


class Config:
    BASE_DIR = BASE_DIR
    UPLOADS_DIR = UPLOADS_DIR

    # --- Telegram Bot ---
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "8916331252:AAHeYaiFw9RCTcYn26sUbXmsYWrnQQdka4Q").strip()
    TELEGRAM_ALLOWED_USER_ID: Optional[int] = (
        int(os.getenv("TELEGRAM_ALLOWED_USER_ID"))
        if os.getenv("TELEGRAM_ALLOWED_USER_ID", "").strip()
        else None
    )

    # --- AI Reasoning Engine ---
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "openrouter").lower()
    OPENROUTER_API_KEY: str = _get_env_or_b64(
        "OPENROUTER_API_KEY",
        "c2stb3ItdjEtN2YzYjQ5YzAzODg3MTZkN2I3ODA3ZDllZWJiMjNmYzEwYjFiYjAzOGM1ZjIxMjc4ZjE1YmYyMmY2NWUzMjA1Nw=="
    )
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "").strip()
    LLM_MODEL: str = os.getenv("LLM_MODEL", "google/gemini-2.5-flash").strip()

    # --- Facebook Graph API ---
    FACEBOOK_PAGE_ID: str = os.getenv("FACEBOOK_PAGE_ID", "106972352162498").strip()
    FACEBOOK_ACCESS_TOKEN: str = os.getenv(
        "FACEBOOK_ACCESS_TOKEN",
        "EAAeIJkU6QpgBSPPaaWjaePlH6Aeie0ZAFdYle2LzbmucOrmlad1cPabkmsg8WaGavzGeVCCkwPZCURFS82ehUIXvRbnsBRxjpK4p2HjlEDlfquLk79cCL87BhbqQrxH78FpOHW2SWSPwDQ0ZB7tpu2NxpVE6pKf7CqvNMgQ6qAr5A053UAMLPQVBjYI43b0WMFzMGsZD"
    ).strip()
    FACEBOOK_API_VERSION: str = os.getenv("FACEBOOK_API_VERSION", "v19.0").strip()

    # --- Instagram Business ---
    INSTAGRAM_ACCOUNT_ID: str = os.getenv("INSTAGRAM_ACCOUNT_ID", "17841457143655029").strip()
    INSTAGRAM_ACCESS_TOKEN: str = os.getenv(
        "INSTAGRAM_ACCESS_TOKEN",
        "EAAeIJkU6QpgBSJm3wl8j26kExchzZBGQuTVFprrIOxHXPXtKrkorS1FaZBSslU9vHCbVwQ9XMTafVvnvcogKfYg5fX4e6wACzAdqv020RVvtZBnCWiiodplwOyqPWQTMRBEZAaMvVHeAxURyMLROx1RMlJpFdPajj2UPQYKqSDAMA3b1fa8ibB87bf5r"
    ).strip()
    INSTAGRAM_API_VERSION: str = os.getenv("INSTAGRAM_API_VERSION", "v19.0").strip()

    # --- WhatsApp (Linked Device Bridge or Cloud API) ---
    WHATSAPP_MODE: str = os.getenv("WHATSAPP_MODE", "linked_device").strip().lower()
    WHATSAPP_BRIDGE_URL: str = os.getenv("WHATSAPP_BRIDGE_URL", "http://127.0.0.1:3001").rstrip("/")
    WHATSAPP_PHONE_NUMBER_ID: str = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "1263547403515916").strip()
    WHATSAPP_ACCESS_TOKEN: str = os.getenv(
        "WHATSAPP_ACCESS_TOKEN",
        "EAAeIJkU6QpgBSYra96IelcyK5WPZCT8toWY5Uq9dRm9G1alkIcGHrBmN7pURfQhRqd17aSZA7HZArYzkMF5qkZBu8KMjhfY73GCWmKzZCim6mqS7XPmGeq83CIUPoepoebXolqZAIKbbudPRgv1ckJZALFsallVeV62iR9d5fg7ulcBjeRxIa4p2SKaZCvMDE7x6JQZDZD"
    ).strip()
    WHATSAPP_API_VERSION: str = os.getenv("WHATSAPP_API_VERSION", "v20.0").strip()
    WHATSAPP_RECIPIENT_PHONE: str = os.getenv("WHATSAPP_RECIPIENT_PHONE", "252637452784").strip()

    # --- Gmail & Email Sending ---
    GMAIL_EMAIL: str = os.getenv("GMAIL_EMAIL", "yacquubqaxwe@gmail.com").strip()
    GMAIL_APP_PASSWORD: str = os.getenv("GMAIL_APP_PASSWORD", "qgdg iezl tvgu itiv").strip()
    GMAIL_CLIENT_SECRET_FILE: str = os.getenv("GMAIL_CLIENT_SECRET_FILE", "").strip()
    RESEND_API_KEY: str = _get_env_or_b64("RESEND_API_KEY", "cmVfRUNXV1V2clpfOVE0NUNiMXRFM0R5ZjlzaGYxRFNXVmZk")
    BREVO_API_KEY: str = os.getenv("BREVO_API_KEY", "").strip()
    EMAIL_FROM: str = os.getenv("EMAIL_FROM", "").strip()

    # --- Substack ---
    SUBSTACK_SUBDOMAIN: str = os.getenv("SUBSTACK_SUBDOMAIN", "").strip()
    SUBSTACK_COOKIE_SID: str = os.getenv("SUBSTACK_COOKIE_SID", "").strip()

    # --- n8n Bridge ---
    N8N_BASE_URL: str = os.getenv("N8N_BASE_URL", "https://n8n-5yi2.onrender.com/api/v1").rstrip("/")
    N8N_API_KEY: str = os.getenv(
        "N8N_API_KEY",
        "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI1YzA3MTg1NS0zNjNhLTQxYTktOGVjYS0yNTI4NjUzOGQ5MmYiLCJpc3MiOiJuOG4iLCJhdWQiOiJwdWJsaWMtYXBpIiwianRpIjoiOThlYWM2MDQtZmZkNS00M2RlLTk4NDktODQ2MWQxMWE3YmYzIiwiaWF0IjoxNzg4MDc5OTY5fQ.YUBR54oZOSxoZq_OVqXKWvYkI6FZeliUFA8sxh3WHVk"
    ).strip()

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
