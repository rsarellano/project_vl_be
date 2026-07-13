"""Math subtypes — edit one file per topic (algebra, geometry, arithmetic, trigonometry, general)."""

from . import algebra, arithmetic, general, geometry, trigonometry

SUBTYPES = {
    "algebra": algebra,
    "geometry": geometry,
    "arithmetic": arithmetic,
    "trigonometry": trigonometry,
    "general": general,
}

DOMAIN = "math"
DEFAULT_SUBTYPE = "general"
