"""Lemon Squeezy test checkouts and signed webhooks.

The API key never leaves the server. The browser only receives a checkout URL.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import urllib.error
import urllib.request
from typing import Any

_API = "https://api.lemonsqueezy.com/v1/checkouts"

_REQUIRED = (
    "LEMONSQUEEZY_API_KEY",
    "LEMONSQUEEZY_STORE_ID",
    "LEMONSQUEEZY_VARIANT_ID",
)


def test_mode() -> bool:
    raw = (os.getenv("LEMONSQUEEZY_TEST_MODE") or "true").strip().lower()
    return raw not in ("0", "false", "no")


def missing_settings() -> list[str]:
    missing: list[str] = []
    for name in _REQUIRED:
        if not (os.getenv(name) or "").strip():
            missing.append(name)
    return missing


def _post_json(url: str, payload: dict[str, Any], api_key: str) -> dict[str, Any]:
    body = json.dumps(payload).encode()
    request = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "Accept": "application/vnd.api+json",
            "Content-Type": "application/vnd.api+json",
            "Authorization": f"Bearer {api_key}",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")
        raise RuntimeError(detail or f"Lemon Squeezy returned {exc.code}") from exc


def create_checkout(
    *,
    user_id: str,
    email: str,
    redirect_url: str,
) -> str:
    """Create a hosted checkout and return the URL the overlay should open."""
    missing = missing_settings()
    if missing:
        raise ValueError(
            "Lemon Squeezy is not configured. Set " + ", ".join(missing) + " in project_vl_be/.env."
        )
    variant_id = os.environ["LEMONSQUEEZY_VARIANT_ID"].strip()
    try:
        variant_number = int(variant_id)
    except ValueError as exc:
        raise ValueError("LEMONSQUEEZY_VARIANT_ID must be the numeric variant id.") from exc

    payload = {
        "data": {
            "type": "checkouts",
            "attributes": {
                "test_mode": test_mode(),
                "checkout_data": {
                    "email": email,
                    "custom": {"user_id": user_id},
                },
                "checkout_options": {
                    "embed": True,
                    "media": False,
                    "logo": True,
                    "desc": True,
                },
                "product_options": {
                    "redirect_url": redirect_url,
                    "enabled_variants": [variant_number],
                },
            },
            "relationships": {
                "store": {
                    "data": {
                        "type": "stores",
                        "id": os.environ["LEMONSQUEEZY_STORE_ID"].strip(),
                    }
                },
                "variant": {
                    "data": {
                        "type": "variants",
                        "id": variant_id,
                    }
                },
            },
        }
    }
    result = _post_json(_API, payload, os.environ["LEMONSQUEEZY_API_KEY"].strip())
    url = ((result.get("data") or {}).get("attributes") or {}).get("url")
    if not isinstance(url, str) or not url:
        raise RuntimeError("Lemon Squeezy did not return a checkout URL.")
    return url


def verify_webhook(raw_body: bytes, signature: str | None) -> dict[str, Any]:
    secret = (os.getenv("LEMONSQUEEZY_WEBHOOK_SECRET") or "").strip()
    if not secret:
        raise ValueError("LEMONSQUEEZY_WEBHOOK_SECRET is not set.")
    if not signature:
        raise ValueError("Missing X-Signature header.")
    digest = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(digest, signature.strip()):
        raise ValueError("Invalid Lemon Squeezy signature.")
    return json.loads(raw_body.decode())
