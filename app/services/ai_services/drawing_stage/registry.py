"""Lookup (domain, subtype) → SubtypePrompt."""

from __future__ import annotations

from app.services.ai_services.question_type_identifier import QuestionTypeInfo

from ._prompt_types import SubtypePrompt
from . import coding, math, science
from .math.general import PROMPT as MATH_GENERAL
from .science.general import PROMPT as SCIENCE_GENERAL
from .coding.general import PROMPT as CODING_GENERAL

_DOMAIN_PACKAGES = {
    math.DOMAIN: math,
    science.DOMAIN: science,
    coding.DOMAIN: coding,
}

_DOMAIN_DEFAULTS = {
    math.DOMAIN: MATH_GENERAL,
    science.DOMAIN: SCIENCE_GENERAL,
    coding.DOMAIN: CODING_GENERAL,
}


def get_subtype_prompt(question_type: QuestionTypeInfo) -> SubtypePrompt:
    package = _DOMAIN_PACKAGES.get(question_type.domain)
    if package is None:
        return MATH_GENERAL

    module = package.SUBTYPES.get(question_type.subtype)
    if module is None:
        return _DOMAIN_DEFAULTS[package.DOMAIN]

    return module.PROMPT


def list_registered_subtypes() -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    for domain, package in _DOMAIN_PACKAGES.items():
        for subtype in package.SUBTYPES:
            rows.append((domain, subtype))
    return sorted(rows)
