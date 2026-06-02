"""Math subtypes — edit one file per topic (algebra, geometry, arithmetic, general)."""

from . import algebra, arithmetic, general, geometry

SUBTYPES = {
    "algebra": algebra,
    "geometry": geometry,
    "arithmetic": arithmetic,
    "general": general,
}

DOMAIN = "math"
DEFAULT_SUBTYPE = "general"
