"""Drawing-stage payload sanitizer (flag-driven only).

The model is locked to the flag-driven shape (``BoxCreation`` /
``TextCreation`` / ``CodeDisplay`` items + optional ``connections``). The
frontend owns every spatial value — there is no layout pipeline here.

This module exists to:

1. Force the canonical canvas (``width=1400``, ``height=1250``,
   ``background="#ffffff"``).
2. Strip any forbidden coordinate / geometry fields that slip through
   (``type``, ``x``, ``y``, ``width``, ``height``, ``radius``, ``fill``,
   ``stroke``, ``strokeWidth``, ``padding``, ``fontSize``, ``lineHeight``,
   ``textColor``, ``points``, ``animation``, top-level ``lines``,
   ``layoutHint``, ``explanation``, ``narrationBeats``).
3. Drop any non-flag items the model emitted (e.g. ``type: "rectangle"``).
4. Drop connections that don't reference valid ids (trunk mode).
5. Normalize ``code-map`` stages (layoutMode, linked boxes, connections).
6. Ensure every item has a stable ``id`` for React keys + connector lookup.
"""

from __future__ import annotations

from typing import Any

from app.services.ai_services.pasted_code import extract_pasted_code, looks_like_coding_request

# =============================================================================
# 1. Canonical canvas constants
# =============================================================================


_CANVAS_WIDTH = 1400.0
_CANVAS_HEIGHT = 1250.0
_CANVAS_BACKGROUND = "#ffffff"


_FORBIDDEN_ITEM_KEYS: frozenset[str] = frozenset(
    {
        "type",
        "x",
        "y",
        "width",
        "height",
        "radius",
        "fill",
        "stroke",
        "strokeWidth",
        "padding",
        "fontSize",
        "lineHeight",
        "textColor",
        "points",
        "animation",
        "fontWeight",
        "textAnchor",
    }
)


# ``role`` is only meaningful on ``TextCreation`` items (selects a preset in
# ``textCreation.tsx``). On ``BoxCreation`` items it is unused noise — strip it.
_BOX_FORBIDDEN_KEYS: frozenset[str] = frozenset({"role"})


_FORBIDDEN_TOP_LEVEL_KEYS: frozenset[str] = frozenset(
    {
        "lines",
        "layoutHint",
        "explanation",
        "narrationBeats",
    }
)


# =============================================================================
# 2. Item-level sanitizers
# =============================================================================


def _is_box_item(obj: Any) -> bool:
    return isinstance(obj, dict) and obj.get("BoxCreation") is True


def _is_text_item(obj: Any) -> bool:
    return isinstance(obj, dict) and obj.get("TextCreation") is True


def _is_code_display_item(obj: Any) -> bool:
    return isinstance(obj, dict) and obj.get("CodeDisplay") is True


def _is_code_map_stage(stage_payload: dict[str, Any]) -> bool:
    if stage_payload.get("layoutMode") == "code-map":
        return True
    objects = stage_payload.get("objects")
    if not isinstance(objects, list):
        return False
    return any(_is_code_display_item(obj) for obj in objects if isinstance(obj, dict))


def _strip_forbidden_item_keys(obj: dict[str, Any]) -> None:
    for key in _FORBIDDEN_ITEM_KEYS:
        obj.pop(key, None)


def _keep_only_flag_driven_objects(stage_payload: dict[str, Any]) -> None:
    """Drop any object that is not a flag-driven item; clean fields on the rest."""
    objects = stage_payload.get("objects")
    if not isinstance(objects, list):
        stage_payload["objects"] = []
        return

    kept: list[dict[str, Any]] = []
    for obj in objects:
        if not isinstance(obj, dict):
            continue
        if not (_is_box_item(obj) or _is_text_item(obj) or _is_code_display_item(obj)):
            continue
        _strip_forbidden_item_keys(obj)
        if _is_box_item(obj):
            for key in _BOX_FORBIDDEN_KEYS:
                obj.pop(key, None)
        kept.append(obj)
    stage_payload["objects"] = kept


def _ensure_unique_ids(stage_payload: dict[str, Any]) -> None:
    """Synthesize / dedupe ids so React keys + connector lookups stay stable."""
    objects = stage_payload.get("objects")
    if not isinstance(objects, list):
        return
    seen: set[str] = set()
    for idx, obj in enumerate(objects):
        if not isinstance(obj, dict):
            continue
        if _is_box_item(obj):
            prefix = "box"
        elif _is_code_display_item(obj):
            prefix = "source"
        else:
            prefix = "text"
        candidate = str(obj.get("id") or f"{prefix}-{idx}")
        while candidate in seen:
            candidate = f"{candidate}-dup"
        obj["id"] = candidate
        seen.add(candidate)


# =============================================================================
# 3. Code-map normalizers
# =============================================================================


