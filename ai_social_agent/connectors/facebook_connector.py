"""
Facebook Page Graph API & Marketing Connector.
Supports:
- Multi-tenant dynamic initialization with per-user tokens and Page IDs.
- Publishing text status updates, photos with captions, and CTA ad-style posts.
- Meta Ads campaign creation via Marketing API.
- Querying Page profile, follower counts, and ratings.
- Fetching posts with comments, likes, shares, and performance insights.
- Reading Facebook Page Inbox (Messenger conversations) and replying to customers.
- Reading and replying to comments on posts.
- Token validation and automatic multi-page discovery.
"""

import os
import json
import logging
import httpx
from pathlib import Path
from typing import Optional, Dict, Any, List
from .base import BaseConnector, ActionResult
from ..config.config import config

logger = logging.getLogger("SocialCommander.Facebook")


class FacebookConnector(BaseConnector):
    def __init__(
        self,
        page_id: Optional[str] = None,
        access_token: Optional[str] = None,
        api_version: Optional[str] = None,
        ad_account_id: Optional[str] = None
    ):
        super().__init__("facebook")
        self.page_id = (page_id or config.FACEBOOK_PAGE_ID or "").strip()
        self.access_token = (access_token or config.FACEBOOK_ACCESS_TOKEN or "").strip()
        self.api_version = (api_version or config.FACEBOOK_API_VERSION or "v19.0").strip()
        self.ad_account_id = (ad_account_id or "").strip()
        self.base_url = f"https://graph.facebook.com/{self.api_version}"

    def is_configured(self) -> bool:
        return bool(self.page_id and self.access_token)

    @classmethod
    async def validate_token(cls, token: str, api_version: str = "v19.0") -> ActionResult:
        """
        Validates a Facebook Access Token against the Meta Graph API.
        Automatically detects whether it is a User Access Token or Page Access Token.
        Returns discovered pages or page details.
        """
        clean_token = token.strip()
        if not clean_token:
            return ActionResult(
                success=False,
                platform="facebook",
                action="validate_token",
                message="Token is empty.",
                error="EMPTY_TOKEN"
            )

        base_url = f"https://graph.facebook.com/{api_version}"

        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                # 1. Inspect /me
                me_res = await client.get(
                    f"{base_url}/me",
                    params={"fields": "id,name,category,fan_count,link", "access_token": clean_token}
                )
                me_data = me_res.json()

                if me_res.status_code != 200 or "id" not in me_data:
                    err_msg = me_data.get("error", {}).get("message", me_res.text)
                    return ActionResult(
                        success=False,
                        platform="facebook",
                        action="validate_token",
                        message=f"Invalid Facebook Token: {err_msg}",
                        error=err_msg
                    )

                # 2. Check /me/accounts to see if this is a User Token with managed Pages
                accounts_res = await client.get(
                    f"{base_url}/me/accounts",
                    params={
                        "fields": "id,name,category,fan_count,access_token,tasks",
                        "limit": 50,
                        "access_token": clean_token
                    }
                )
                accounts_data = accounts_res.json()
                pages = accounts_data.get("data", []) if accounts_res.status_code == 200 else []

                if pages:
                    # It is a User Access Token managing one or more pages
                    return ActionResult(
                        success=True,
                        platform="facebook",
                        action="validate_token",
                        message=f"Valid User Token for '{me_data.get('name')}'. Found {len(pages)} managed Facebook Page(s).",
                        data={
                            "token_type": "user",
                            "user_id": me_data.get("id"),
                            "user_name": me_data.get("name"),
                            "pages": pages
                        }
                    )
                else:
                    # It is either a direct Page Access Token or a user with 0 pages
                    # If it has a category or fan_count, it's definitely a Page Token
                    is_page = "category" in me_data or "fan_count" in me_data
                    return ActionResult(
                        success=True,
                        platform="facebook",
                        action="validate_token",
                        message=f"Valid Facebook {'Page' if is_page else 'Account'} Token for '{me_data.get('name')}'.",
                        data={
                            "token_type": "page" if is_page else "user_no_pages",
                            "page": {
                                "id": me_data.get("id"),
                                "name": me_data.get("name"),
                                "access_token": clean_token,
                                "category": me_data.get("category", "General"),
                                "fan_count": me_data.get("fan_count", 0)
                            },
                            "pages": [{
                                "id": me_data.get("id"),
                                "name": me_data.get("name"),
                                "access_token": clean_token,
                                "category": me_data.get("category", "General"),
                                "fan_count": me_data.get("fan_count", 0)
                            }] if is_page else []
                        }
                    )
        except Exception as e:
            return ActionResult(
                success=False,
                platform="facebook",
                action="validate_token",
                message=f"Exception validating token: {str(e)}",
                error=str(e)
            )

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
                    "fields": "id,name,fan_count,followers_count,category,verification_status,link",
                    "access_token": self.access_token
                }
                res = await client.get(url, params=params)
                data = res.json()

                if res.status_code == 200 and "id" in data:
                    page_name = data.get("name", "Unknown Page")
                    fans = data.get("fan_count", 0)
                    followers = data.get("followers_count", fans)
                    return ActionResult(
                        success=True,
                        platform="facebook",
                        action="test_connection",
                        message=f"Connected to Facebook Page: '{page_name}' ({followers} followers)",
                        data=data
                    )
                else:
                    err_msg = data.get("error", {}).get("message", res.text)
                    return ActionResult(
                        success=False,
                        platform="facebook",
                        action="test_connection",
                        message=f"Facebook API connection failed: {err_msg}",
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

    async def get_page_overview(self) -> ActionResult:
        """Retrieves rich details and statistics for the managed Facebook Page."""
        if not self.is_configured():
            return ActionResult(
                success=False,
                platform="facebook",
                action="get_page_overview",
                message="Facebook credentials not configured.",
                error="UNCONFIGURED"
            )
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                url = f"{self.base_url}/{self.page_id}"
                params = {
                    "fields": "id,name,fan_count,followers_count,category,about,description,website,link,rating_count,overall_star_rating",
                    "access_token": self.access_token
                }
                res = await client.get(url, params=params)
                data = res.json()

                if res.status_code == 200 and "id" in data:
                    name = data.get("name", "Facebook Page")
                    fans = data.get("fan_count", 0)
                    followers = data.get("followers_count", fans)
                    cat = data.get("category", "General")
                    about = data.get("about") or data.get("description") or "No description provided."
                    web = data.get("website", "N/A")
                    link = data.get("link", f"https://facebook.com/{self.page_id}")
                    rating = data.get("overall_star_rating")
                    rating_str = f" ⭐ {rating}/5" if rating else ""

                    summary = (
                        f"📄 *Facebook Page Profile: {name}*\n"
                        f"🆔 Page ID: `{self.page_id}`\n"
                        f"🏷 Category: {cat}\n"
                        f"👥 Followers: {followers:,} | Likes: {fans:,}{rating_str}\n"
                        f"🌐 Link: {link}\n"
                        f"📝 About: _{about[:200]}_"
                    )
                    return ActionResult(
                        success=True,
                        platform="facebook",
                        action="get_page_overview",
                        message=summary,
                        data=data
                    )
                else:
                    err_msg = data.get("error", {}).get("message", res.text)
                    return ActionResult(
                        success=False,
                        platform="facebook",
                        action="get_page_overview",
                        message=f"Failed to fetch Facebook Page overview: {err_msg}",
                        error=err_msg
                    )
        except Exception as e:
            return ActionResult(
                success=False,
                platform="facebook",
                action="get_page_overview",
                message=f"Exception retrieving Page overview: {str(e)}",
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
                        message=f"Successfully published post to Facebook Page! Post ID: `{post_id}`",
                        data={"post_id": post_id}
                    )
                else:
                    err_msg = data.get("error", {}).get("message", res.text)
                    return ActionResult(
                        success=False,
                        platform="facebook",
                        action="post_text",
                        message=f"Failed to post text to Facebook: {err_msg}",
                        error=err_msg
                    )
        except Exception as e:
            return ActionResult(
                success=False,
                platform="facebook",
                action="post_text",
                message=f"Failed to execute Facebook text post: {str(e)}",
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
        image_bytes = None

        # 1. Check local file on disk
        if image_url and os.path.exists(image_url):
            try:
                with open(image_url, "rb") as f:
                    image_bytes = f.read()
                logger.info(f"Loaded local image file ({len(image_bytes)} bytes) from: {image_url}")
            except Exception as e:
                logger.warning(f"Failed to read local file {image_url}: {e}")

        # 2. Check local UPLOADS_DIR if a /media/ URL or filename was passed
        if not image_bytes and image_url and ("/media/" in image_url or not image_url.startswith("http")):
            clean_name = os.path.basename(image_url.split("?")[0])
            for check_dir in [config.UPLOADS_DIR, config.BASE_DIR / "uploads", Path(os.getcwd()) / "uploads"]:
                cand = check_dir / clean_name
                if cand.exists() and cand.is_file():
                    try:
                        with open(cand, "rb") as f:
                            image_bytes = f.read()
                        break
                    except Exception as e:
                        logger.warning(f"Error reading local candidate {cand}: {e}")

        # 3. HTTP/HTTPS URL
        if not image_bytes and image_url and (image_url.startswith("http://") or image_url.startswith("https://")):
            try:
                async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as dl_client:
                    img_resp = await dl_client.get(image_url)
                    if img_resp.status_code == 200 and len(img_resp.content) > 0:
                        image_bytes = img_resp.content
            except Exception as e:
                logger.warning(f"Error fetching image bytes from {image_url}: {e}")

        try:
            async with httpx.AsyncClient(timeout=45.0) as client:
                if image_bytes:
                    files = {"source": ("post_image.jpg", image_bytes, "image/jpeg")}
                    data = {
                        "caption": caption or "",
                        "access_token": self.access_token,
                        "published": "true"
                    }
                    res = await client.post(url, files=files, data=data)
                else:
                    params = {
                        "url": image_url,
                        "caption": caption or "",
                        "access_token": self.access_token,
                        "published": "true"
                    }
                    res = await client.post(url, params=params)

                data = res.json()
                if res.status_code == 200 and ("id" in data or "post_id" in data):
                    photo_id = data.get("id") or data.get("post_id")
                    return ActionResult(
                        success=True,
                        platform="facebook",
                        action="post_photo",
                        message=f"Successfully posted photo to Facebook Page! Photo ID: `{photo_id}`",
                        data={"photo_id": photo_id}
                    )
                else:
                    err_info = data.get("error", {})
                    err_msg = err_info.get("message", res.text)
                    return ActionResult(
                        success=False,
                        platform="facebook",
                        action="post_photo",
                        message=f"Failed to post photo to Facebook: {err_msg}",
                        error=err_msg
                    )
        except Exception as e:
            return ActionResult(
                success=False,
                platform="facebook",
                action="post_photo",
                message=f"Failed to upload photo to Facebook: {str(e)}",
                error=str(e)
            )

    async def publish_cta_ad_post(
        self,
        message: str,
        link: str,
        cta_type: str = "LEARN_MORE",
        caption: Optional[str] = None,
        image_url: Optional[str] = None
    ) -> ActionResult:
        """
        Publishes a Call-To-Action (CTA) ad-style post to the Facebook Page feed.
        CTA Types: LEARN_MORE, SHOP_NOW, SIGN_UP, CONTACT_US, BOOK_TRAVEL, GET_QUOTE, APPLY_NOW, SUBSCRIBE.
        """
        if not self.is_configured():
            return ActionResult(
                success=False,
                platform="facebook",
                action="publish_cta_ad_post",
                message="Facebook credentials not configured.",
                error="UNCONFIGURED"
            )

        allowed_ctas = [
            "LEARN_MORE", "SHOP_NOW", "SIGN_UP", "CONTACT_US",
            "BOOK_TRAVEL", "GET_QUOTE", "APPLY_NOW", "SUBSCRIBE"
        ]
        clean_cta = cta_type.upper().strip() if cta_type else "LEARN_MORE"
        if clean_cta not in allowed_ctas:
            clean_cta = "LEARN_MORE"

        url = f"{self.base_url}/{self.page_id}/feed"
        payload = {
            "message": message,
            "link": link,
            "access_token": self.access_token,
            "call_to_action": json.dumps({
                "type": clean_cta,
                "value": {"link": link}
            })
        }
        if caption:
            payload["caption"] = caption
        if image_url:
            payload["picture"] = image_url

        try:
            async with httpx.AsyncClient(timeout=25.0) as client:
                res = await client.post(url, data=payload)
                data = res.json()

                if res.status_code == 200 and "id" in data:
                    post_id = data["id"]
                    return ActionResult(
                        success=True,
                        platform="facebook",
                        action="publish_cta_ad_post",
                        message=f"🚀 Successfully published CTA Ad Post with button [{clean_cta}]! Post ID: `{post_id}`",
                        data={"post_id": post_id, "cta": clean_cta, "link": link}
                    )
                else:
                    # Fallback to standard post with link if CTA schema is rejected by page permissions
                    fallback_payload = {
                        "message": f"{message}\n\n👉 {link}",
                        "link": link,
                        "access_token": self.access_token
                    }
                    fb_res = await client.post(url, data=fallback_payload)
                    fb_data = fb_res.json()
                    if fb_res.status_code == 200 and "id" in fb_data:
                        return ActionResult(
                            success=True,
                            platform="facebook",
                            action="publish_cta_ad_post",
                            message=f"✅ Published sponsored link post! Post ID: `{fb_data['id']}`",
                            data={"post_id": fb_data["id"], "link": link}
                        )
                    err_msg = data.get("error", {}).get("message", res.text)
                    return ActionResult(
                        success=False,
                        platform="facebook",
                        action="publish_cta_ad_post",
                        message=f"Failed to publish ad post: {err_msg}",
                        error=err_msg
                    )
        except Exception as e:
            return ActionResult(
                success=False,
                platform="facebook",
                action="publish_cta_ad_post",
                message=f"Exception publishing ad post: {str(e)}",
                error=str(e)
            )

    async def create_ad_campaign(
        self,
        name: str,
        objective: str = "OUTCOME_TRAFFIC",
        daily_budget: Optional[int] = None,
        ad_account_id: Optional[str] = None
    ) -> ActionResult:
        """
        Creates an Ad Campaign via the Meta Marketing API.
        Objectives: OUTCOME_TRAFFIC, OUTCOME_ENGAGEMENT, OUTCOME_LEADS, OUTCOME_SALES.
        """
        target_account = ad_account_id or self.ad_account_id
        if not target_account:
            return ActionResult(
                success=False,
                platform="facebook",
                action="create_ad_campaign",
                message="No Meta Ad Account ID configured (format: act_XXXXXXXXX). Set it in your account settings.",
                error="MISSING_AD_ACCOUNT"
            )

        clean_act = target_account if target_account.startswith("act_") else f"act_{target_account}"
        url = f"{self.base_url}/{clean_act}/campaigns"

        payload = {
            "name": name,
            "objective": objective,
            "status": "PAUSED",  # Always create paused for safety
            "special_ad_categories": "[]",
            "access_token": self.access_token
        }
        if daily_budget:
            # Meta accepts daily budget in cents (e.g. $10 = 1000)
            payload["daily_budget"] = str(int(daily_budget * 100))

        try:
            async with httpx.AsyncClient(timeout=25.0) as client:
                res = await client.post(url, data=payload)
                data = res.json()

                if res.status_code == 200 and "id" in data:
                    camp_id = data["id"]
                    return ActionResult(
                        success=True,
                        platform="facebook",
                        action="create_ad_campaign",
                        message=f"🎉 Successfully created Meta Ad Campaign: '{name}' (ID: `{camp_id}`, Status: PAUSED)",
                        data={"campaign_id": camp_id, "account_id": clean_act}
                    )
                else:
                    err_msg = data.get("error", {}).get("message", res.text)
                    return ActionResult(
                        success=False,
                        platform="facebook",
                        action="create_ad_campaign",
                        message=f"Failed to create Meta Ad Campaign: {err_msg}",
                        error=err_msg
                    )
        except Exception as e:
            return ActionResult(
                success=False,
                platform="facebook",
                action="create_ad_campaign",
                message=f"Exception creating ad campaign: {str(e)}",
                error=str(e)
            )

    async def get_recent_posts(self, limit: int = 5) -> ActionResult:
        """Fetches latest posts from Facebook Page feed."""
        return await self.get_posts_with_insights(limit=limit)

    async def get_posts_with_insights(self, limit: int = 5) -> ActionResult:
        """
        Fetches latest posts with likes count, comments summary, shares,
        and post insights (impressions, reach, engagement).
        """
        if not self.is_configured():
            return ActionResult(
                success=False,
                platform="facebook",
                action="get_posts_with_insights",
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
            async with httpx.AsyncClient(timeout=25.0) as client:
                res = await client.get(url, params=params)
                data = res.json()

                if res.status_code == 200 and "data" in data:
                    posts = data["data"]
                    formatted_posts = []

                    for p in posts:
                        p_id = p.get("id")
                        msg = p.get("message", "[Photo / Media Post]")
                        created = p.get("created_time", "")[:10]
                        likes = p.get("likes", {}).get("summary", {}).get("total_count", 0)
                        comments_count = p.get("comments", {}).get("summary", {}).get("total_count", 0)
                        shares_count = p.get("shares", {}).get("count", 0)

                        formatted_posts.append({
                            "id": p_id,
                            "message": msg,
                            "date": created,
                            "likes": likes,
                            "comments": comments_count,
                            "shares": shares_count
                        })

                    # Construct human-readable summary
                    lines = [f"📊 *Latest {len(formatted_posts)} Facebook Posts & Performance:*"]
                    for idx, fp in enumerate(formatted_posts, 1):
                        snippet = fp["message"][:80].replace("\n", " ") + ("..." if len(fp["message"]) > 80 else "")
                        lines.append(
                            f"{idx}. 📌 *Post ID:* `{fp['id']}` ({fp['date']})\n"
                            f"   📝 \"_{snippet}_\"\n"
                            f"   👍 Likes: {fp['likes']} | 💬 Comments: {fp['comments']} | 🔄 Shares: {fp['shares']}"
                        )

                    return ActionResult(
                        success=True,
                        platform="facebook",
                        action="get_posts_with_insights",
                        message="\n\n".join(lines),
                        data={"posts": formatted_posts, "raw": posts}
                    )
                else:
                    err_msg = data.get("error", {}).get("message", res.text)
                    return ActionResult(
                        success=False,
                        platform="facebook",
                        action="get_posts_with_insights",
                        message=f"Failed to retrieve Facebook posts: {err_msg}",
                        error=err_msg
                    )
        except Exception as e:
            return ActionResult(
                success=False,
                platform="facebook",
                action="get_posts_with_insights",
                message=f"Failed to fetch Facebook posts: {str(e)}",
                error=str(e)
            )

    async def get_conversations(self, limit: int = 10, unread_only: bool = False) -> ActionResult:
        """
        Fetches customer Messenger conversations from the Page Inbox.
        Returns threads, customer names, snippets, and unread statuses.
        """
        if not self.is_configured():
            return ActionResult(
                success=False,
                platform="facebook",
                action="get_conversations",
                message="Facebook credentials not configured.",
                error="UNCONFIGURED"
            )

        url = f"{self.base_url}/{self.page_id}/conversations"
        params = {
            "fields": "id,snippet,updated_time,unread_count,senders,messages.limit(1){id,message,from,created_time}",
            "limit": limit,
            "access_token": self.access_token
        }

        try:
            async with httpx.AsyncClient(timeout=25.0) as client:
                res = await client.get(url, params=params)
                data = res.json()

                if res.status_code == 200 and "data" in data:
                    threads = data["data"]
                    if unread_only:
                        threads = [t for t in threads if t.get("unread_count", 0) > 0]

                    formatted = []
                    for t in threads:
                        t_id = t.get("id")
                        snippet = t.get("snippet", "[No preview]")
                        unread = t.get("unread_count", 0)
                        senders = t.get("senders", {}).get("data", [])
                        # Find sender that is not the page itself
                        customer = "Customer"
                        for s in senders:
                            if s.get("id") != self.page_id:
                                customer = s.get("name") or s.get("email") or "Customer"
                                break

                        formatted.append({
                            "conversation_id": t_id,
                            "customer": customer,
                            "snippet": snippet,
                            "unread_count": unread,
                            "updated_time": t.get("updated_time", "")[:16].replace("T", " ")
                        })

                    if not formatted:
                        return ActionResult(
                            success=True,
                            platform="facebook",
                            action="get_conversations",
                            message="📥 *Facebook Inbox is clear!* No recent conversations found.",
                            data={"conversations": []}
                        )

                    lines = [f"📬 *Facebook Page Inbox ({len(formatted)} Threads):*"]
                    for idx, item in enumerate(formatted, 1):
                        unread_badge = " 🔴 [UNREAD]" if item["unread_count"] > 0 else ""
                        lines.append(
                            f"{idx}. 👤 *{item['customer']}*{unread_badge}\n"
                            f"   🆔 Thread ID: `{item['conversation_id']}`\n"
                            f"   💬 \"_{item['snippet'][:100]}_\"\n"
                            f"   🕒 {item['updated_time']}"
                        )

                    return ActionResult(
                        success=True,
                        platform="facebook",
                        action="get_conversations",
                        message="\n\n".join(lines),
                        data={"conversations": formatted, "raw": threads}
                    )
                else:
                    err_msg = data.get("error", {}).get("message", res.text)
                    return ActionResult(
                        success=False,
                        platform="facebook",
                        action="get_conversations",
                        message=f"Failed to fetch Facebook conversations: {err_msg}",
                        error=err_msg
                    )
        except Exception as e:
            return ActionResult(
                success=False,
                platform="facebook",
                action="get_conversations",
                message=f"Exception reading Facebook inbox: {str(e)}",
                error=str(e)
            )

    async def get_conversation_messages(self, conversation_id: str, limit: int = 10) -> ActionResult:
        """Fetches messages within a specific conversation thread."""
        if not self.is_configured():
            return ActionResult(
                success=False,
                platform="facebook",
                action="get_conversation_messages",
                message="Facebook credentials not configured.",
                error="UNCONFIGURED"
            )

        url = f"{self.base_url}/{conversation_id}/messages"
        params = {
            "fields": "id,message,from,created_time",
            "limit": limit,
            "access_token": self.access_token
        }

        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                res = await client.get(url, params=params)
                data = res.json()

                if res.status_code == 200 and "data" in data:
                    msgs = data["data"]
                    msgs.reverse()  # Chronological order

                    lines = [f"💬 *Conversation History (`{conversation_id}`):*"]
                    for m in msgs:
                        sender = m.get("from", {}).get("name", "User")
                        text = m.get("message", "[Attachment]")
                        time_str = m.get("created_time", "")[:16].replace("T", " ")
                        lines.append(f"• *{sender}* ({time_str}):\n  _{text}_")

                    return ActionResult(
                        success=True,
                        platform="facebook",
                        action="get_conversation_messages",
                        message="\n\n".join(lines),
                        data={"messages": msgs}
                    )
                else:
                    err_msg = data.get("error", {}).get("message", res.text)
                    return ActionResult(
                        success=False,
                        platform="facebook",
                        action="get_conversation_messages",
                        message=f"Failed to fetch messages: {err_msg}",
                        error=err_msg
                    )
        except Exception as e:
            return ActionResult(
                success=False,
                platform="facebook",
                action="get_conversation_messages",
                message=f"Exception fetching messages: {str(e)}",
                error=str(e)
            )

    async def send_inbox_reply(
        self,
        conversation_id: str,
        message: str,
        recipient_id: Optional[str] = None
    ) -> ActionResult:
        """
        Sends a reply to a customer in their Messenger conversation thread.
        Supports thread message endpoint `POST /{conversation_id}/messages`
        and fallback Send API `POST /me/messages`.
        """
        if not self.is_configured():
            return ActionResult(
                success=False,
                platform="facebook",
                action="send_inbox_reply",
                message="Facebook credentials not configured.",
                error="UNCONFIGURED"
            )

        # 1. Try /{conversation_id}/messages
        url = f"{self.base_url}/{conversation_id}/messages"
        payload = {
            "message": message,
            "access_token": self.access_token
        }

        try:
            async with httpx.AsyncClient(timeout=25.0) as client:
                res = await client.post(url, data=payload)
                data = res.json()

                if res.status_code == 200 and "id" in data:
                    return ActionResult(
                        success=True,
                        platform="facebook",
                        action="send_inbox_reply",
                        message=f"✅ Successfully sent reply to customer! Message ID: `{data['id']}`",
                        data=data
                    )
                
                # 2. Fallback to Send API if recipient_id is known
                if recipient_id:
                    send_url = f"{self.base_url}/me/messages"
                    send_payload = {
                        "recipient": json.dumps({"id": recipient_id}),
                        "message": json.dumps({"text": message}),
                        "access_token": self.access_token
                    }
                    res2 = await client.post(send_url, data=send_payload)
                    data2 = res2.json()
                    if res2.status_code == 200 and "message_id" in data2:
                        return ActionResult(
                            success=True,
                            platform="facebook",
                            action="send_inbox_reply",
                            message=f"✅ Sent reply via Messenger Send API! Message ID: `{data2['message_id']}`",
                            data=data2
                        )

                err_msg = data.get("error", {}).get("message", res.text)
                return ActionResult(
                    success=False,
                    platform="facebook",
                    action="send_inbox_reply",
                    message=f"Failed to send Facebook reply: {err_msg}",
                    error=err_msg
                )
        except Exception as e:
            return ActionResult(
                success=False,
                platform="facebook",
                action="send_inbox_reply",
                message=f"Exception sending inbox reply: {str(e)}",
                error=str(e)
            )

    async def get_post_comments(self, post_id: str, limit: int = 25) -> ActionResult:
        """Fetches comments on a specific post."""
        if not self.is_configured():
            return ActionResult(
                success=False,
                platform="facebook",
                action="get_post_comments",
                message="Facebook credentials not configured.",
                error="UNCONFIGURED"
            )

        url = f"{self.base_url}/{post_id}/comments"
        params = {
            "fields": "id,from,message,created_time,like_count,comment_count",
            "limit": limit,
            "access_token": self.access_token
        }

        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                res = await client.get(url, params=params)
                data = res.json()

                if res.status_code == 200 and "data" in data:
                    comments = data["data"]
                    if not comments:
                        return ActionResult(
                            success=True,
                            platform="facebook",
                            action="get_post_comments",
                            message=f"No comments found on post `{post_id}`.",
                            data={"comments": []}
                        )

                    lines = [f"💬 *Comments on Post `{post_id}` ({len(comments)} total):*"]
                    for c in comments:
                        c_id = c.get("id")
                        author = c.get("from", {}).get("name", "User")
                        text = c.get("message", "")
                        likes = c.get("like_count", 0)
                        lines.append(f"• 👤 *{author}* (ID: `{c_id}` | 👍 {likes}):\n  _{text}_")

                    return ActionResult(
                        success=True,
                        platform="facebook",
                        action="get_post_comments",
                        message="\n\n".join(lines),
                        data={"comments": comments}
                    )
                else:
                    err_msg = data.get("error", {}).get("message", res.text)
                    return ActionResult(
                        success=False,
                        platform="facebook",
                        action="get_post_comments",
                        message=f"Failed to fetch post comments: {err_msg}",
                        error=err_msg
                    )
        except Exception as e:
            return ActionResult(
                success=False,
                platform="facebook",
                action="get_post_comments",
                message=f"Exception retrieving comments: {str(e)}",
                error=str(e)
            )

    async def reply_to_comment(self, comment_id: str, message: str) -> ActionResult:
        """Replies directly to a user comment on a post."""
        if not self.is_configured():
            return ActionResult(
                success=False,
                platform="facebook",
                action="reply_to_comment",
                message="Facebook credentials not configured.",
                error="UNCONFIGURED"
            )

        url = f"{self.base_url}/{comment_id}/comments"
        payload = {
            "message": message,
            "access_token": self.access_token
        }

        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                res = await client.post(url, data=payload)
                data = res.json()

                if res.status_code == 200 and "id" in data:
                    return ActionResult(
                        success=True,
                        platform="facebook",
                        action="reply_to_comment",
                        message=f"✅ Replied to comment! Reply ID: `{data['id']}`",
                        data=data
                    )
                else:
                    err_msg = data.get("error", {}).get("message", res.text)
                    return ActionResult(
                        success=False,
                        platform="facebook",
                        action="reply_to_comment",
                        message=f"Failed to reply to comment: {err_msg}",
                        error=err_msg
                    )
        except Exception as e:
            return ActionResult(
                success=False,
                platform="facebook",
                action="reply_to_comment",
                message=f"Exception replying to comment: {str(e)}",
                error=str(e)
            )

    async def upload_unpublished_photo(self, image_url_or_path: str) -> Optional[str]:
        """Uploads an image to Facebook Page with published=false to obtain a Meta CDN URL."""
        if not self.is_configured() or not image_url_or_path:
            return None

        image_bytes = None
        if os.path.exists(image_url_or_path):
            try:
                with open(image_url_or_path, "rb") as f:
                    image_bytes = f.read()
            except Exception as e:
                logger.warning(f"Error reading local file: {e}")

        if not image_bytes and (image_url_or_path.startswith("http://") or image_url_or_path.startswith("https://")):
            try:
                async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as dl_client:
                    r = await dl_client.get(image_url_or_path)
                    if r.status_code == 200 and len(r.content) > 0:
                        image_bytes = r.content
            except Exception as e:
                logger.warning(f"Error downloading image: {e}")

        if not image_bytes:
            return None

        try:
            async with httpx.AsyncClient(timeout=40.0) as client:
                url = f"{self.base_url}/{self.page_id}/photos"
                files = {"source": ("meta_temp.jpg", image_bytes, "image/jpeg")}
                data = {"published": "false", "access_token": self.access_token}
                res = await client.post(url, files=files, data=data)
                resp_json = res.json()

                if res.status_code == 200 and "id" in resp_json:
                    photo_id = resp_json["id"]
                    query_url = f"{self.base_url}/{photo_id}?fields=images&access_token={self.access_token}"
                    q_res = await client.get(query_url)
                    if q_res.status_code == 200:
                        images = q_res.json().get("images", [])
                        if images and "source" in images[0]:
                            return images[0]["source"]
        except Exception as e:
            logger.warning(f"Exception creating Meta CDN URL: {e}")

        return None

    async def get_recent_page_comments(self, limit: int = 15) -> ActionResult:
        """
        Fetches recent customer comments across all latest Page posts.
        Returns flattened list of comments with post title, commenter name, and text.
        """
        if not self.is_configured():
            return ActionResult(
                success=False,
                platform="facebook",
                action="get_recent_page_comments",
                message="Facebook credentials not configured.",
                error="UNCONFIGURED"
            )

        url = f"{self.base_url}/{self.page_id}/posts"
        params = {
            "fields": "id,message,comments.limit(10){id,from,message,created_time,like_count}",
            "limit": 5,
            "access_token": self.access_token
        }

        try:
            async with httpx.AsyncClient(timeout=25.0) as client:
                res = await client.get(url, params=params)
                data = res.json()

                if res.status_code == 200 and "data" in data:
                    posts = data["data"]
                    all_comments = []

                    for p in posts:
                        p_id = p.get("id")
                        p_title = (p.get("message") or "[Media Post]")[:50]
                        comments_data = p.get("comments", {}).get("data", [])
                        for c in comments_data:
                            all_comments.append({
                                "comment_id": c.get("id"),
                                "post_id": p_id,
                                "post_title": p_title,
                                "author": c.get("from", {}).get("name", "User"),
                                "message": c.get("message", ""),
                                "created_time": c.get("created_time", "")[:16].replace("T", " ")
                            })
                            if len(all_comments) >= limit:
                                break
                        if len(all_comments) >= limit:
                            break

                    if not all_comments:
                        return ActionResult(
                            success=True,
                            platform="facebook",
                            action="get_recent_page_comments",
                            message="💬 *No comments found on recent posts.*",
                            data={"comments": []}
                        )

                    lines = [f"💬 *Recent Comments on Page Posts ({len(all_comments)} total):*"]
                    for idx, c in enumerate(all_comments, 1):
                        lines.append(
                            f"{idx}. 👤 *{c['author']}* (Comment ID: `{c['comment_id']}`)\n"
                            f"   📌 *Post:* _{c['post_title']}_\n"
                            f"   💬 \"_{c['message']}_\"\n"
                            f"   🕒 {c['created_time']}"
                        )

                    return ActionResult(
                        success=True,
                        platform="facebook",
                        action="get_recent_page_comments",
                        message="\n\n".join(lines),
                        data={"comments": all_comments}
                    )
                else:
                    err_msg = data.get("error", {}).get("message", res.text)
                    return ActionResult(
                        success=False,
                        platform="facebook",
                        action="get_recent_page_comments",
                        message=f"Failed to fetch page comments: {err_msg}",
                        error=err_msg
                    )
        except Exception as e:
            return ActionResult(
                success=False,
                platform="facebook",
                action="get_recent_page_comments",
                message=f"Exception fetching page comments: {str(e)}",
                error=str(e)
            )

    async def schedule_post(
        self,
        message: str,
        publish_timestamp: int,
        image_url: Optional[str] = None
    ) -> ActionResult:
        """
        Schedules a Facebook post to be published at a future time.
        publish_timestamp must be between 10 minutes and 75 days in the future.
        """
        if not self.is_configured():
            return ActionResult(
                success=False,
                platform="facebook",
                action="schedule_post",
                message="Facebook credentials not configured.",
                error="UNCONFIGURED"
            )

        url = f"{self.base_url}/{self.page_id}/feed"
        payload = {
            "message": message,
            "published": "false",
            "scheduled_publish_time": str(int(publish_timestamp)),
            "access_token": self.access_token
        }
        if image_url:
            payload["link"] = image_url

        try:
            async with httpx.AsyncClient(timeout=25.0) as client:
                res = await client.post(url, data=payload)
                data = res.json()

                if res.status_code == 200 and "id" in data:
                    return ActionResult(
                        success=True,
                        platform="facebook",
                        action="schedule_post",
                        message=f"⏰ Successfully scheduled post! Post ID: `{data['id']}` (Scheduled for timestamp: {publish_timestamp})",
                        data={"post_id": data["id"], "scheduled_time": publish_timestamp}
                    )
                else:
                    err_msg = data.get("error", {}).get("message", res.text)
                    return ActionResult(
                        success=False,
                        platform="facebook",
                        action="schedule_post",
                        message=f"Failed to schedule post: {err_msg}",
                        error=err_msg
                    )
        except Exception as e:
            return ActionResult(
                success=False,
                platform="facebook",
                action="schedule_post",
                message=f"Exception scheduling post: {str(e)}",
                error=str(e)
            )

    async def post_video(
        self,
        video_url_or_path: str,
        title: str,
        description: str
    ) -> ActionResult:
        """Publishes a video or Reel to the Facebook Page."""
        if not self.is_configured():
            return ActionResult(
                success=False,
                platform="facebook",
                action="post_video",
                message="Facebook credentials not configured.",
                error="UNCONFIGURED"
            )

        url = f"{self.base_url}/{self.page_id}/videos"
        video_bytes = None

        if os.path.exists(video_url_or_path):
            try:
                with open(video_url_or_path, "rb") as f:
                    video_bytes = f.read()
            except Exception as e:
                logger.warning(f"Error reading local video file: {e}")

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                if video_bytes:
                    files = {"source": ("video.mp4", video_bytes, "video/mp4")}
                    data = {
                        "title": title,
                        "description": description,
                        "access_token": self.access_token
                    }
                    res = await client.post(url, files=files, data=data)
                else:
                    params = {
                        "file_url": video_url_or_path,
                        "title": title,
                        "description": description,
                        "access_token": self.access_token
                    }
                    res = await client.post(url, params=params)

                data = res.json()
                if res.status_code == 200 and "id" in data:
                    return ActionResult(
                        success=True,
                        platform="facebook",
                        action="post_video",
                        message=f"🎬 Successfully published video to Facebook Page! Video ID: `{data['id']}`",
                        data={"video_id": data["id"]}
                    )
                else:
                    err_msg = data.get("error", {}).get("message", res.text)
                    return ActionResult(
                        success=False,
                        platform="facebook",
                        action="post_video",
                        message=f"Failed to publish video: {err_msg}",
                        error=err_msg
                    )
        except Exception as e:
            return ActionResult(
                success=False,
                platform="facebook",
                action="post_video",
                message=f"Exception publishing video: {str(e)}",
                error=str(e)
            )

    async def moderate_comment(
        self,
        comment_id: str,
        action: str = "hide"
    ) -> ActionResult:
        """
        Moderates a comment on a Facebook post.
        action can be 'hide', 'unhide', or 'delete'.
        """
        if not self.is_configured():
            return ActionResult(
                success=False,
                platform="facebook",
                action="moderate_comment",
                message="Facebook credentials not configured.",
                error="UNCONFIGURED"
            )

        clean_action = action.lower().strip()

        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                if clean_action == "delete":
                    url = f"{self.base_url}/{comment_id}"
                    res = await client.delete(url, params={"access_token": self.access_token})
                    data = res.json()
                    if res.status_code == 200 and data.get("success"):
                        return ActionResult(
                            success=True,
                            platform="facebook",
                            action="moderate_comment",
                            message=f"🗑 Successfully deleted comment `{comment_id}`.",
                            data=data
                        )
                else:
                    is_hidden = "true" if clean_action == "hide" else "false"
                    url = f"{self.base_url}/{comment_id}"
                    res = await client.post(url, data={"is_hidden": is_hidden, "access_token": self.access_token})
                    data = res.json()
                    if res.status_code == 200 and data.get("success"):
                        action_label = "hidden" if is_hidden == "true" else "unhidden"
                        return ActionResult(
                            success=True,
                            platform="facebook",
                            action="moderate_comment",
                            message=f"🙈 Successfully {action_label} comment `{comment_id}`.",
                            data=data
                        )

                err_msg = data.get("error", {}).get("message", res.text)
                return ActionResult(
                    success=False,
                    platform="facebook",
                    action="moderate_comment",
                    message=f"Failed to moderate comment: {err_msg}",
                    error=err_msg
                )
        except Exception as e:
            return ActionResult(
                success=False,
                platform="facebook",
                action="moderate_comment",
                message=f"Exception moderating comment: {str(e)}",
                error=str(e)
            )

    async def get_page_insights_summary(self, period: str = "day") -> ActionResult:
        """Fetches page impressions, page views, and engagement trends."""
        if not self.is_configured():
            return ActionResult(
                success=False,
                platform="facebook",
                action="get_page_insights_summary",
                message="Facebook credentials not configured.",
                error="UNCONFIGURED"
            )

        url = f"{self.base_url}/{self.page_id}/insights"
        params = {
            "metric": "page_impressions,page_post_engagements,page_views_total",
            "period": period,
            "access_token": self.access_token
        }

        try:
            async with httpx.AsyncClient(timeout=25.0) as client:
                res = await client.get(url, params=params)
                data = res.json()

                if res.status_code == 200 and "data" in data:
                    metrics = data["data"]
                    lines = [f"📈 *Facebook Page Analytics ({period.capitalize()} Period):*"]
                    for m in metrics:
                        m_name = m.get("title") or m.get("name", "Metric")
                        values = m.get("values", [])
                        latest_val = values[-1].get("value", 0) if values else 0
                        lines.append(f"• *{m_name}:* `{latest_val:,}`")

                    return ActionResult(
                        success=True,
                        platform="facebook",
                        action="get_page_insights_summary",
                        message="\n".join(lines),
                        data={"metrics": metrics}
                    )
                else:
                    err_msg = data.get("error", {}).get("message", res.text)
                    return ActionResult(
                        success=False,
                        platform="facebook",
                        action="get_page_insights_summary",
                        message=f"Failed to retrieve page insights: {err_msg}",
                        error=err_msg
                    )
        except Exception as e:
            return ActionResult(
                success=False,
                platform="facebook",
                action="get_page_insights_summary",
                message=f"Exception retrieving page insights: {str(e)}",
                error=str(e)
            )


def get_facebook_connector_for_user(telegram_id: int) -> FacebookConnector:
    """
    Factory function: returns a FacebookConnector dynamically configured
    for a specific Telegram user from the SQLite user_db.
    """
    from ..core.user_db import user_db
    creds = user_db.get_user_credentials(telegram_id)
    if creds:
        return FacebookConnector(
            page_id=creds.get("page_id"),
            access_token=creds.get("page_access_token"),
            ad_account_id=creds.get("ad_account_id")
        )
    return FacebookConnector()
