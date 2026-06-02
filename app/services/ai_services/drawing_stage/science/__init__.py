"""Science subtypes — edit biology.py, chemistry.py, physics.py, or general.py."""

from . import biology, chemistry, general, physics

SUBTYPES = {
    "biology": biology,
    "chemistry": chemistry,
    "physics": physics,
    "general": general,
}

DOMAIN = "science"
DEFAULT_SUBTYPE = "general"