def _normalize_code_map_stage(stage_payload: dict[str, Any]) -> None:
    """Keep code-map contract tight: one CodeDisplay, linked explain boxes only."""
    if not _is_code_map_stage(stage_payload):
        return

    stage_payload["layoutMode"] = "code-map"
    objects = stage_payload.get("objects")
    if not isinstance(objects, list):
        return

    code_displays = [obj for obj in objects if _is_code_display_item(obj)]
    if len(code_displays) > 1:
        # Keep the first CodeDisplay only.
        first_id = id(code_displays[0])
        objects[:] = [
            obj
            for obj in objects
            if not _is_code_display_item(obj) or id(obj) == first_id
        ]

    portion_ids: set[str] = set()
    for obj in objects:
        if not _is_code_display_item(obj):
            continue
        portions = obj.get("portions")
        if not isinstance(portions, list):
            obj["portions"] = []
            continue
        cleaned: list[dict[str, Any]] = []
        for portion in portions:
            if not isinstance(portion, dict):
                continue
            pid = str(portion.get("id") or "").strip()
            lines = portion.get("lines")
            if not pid or not isinstance(lines, list) or len(lines) != 2:
                continue
            try:
                start, end = int(lines[0]), int(lines[1])
            except (TypeError, ValueError):
                continue
            if start < 0 or end < start:
                continue
            cleaned.append(
                {
                    "id": pid,
                    "lines": [start, end],
                    **({"label": portion["label"]} if portion.get("label") else {}),
                }
            )
            portion_ids.add(pid)

        code_text = obj.get("text")
        line_count = 0
        if isinstance(code_text, list):
            line_count = len(code_text)
        elif isinstance(code_text, str) and code_text.strip():
            line_count = 1

        if cleaned and line_count > 0:
            starts = [item["lines"][0] for item in cleaned]
            min_start = min(starts)
            max_end = max(item["lines"][1] for item in cleaned)
            if min_start >= 1 and max_end <= line_count and 0 not in starts:
                for item in cleaned:
                    item["lines"] = [item["lines"][0] - 1, item["lines"][1] - 1]

        obj["portions"] = cleaned

    # Code-map uses TextCreation-free layout; drop role labels.
    objects[:] = [
        obj
        for obj in objects
        if not _is_text_item(obj)
        and (not _is_box_item(obj) or obj.get("linkedPortion"))
    ]

    # Drop trunk-only boxes without linkedPortion in code-map mode.
    for obj in objects:
        if _is_box_item(obj) and obj.get("linkedPortion"):
            if str(obj["linkedPortion"]) not in portion_ids:
                obj.pop("linkedPortion", None)

    objects[:] = [
        obj
        for obj in objects
        if _is_code_display_item(obj)
        or (_is_box_item(obj) and obj.get("linkedPortion") in portion_ids)
    ]

    # Frontend auto-wires connectors from linkedPortion; omit stale trunk links.
    stage_payload["connections"] = []


def _normalize_code_lines(text: Any) -> list[str]:
    if isinstance(text, list):
        return [str(line) for line in text]
    if isinstance(text, str) and text.strip():
        return text.splitlines()
    return []


def _codes_look_unrelated(expected: list[str], actual: list[str]) -> bool:
    if not expected or not actual:
        return False
    if len(expected) == len(actual):
        matching = sum(
            1 for a, b in zip(expected, actual, strict=False) if a.strip() == b.strip()
        )
        if matching / len(expected) >= 0.6:
            return False
    exp_joined = "\n".join(line.strip() for line in expected).lower()
    act_joined = "\n".join(line.strip() for line in actual).lower()
    if exp_joined == act_joined:
        return False
    exp_tokens = {token for line in expected for token in line.split() if token}
    act_tokens = {token for line in actual for token in line.split() if token}
    if not exp_tokens:
        return False
    overlap = len(exp_tokens & act_tokens) / len(exp_tokens)
    return overlap < 0.35


def _upgrade_trunk_coding_to_code_map(stage_payload: dict[str, Any]) -> None:
    """If the model returned legacy trunk coding layout, convert to code-map."""
    if _is_code_map_stage(stage_payload):
        return

    objects = stage_payload.get("objects")
    if not isinstance(objects, list):
        return

    code_lines: list[str] = []
    for obj in objects:
        if _is_text_item(obj) and obj.get("role") == "code-title":
            code_lines = _normalize_code_lines(obj.get("text"))
            break

    if not code_lines:
        return

    trunk_boxes = [
        obj
        for obj in objects
        if isinstance(obj, dict) and _is_box_item(obj) and not obj.get("linkedPortion")
    ]
    if not trunk_boxes:
        return

    line_count = len(code_lines)
    box_count = len(trunk_boxes)
    portions: list[dict[str, Any]] = []
    linked_boxes: list[dict[str, Any]] = []

    for index, box in enumerate(trunk_boxes):
        if box_count == 1:
            start, end = 0, line_count - 1
        else:
            start = (index * line_count) // box_count
            end = ((index + 1) * line_count) // box_count - 1
            if index == box_count - 1:
                end = line_count - 1
        end = max(start, end)
        portion_id = f"step-{index + 1}"
        portions.append(
            {
                "id": portion_id,
                "lines": [start, end],
                **({"label": f"Step {index + 1}"} if box_count > 1 else {}),
            }
        )
        linked_boxes.append(
            {
                "id": str(box.get("id") or f"explain-{index + 1}"),
                "BoxCreation": True,
                "linkedPortion": portion_id,
                "text": box.get("text"),
            }
        )

    stage_payload["layoutMode"] = "code-map"
    stage_payload["objects"] = [
        {
            "id": "source",
            "CodeDisplay": True,
            "language": "javascript",
            "text": code_lines,
            "portions": portions,
        },
        *linked_boxes,
    ]
    stage_payload["connections"] = []


