"""
Facebook Page Graph API Connector.
Supports publishing text status updates, photos with captions, and querying page posts.
"""

import httpx
from typing import Optional, Dict, Any, List
from .base import BaseConnector, ActionResult
from ..config.config import config


class FacebookConnector(BaseConnector):
    def __init__(self):
        super().__init__("facebook")
        self.page_id = config.FACEBOOK_PAGE_ID
        self.access_token = config.FACEBOOK_ACCESS_TOKEN
        self.api_version = config.FACEBOOK_API_VERSION or "v19.0"
        self.base_url = f"https://graph.facebook.com/{self.api_version}"

    def is_configured(self) -> bool:
        return bool(self.page_id and self.access_token)

    async def test_connection(self) -> ActionResult:
        if not self.is_configured():
            return ActionResult(
                success=False,
                platform="facebook",
                action="test_connection",
                message="Facebook Page ID or Access Token is missing.",
                error="UNCONFIGURED"
            )
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                url = f"{self.base_url}/{self.page_id}"
                params = {
                    "fields": "id,name,fan_count,category",
                    "access_token": self.access_token
                }
                res = await client.get(url, params=params)
                data = res.json()

                if res.status_code == 200 and "id" in data:
                    page_name = data.get("name", "Unknown Page")
                    fans = data.get("fan_count", 0)
                    return ActionResult(
                        success=True,
                        platform="facebook",
                        action="test_connection",
                        message=f"Connected to Facebook Page: '{page_name}' ({fans} followers)",
                        data=data
                    )
                else:
                    err_msg = data.get("error", {}).get("message", res.text)
                    return ActionResult(
                        success=False,
                        platform="facebook",
                        action="test_connection",
                        message="Facebook API connection failed.",
                        error=err_msg
                    )
        except Exception as e:
            return ActionResult(
                success=False,
                platform="facebook",
                action="test_connection",
                message=f"Exception connecting to Facebook: {str(e)}",
                error=str(e)
            )

    async def post_text(self, message: str) -> ActionResult:
        """Publishes a text status update to the Facebook Page feed."""
        if not self.is_configured():
            return ActionResult(
                success=False,
                platform="facebook",
                action="post_text",
                message="Facebook credentials not configured.",
                error="UNCONFIGURED"
            )

        url = f"{self.base_url}/{self.page_id}/feed"
        payload = {
            "message": message,
            "access_token": self.access_token
        }

        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                res = await client.post(url, data=payload)
                data = res.json()

                if res.status_code == 200 and "id" in data:
                    post_id = data["id"]
                    return ActionResult(
                        success=True,
                        platform="facebook",
                        action="post_text",
                        message=f"Successfully published post to Facebook Page! Post ID: {post_id}",
                        data={"post_id": post_id}
                    )
                else:
                    err_msg = data.get("error", {}).get("message", res.text)
                    return ActionResult(
                        success=False,
                        platform="facebook",
                        action="post_text",
                        message="Failed to post text to Facebook.",
                        error=err_msg
                    )
        except Exception as e:
            return ActionResult(
                success=False,
                platform="facebook",
                action="post_text",
                message="Failed to execute Facebook text post.",
                error=str(e)
            )

    async def post_photo(self, image_url: str, caption: str) -> ActionResult:
        """Publishes a photo with a caption to the Facebook Page."""
        if not self.is_configured():
            return ActionResult(
                success=False,
                platform="facebook",
                action="post_photo",
                message="Facebook credentials not configured.",
                error="UNCONFIGURED"
            )

        url = f"{self.base_url}/{self.page_id}/photos"
        params = {
            "url": image_url,
            "caption": caption,
            "access_token": self.access_token
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                res = await client.post(url, params=params)
                data = res.json()

                if res.status_code == 200 and ("id" in data or "post_id" in data):
                    photo_id = data.get("id") or data.get("post_id")
                    return ActionResult(
                        success=True,
                        platform="facebook",
                        action="post_photo",
                        message=f"Successfully posted photo to Facebook Page! Photo ID: {photo_id}",
                        data={"photo_id": photo_id}
                    )
                else:
                    err_msg = data.get("error", {}).get("message", res.text)
                    return ActionResult(
                        success=False,
                        platform="facebook",
                        action="post_photo",
                        message="Failed to post photo to Facebook.",
                        error=err_msg
                    )
        except Exception as e:
            return ActionResult(
                success=False,
                platform="facebook",
                action="post_photo",
                message="Failed to upload photo to Facebook.",
                error=str(e)
            )

    async def get_recent_posts(self, limit: int = 5) -> ActionResult:
        """Fetches latest posts from Facebook Page feed."""
        if not self.is_configured():
            return ActionResult(
                success=False,
                platform="facebook",
                action="get_recent_posts",
                message="Facebook credentials not configured.",
                error="UNCONFIGURED"
            )

        url = f"{self.base_url}/{self.page_id}/posts"
        params = {
            "fields": "id,message,created_time,shares,comments.summary(true),likes.summary(true)",
            "limit": limit,
            "access_token": self.access_token
        }

        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                res = await client.get(url, params=params)
                data = res.json()

                if res.status_code == 200 and "data" in data:
                    posts = data["data"]
                    return ActionResult(
                        success=True,
                        platform="facebook",
                        action="get_recent_posts",
                        message=f"Retrieved {len(posts)} recent Facebook posts.",
                        data={"posts": posts}
                    )
                else:
                    err_msg = data.get("error", {}).get("message", res.text)
                    return ActionResult(
                        success=False,
                        platform="facebook",
                        action="get_recent_posts",
                        message="Failed to retrieve Facebook posts.",
                        error=err_msg
                    )
        except Exception as e:
            return ActionResult(
                success=False,
                platform="facebook",
                action="get_recent_posts",
                message="Failed to fetch Facebook posts.",
                error=str(e)
            )
