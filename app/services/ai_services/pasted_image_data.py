"""Shared helpers for pasted screenshot data URLs."""

from __future__ import annotations

_MAX_IMAGE_DATA_URL_LEN = 4_000_000


def normalize_image_data_url(value: str) -> str:
    """Accept a data URL or raw base64 and return a vision-ready data URL."""
    cleaned = (value or "").strip()
    if not cleaned:
        raise ValueError("Pasted image is empty.")
    if len(cleaned) > _MAX_IMAGE_DATA_URL_LEN:
        raise ValueError("Pasted image is too large. Paste a smaller screenshot.")
    if cleaned.startswith("data:"):
        if not cleaned.startswith("data:image/"):
            raise ValueError("Only image files are supported for paste.")
        return cleaned
    return f"data:image/png;base64,{cleaned}"