def _inject_pasted_code_when_mismatched(
    stage_payload: dict[str, Any],
    prompt: str,
) -> None:
    """If the user pasted code but the model returned unrelated code, force the snippet."""
    if not _is_code_map_stage(stage_payload):
        return

    pasted = extract_pasted_code(prompt)
    if not pasted:
        return

    objects = stage_payload.get("objects")
    if not isinstance(objects, list):
        return

    for obj in objects:
        if not _is_code_display_item(obj):
            continue
        actual = _normalize_code_lines(obj.get("text"))
        if _codes_look_unrelated(pasted.lines, actual):
            obj["text"] = list(pasted.lines)
            obj["language"] = pasted.language
        return


# =============================================================================
# 4. Connection-level sanitizers
# =============================================================================


def _sanitize_connections(stage_payload: dict[str, Any]) -> None:
    """Keep only ``LineCreation: true`` connections that reference real box ids."""
    if _is_code_map_stage(stage_payload):
        stage_payload["connections"] = []
        return

    raw = stage_payload.get("connections")
    if not isinstance(raw, list):
        stage_payload["connections"] = []
        return

    box_ids: set[str] = {
        str(o["id"])
        for o in stage_payload.get("objects", [])
        if isinstance(o, dict) and _is_box_item(o) and o.get("id") is not None
    }

    kept: list[dict[str, Any]] = []
    for conn in raw:
        if not isinstance(conn, dict) or conn.get("LineCreation") is not True:
            continue
        from_id = conn.get("from") if "from" in conn else conn.get("from_")
        to_id = conn.get("to")
        if from_id is None or to_id is None:
            continue
        if str(from_id) not in box_ids or str(to_id) not in box_ids:
            continue
        kept.append(
            {
                "LineCreation": True,
                "from": from_id,
                "to": to_id,
                **({"id": conn["id"]} if "id" in conn and conn["id"] is not None else {}),
            }
        )
    stage_payload["connections"] = kept


# =============================================================================
# 5. Stage-level sanitizer
# =============================================================================


def _force_canonical_canvas(stage_payload: dict[str, Any]) -> None:
    stage_payload["width"] = _CANVAS_WIDTH
    stage_payload["height"] = _CANVAS_HEIGHT
    stage_payload["background"] = _CANVAS_BACKGROUND


def _drop_forbidden_top_level(stage_payload: dict[str, Any]) -> None:
    for key in _FORBIDDEN_TOP_LEVEL_KEYS:
        stage_payload.pop(key, None)


# =============================================================================
# 6. Pipeline — call from ``answer_service``
# =============================================================================


def improve_stage_quality(
    stage_payload: dict[str, Any],
    *,
    domain: str,
    prompt: str,
) -> dict[str, Any]:
    """Sanitize an LLM payload into the flag-driven contract.

    Mutates and returns ``stage_payload``. Safe to call repeatedly.
    """

    if not isinstance(stage_payload, dict):
        return {
            "width": _CANVAS_WIDTH,
            "height": _CANVAS_HEIGHT,
            "background": _CANVAS_BACKGROUND,
            "objects": [],
            "connections": [],
        }

    _force_canonical_canvas(stage_payload)
    _drop_forbidden_top_level(stage_payload)
    _keep_only_flag_driven_objects(stage_payload)
    _ensure_unique_ids(stage_payload)
    wants_code_map = domain == "coding" or looks_like_coding_request(prompt)
    if wants_code_map:
        _upgrade_trunk_coding_to_code_map(stage_payload)
    _normalize_code_map_stage(stage_payload)
    _inject_pasted_code_when_mismatched(stage_payload, prompt)
    _normalize_code_map_stage(stage_payload)
    _sanitize_connections(stage_payload)
    if not wants_code_map and not any(
        o.get("CodeDisplay") is True for o in stage_payload.get("objects", []) if isinstance(o, dict)
    ):
        if domain == "science":
            stage_payload["layoutMode"] = "science"
        elif domain == "math":
            stage_payload["layoutMode"] = "math"
        elif stage_payload.get("layoutMode") not in ("math", "science", "trunk"):
            stage_payload["layoutMode"] = "trunk"
    return stage_payload
