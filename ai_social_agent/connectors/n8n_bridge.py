"""
n8n Bridge Connector.
Interacts with user's self-hosted/cloud n8n instance via REST API.
Enables triggering automated workflows, checking execution statuses, and running automation nodes.
"""

import httpx
from typing import Optional, Dict, Any, List
from .base import BaseConnector, ActionResult
from ..config.config import config


class N8NBridge(BaseConnector):
    def __init__(self):
        super().__init__("n8n")
        self.base_url = config.N8N_BASE_URL
        self.api_key = config.N8N_API_KEY
        self.headers = {
            "X-N8N-API-KEY": self.api_key,
            "Accept": "application/json",
            "Content-Type": "application/json"
        }

    def is_configured(self) -> bool:
        return bool(self.base_url and self.api_key)

    async def test_connection(self) -> ActionResult:
        if not self.is_configured():
            return ActionResult(
                success=False,
                platform="n8n",
                action="test_connection",
                message="n8n Base URL or API key is missing.",
                error="UNCONFIGURED"
            )

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                res = await client.get(f"{self.base_url}/workflows", headers=self.headers)
                if res.status_code == 200:
                    data = res.json()
                    wf_list = data.get("data", [])
                    active_count = sum(1 for w in wf_list if w.get("active"))
                    return ActionResult(
                        success=True,
                        platform="n8n",
                        action="test_connection",
                        message=f"Connected to n8n ({len(wf_list)} total workflows, {active_count} active).",
                        data={"total": len(wf_list), "active": active_count}
                    )
                else:
                    return ActionResult(
                        success=False,
                        platform="n8n",
                        action="test_connection",
                        message=f"n8n API responded with HTTP {res.status_code}",
                        error=res.text[:200]
                    )
        except Exception as e:
            return ActionResult(
                success=False,
                platform="n8n",
                action="test_connection",
                message=f"Exception connecting to n8n instance: {str(e)}",
                error=str(e)
            )

    async def list_workflows(self) -> ActionResult:
        """Lists workflows on the n8n instance."""
        if not self.is_configured():
            return ActionResult(
                success=False,
                platform="n8n",
                action="list_workflows",
                message="n8n credentials not configured.",
                error="UNCONFIGURED"
            )

        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                res = await client.get(f"{self.base_url}/workflows", headers=self.headers)
                if res.status_code == 200:
                    data = res.json().get("data", [])
                    simplified = [{"id": w.get("id"), "name": w.get("name"), "active": w.get("active")} for w in data]
                    return ActionResult(
                        success=True,
                        platform="n8n",
                        action="list_workflows",
                        message=f"Found {len(simplified)} workflows in n8n.",
                        data={"workflows": simplified}
                    )
                else:
                    return ActionResult(
                        success=False,
                        platform="n8n",
                        action="list_workflows",
                        message="Failed to list n8n workflows.",
                        error=res.text[:200]
                    )
        except Exception as e:
            return ActionResult(
                success=False,
                platform="n8n",
                action="list_workflows",
                message="Exception listing n8n workflows.",
                error=str(e)
            )

    async def trigger_webhook(self, webhook_path_or_url: str, payload: Optional[Dict[str, Any]] = None) -> ActionResult:
        """Triggers an n8n webhook workflow."""
        url = (
            webhook_path_or_url
            if webhook_path_or_url.startswith("http")
            else f"{self.base_url.replace('/api/v1', '')}/webhook/{webhook_path_or_url.lstrip('/')}"
        )
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                res = await client.post(url, json=payload or {})
                if res.status_code in (200, 201):
                    return ActionResult(
                        success=True,
                        platform="n8n",
                        action="trigger_webhook",
                        message=f"Successfully triggered n8n workflow at {url}",
                        data=res.json() if res.headers.get("content-type", "").startswith("application/json") else {"response": res.text}
                    )
                else:
                    return ActionResult(
                        success=False,
                        platform="n8n",
                        action="trigger_webhook",
                        message=f"n8n webhook responded with HTTP {res.status_code}",
                        error=res.text[:200]
                    )
        except Exception as e:
            return ActionResult(
                success=False,
                platform="n8n",
                action="trigger_webhook",
                message="Exception triggering n8n webhook.",
                error=str(e)
            )
