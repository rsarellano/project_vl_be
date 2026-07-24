"""Default lecture scene_spec builders (mirror frontend heuristics).

Scenes are stored on each slide so educators can edit motion later.
"""

from __future__ import annotations

from typing import Any


def _truncate(text: str, max_len: int) -> str:
    t = " ".join((text or "").split())
    if len(t) <= max_len:
        return t
    return f"{t[: max_len - 1]}…"


def create_trains_scene(
    *,
    length_km: float = 200,
    speed_a: float = 60,
    speed_b: float = 40,
    direction_a: str = "east",
    direction_b: str = "west",
) -> dict[str, Any]:
    width, height = 900, 420
    track_y, x1, x2 = 260, 80, 820
    dir_a = direction_a if direction_a in ("east", "west") else "east"
    dir_b = direction_b if direction_b in ("east", "west") else "west"
    # Place by direction: eastbound starts left, westbound starts right
    a_x = x1 if dir_a == "east" else x2 - 72
    b_x = x2 - 72 if dir_b == "west" else x1
    closing = max(speed_a + speed_b, 0.001)
    hours = round(length_km / closing, 2)

    return {
        "type": "relative_motion.trains",
        "width": width,
        "height": height,
        "units": "km_h",
        "track": {"y": track_y, "x1": x1, "x2": x2, "length_km": length_km},
        "train_a": {
            "speed": speed_a,
            "direction": dir_a,
            "start_km": 0 if dir_a == "east" else length_km,
        },
        "train_b": {
            "speed": speed_b,
            "direction": dir_b,
            "start_km": length_km if dir_b == "west" else 0,
        },
        "ask": "time_to_collide",
        "answer": {"hours": hours},
        "objects": [
            {
                "id": "track",
                "role": "track",
                "assetSlot": "track.horizontal",
                "x": x1,
                "y": track_y - 4,
                "width": x2 - x1,
                "height": 8,
                "label": "Railway",
            },
            {
                "id": "train_a",
                "role": "train.a",
                "assetSlot": f"train.engine.{dir_a}",
                "x": a_x,
                "y": track_y - 48,
                "width": 72,
                "height": 40,
                "label": f"Train A · {speed_a:g} km/h",
            },
            {
                "id": "train_b",
                "role": "train.b",
                "assetSlot": f"train.engine.{dir_b}",
                "x": b_x,
                "y": track_y - 48,
                "width": 72,
                "height": 40,
                "label": f"Train B · {speed_b:g} km/h",
            },
            {
                "id": "arrow_a",
                "role": "arrow",
                "assetSlot": f"arrow.{dir_a}",
                "x": a_x + (20 if dir_a == "east" else 4),
                "y": track_y - 90,
                "width": 48,
                "height": 24,
                "label": "→" if dir_a == "east" else "←",
            },
            {
                "id": "arrow_b",
                "role": "arrow",
                "assetSlot": f"arrow.{dir_b}",
                "x": b_x + (4 if dir_b == "west" else 20),
                "y": track_y - 90,
                "width": 48,
                "height": 24,
                "label": "←" if dir_b == "west" else "→",
            },
        ],
        "motionCues": [
            {
                "objectId": "arrow_a",
                "type": "translate",
                "from": {"x": a_x + 20, "y": track_y - 90},
                "to": {
                    "x": a_x + (160 if dir_a == "east" else -120),
                    "y": track_y - 90,
                },
                "durationMs": 1800,
                "delayMs": 200,
            },
            {
                "objectId": "arrow_b",
                "type": "translate",
                "from": {"x": b_x + 4, "y": track_y - 90},
                "to": {
                    "x": b_x + (-140 if dir_b == "west" else 140),
                    "y": track_y - 90,
                },
                "durationMs": 1800,
                "delayMs": 200,
            },
        ],
    }



def _style(
    *,
    size: int,
    weight: str = "normal",
    color: str = "#0f172a",
) -> dict[str, Any]:
    return {
        "fontFamily": "system-ui, sans-serif",
        "fontSize": size,
        "fontWeight": weight,
        "fontStyle": "normal",
        "textAlign": "left",
        "color": color,
    }


def _entrance(
    object_id: str,
    x: float,
    y: float,
    *,
    delay_ms: int,
    dy: float = 16,
    duration_ms: int = 520,
) -> list[dict[str, Any]]:
    return [
        {
            "objectId": object_id,
            "type": "fade_in",
            "durationMs": duration_ms,
            "delayMs": delay_ms,
        },
        {
            "objectId": object_id,
            "type": "translate",
            "from": {"x": x, "y": y + dy},
            "to": {"x": x, "y": y},
            "durationMs": duration_ms,
            "delayMs": delay_ms,
        },
    ]


