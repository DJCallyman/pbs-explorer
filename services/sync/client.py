from __future__ import annotations

import asyncio
import random
from typing import Any, Dict, Optional

import httpx

from config import get_settings


class PBSAPIClient:
    def __init__(
        self,
        *,
        timeout_seconds: float = 30.0,
        read_timeout_seconds: float = 120.0,
        max_retries: int = 6,
    ) -> None:
        settings = get_settings()
        self.base_url = settings.pbs.api_base_url.rstrip("/")
        self.subscription_key = settings.pbs.subscription_key
        self.timeout_seconds = timeout_seconds
        self.read_timeout_seconds = read_timeout_seconds
        self.max_retries = max_retries
        self._client: httpx.AsyncClient | None = None

    def _headers(self) -> Dict[str, str]:
        headers = {"Accept": "application/json"}
        if self.subscription_key:
            headers["Subscription-Key"] = self.subscription_key
        return headers

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    @staticmethod
    def _retry_delay_seconds(response: httpx.Response | None, attempt: int) -> float:
        if response is not None:
            retry_after = response.headers.get("Retry-After", "").strip()
            if retry_after.isdigit():
                return float(retry_after) + random.uniform(0.0, 0.5)
        return min(60.0, (2 ** attempt)) + random.uniform(0.0, 0.5)

    async def get(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> httpx.Response:
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        if self._client is None:
            timeout = httpx.Timeout(self.timeout_seconds, read=self.read_timeout_seconds)
            self._client = httpx.AsyncClient(timeout=timeout)

        attempt = 0
        while True:
            try:
                response = await self._client.get(url, params=params, headers=self._headers())
                if response.status_code in {429, 502, 503, 504} and attempt < self.max_retries:
                    await asyncio.sleep(self._retry_delay_seconds(response, attempt))
                    attempt += 1
                    continue
                response.raise_for_status()
                return response
            except (httpx.ReadTimeout, httpx.ConnectTimeout, httpx.RemoteProtocolError, httpx.ReadError):
                if attempt >= self.max_retries:
                    raise
                await asyncio.sleep(self._retry_delay_seconds(None, attempt))
                attempt += 1
