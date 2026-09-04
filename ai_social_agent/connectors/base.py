"""
Base Connector interface and standardized ActionResult representation.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class ActionResult(BaseModel):
    success: bool
    platform: str
    action: str
    message: str
    data: Optional[Dict[str, Any]] = Field(default_factory=dict)
    error: Optional[str] = None

    def format_summary(self) -> str:
        """Returns a user-friendly status badge and summary message."""
        status_icon = "✅" if self.success else "❌"
        res = f"{status_icon} *{self.platform.capitalize()} - {self.action}*\n{self.message}"
        if not self.success and self.error:
            res += f"\n_Details:_ `{self.error}`"
        return res


class BaseConnector(ABC):
    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    def is_configured(self) -> bool:
        """Checks whether credentials and endpoints are present."""
        pass

    @abstractmethod
    async def test_connection(self) -> ActionResult:
        """Runs a lightweight ping or read check."""
        pass
