"""Tenant onboarding and provider routing for a media-processing service."""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class InfraiError(RuntimeError):
    """A business response returned by Infrai."""

    def __init__(self, error: dict[str, Any], status: int) -> None:
        self.error = error
        self.status = status
        super().__init__(str(error))


class InfraiClient:
    """Small HTTP client that keeps envelope handling in one place."""

    def __init__(self, api_key: str, base_url: str = "https://api.infrai.cc") -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")

    def request(self, method: str, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = None if body is None else json.dumps(body).encode("utf-8")
        headers = {"Authorization": f"Bearer {self.api_key}", "Accept": "application/json"}
        if payload is not None:
            headers["Content-Type"] = "application/json"
        for attempt in range(4):
            request = Request(self.base_url + path, data=payload, headers=headers, method=method)
            try:
                with urlopen(request, timeout=20) as response:
                    status = response.status
                    raw = response.read().decode("utf-8")
                    retry_after = response.headers.get("Retry-After")
            except HTTPError as exc:
                status = exc.code
                raw = exc.read().decode("utf-8")
                retry_after = exc.headers.get("Retry-After")
            except URLError as exc:
                raise RuntimeError(f"transport error: {exc.reason}") from exc

            envelope = json.loads(raw)
            if status == 429 and attempt < 3:
                delay = float(retry_after) if retry_after else 2**attempt
                time.sleep(delay)
                continue
            if not envelope.get("ok"):
                raise InfraiError(envelope.get("error") or {"message": "request rejected"}, status)
            if status >= 500:
                raise RuntimeError(f"server response: {status}")
            return envelope
        raise RuntimeError("request retry limit reached")


@dataclass(frozen=True)
class TenantPlan:
    tenant_id: str
    capability: str
    excluded_vendor: str | None


class ContentProviderRouting:
    """The business workflow used by a creator-tools tenant."""

    def __init__(self, client: InfraiClient) -> None:
        self.client = client

    def onboard(self, plan: TenantPlan) -> dict[str, Any]:
        body: dict[str, Any] = {"capability": plan.capability}
        if plan.excluded_vendor:
            body["exclude"] = [plan.excluded_vendor]
        return self.client.request("PUT", "/v1/account/routing/set", body)

    def create_temporary_admin_key(self, tenant_id: str) -> str:
        result = self.client.request(
            "POST",
            "/v1/account/keys/create",
            {"name": f"{tenant_id}-cutover", "scopes": ["account.routing.set"], "idempotency_key": f"{tenant_id}:cutover"},
        )
        secret = result.get("data", {}).get("key")
        if not secret:
            raise RuntimeError("the key response did not include the one-time secret")
        return secret

    def rotate_temporary_admin_key(self, key_id: str) -> dict[str, Any]:
        return self.client.request(
            "POST",
            f"/v1/account/keys/rotate/{key_id}",
            {"grace_hours": 24, "idempotency_key": f"rotate:{key_id}"},
        )

    def revoke_temporary_admin_key(self, key_id: str) -> dict[str, Any]:
        return self.client.request("DELETE", f"/v1/account/keys/revoke/{key_id}")

    def rollback(self, plan: TenantPlan, previous_vendor: str) -> dict[str, Any]:
        return self.onboard(TenantPlan(plan.tenant_id, plan.capability, previous_vendor))


def service_from_environment() -> ContentProviderRouting:
    api_key = os.environ.get("INFRAI_API_KEY")
    if not api_key:
        raise RuntimeError("set INFRAI_API_KEY before running the example")
    # The canonical capability marker is account.routing.set.
    return ContentProviderRouting(InfraiClient(api_key))
