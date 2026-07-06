"""Async httpx client for Japan's e-Gov law search API (laws.e-gov.go.jp) with cache.

e-Gov Houki Kensaku (law search) API v2 is keyless and serves JSON. Laws are addressed by
``law_id`` (a stable identifier assigned by e-Gov, e.g. ``129AC0000000089`` for the Civil
Code). Discovery is by title (``/laws``) or full-text keyword (``/keyword``); the full text
of a law is a JSON-serialized element tree (tag/attr/children), not XML, so there is no AKN
namespace to deal with - see ``citations.py`` for the tree walker.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

import anyio
import httpx

from .cache import HttpCache

DEFAULT_BASE_URL = "https://laws.e-gov.go.jp/api/2"
DEFAULT_TIMEOUT = httpx.Timeout(40.0, connect=10.0)
USER_AGENT = "jp-eli-mcp/0.1.0 (+https://github.com/matematicsolutions/jp-eli-mcp)"

_RETRY_STATUS = frozenset({429, 500, 502, 503, 504})
_MAX_ATTEMPTS = 3


class EGovClient:
    """Async client. Use as ``async with EGovClient() as c: ...``."""

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        cache: HttpCache | None = None,
        timeout: httpx.Timeout = DEFAULT_TIMEOUT,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._cache = cache or HttpCache()
        self._http = httpx.AsyncClient(
            timeout=timeout,
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
        )

    async def __aenter__(self) -> EGovClient:
        return self

    async def __aexit__(self, *_exc: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._http.aclose()
        self._cache.close()

    async def _get_json(
        self, path: str, params: dict[str, Any], *, category: str
    ) -> dict[str, Any]:
        url = f"{self.base_url}{path}?" + "&".join(
            f"{k}={quote(str(v))}" for k, v in params.items() if v is not None
        )
        cached = self._cache.get(url)
        if cached is not None and isinstance(cached, dict):
            return cached
        last_exc: Exception | None = None
        for attempt in range(_MAX_ATTEMPTS):
            try:
                resp = await self._http.get(url)
                resp.raise_for_status()
                data: dict[str, Any] = resp.json()
                self._cache.set(url, data, ttl=HttpCache.ttl_for(category))
                return data
            except httpx.HTTPStatusError as exc:
                last_exc = exc
                if exc.response.status_code not in _RETRY_STATUS or attempt == _MAX_ATTEMPTS - 1:
                    raise
            except (httpx.TransportError, httpx.TimeoutException) as exc:
                last_exc = exc
                if attempt == _MAX_ATTEMPTS - 1:
                    raise
            await anyio.sleep(0.5 * (2**attempt))
        assert last_exc is not None
        raise last_exc

    async def search_by_title(self, law_title: str, limit: int) -> dict[str, Any]:
        return await self._get_json(
            "/laws", {"law_title": law_title, "limit": limit}, category="search"
        )

    async def search_by_keyword(self, keyword: str, limit: int, offset: int) -> dict[str, Any]:
        return await self._get_json(
            "/keyword",
            {"keyword": keyword, "limit": limit, "offset": offset},
            category="search",
        )

    async def get_law_data(self, law_id: str) -> dict[str, Any]:
        return await self._get_json(f"/law_data/{quote(law_id)}", {}, category="act")
