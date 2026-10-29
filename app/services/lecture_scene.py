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


_CODE_HINT = (
    "function",
    "const ",
    "let ",
    "var ",
    "class ",
    "def ",
    "import ",
    "export ",
    "return ",
    "console.",
    "=>",
    "public ",
    "System.out",
    "printf",
    "fn ",
)


def _looks_like_code(text: str) -> bool:
    t = (text or "").strip()
    if not t:
        return False
    if len(t) < 40 and "\n" not in t and not any(h in t for h in _CODE_HINT):
        return False
    if any(h in t for h in _CODE_HINT):
        return True
    if "\n" in t and any(ch in t for ch in "{};"):
        return True
    if t.count(";") >= 2:
        return True
    return False


def _infer_code_language(text: str) -> str:
    t = text or ""
    if ("def " in t or "print(" in t) and "function" not in t and "const " not in t:
        return "Python"
    if "public class" in t or "System.out" in t:
        return "Java"
    if "fn " in t or "let mut" in t:
        return "Rust"
    if "func " in t or "fmt." in t:
        return "Go"
    if "#include" in t or "std::" in t:
        return "C++"
    return "JavaScript"


def _prepare_equation_body(text: str, max_len: int = 120) -> str:
    raw = text or ""
    if _looks_like_code(raw):
        code = raw.replace("\r\n", "\n").rstrip()
        if len(code) <= 2400:
            return code
        return f"{code[:2399]}…"
    return _truncate(raw, max_len)