def _slide_steps(slide: dict[str, Any]) -> list[str]:
    raw = slide.get("steps") or []
    steps: list[str] = []
    if isinstance(raw, list):
        for item in raw:
            text = _truncate(str(item or ""), 72)
            if text:
                steps.append(text)
            if len(steps) >= 3:
                break
    if len(steps) >= 2:
        return steps

    explanation = str(slide.get("explanation") or "").strip()
    parts = [
        p.strip()
        for p in explanation.replace("!", ".").replace("?", ".").split(".")
        if p.strip()
    ]
    for part in parts:
        steps.append(_truncate(part, 72))
        if len(steps) >= 3:
            break
    if len(steps) >= 2:
        return steps[:3]

    role = str(slide.get("slide_role") or "concept").replace("_", " ")
    return [
        f"Frame the {role}",
        "Show the key move",
        "Check understanding",
    ]


def create_basic_boxes_scene(slide: dict[str, Any]) -> dict[str, Any]:
    """Showcase-first stage: topic, equation, stepped boxes, arrow, callout, accent."""
    width, height = 900, 480
    title_style = _style(size=12, weight="bold")
    body_style = _style(size=11)
    equation_style = _style(size=13, weight="bold")
    callout_style = _style(size=11, weight="bold", color="#9a3412")
    role_style = _style(size=10, weight="bold", color="#1d4ed8")

    objects: list[dict[str, Any]] = []
    cues: list[dict[str, Any]] = []
    delay = 0

    role = str(slide.get("slide_role") or "concept").strip() or "concept"
    role_label = role.replace("_", " ").title()

    topic_x, topic_y = 36.0, 28.0
    objects.append(
        {
            "id": "box_title",
            "role": "box.title",
            "assetSlot": "box.placeholder",
            "x": topic_x,
            "y": topic_y,
            "width": 540,
            "height": 58,
            "label": "Topic",
            "body": _truncate(str(slide.get("title") or "Slide"), 90),
            "textStyle": title_style,
        }
    )
    cues.extend(_entrance("box_title", topic_x, topic_y, delay_ms=delay, dy=14))
    delay += 180

    objects.append(
        {
            "id": "text_role",
            "role": "text",
            "assetSlot": "text.freeform",
            "x": 600,
            "y": 32,
            "width": 260,
            "height": 50,
            "label": "Role",
            "body": f"Slide focus\n{role_label}",
            "textStyle": role_style,
        }
    )
    cues.extend(_entrance("text_role", 600, 32, delay_ms=delay, dy=10, duration_ms=420))
    delay += 140

    y = 104.0
    equation = str(slide.get("equation") or "").strip()
    if equation:
        objects.append(
            {
                "id": "box_equation",
                "role": "box.equation",
                "assetSlot": "box.placeholder",
                "x": 36,
                "y": y,
                "width": 540,
                "height": 70,
                "label": "Equation",
                "body": _truncate(equation, 120),
                "textStyle": equation_style,
            }
        )
        cues.extend(_entrance("box_equation", 36, y, delay_ms=delay))
        delay += 200
        objects.append(
            {
                "id": "arrow_to_equation",
                "role": "arrow",
                "assetSlot": "arrow.down",
                "x": 290,
                "y": 86,
                "width": 28,
                "height": 22,
                "label": "↓",
            }
        )
        cues.extend(
            _entrance(
                "arrow_to_equation",
                290,
                86,
                delay_ms=max(0, delay - 80),
                dy=8,
                duration_ms=360,
            )
        )
        y = 190.0
    else:
        y = 108.0

    steps = _slide_steps(slide)
    step_w = 250.0
    step_h = 88.0
    step_y = y
    gap = 56.0
    step_xs = [36.0, 36.0 + step_w + gap]
    for i, step in enumerate(steps[:2]):
        oid = f"box_step_{i + 1}"
        sx = step_xs[i]
        objects.append(
            {
                "id": oid,
                "role": "box.custom",
                "assetSlot": "box.placeholder",
                "x": sx,
                "y": step_y,
                "width": step_w,
                "height": step_h,
                "label": f"Step {i + 1}",
                "body": step,
                "textStyle": body_style,
            }
        )
        cues.extend(_entrance(oid, sx, step_y, delay_ms=delay + i * 160, dy=18))

    if len(steps) >= 2:
        ax = step_xs[0] + step_w + 12
        ay = step_y + 30
        objects.append(
            {
                "id": "arrow_steps",
                "role": "arrow",
                "assetSlot": "arrow.east",
                "x": ax,
                "y": ay,
                "width": 36,
                "height": 24,
                "label": "→",
            }
        )
        cues.extend(_entrance("arrow_steps", ax, ay, delay_ms=delay + 120, dy=0, duration_ms=400))
    delay += 360

    callout = str(slide.get("callout") or "").strip()
    if not callout:
        narration = str(slide.get("narration") or "").strip()
        if narration:
            callout = _truncate(narration.split(".")[0], 90)
    if callout:
        objects.append(
            {
                "id": "box_callout",
                "role": "box.custom",
                "assetSlot": "box.placeholder",
                "x": 620,
                "y": 104,
                "width": 244,
                "height": 100,
                "label": "Callout",
                "body": _truncate(callout, 110),
                "textStyle": callout_style,
            }
        )
        cues.extend(_entrance("box_callout", 620, 104, delay_ms=delay, dy=12))
        delay += 160

    explanation = str(slide.get("explanation") or "").strip()
    key_y = step_y + step_h + 24
    if explanation:
        objects.append(
            {
                "id": "box_explain",
                "role": "box.explain",
                "assetSlot": "box.placeholder",
                "x": 36,
                "y": key_y,
                "width": 560,
                "height": 100,
                "label": "Key idea",
                "body": _truncate(explanation, 200),
                "textStyle": body_style,
            }
        )
        cues.extend(_entrance("box_explain", 36, key_y, delay_ms=delay, dy=18))
        delay += 160

    visual = str(slide.get("visual_type") or "equation").lower()
    shape_x, shape_y = 650.0, key_y + 8
    if visual == "triangle":
        objects.append(
            {
                "id": "shape_accent",
                "role": "triangle",
                "assetSlot": "shape.triangle",
                "x": shape_x,
                "y": shape_y,
                "width": 90,
                "height": 78,
                "label": "Triangle",
            }
        )
        cues.extend(
            _entrance("shape_accent", shape_x, shape_y, delay_ms=delay, dy=14, duration_ms=480)
        )
    elif visual in ("circle", "graph"):
        objects.append(
            {
                "id": "shape_accent",
                "role": "circle",
                "assetSlot": "shape.circle",
                "x": shape_x,
                "y": shape_y,
                "width": 84,
                "height": 84,
                "label": "Circle",
            }
        )
        cues.extend(
            _entrance("shape_accent", shape_x, shape_y, delay_ms=delay, dy=14, duration_ms=480)
        )

    return {
        "type": "basic_boxes",
        "width": width,
        "height": height,
        "objects": objects,
        "motionCues": cues,
    }


