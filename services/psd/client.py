from __future__ import annotations

import asyncio
import random
import time
from dataclasses import dataclass, field

import httpx


@dataclass(slots=True)
class PoliteHTTPClient:
    delay_seconds: float = 1.5
    timeout_seconds: float = 30.0
    max_retries: int = 4
    user_agent: str = "pbs-explorer-psd-sync/0.1 (+https://github.com/djcallyman/pbs-explorer)"
    _last_request_time: float = field(init=False, default=0.0)
    _client: httpx.AsyncClient = field(init=False)

    def __post_init__(self) -> None:
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(self.timeout_seconds, read=max(self.timeout_seconds, 120.0)),
            follow_redirects=True,
            headers={
                "User-Agent": self.user_agent,
                "Accept": "*/*",
            },
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _wait_turn(self) -> None:
        elapsed = time.monotonic() - self._last_request_time
        if elapsed < self.delay_seconds:
            await asyncio.sleep(self.delay_seconds - elapsed)
        self._last_request_time = time.monotonic()

    async def request(self, method: str, url: str, **kwargs) -> httpx.Response:
        attempt = 0
        while True:
            await self._wait_turn()
            try:
                response = await self._client.request(method, url, **kwargs)
                if response.status_code == 429 and attempt < self.max_retries:
                    retry_after = response.headers.get("Retry-After")
                    wait_seconds = float(retry_after) if retry_after and retry_after.isdigit() else 15.0
                    wait_seconds += random.uniform(0.0, 1.0)
                    await asyncio.sleep(wait_seconds)
                    attempt += 1
                    continue

                response.raise_for_status()
                return response
            except (httpx.HTTPError, httpx.TimeoutException):
                if attempt >= self.max_retries:
                    raise
                attempt += 1
                await asyncio.sleep((2**attempt) + random.uniform(0.0, 0.5))
