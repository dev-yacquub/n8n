"""
Substack Connector.
Supports querying publication posts, creating drafts, publishing notes, and generating newsletter formats.
Uses Substack API endpoints authenticated via session cookie (`connect.sid`) with RSS fallback.
"""

import httpx
import json
from typing import Optional, Dict, Any, List
from .base import BaseConnector, ActionResult
from ..config.config import config


def _markdown_to_substack_tiptap(text: str) -> Dict[str, Any]:
    """
    Converts markdown paragraphs into Substack's ProseMirror/TipTap JSON format.
    """
    paragraphs = text.strip().split("\n\n")
    content_nodes = []
    for p in paragraphs:
        cleaned = p.strip().replace("\n", " ")
        if cleaned.startswith("# "):
            content_nodes.append({
                "type": "heading",
                "attrs": {"level": 1},
                "content": [{"type": "text", "text": cleaned[2:]}]
            })
        elif cleaned.startswith("## "):
            content_nodes.append({
                "type": "heading",
                "attrs": {"level": 2},
                "content": [{"type": "text", "text": cleaned[3:]}]
            })
        elif cleaned.startswith("> "):
            content_nodes.append({
                "type": "blockquote",
                "content": [{
                    "type": "paragraph",
                    "content": [{"type": "text", "text": cleaned[2:]}]
                }]
            })
        else:
            content_nodes.append({
                "type": "paragraph",
                "content": [{"type": "text", "text": cleaned}]
            })

    return {
        "type": "doc",
        "content": content_nodes
    }


