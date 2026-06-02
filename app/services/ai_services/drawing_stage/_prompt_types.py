"""Registry entry for one (domain, subtype) prompt."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SubtypePrompt:
    domain: str
    subtype: str
    layout_mode: str
    system: str
    human_hint: str = ""
    produce_line: str = ""