def _code_box_metrics(body: str) -> tuple[float, float]:
    lines = body.replace("\r\n", "\n").split("\n")
    line_count = max(1, len(lines))
    longest = max((len(l) for l in lines), default=1)
    width = min(620.0, max(360.0, round(24 + longest * 11 * 0.62)))
    height = min(280.0, max(96.0, round(20 + 18 + line_count * 15 + 4)))
    return float(width), float(height)


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
    family: str = "system-ui, sans-serif",
) -> dict[str, Any]:
    return {
        "fontFamily": family,
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
    body_style = _style(size=11)
    equation_style = _style(size=13, weight="bold")
    callout_style = _style(size=11, weight="bold", color="#9a3412")

    objects: list[dict[str, Any]] = []
    cues: list[dict[str, Any]] = []
    delay = 0

    # The player header already owns the slide title. Do not add a duplicate
    # title/role scaffold inside the editable stage.
    y = 40.0
    equation = str(slide.get("equation") or "").strip()
    if equation:
        eq_body = _prepare_equation_body(equation)
        is_code = _looks_like_code(eq_body)
        if is_code:
            box_w, box_h = _code_box_metrics(eq_body)
            objects.append(
                {
                    "id": "box_equation",
                    "role": "box.code",
                    "assetSlot": "code.sample",
                    "x": 36,
                    "y": y,
                    "width": box_w,
                    "height": box_h,
                    "label": _infer_code_language(eq_body),
                    "body": eq_body,
                    "textStyle": _style(
                        size=11,
                        family="ui-monospace, Menlo, Consolas, monospace",
                        color="#d4d4d4",
                    ),
                }
            )
            y_after = y + box_h + 16.0
        else:
            box_w, box_h = 540.0, 70.0
            objects.append(
                {
                    "id": "box_equation",
                    "role": "box.equation",
                    "assetSlot": "box.placeholder",
                    "x": 36,
                    "y": y,
                    "width": box_w,
                    "height": box_h,
                    "label": "Equation",
                    "body": eq_body,
                    "textStyle": equation_style,
                }
            )
            y_after = y + box_h + 16.0
        cues.extend(_entrance("box_equation", 36, y, delay_ms=delay))
        delay += 200
        y = y_after
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


def add_code_object_to_scene(
    scene: dict[str, Any],
    *,
    body: str,
    language: str | None = None,
    x: float | None = None,
    y: float | None = None,
) -> dict[str, Any]:
    """Insert a dark IDE-style code sample panel onto the stage."""
    out = dict(scene)
    objects = [dict(o) for o in (out.get("objects") or []) if isinstance(o, dict)]
    cues = list(out.get("motionCues") or [])
    stage_w = float(out.get("width") or 900)
    code = (body or "").replace("\r\n", "\n").rstrip() or "// code"
    lang = (language or "").strip() or _infer_code_language(code)
    box_w, box_h = _code_box_metrics(code)
    box_w = min(box_w, stage_w - 48)
    place_x = float(x) if x is not None else 36.0
    place_y = float(y) if y is not None else 100.0
    oid = _next_object_id(objects, "code_")
    objects.append(
        {
            "id": oid,
            "role": "box.code",
            "assetSlot": "code.sample",
            "x": round(place_x, 1),
            "y": round(place_y, 1),
            "width": round(box_w, 1),
            "height": round(box_h, 1),
            "label": lang,
            "body": code,
            "textStyle": _style(
                size=11,
                family="ui-monospace, Menlo, Consolas, monospace",
                color="#d4d4d4",
            ),
        }
    )
    cues.append({"objectId": oid, "type": "fade_in", "durationMs": 450, "delayMs": 120})
    out["objects"] = objects
    out["motionCues"] = cues
    if out.get("type") not in ("basic_boxes", "relative_motion.trains"):
        out["type"] = "basic_boxes"
        out.setdefault("width", 900)
        out.setdefault("height", 480)
    return out


def update_object_in_scene(
    scene: dict[str, Any],
    object_id: str,
    *,
    label: str | None = None,
    body: str | None = None,
    x: float | None = None,
    y: float | None = None,
    width: float | None = None,
    height: float | None = None,
) -> dict[str, Any]:
    """Patch an existing stage object's label, body, and/or geometry."""
    out = dict(scene)
    objects = [dict(o) for o in (out.get("objects") or []) if isinstance(o, dict)]
    found = False
    for obj in objects:
        if str(obj.get("id")) != object_id:
            continue
        found = True
        if label is not None:
            obj["label"] = label
        if body is not None:
            obj["body"] = body
            # Promote plain text/equation boxes to code panels when body is source code.
            if _looks_like_code(body):
                obj["role"] = "box.code"
                obj["assetSlot"] = "code.sample"
                if label is None:
                    obj["label"] = _infer_code_language(body)
                if width is None and height is None:
                    bw, bh = _code_box_metrics(body)
                    obj["width"] = bw
                    obj["height"] = bh
                obj["textStyle"] = _style(
                    size=11,
                    family="ui-monospace, Menlo, Consolas, monospace",
                    color="#d4d4d4",
                )
        if x is not None:
            obj["x"] = round(float(x), 1)
        if y is not None:
            obj["y"] = round(float(y), 1)
        if width is not None:
            obj["width"] = round(float(width), 1)
        if height is not None:
            obj["height"] = round(float(height), 1)
        break
    if not found:
        return scene
    out["objects"] = objects
    return out


def remove_object_from_scene(scene: dict[str, Any], object_id: str) -> dict[str, Any]:
    """Remove a stage object and its motion cues."""
    out = dict(scene)
    objects = [
        dict(o)
        for o in (out.get("objects") or [])
        if isinstance(o, dict) and str(o.get("id")) != object_id
    ]
    cues = [
        c
        for c in (out.get("motionCues") or [])
        if not (isinstance(c, dict) and str(c.get("objectId")) == object_id)
    ]
    out["objects"] = objects
    out["motionCues"] = cues
    return out


_SCENE_ARCHETYPES = {
    "math_worked_example",
    "math_graph",
    "math_geometry",
    "code_walkthrough",
    "code_flow",
    "science_process",
    "science_force_vector",
    "relative_motion_trains",
    "concept_comparison",
    "basic_boxes",
}


def _hint(slide: dict[str, Any]) -> dict[str, Any]:
    raw = slide.get("scene_hint")
    return dict(raw) if isinstance(raw, dict) else {}


def _archetype(slide: dict[str, Any], subject: str) -> str:
    requested = str(_hint(slide).get("archetype") or "")
    if subject == "coding":
        # Never fall back to generic pedagogy boxes for programming lectures.
        if requested == "code_flow":
            return "code_flow"
        return "code_walkthrough"
    if requested in _SCENE_ARCHETYPES:
        return requested
    if _wants_trains(slide):
        return "relative_motion_trains"
    visual = str(slide.get("visual_type") or "").lower()
    if subject == "math":
        if visual == "graph":
            return "math_graph"
        if visual in ("triangle", "circle"):
            return "math_geometry"
        return "math_worked_example"
    if subject == "science":
        return "science_force_vector" if "force" in str(slide.get("title") or "").lower() else "science_process"
    return "concept_comparison"


def _scene_object(
    object_id: str,
    role: str,
    x: float,
    y: float,
    width: float,
    height: float,
    *,
    label: str = "",
    body: str = "",
    asset_slot: str = "box.placeholder",
    style: dict[str, Any] | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "id": object_id,
        "role": role,
        "assetSlot": asset_slot,
        "x": x,
        "y": y,
        "width": width,
        "height": height,
    }
    if label:
        result["label"] = label
    if body:
        result["body"] = body
    if style:
        result["textStyle"] = style
    return result


def _scene(
    archetype: str,
    objects: list[dict[str, Any]],
    cues: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "type": "basic_boxes",
        "archetype": archetype,
        "width": 900,
        "height": 480,
        "objects": objects,
        "motionCues": cues,
    }


def _build_math_worked_example(slide: dict[str, Any]) -> dict[str, Any]:
    equation = _prepare_equation_body(str(slide.get("equation") or "")) or "Key expression"
    steps = _slide_steps(slide)
    objects = [
        _scene_object("title", "text", 48, 32, 800, 34, body=_truncate(str(slide.get("title") or "Worked example"), 90), style=_style(size=20, weight="bold")),
        _scene_object("equation", "box.equation", 110, 92, 680, 88, label="Start here", body=equation, style=_style(size=22, weight="bold")),
        _scene_object("operation_arrow", "arrow", 436, 190, 28, 44, label="↓", asset_slot="arrow.down"),
    ]
    for index, step in enumerate(steps[:3]):
        objects.append(
            _scene_object(
                f"step_{index + 1}",
                "box.math_step",
                70 + index * 275,
                255,
                220,
                96,
                label=f"Step {index + 1}",
                body=step,
                style=_style(size=12),
            )
        )
    emphasis = str(_hint(slide).get("emphasis") or slide.get("callout") or "")
    if emphasis:
        objects.append(_scene_object("answer_hint", "text", 110, 390, 680, 48, label="Remember", body=_truncate(emphasis, 150), style=_style(size=13, weight="bold", color="#1d4ed8"), asset_slot="text.freeform"))
    cues = [cue for index, obj in enumerate(objects) for cue in _entrance(str(obj["id"]), float(obj["x"]), float(obj["y"]), delay_ms=index * 130)]
    return _scene("math_worked_example", objects, cues)


def _build_math_graph(slide: dict[str, Any]) -> dict[str, Any]:
    equation = _prepare_equation_body(str(slide.get("equation") or ""))
    objects = [
        _scene_object("title", "text", 48, 28, 780, 34, body=_truncate(str(slide.get("title") or "Graph"), 90), style=_style(size=20, weight="bold")),
        _scene_object("axes", "graph.axes", 80, 90, 440, 320, label=equation or "Relationship"),
        _scene_object("insight", "box.explain", 570, 125, 260, 125, label="What to notice", body=_truncate(str(slide.get("explanation") or ""), 180), style=_style(size=12)),
        _scene_object("callout", "text", 570, 285, 260, 76, label="Key point", body=_truncate(str(slide.get("callout") or ""), 100), style=_style(size=12, weight="bold", color="#1d4ed8"), asset_slot="text.freeform"),
    ]
    cues = [cue for index, obj in enumerate(objects) for cue in _entrance(str(obj["id"]), float(obj["x"]), float(obj["y"]), delay_ms=index * 150)]
    return _scene("math_graph", objects, cues)


def _build_code_walkthrough(slide: dict[str, Any]) -> dict[str, Any]:
    """Editable lecture stage: code box + explain boxes + arrows (palette objects)."""
    code_lines = slide.get("code_lines")
    if isinstance(code_lines, list) and any(str(item).strip() for item in code_lines):
        code = "\n".join(str(item).rstrip("\n") for item in code_lines)
    else:
        code = _prepare_equation_body(str(slide.get("equation") or ""))
    if not _looks_like_code(code):
        code = f"// {str(slide.get('title') or 'Code concept')}\n{code or '// Add your example here'}"
    language = str(_hint(slide).get("code_language") or _infer_code_language(code))
    code_w, code_h = _code_box_metrics(code)
    steps = _slide_steps(slide)
    # Prefer real teaching steps; avoid abstract filler when explanation exists.
    fluff = ("frame the", "show the key", "check understanding")
    if all(any(f in s.lower() for f in fluff) for s in steps[:3]):
        bits = [
            p.strip()
            for p in str(slide.get("explanation") or "")
            .replace("!", ".")
            .replace("?", ".")
            .split(".")
            if p.strip()
        ]
        if bits:
            steps = [_truncate(b, 72) for b in bits[:3]]
        callout = str(slide.get("callout") or "").strip()
        if callout and len(steps) < 3:
            steps.append(_truncate(callout, 72))

    code_box_w = min(max(code_w, 420), 560)
    code_box_h = min(max(code_h, 200), 320)
    objects = [
        _scene_object(
            "title",
            "text",
            42,
            26,
            810,
            34,
            body=_truncate(str(slide.get("title") or "Code walkthrough"), 90),
            style=_style(size=20, weight="bold"),
            asset_slot="text.freeform",
        ),
        _scene_object(
            "code",
            "box.code",
            42,
            86,
            code_box_w,
            code_box_h,
            label=language,
            body=code,
            asset_slot="code.sample",
            style=_style(
                size=11,
                family="ui-monospace, Menlo, Consolas, monospace",
                color="#d4d4d4",
            ),
        ),
    ]
    for index, step in enumerate(steps[:3]):
        cy = 96 + index * 112
        objects.append(
            _scene_object(
                f"arrow_{index + 1}",
                "arrow",
                code_box_w + 52,
                cy + 26,
                48,
                28,
                label="→",
                asset_slot="arrow.east",
            )
        )
        label = step.split("—")[0].split("-")[0].strip()[:28] or f"Step {index + 1}"
        objects.append(
            _scene_object(
                f"callout_{index + 1}",
                "box.custom",
                code_box_w + 110,
                cy,
                240,
                88,
                label=label,
                body=step,
                style=_style(size=11),
            )
        )
    cues = [
        cue
        for index, obj in enumerate(objects)
        for cue in _entrance(
            str(obj["id"]), float(obj["x"]), float(obj["y"]), delay_ms=index * 120
        )
    ]
    return _scene("code_walkthrough", objects, cues)


def _build_code_flow(slide: dict[str, Any]) -> dict[str, Any]:
    code = _prepare_equation_body(str(slide.get("equation") or ""))
    if not _looks_like_code(code):
        code = f"// {str(slide.get('title') or 'Transform data')}\n{code or 'return result;'}"
    steps = _slide_steps(slide)
    objects = [
        _scene_object("title", "text", 48, 28, 800, 34, body=_truncate(str(slide.get("title") or "Code flow"), 90), style=_style(size=20, weight="bold")),
        _scene_object("input", "box.flow", 48, 170, 190, 110, label="Input", body=steps[0], style=_style(size=12)),
        _scene_object("to_transform", "arrow", 252, 210, 48, 28, label="→", asset_slot="arrow.east"),
        _scene_object("transform", "box.code", 320, 115, 300, 190, label=str(_hint(slide).get("code_language") or _infer_code_language(code)), body=code, asset_slot="code.sample", style=_style(size=10, family="ui-monospace, Menlo, Consolas, monospace", color="#d4d4d4")),
        _scene_object("to_output", "arrow", 636, 210, 48, 28, label="→", asset_slot="arrow.east"),
        _scene_object("output", "box.flow", 700, 170, 152, 110, label="Output", body=steps[1], style=_style(size=12)),
    ]
    cues = [cue for index, obj in enumerate(objects) for cue in _entrance(str(obj["id"]), float(obj["x"]), float(obj["y"]), delay_ms=index * 140)]
    return _scene("code_flow", objects, cues)


def _build_science_process(slide: dict[str, Any]) -> dict[str, Any]:
    concepts = [str(item) for item in _hint(slide).get("concepts") or [] if str(item).strip()]
    stages = (concepts + _slide_steps(slide))[:3]
    while len(stages) < 3:
        stages.append(["Observe", "Explain", "Apply"][len(stages)])
    objects = [
        _scene_object("title", "text", 48, 32, 800, 34, body=_truncate(str(slide.get("title") or "Science process"), 90), style=_style(size=20, weight="bold")),
    ]
    for index, stage in enumerate(stages):
        x = 55 + index * 285
        objects.append(_scene_object(f"process_{index + 1}", "box.process", x, 165, 205, 112, label=f"{index + 1}", body=_truncate(stage, 100), style=_style(size=13, weight="bold")))
        if index < 2:
            objects.append(_scene_object(f"flow_{index + 1}", "arrow", x + 215, 207, 52, 28, label="→", asset_slot="arrow.east"))
    objects.append(_scene_object("explain", "box.explain", 150, 345, 600, 80, label="Why it matters", body=_truncate(str(slide.get("explanation") or ""), 180), style=_style(size=12)))
    cues = [cue for index, obj in enumerate(objects) for cue in _entrance(str(obj["id"]), float(obj["x"]), float(obj["y"]), delay_ms=index * 120)]
    return _scene("science_process", objects, cues)


def _build_science_force_vector(slide: dict[str, Any]) -> dict[str, Any]:
    objects = [
        _scene_object("title", "text", 48, 28, 800, 34, body=_truncate(str(slide.get("title") or "Force diagram"), 90), style=_style(size=20, weight="bold")),
        _scene_object("body", "science.body", 355, 190, 150, 110, label=str(_hint(slide).get("focus") or "Object")),
        _scene_object("force_up", "science.vector", 415, 92, 32, 96, label="↑", body="Normal", asset_slot="arrow.up"),
        _scene_object("force_down", "science.vector", 415, 306, 32, 96, label="↓", body="Weight", asset_slot="arrow.down"),
        _scene_object("force_right", "science.vector", 520, 225, 150, 32, label="→", body="Applied force", asset_slot="arrow.east"),
        _scene_object("explain", "box.explain", 78, 345, 240, 85, label="Analyze", body=_truncate(str(slide.get("explanation") or ""), 150), style=_style(size=11)),
    ]
    cues = [cue for index, obj in enumerate(objects) for cue in _entrance(str(obj["id"]), float(obj["x"]), float(obj["y"]), delay_ms=index * 130)]
    return _scene("science_force_vector", objects, cues)


def _build_concept_comparison(slide: dict[str, Any]) -> dict[str, Any]:
    steps = _slide_steps(slide)
    objects = [
        _scene_object("title", "text", 50, 36, 800, 36, body=_truncate(str(slide.get("title") or "Compare ideas"), 90), style=_style(size=20, weight="bold")),
        _scene_object("left", "box.comparison", 80, 135, 310, 170, label="Idea A", body=steps[0], style=_style(size=13)),
        _scene_object("right", "box.comparison", 510, 135, 310, 170, label="Idea B", body=steps[1], style=_style(size=13)),
        _scene_object("compare", "arrow", 414, 205, 72, 30, label="↔", asset_slot="arrow.east"),
        _scene_object("summary", "box.explain", 160, 355, 580, 70, label="Takeaway", body=_truncate(str(slide.get("explanation") or ""), 180), style=_style(size=12)),
    ]
    cues = [cue for index, obj in enumerate(objects) for cue in _entrance(str(obj["id"]), float(obj["x"]), float(obj["y"]), delay_ms=index * 140)]
    return _scene("concept_comparison", objects, cues)


def _wants_trains(slide: dict[str, Any]) -> bool:
    visual = str(slide.get("visual_type") or "").lower()
    if visual in ("trains", "scene"):
        return True
    blob = " ".join(
        str(slide.get(k) or "")
        for k in ("title", "narration", "explanation")
    ).lower()
    return any(token in blob for token in ("train", "collide", "collision", "railway"))


def ensure_slide_scene(slide: dict[str, Any], *, subject: str = "general") -> dict[str, Any]:
    """Attach a scene_spec if missing. Does not overwrite an existing scene."""
    out = dict(slide)
    code_lines = out.get("code_lines")
    if (
        not str(out.get("equation") or "").strip()
        and isinstance(code_lines, list)
        and any(str(item).strip() for item in code_lines)
    ):
        out["equation"] = "\n".join(str(item).rstrip("\n") for item in code_lines)

    if isinstance(out.get("scene"), dict) and out["scene"].get("type"):
        return out
    archetype = _archetype(out, subject)
    if archetype == "relative_motion_trains":
        out["scene"] = create_trains_scene()
        out.setdefault("visual_type", "trains")
    elif archetype == "math_worked_example":
        out["scene"] = _build_math_worked_example(out)
    elif archetype == "math_graph":
        out["scene"] = _build_math_graph(out)
    elif archetype == "math_geometry":
        # The existing scene builder already has editable geometry accent objects.
        scene = create_basic_boxes_scene(out)
        scene["archetype"] = archetype
        out["scene"] = scene
    elif archetype == "code_walkthrough":
        out["scene"] = _build_code_walkthrough(out)
    elif archetype == "code_flow":
        out["scene"] = _build_code_flow(out)
    elif archetype == "science_process":
        out["scene"] = _build_science_process(out)
    elif archetype == "science_force_vector":
        out["scene"] = _build_science_force_vector(out)
    elif archetype == "concept_comparison":
        out["scene"] = _build_concept_comparison(out)
    else:
        out["scene"] = create_basic_boxes_scene(out)
        out["scene"]["archetype"] = "basic_boxes"
    return out


def materialize_slides(
    slides: list[Any],
    *,
    subject: str = "general",
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for i, slide in enumerate(slides, start=1):
        if hasattr(slide, "model_dump"):
            data = slide.model_dump()
        elif isinstance(slide, dict):
            data = dict(slide)
        else:
            continue
        data.setdefault("number", i)
        result.append(ensure_slide_scene(data, subject=subject))
    return result
