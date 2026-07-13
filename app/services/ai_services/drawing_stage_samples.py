"""Sample ``DrawingStage`` payloads (flag-driven only).

Static fixtures for contract / frontend testing without the LLM. Served by
``GET /api/answers/samples/while-loop``.
"""

from __future__ import annotations

from app.schemas.infographics_schema import DrawingStage


def get_while_loop_stage() -> DrawingStage:
    """Return a validated flag-driven ``DrawingStage`` tracing ``while (i < 3)``."""

    payload: dict = {
        "width": 1400,
        "height": 1250,
        "background": "#ffffff",
        "objects": [
            {
                "id": "code-title",
                "TextCreation": True,
                "role": "code-title",
                "text": ["let i = 0;", "while (i < 3) {", "  console.log(i);", "  i++;", "}"],
            },
            {
                "id": "objective",
                "TextCreation": True,
                "role": "objective",
                "text": [
                    "Objective:",
                    "Trace the while loop",
                    "until i is no longer",
                    "less than 3.",
                ],
            },
            {
                "id": "step-1",
                "BoxCreation": True,
                "text": [
                    "i = 0",
                    "",
                    "0 < 3 is true so",
                    "the body runs and",
                    "i++ makes i = 1.",
                ],
            },
            {
                "id": "log-1",
                "TextCreation": True,
                "role": "console",
                "text": "console.log = 0",
            },
            {
                "id": "step-2",
                "BoxCreation": True,
                "text": [
                    "2nd iteration",
                    "",
                    "i = 1",
                    "",
                    "1 < 3 is true so",
                    "the body runs and",
                    "i++ makes i = 2.",
                ],
            },
            {
                "id": "log-2",
                "TextCreation": True,
                "role": "console",
                "text": "console.log = 1",
            },
            {
                "id": "step-3",
                "BoxCreation": True,
                "text": [
                    "3rd iteration",
                    "",
                    "i = 2",
                    "",
                    "2 < 3 is true so",
                    "the body runs and",
                    "i++ makes i = 3.",
                ],
            },
            {
                "id": "log-3",
                "TextCreation": True,
                "role": "console",
                "text": "console.log = 2",
            },
            {
                "id": "step-4",
                "BoxCreation": True,
                "text": [
                    "final check",
                    "",
                    "i = 3",
                    "3 < 3 is false so",
                    "the loop exits.",
                ],
            },
        ],
        "connections": [
            {"LineCreation": True, "from": "step-1", "to": "step-2"},
            {"LineCreation": True, "from": "step-2", "to": "step-3"},
            {"LineCreation": True, "from": "step-3", "to": "step-4"},
        ],
    }

    return DrawingStage.model_validate(payload)