class SubstackConnector(BaseConnector):
    def __init__(self):
        super().__init__("substack")
        self.subdomain = config.SUBSTACK_SUBDOMAIN.strip().lower()
        self.cookie_sid = config.SUBSTACK_COOKIE_SID.strip()
        self.base_url = f"https://{self.subdomain}.substack.com" if self.subdomain else "https://substack.com"

    def is_configured(self) -> bool:
        return bool(self.subdomain)

    async def test_connection(self) -> ActionResult:
        if not self.is_configured():
            return ActionResult(
                success=False,
                platform="substack",
                action="test_connection",
                message="Substack Subdomain is not configured.",
                error="UNCONFIGURED"
            )

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        cookies = {"connect.sid": self.cookie_sid} if self.cookie_sid else {}

        try:
            async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
                res = await client.get(f"{self.base_url}/api/v1/posts?limit=3", headers=headers, cookies=cookies)

                if res.status_code == 200:
                    data = res.json()
                    authenticated = bool(self.cookie_sid)
                    auth_note = " (Authenticated via Session)" if authenticated else " (Public Read-Only Mode)"
                    return ActionResult(
                        success=True,
                        platform="substack",
                        action="test_connection",
                        message=f"Connected to Substack publication: {self.subdomain}.substack.com{auth_note}",
                        data={"post_count": len(data) if isinstance(data, list) else 0, "authenticated": authenticated}
                    )
                else:
                    return ActionResult(
                        success=False,
                        platform="substack",
                        action="test_connection",
                        message=f"Could not reach {self.subdomain}.substack.com (HTTP {res.status_code})",
                        error=res.text[:200]
                    )
        except Exception as e:
            return ActionResult(
                success=False,
                platform="substack",
                action="test_connection",
                message=f"Exception connecting to Substack: {str(e)}",
                error=str(e)
            )

    async def get_recent_posts(self, limit: int = 5) -> ActionResult:
        """Fetches recent published posts from the publication."""
        if not self.is_configured():
            return ActionResult(
                success=False,
                platform="substack",
                action="get_recent_posts",
                message="Substack Subdomain not configured.",
                error="UNCONFIGURED"
            )

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
        }
        try:
            async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
                res = await client.get(f"{self.base_url}/api/v1/posts?limit={limit}", headers=headers)
                if res.status_code == 200:
                    posts_raw = res.json()
                    posts = []
                    for p in posts_raw[:limit]:
                        posts.append({
                            "id": p.get("id"),
                            "title": p.get("title"),
                            "subtitle": p.get("subtitle"),
                            "url": p.get("canonical_url"),
                            "date": p.get("post_date")
                        })
                    return ActionResult(
                        success=True,
                        platform="substack",
                        action="get_recent_posts",
                        message=f"Retrieved {len(posts)} recent Substack articles.",
                        data={"posts": posts}
                    )
                else:
                    return ActionResult(
                        success=False,
                        platform="substack",
                        action="get_recent_posts",
                        message="Failed to fetch Substack articles.",
                        error=res.text[:200]
                    )
        except Exception as e:
            return ActionResult(
                success=False,
                platform="substack",
                action="get_recent_posts",
                message="Exception fetching Substack articles.",
                error=str(e)
            )

    async def create_draft(self, title: str, subtitle: str, body_markdown: str) -> ActionResult:
        """
        Creates a new draft post on Substack using session authentication.
        """
        if not self.is_configured():
            return ActionResult(
                success=False,
                platform="substack",
                action="create_draft",
                message="Substack Subdomain not configured.",
                error="UNCONFIGURED"
            )

        if not self.cookie_sid:
            return ActionResult(
                success=False,
                platform="substack",
                action="create_draft",
                message="SUBSTACK_COOKIE_SID is required to create drafts directly. Please provide your session cookie.",
                error="AUTH_REQUIRED"
            )

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        cookies = {"connect.sid": self.cookie_sid}
        tiptap_body = _markdown_to_substack_tiptap(body_markdown)

        payload = {
            "draft_title": title,
            "draft_subtitle": subtitle,
            "draft_body": json.dumps(tiptap_body),
            "type": "newsletter"
        }

        try:
            async with httpx.AsyncClient(timeout=25.0, follow_redirects=True) as client:
                res = await client.post(f"{self.base_url}/api/v1/drafts", headers=headers, cookies=cookies, json=payload)

                if res.status_code in (200, 201):
                    data = res.json()
                    draft_id = data.get("id")
                    draft_url = f"{self.base_url}/publish/post/{draft_id}" if draft_id else f"{self.base_url}/publish"
                    return ActionResult(
                        success=True,
                        platform="substack",
                        action="create_draft",
                        message=f"Substack draft '{title}' created successfully! Edit or publish at: {draft_url}",
                        data={"draft_id": draft_id, "draft_url": draft_url}
                    )
                else:
                    return ActionResult(
                        success=False,
                        platform="substack",
                        action="create_draft",
                        message=f"Failed to create draft on Substack (HTTP {res.status_code}). Session cookie may have expired.",
                        error=res.text[:300]
                    )
        except Exception as e:
            return ActionResult(
                success=False,
                platform="substack",
                action="create_draft",
                message="Exception creating Substack draft.",
                error=str(e)
            )

    async def post_note(self, content: str) -> ActionResult:
        """Publishes a Substack Note."""
        if not self.cookie_sid:
            return ActionResult(
                success=False,
                platform="substack",
                action="post_note",
                message="SUBSTACK_COOKIE_SID required to publish Substack Notes.",
                error="AUTH_REQUIRED"
            )

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "Content-Type": "application/json"
        }
        cookies = {"connect.sid": self.cookie_sid}
        payload = {
            "body": content,
            "content": _markdown_to_substack_tiptap(content)
        }

        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                res = await client.post("https://substack.com/api/v1/comment", headers=headers, cookies=cookies, json=payload)
                if res.status_code in (200, 201):
                    data = res.json()
                    return ActionResult(
                        success=True,
                        platform="substack",
                        action="post_note",
                        message="Substack Note published successfully!",
                        data=data
                    )
                else:
                    return ActionResult(
                        success=False,
                        platform="substack",
                        action="post_note",
                        message=f"Failed to publish Substack Note (HTTP {res.status_code}).",
                        error=res.text[:200]
                    )
        except Exception as e:
            return ActionResult(
                success=False,
                platform="substack",
                action="post_note",
                message="Exception publishing Substack note.",
                error=str(e)
            )
