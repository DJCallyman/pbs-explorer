from __future__ import annotations

from typing import Any, Dict, Optional

import httpx

from config import get_settings


class PBSAPIClient:
    def __init__(self) -> None:
        settings = get_settings()
        self.base_url = settings.pbs.api_base_url.rstrip("/")
        self.subscription_key = settings.pbs.subscription_key

    def _headers(self) -> Dict[str, str]:
        headers = {"Accept": "application/json"}
        if self.subscription_key:
            headers["subscription-key"] = self.subscription_key
        return headers

    async def get(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> httpx.Response:
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.get(url, params=params, headers=self._headers())
            response.raise_for_status()
            return response
