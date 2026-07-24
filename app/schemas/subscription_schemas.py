"""Pydantic schemas for subscription endpoints."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class TierDisplayResponse(BaseModel):
    slug: str
    name: str
    price: float
    price_label: str
    billing_period: str | None
    yearly_price: float | None = None
    yearly_price_label: str | None = None
    description: str
    badge: str | None
    features: list[str]
    limits: dict[str, int | None]


class UsageResponse(BaseModel):
    tier: str
    limits: dict[str, int | None]
    usage: dict[str, int]
    remaining: dict[str, int | None]


class UpgradeRequest(BaseModel):
    tier: str = "pro"
    billing_period: str = "month"  # "month" | "year"


class SubscriptionResponse(BaseModel):
    success: bool
    tier: str
    message: str
