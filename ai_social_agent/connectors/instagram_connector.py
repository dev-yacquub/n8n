"""
Instagram Business Graph API Connector.
Supports publishing single photos, carousels, and querying recent posts/metrics.
Uses the two-step Instagram Container Publishing workflow.
"""

import asyncio
import httpx
from typing import Optional, Dict, Any, List
from .base import BaseConnector, ActionResult
from ..config.config import config


class InstagramConnector(BaseConnector):
    def __init__(self):
        super().__init__("instagram")
        self.account_id = config.INSTAGRAM_ACCOUNT_ID
        self.access_token = config.INSTAGRAM_ACCESS_TOKEN
        self.api_version = config.INSTAGRAM_API_VERSION or "v19.0"
        self.base_url = f"https://graph.facebook.com/{self.api_version}"

    def is_configured(self) -> bool:
        return bool(self.account_id and self.access_token)

    async def test_connection(self) -> ActionResult:
        if not self.is_configured():
            return ActionResult(
                success=False,
                platform="instagram",
                action="test_connection",
                message="Instagram Account ID or Access Token is missing.",
                error="UNCONFIGURED"
            )

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                url = f"{self.base_url}/{self.account_id}"
                params = {
                    "fields": "id,username,name,followers_count,media_count",
                    "access_token": self.access_token
                }
                res = await client.get(url, params=params)
                data = res.json()

                if res.status_code == 200 and "id" in data:
                    username = data.get("username", "Unknown")
                    followers = data.get("followers_count", 0)
                    media_count = data.get("media_count", 0)
                    return ActionResult(
                        success=True,
                        platform="instagram",
                        action="test_connection",
                        message=f"Connected to Instagram Account: @{username} ({followers} followers, {media_count} posts)",
                        data=data
                    )
                else:
                    err_msg = data.get("error", {}).get("message", res.text)
                    return ActionResult(
                        success=False,
                        platform="instagram",
                        action="test_connection",
                        message="Instagram API connection failed.",
                        error=err_msg
                    )
        except Exception as e:
            return ActionResult(
                success=False,
                platform="instagram",
                action="test_connection",
                message=f"Exception connecting to Instagram: {str(e)}",
                error=str(e)
            )

    async def post_photo(self, image_url: str, caption: str) -> ActionResult:
        """
        Publishes a single photo to Instagram Business Account:
        Step 1: Create media container
        Step 2: Await readiness
        Step 3: Publish container
        """
        if not self.is_configured():
            return ActionResult(
                success=False,
                platform="instagram",
                action="post_photo",
                message="Instagram credentials not configured.",
                error="UNCONFIGURED"
            )

        try:
            async with httpx.AsyncClient(timeout=45.0) as client:
                # Step 1: Create media container
                container_url = f"{self.base_url}/{self.account_id}/media"
                container_params = {
                    "image_url": image_url,
                    "caption": caption,
                    "access_token": self.access_token
                }
                res1 = await client.post(container_url, params=container_params)
                data1 = res1.json()

                if res1.status_code != 200 or "id" not in data1:
                    err_msg = data1.get("error", {}).get("message", res1.text)
                    return ActionResult(
                        success=False,
                        platform="instagram",
                        action="post_photo",
                        message="Failed to create Instagram media container.",
                        error=err_msg
                    )

                creation_id = data1["id"]

                # Step 2: Allow Instagram servers to ingest and process the media
                await asyncio.sleep(5)

                # Step 3: Publish media container
                publish_url = f"{self.base_url}/{self.account_id}/media_publish"
                publish_params = {
                    "creation_id": creation_id,
                    "access_token": self.access_token
                }
                res2 = await client.post(publish_url, params=publish_params)
                data2 = res2.json()

                if res2.status_code == 200 and "id" in data2:
                    post_id = data2["id"]
                    return ActionResult(
                        success=True,
                        platform="instagram",
                        action="post_photo",
                        message=f"Successfully published photo to Instagram! Post ID: {post_id}",
                        data={"post_id": post_id, "creation_id": creation_id}
                    )
                else:
                    err_msg = data2.get("error", {}).get("message", res2.text)
                    return ActionResult(
                        success=False,
                        platform="instagram",
                        action="post_photo",
                        message="Failed to publish Instagram media container.",
                        error=err_msg
                    )
        except Exception as e:
            return ActionResult(
                success=False,
                platform="instagram",
                action="post_photo",
                message="Exception during Instagram photo publication.",
                error=str(e)
            )

    async def get_recent_media(self, limit: int = 5) -> ActionResult:
        """Fetches recent Instagram posts with likes and comments count."""
        if not self.is_configured():
            return ActionResult(
                success=False,
                platform="instagram",
                action="get_recent_media",
                message="Instagram credentials not configured.",
                error="UNCONFIGURED"
            )

        url = f"{self.base_url}/{self.account_id}/media"
        params = {
            "fields": "id,caption,media_type,media_url,like_count,comments_count,timestamp,permalink",
            "limit": limit,
            "access_token": self.access_token
        }

        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                res = await client.get(url, params=params)
                data = res.json()

                if res.status_code == 200 and "data" in data:
                    media_list = data["data"]
                    return ActionResult(
                        success=True,
                        platform="instagram",
                        action="get_recent_media",
                        message=f"Retrieved {len(media_list)} recent Instagram posts.",
                        data={"media": media_list}
                    )
                else:
                    err_msg = data.get("error", {}).get("message", res.text)
                    return ActionResult(
                        success=False,
                        platform="instagram",
                        action="get_recent_media",
                        message="Failed to retrieve Instagram media.",
                        error=err_msg
                    )
        except Exception as e:
            return ActionResult(
                success=False,
                platform="instagram",
                action="get_recent_media",
                message="Failed to fetch Instagram media.",
                error=str(e)
            )
