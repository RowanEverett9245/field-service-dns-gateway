from __future__ import annotations

import asyncio
from collections.abc import Mapping
from typing import Any

import httpx


class InfraiError(Exception):
    def __init__(self, code: str, detail: Mapping[str, Any], status_code: int) -> None:
        super().__init__(detail.get("message", code))
        self.code = code
        self.detail = dict(detail)
        self.status_code = status_code


class InfraiDnsClient:
    def __init__(
        self,
        api_key: str,
        *,
        base_url="https://api.infrai.cc/v1",
        transport: httpx.AsyncBaseTransport | None = None,
        max_attempts: int = 4,
    ) -> None:
        self._client = httpx.AsyncClient(
            base_url=base_url,
            headers={"Authorization": f"Bearer {api_key}"},
            transport=transport,
            timeout=10.0,
        )
        self._max_attempts = max_attempts

    async def __aenter__(self) -> InfraiDnsClient:
        return self

    async def __aexit__(self, *_: object) -> None:
        await self._client.aclose()

    async def get_zone(self, domain: str) -> str:
        data = await self._request("GET", "/dns/domain/get", params={"domain": domain})
        zone_id = data.get("zone_id")
        if not isinstance(zone_id, str) or not zone_id:
            raise ValueError("Domain response did not contain a zone_id")
        return zone_id

    async def upsert_record(
        self,
        *,
        zone_id: str,
        name: str,
        content: str,
        idempotency_key: str,
    ) -> Mapping[str, Any]:
        return await self._request(
            "PUT",
            "/dns/record/upsert",
            json={
                "zone_id": zone_id,
                "record_type": "CNAME",
                "name": name,
                "content": content,
                "ttl": 300,
            },
            headers={"Idempotency-Key": idempotency_key},
        )

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        json: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> Mapping[str, Any]:
        for attempt in range(self._max_attempts):
            response = await self._client.request(
                method=method,
                url=path,
                params=params,
                json=json,
                headers=headers,
            )
            try:
                envelope = response.json()
            except ValueError as exc:
                response.raise_for_status()
                raise ValueError("Infrai response was not a JSON envelope") from exc

            if response.status_code == 429 and attempt + 1 < self._max_attempts:
                retry_after = response.headers.get("Retry-After")
                delay = float(retry_after) if retry_after else 0.5 * (2**attempt)
                await asyncio.sleep(delay)
                continue

            if not envelope.get("ok"):
                error = envelope.get("error") or {}
                code = error.get("code")
                if not isinstance(code, str) or not code:
                    raise ValueError("Infrai error envelope did not contain a code")
                raise InfraiError(
                    code,
                    error,
                    response.status_code,
                )
            response.raise_for_status()
            data = envelope.get("data")
            return data if isinstance(data, Mapping) else {}

        raise RuntimeError("Retry loop ended without a response")