def apply_boxes_slide_direction(
    scene: dict[str, Any],
    *,
    direction: str,
    distance: float = 120,
    object_id: str | None = None,
) -> dict[str, Any]:
    """Rewrite translate motion cues so boxes slide in a compass direction."""
    out = dict(scene)
    objects = list(out.get("objects") or [])
    by_id = {str(o.get("id")): o for o in objects if isinstance(o, dict)}
    dist = max(20.0, float(distance or 120))
    dx = dy = 0.0
    d = (direction or "").lower()
    if d in ("right", "east"):
        dx = dist
    elif d in ("left", "west"):
        dx = -dist
    elif d in ("down", "south"):
        dy = dist
    elif d in ("up", "north"):
        dy = -dist
    else:
        dx = dist  # default right

    cues: list[dict[str, Any]] = []
    for cue in out.get("motionCues") or []:
        if not isinstance(cue, dict):
            continue
        cue = dict(cue)
        if cue.get("type") != "translate":
            cues.append(cue)
            continue
        oid = str(cue.get("objectId") or "")
        if object_id and oid != object_id:
            cues.append(cue)
            continue
        obj = by_id.get(oid) or {}
        x = float(obj.get("x") or 0)
        y = float(obj.get("y") or 0)
        # Start offset opposite the travel so the object visibly moves into place
        cue["from"] = {"x": x - dx, "y": y - dy}
        cue["to"] = {"x": x, "y": y}
        cue["durationMs"] = int(cue.get("durationMs") or 600)
        cues.append(cue)

    # If no translate cues matched, add one for each object (or the named one)
    has_translate = any(c.get("type") == "translate" for c in cues)
    if not has_translate:
        targets = [object_id] if object_id else [str(o.get("id")) for o in objects]
        for i, oid in enumerate(targets):
            if not oid or oid not in by_id:
                continue
            obj = by_id[oid]
            x = float(obj.get("x") or 0)
            y = float(obj.get("y") or 0)
            cues.append(
                {
                    "objectId": oid,
                    "type": "translate",
                    "from": {"x": x - dx, "y": y - dy},
                    "to": {"x": x, "y": y},
                    "durationMs": 650,
                    "delayMs": i * 120,
                }
            )

    out["motionCues"] = cues
    out["objects"] = objects
    return out


def _next_object_id(objects: list[dict[str, Any]], prefix: str) -> str:
    used = {str(o.get("id")) for o in objects if isinstance(o, dict)}
    n = 1
    while f"{prefix}{n}" in used:
        n += 1
    return f"{prefix}{n}"


