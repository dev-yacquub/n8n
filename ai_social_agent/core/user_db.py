"""
User Database Manager for Multi-Tenant Facebook Page AI Agent.
Handles SQLite storage for Telegram user credentials, connected Facebook Pages,
active page selection, ad account settings, and AI auto-reply preferences.
"""

import os
import sqlite3
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
from ..config.config import config

logger = logging.getLogger("SocialCommander.UserDB")

DATA_DIR = config.BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "facebook_agent.db"


class UserDatabase:
    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = str(db_path)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        """Initializes database schema if tables don't already exist."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Users table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    telegram_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    user_access_token TEXT,
                    active_page_id TEXT,
                    active_page_name TEXT,
                    active_page_token TEXT,
                    ad_account_id TEXT,
                    auto_reply_enabled INTEGER DEFAULT 0,
                    auto_reply_instructions TEXT DEFAULT 'Be polite, helpful, and concise',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # User Pages table (supports users who manage multiple pages)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_pages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    telegram_id INTEGER NOT NULL,
                    page_id TEXT NOT NULL,
                    page_name TEXT NOT NULL,
                    page_access_token TEXT NOT NULL,
                    category TEXT,
                    fan_count INTEGER DEFAULT 0,
                    is_active INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(telegram_id, page_id)
                )
            """)
            conn.commit()
            logger.info(f"Initialized User Database at: {self.db_path}")

    def register_or_update_user(
        self,
        telegram_id: int,
        username: Optional[str] = None,
        first_name: Optional[str] = None
    ):
        """Ensures a user row exists."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO users (telegram_id, username, first_name)
                VALUES (?, ?, ?)
                ON CONFLICT(telegram_id) DO UPDATE SET
                    username = COALESCE(excluded.username, users.username),
                    first_name = COALESCE(excluded.first_name, users.first_name),
                    updated_at = CURRENT_TIMESTAMP
            """, (telegram_id, username, first_name))
            conn.commit()

    def save_page(
        self,
        telegram_id: int,
        page_id: str,
        page_name: str,
        page_access_token: str,
        category: str = "",
        fan_count: int = 0,
        set_active: bool = True
    ):
        """Saves a Facebook Page for a specific Telegram user."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Upsert into user_pages
            cursor.execute("""
                INSERT INTO user_pages (telegram_id, page_id, page_name, page_access_token, category, fan_count, is_active)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(telegram_id, page_id) DO UPDATE SET
                    page_name = excluded.page_name,
                    page_access_token = excluded.page_access_token,
                    category = excluded.category,
                    fan_count = excluded.fan_count,
                    is_active = excluded.is_active
            """, (telegram_id, page_id, page_name, page_access_token, category, fan_count, 1 if set_active else 0))

            if set_active:
                # Demote other pages
                cursor.execute("""
                    UPDATE user_pages SET is_active = 0 WHERE telegram_id = ? AND page_id != ?
                """, (telegram_id, page_id))

                # Update or insert active page in users table
                cursor.execute("""
                    INSERT INTO users (telegram_id, active_page_id, active_page_name, active_page_token, updated_at)
                    VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(telegram_id) DO UPDATE SET
                        active_page_id = excluded.active_page_id,
                        active_page_name = excluded.active_page_name,
                        active_page_token = excluded.active_page_token,
                        updated_at = CURRENT_TIMESTAMP
                """, (telegram_id, page_id, page_name, page_access_token))

            conn.commit()
            logger.info(f"Saved page '{page_name}' ({page_id}) for user {telegram_id} (active={set_active})")

    def save_user_token_and_pages(
        self,
        telegram_id: int,
        user_token: str,
        pages: List[Dict[str, Any]],
        username: Optional[str] = None,
        first_name: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Saves user token and all discovered pages.
        If pages are provided, activates the first page by default.
        Returns the active page dict or None.
        """
        self.register_or_update_user(telegram_id, username, first_name)
        active_page = None

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE users SET user_access_token = ?, updated_at = CURRENT_TIMESTAMP WHERE telegram_id = ?
            """, (user_token, telegram_id))
            conn.commit()

        for idx, p in enumerate(pages):
            p_id = str(p.get("id"))
            p_name = p.get("name", "Unknown Page")
            p_token = p.get("access_token", user_token)
            p_cat = p.get("category", "")
            p_fans = p.get("fan_count", 0)
            is_first = (idx == 0)

            self.save_page(
                telegram_id=telegram_id,
                page_id=p_id,
                page_name=p_name,
                page_access_token=p_token,
                category=p_cat,
                fan_count=p_fans,
                set_active=is_first
            )
            if is_first:
                active_page = {
                    "id": p_id,
                    "name": p_name,
                    "access_token": p_token,
                    "category": p_cat,
                    "fan_count": p_fans
                }

        return active_page

    def get_user_credentials(self, telegram_id: int) -> Optional[Dict[str, Any]]:
        """
        Retrieves active Facebook credentials for a Telegram user.
        Returns dict with: page_id, page_name, page_access_token, ad_account_id
        Falls back to .env configuration if user has no DB record but allowed.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT active_page_id, active_page_name, active_page_token, ad_account_id,
                       auto_reply_enabled, auto_reply_instructions
                FROM users WHERE telegram_id = ?
            """, (telegram_id,))
            row = cursor.fetchone()

            if row and row["active_page_id"] and row["active_page_token"]:
                return {
                    "page_id": row["active_page_id"],
                    "page_name": row["active_page_name"],
                    "page_access_token": row["active_page_token"],
                    "ad_account_id": row["ad_account_id"],
                    "auto_reply_enabled": bool(row["auto_reply_enabled"]),
                    "auto_reply_instructions": row["auto_reply_instructions"]
                }

        # Auto-seed from .env if configured so user is never unauthenticated or forgotten
        if config.FACEBOOK_PAGE_ID and config.FACEBOOK_ACCESS_TOKEN:
            default_name = "BUUB CAWL" if config.FACEBOOK_PAGE_ID == "106972352162498" else "Connected Facebook Page"
            self.save_page(
                telegram_id=telegram_id,
                page_id=config.FACEBOOK_PAGE_ID,
                page_name=default_name,
                page_access_token=config.FACEBOOK_ACCESS_TOKEN,
                category="Digital creator",
                set_active=True
            )
            return {
                "page_id": config.FACEBOOK_PAGE_ID,
                "page_name": default_name,
                "page_access_token": config.FACEBOOK_ACCESS_TOKEN,
                "ad_account_id": None,
                "auto_reply_enabled": False,
                "auto_reply_instructions": "Be polite and helpful."
            }

        return None

    def list_user_pages(self, telegram_id: int) -> List[Dict[str, Any]]:
        """Lists all Facebook Pages connected by a user."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT page_id, page_name, category, fan_count, is_active
                FROM user_pages
                WHERE telegram_id = ?
                ORDER BY is_active DESC, page_name ASC
            """, (telegram_id,))
            rows = cursor.fetchall()
            if not rows and config.FACEBOOK_PAGE_ID and config.FACEBOOK_ACCESS_TOKEN:
                # Seed default page
                self.get_user_credentials(telegram_id)
                cursor.execute("""
                    SELECT page_id, page_name, category, fan_count, is_active
                    FROM user_pages
                    WHERE telegram_id = ?
                    ORDER BY is_active DESC, page_name ASC
                """, (telegram_id,))
                rows = cursor.fetchall()
            return [dict(r) for r in rows]

    def set_active_page(self, telegram_id: int, page_id: str) -> bool:
        """Switches the user's active Facebook Page."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # Fetch page from user_pages
            cursor.execute("""
                SELECT page_id, page_name, page_access_token
                FROM user_pages
                WHERE telegram_id = ? AND page_id = ?
            """, (telegram_id, page_id))
            row = cursor.fetchone()

            if not row:
                return False

            # Set is_active flags
            cursor.execute("""
                UPDATE user_pages SET is_active = CASE WHEN page_id = ? THEN 1 ELSE 0 END
                WHERE telegram_id = ?
            """, (page_id, telegram_id))

            # Update users table
            cursor.execute("""
                UPDATE users SET
                    active_page_id = ?,
                    active_page_name = ?,
                    active_page_token = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE telegram_id = ?
            """, (row["page_id"], row["page_name"], row["page_access_token"], telegram_id))

            conn.commit()
            return True

    def set_ad_account(self, telegram_id: int, ad_account_id: str):
        """Sets or updates the user's Facebook Ad Account ID."""
        clean_id = ad_account_id.strip()
        if not clean_id.startswith("act_") and clean_id.isdigit():
            clean_id = f"act_{clean_id}"

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE users SET ad_account_id = ?, updated_at = CURRENT_TIMESTAMP
                WHERE telegram_id = ?
            """, (clean_id, telegram_id))
            conn.commit()

    def set_auto_reply_settings(
        self,
        telegram_id: int,
        enabled: bool,
        instructions: Optional[str] = None
    ):
        """Updates AI auto-reply preferences."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if instructions:
                cursor.execute("""
                    UPDATE users SET auto_reply_enabled = ?, auto_reply_instructions = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE telegram_id = ?
                """, (1 if enabled else 0, instructions, telegram_id))
            else:
                cursor.execute("""
                    UPDATE users SET auto_reply_enabled = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE telegram_id = ?
                """, (1 if enabled else 0, telegram_id))
            conn.commit()

    def disconnect_user(self, telegram_id: int):
        """Deletes all Facebook tokens and pages for a specific Telegram user."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM user_pages WHERE telegram_id = ?", (telegram_id,))
            cursor.execute("""
                UPDATE users SET
                    user_access_token = NULL,
                    active_page_id = NULL,
                    active_page_name = NULL,
                    active_page_token = NULL,
                    ad_account_id = NULL,
                    auto_reply_enabled = 0,
                    updated_at = CURRENT_TIMESTAMP
                WHERE telegram_id = ?
            """, (telegram_id,))
            conn.commit()
            logger.info(f"Disconnected Facebook account for Telegram user {telegram_id}")


user_db = UserDatabase()
