"""HTTP transport adapter using ``httpx.AsyncClient``."""

from __future__ import annotations

from typing import Any

import httpx

from appss_sdk._types import TransportResponse


class HttpxTransport:
    """ITransport implementation backed by ``httpx.AsyncClient``.

    The client is created lazily on first ``send`` so that instantiation is safe
    outside an event loop. HTTP errors are not caught here — the dispatcher's
    retry loop is responsible for handling them.
    """

    def __init__(self, endpoint: str, request_timeout_ms: int) -> None:
        self._endpoint = endpoint
        self._timeout = httpx.Timeout(request_timeout_ms / 1000)
        self._client: httpx.AsyncClient | None = None

    async def send(
        self,
        path: str,
        body: Any,
        headers: dict[str, str],
    ) -> TransportResponse:
        client = await self._get_client()
        url = f"{self._endpoint}{path}"
        response = await client.post(url, json=body, headers=headers, timeout=self._timeout)

        content_type = response.headers.get("content-type", "")
        body_data: Any = response.json() if content_type.startswith("application/json") else None

        return TransportResponse(
            status_code=response.status_code,
            headers=dict(response.headers),
            body=body_data,
        )

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self._timeout)
        return self._client
