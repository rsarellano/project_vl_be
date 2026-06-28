"""User-facing errors when diagram generation fails."""

from __future__ import annotations


def friendly_diagram_generation_error(*, domain: str, subtype: str) -> str:
    """Plain-language message instead of raw Pydantic validation dumps."""
    if domain == "math":
        if subtype == "algebra":
            return (
                "We couldn't build a valid algebra diagram for this question. "
                "Try splitting chained equations (for example, 2x = 10 and y + 1 = 10) "
                "or rephrase the problem in plain text."
            )
        if subtype == "arithmetic":
            return (
                "We couldn't build a valid arithmetic diagram for this question. "
                "Try rephrasing with clearer numbers and one step at a time."
            )
        if subtype == "geometry":
            return (
                "We couldn't build a valid geometry diagram for this question. "
                "Try stating the given measurements and what you want to find."
            )
        return (
            "We couldn't build a valid math diagram for this question. "
            "Try rephrasing or breaking the problem into smaller steps."
        )

    if domain == "coding":
        return (
            "We couldn't build a valid coding diagram for this question. "
            "Try a shorter snippet or a clearer description of what to explain."
        )

    if domain == "science":
        return (
            "We couldn't build a valid science diagram for this question. "
            "Try rephrasing the process or concept you want illustrated."
        )

    return (
        "We couldn't build a diagram for this question. "
        "Try rephrasing or simplifying what you paste."
    )
