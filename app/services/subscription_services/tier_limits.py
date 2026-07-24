"""Tier-based usage limits configuration and helpers.

Add new tiers by inserting an entry into ``TIER_LIMITS``.
Add new limit dimensions by adding a key to each tier dict.
No migrations required for either operation.
"""

from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# Tier definitions – single source of truth
# ---------------------------------------------------------------------------
# ``None`` means unlimited.

TIER_LIMITS: dict[str, dict[str, int | None]] = {
    "free": {
        "max_classrooms": 5,
        "max_students_per_classroom": 20,
        "max_assignments_per_classroom": 5,
        "max_diagrams_per_day": 10,
    },
    "pro": {
        "max_classrooms": None,
        "max_students_per_classroom": None,
        "max_assignments_per_classroom": None,
        "max_diagrams_per_day": None,
    },
}

# Display metadata for each tier (used by GET /api/subscriptions/tiers)
TIER_DISPLAY: dict[str, dict[str, Any]] = {
    "free": {
        "slug": "free",
        "name": "Free",
        "price": 0,
        "price_label": "$0",
        "billing_period": None,
        "yearly_price": None,
        "yearly_price_label": None,
        "description": "Get started with the essentials",
        "badge": None,
        "features": [
            "Up to 5 classrooms",
            "Up to 20 students per classroom",
            "Up to 5 assignments per classroom",
            "Up to 10 diagram generations per day",
            "Join classrooms via code",
            "View assignments & visual diagrams",
        ],
    },
    "pro": {
        "slug": "pro",
        "name": "Pro",
        "price": 14.99,
        "price_label": "$14.99",
        "billing_period": "month",
        "yearly_price": 149,
        "yearly_price_label": "$149",
        "description": "Unlimited everything for serious educators",
        "badge": "Most Popular",
        "features": [
            "Unlimited classrooms",
            "Unlimited students per classroom",
            "Unlimited assignments per classroom",
            "Unlimited diagram generations",
            "Priority generation queue",
            "Advanced diagram export options",
        ],
    },
}

DEFAULT_TIER = "free"


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def get_limits(tier: str) -> dict[str, int | None]:
    """Return the limits dict for a tier, falling back to free."""
    return TIER_LIMITS.get(tier, TIER_LIMITS[DEFAULT_TIER])


def get_limit_value(tier: str, key: str) -> int | None:
    """Return a single limit value. ``None`` means unlimited."""
    return get_limits(tier).get(key)


def check_limit(tier: str, key: str, current_count: int) -> bool:
    """Return ``True`` if the user is within the limit, ``False`` if at/over cap."""
    cap = get_limit_value(tier, key)
    if cap is None:
        return True
    return current_count < cap


def get_remaining(tier: str, key: str, current_count: int) -> int | None:
    """Return how many more the user can create. ``None`` = unlimited."""
    cap = get_limit_value(tier, key)
    if cap is None:
        return None
    return max(0, cap - current_count)


def get_all_tiers_display() -> list[dict[str, Any]]:
    """Return tier display info for all tiers (ordered)."""
    return [TIER_DISPLAY[slug] for slug in TIER_LIMITS if slug in TIER_DISPLAY]
