"""Math subtypes — edit one file per topic (algebra, geometry, arithmetic, trigonometry, calculus, general)."""

from . import algebra, arithmetic, calculus, general, geometry, trigonometry

SUBTYPES = {
    "algebra": algebra,
    "geometry": geometry,
    "arithmetic": arithmetic,
    "trigonometry": trigonometry,
    "calculus": calculus,
    "general": general,
}

DOMAIN = "math"
DEFAULT_SUBTYPE = "general"