def add_arrow_to_scene(
    scene: dict[str, Any],
    *,
    direction: str = "down",
    below_object_id: str | None = None,
    above_object_id: str | None = None,
    x: float | None = None,
    y: float | None = None,
) -> dict[str, Any]:
    """Insert a visible arrow graphic onto the stage (not motion-only)."""
    out = dict(scene)
    objects = [dict(o) for o in (out.get("objects") or []) if isinstance(o, dict)]
    cues = list(out.get("motionCues") or [])
    by_id = {str(o.get("id")): o for o in objects}

    d = (direction or "down").lower()
    if d in ("right", "east"):
        slot, label, w, h = "arrow.east", "→", 48, 28
    elif d in ("left", "west"):
        slot, label, w, h = "arrow.west", "←", 48, 28
    elif d in ("up", "north"):
        slot, label, w, h = "arrow.up", "↑", 28, 48
    else:
        slot, label, w, h = "arrow.down", "↓", 28, 48
        d = "down"

    stage_w = float(out.get("width") or 900)
    place_x = float(x) if x is not None else (stage_w - w) / 2
    place_y = float(y) if y is not None else 200.0

    anchor_id = below_object_id or above_object_id
    if anchor_id and anchor_id in by_id:
        anchor = by_id[anchor_id]
        ax = float(anchor.get("x") or 0)
        ay = float(anchor.get("y") or 0)
        aw = float(anchor.get("width") or 100)
        ah = float(anchor.get("height") or 40)
        place_x = ax + (aw - w) / 2
        if below_object_id:
            place_y = ay + ah + 12
        else:
            place_y = max(8.0, ay - h - 12)

    oid = _next_object_id(objects, "arrow_")
    objects.append(
        {
            "id": oid,
            "role": "arrow",
            "assetSlot": slot,
            "x": round(place_x, 1),
            "y": round(place_y, 1),
            "width": w,
            "height": h,
            "label": label,
        }
    )
    cues.append(
        {
            "objectId": oid,
            "type": "fade_in",
            "durationMs": 450,
            "delayMs": 200,
        }
    )
    out["objects"] = objects
    out["motionCues"] = cues
    if out.get("type") not in ("basic_boxes", "relative_motion.trains"):
        out["type"] = "basic_boxes"
        out.setdefault("width", 900)
        out.setdefault("height", 420)
    return out


def add_text_object_to_scene(
    scene: dict[str, Any],
    *,
    body: str,
    x: float | None = None,
    y: float | None = None,
) -> dict[str, Any]:
    """Insert a freeform text box onto the stage."""
    out = dict(scene)
    objects = [dict(o) for o in (out.get("objects") or []) if isinstance(o, dict)]
    cues = list(out.get("motionCues") or [])
    stage_w = float(out.get("width") or 900)
    text = (body or "").strip() or "New text"
    box_w = min(720.0, stage_w - 80)
    place_x = float(x) if x is not None else (stage_w - box_w) / 2
    place_y = float(y) if y is not None else 180.0
    oid = _next_object_id(objects, "text_")
    objects.append(
        {
            "id": oid,
            "role": "text",
            "assetSlot": "text.freeform",
            "x": round(place_x, 1),
            "y": round(place_y, 1),
            "width": box_w,
            "height": 72,
            "label": "Text",
            "body": text,
        }
    )
    cues.append({"objectId": oid, "type": "fade_in", "durationMs": 450, "delayMs": 120})
    out["objects"] = objects
    out["motionCues"] = cues
    if out.get("type") not in ("basic_boxes", "relative_motion.trains"):
        out["type"] = "basic_boxes"
        out.setdefault("width", 900)
        out.setdefault("height", 420)
    return out


def _wants_trains(slide: dict[str, Any]) -> bool:
    visual = str(slide.get("visual_type") or "").lower()
    if visual in ("trains", "scene"):
        return True
    blob = " ".join(
        str(slide.get(k) or "")
        for k in ("title", "narration", "explanation")
    ).lower()
    return any(token in blob for token in ("train", "collide", "collision", "railway"))


def ensure_slide_scene(slide: dict[str, Any]) -> dict[str, Any]:
    """Attach a scene_spec if missing. Does not overwrite an existing scene."""
    out = dict(slide)
    if isinstance(out.get("scene"), dict) and out["scene"].get("type"):
        return out
    if _wants_trains(out):
        out["scene"] = create_trains_scene()
        out.setdefault("visual_type", "trains")
    else:
        out["scene"] = create_basic_boxes_scene(out)
    return out


def materialize_slides(slides: list[Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for i, slide in enumerate(slides, start=1):
        if hasattr(slide, "model_dump"):
            data = slide.model_dump()
        elif isinstance(slide, dict):
            data = dict(slide)
        else:
            continue
        data.setdefault("number", i)
        result.append(ensure_slide_scene(data))
    return result
