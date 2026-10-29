"""AI edit assistant for existing lectures — NL prompt → allowlisted slide + stage updates."""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Literal, Optional

from fastapi import HTTPException
from langchain_core.messages import HumanMessage, SystemMessage

from app.services.ai_services.llm_client import build_chat_model
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.models.lecture_models.Lecture import Lecture
from app.models.user_models.User import User
from app.schemas.lecture_schemas import (
    LectureCheckpoint,
    LectureEditRequest,
    LectureEditResponse,
)
from app.services.lecture_scene import (
    add_arrow_to_scene,
    add_code_object_to_scene,
    add_text_object_to_scene,
    apply_boxes_slide_direction,
    create_basic_boxes_scene,
    create_trains_scene,
    materialize_slides,
    remove_object_from_scene,
    update_object_in_scene,
)
from app.services.lecture_subjects import SUBJECT_GUIDANCE, normalize_subject

logger = logging.getLogger(__name__)


def _openai_api_key() -> str | None:
    return os.getenv("OPENAI_API_KEY")


def _assistant_model() -> str:
    return os.getenv("OPENAI_ANSWER_MODEL", "gpt-4o-mini")


DirectionWord = Literal[
    "left", "right", "up", "down", "east", "west", "north", "south"
]


class TrainsMotionPatch(BaseModel):
    length_km: Optional[float] = None
    speed_a: Optional[float] = None
    speed_b: Optional[float] = None
    direction_a: Optional[Literal["east", "west"]] = None
    direction_b: Optional[Literal["east", "west"]] = None
    # NL helpers: "make train A go right" → move_a="right"
    move_a: Optional[DirectionWord] = None
    move_b: Optional[DirectionWord] = None


class BoxesMotionPatch(BaseModel):
    """Animate basic_boxes stage objects sliding in a direction."""

    direction: DirectionWord = Field(
        description="Where objects should appear to move: right/left/up/down (or east/west)"
    )
    distance: Optional[float] = Field(
        default=120, description="Travel distance in stage pixels"
    )
    object_id: Optional[str] = Field(
        default=None,
        description="Optional object id (box_title, box_equation, box_explain). Null = all boxes.",
    )


class AddStageObject(BaseModel):
    """Add a real graphic onto the stage (visible object), NOT motion direction."""

    kind: Literal["arrow", "text", "code"] = Field(
        description=(
            "arrow = visible arrow; text = freeform label/prose; "
            "code = dark IDE-style code sample panel (use for Two Sum, factorial, etc.)"
        )
    )
    direction: Optional[DirectionWord] = Field(
        default="down",
        description="For kind=arrow only: which way the arrow points (down/up/left/right)",
    )
    body: Optional[str] = Field(
        default=None,
        description=(
            "For kind=text: short label/prose. "
            "For kind=code: the FULL source code with newlines (required)."
        ),
    )
    language: Optional[str] = Field(
        default=None,
        description="For kind=code: e.g. JavaScript, Python, Java (optional; inferred if omitted)",
    )
    below_object_id: Optional[str] = Field(
        default=None,
        description="Place below this existing object id (e.g. box_title)",
    )
    above_object_id: Optional[str] = Field(
        default=None,
        description="Place above this existing object id",
    )
    x: Optional[float] = None
    y: Optional[float] = None


class UpdateStageObject(BaseModel):
    """Change an EXISTING stage object (label, body text, or position/size)."""

    object_id: Optional[str] = Field(
        default=None,
        description="Exact object id from stage.objects (preferred when known)",
    )
    match: Optional[str] = Field(
        default=None,
        description=(
            "Human name for the object when id is unknown, e.g. 'topic', 'title', "
            "'equation', 'callout', 'key idea', or the current label text"
        ),
    )
    label: Optional[str] = Field(
        default=None, description="New badge/label on the box (e.g. change Topic → Lesson)"
    )
    body: Optional[str] = Field(
        default=None, description="New main text inside the object"
    )
    x: Optional[float] = None
    y: Optional[float] = None
    width: Optional[float] = None
    height: Optional[float] = None


class RemoveStageObject(BaseModel):
    """Delete an EXISTING stage object."""

    object_id: Optional[str] = Field(
        default=None, description="Exact object id from stage.objects"
    )
    match: Optional[str] = Field(
        default=None,
        description="Human name when id unknown: topic, equation, callout, etc.",
    )


class StagePatch(BaseModel):
    """Stage / animation edits for a slide's scene_spec."""

    use_trains_scene: Optional[bool] = Field(
        default=None,
        description="True to switch this slide to the trains stage",
    )
    use_boxes_scene: Optional[bool] = Field(
        default=None,
        description="True to switch this slide to basic boxes stage",
    )
    trains: Optional[TrainsMotionPatch] = None
    boxes: Optional[BoxesMotionPatch] = Field(
        default=None,
        description=(
            "ONLY for animating existing boxes sliding. "
            "Do NOT use this when the user asks to ADD an arrow/shape on the stage."
        ),
    )
    update_objects: list[UpdateStageObject] = Field(
        default_factory=list,
        description=(
            "Edit EXISTING stage objects in place. "
            "Use for 'change the topic label to Lesson', 'rename Topic to …', "
            "'change the equation text', 'move the callout'."
        ),
    )
    remove_objects: list[RemoveStageObject] = Field(
        default_factory=list,
        description=(
            "Remove EXISTING stage objects. "
            "Use for 'delete the topic box', 'remove the callout'."
        ),
    )
    add_objects: list[AddStageObject] = Field(
        default_factory=list,
        description=(
            "Add NEW visible graphics onto the stage. "
            "Use kind=code for programming samples (full source in body). "
            "Use kind=text only for short labels/prose — NEVER for code. "
            "Do NOT use this to rename/change an existing box — use update_objects."
        ),
    )


class SlidePatch(BaseModel):
    number: int = Field(description="1-based slide number (page) to update")
    title: Optional[str] = None
    equation: Optional[str] = None
    narration: Optional[str] = None
    explanation: Optional[str] = None
    visual_type: Optional[str] = None
    trains: Optional[TrainsMotionPatch] = Field(
        default=None,
        description="Legacy shortcut; prefer stage.trains",
    )
    stage: Optional[StagePatch] = Field(
        default=None,
        description="Edit the animated stage on this slide (objects, motion, scene type)",
    )
    checkpoint: Optional[LectureCheckpoint] = Field(
        default=None,
        description="Question students attempt before the next slide",
    )


class SlideDraft(BaseModel):
    number: int = 1
    title: str = ""
    equation: str = ""
    narration: str = ""
    explanation: str = ""
    visual_type: str = "equation"
    checkpoint: Optional[LectureCheckpoint] = None


class LectureEditIntent(BaseModel):
    message: str = Field(description="What you changed, in plain language for the educator")
    title: Optional[str] = Field(default=None, description="New lecture title if renaming")
    patch_slides: list[SlidePatch] = Field(
        default_factory=list,
        description="Partial updates to existing slides by number",
    )
    replace_slides: Optional[list[SlideDraft]] = Field(
        default=None,
        description="If set, replace the entire slide deck with this list",
    )
    no_action: bool = Field(
        default=False,
        description="True when only answering a question with no edits",
    )


SYSTEM_PROMPT = """You are a Lecture Edit Assistant for Project VL.
Educators already have a saved lecture with TEXT (narration/explanation) AND an animated STAGE (scene_spec with objects).
They will say things like:
- "change the topic label to Lesson" / "rename Topic to Lesson on all slides"
- "change the body of the equation box to …"
- "delete the callout" / "remove the yellow text box"
- "add a downward arrow on the stage" / "put an arrow below the topic box"
- "add a Two Sum example in JavaScript" / "put a factorial code sample on this slide"
- "on page 1, make the boxes slide to the right"
- "make train A go east and faster"
- "shorten the narration on slide 1"

CRITICAL distinctions:
1. CHANGE / RENAME / EDIT an existing stage box → stage.update_objects
   - "change the topic label to Lesson" →
     update_objects: [{match:"topic", label:"Lesson"}]
   - NEVER use add_objects for renames or label changes.
2. DELETE / REMOVE an existing stage object → stage.remove_objects
3. ADD a new graphic → stage.add_objects
4. CODE / programming samples (Two Sum, factorial, recursion, etc.):
   - MUST use add_objects with kind="code"
   - body MUST be the FULL working source (multi-line, with newlines)
   - language e.g. "JavaScript" or "Python"
   - NEVER use kind="text" for code — that only creates a yellow prose box
   - NEVER put only a problem title like "Two Sum Problem" — include the actual code
   Example:
     add_objects: [{
       kind: "code",
       language: "JavaScript",
       body: "function twoSum(nums, target) {\\n  const map = new Map();\\n  for (let i = 0; i < nums.length; i++) {\\n    const need = target - nums[i];\\n    if (map.has(need)) return [map.get(need), i];\\n    map.set(nums[i], i);\\n  }\\n  return [];\\n}"
     }]
5. "make it move down" / animate → stage.boxes.direction (entrance motion only)

You may:
1. Rename the lecture (title)
2. Patch slide TEXT: title, equation, narration, explanation, visual_type
   Optional checkpoint: a subject question students attempt before the next slide.
   Preserve an existing checkpoint unless the educator asks to change or remove it.
3. Patch STAGE via patch_slides[].stage:
   - update_objects / remove_objects
   - add_objects: [{kind:"arrow"|"text"|"code", ...}]
   - trains / boxes motion
   - use_trains_scene / use_boxes_scene
4. replace_slides only for heavy rebuilds
5. no_action=true if they only ask a question

Object matching tips (use match OR object_id from stage.objects):
- topic / title / topic box → usually id "box_title", label "Topic"
- equation / equation box / code → "box_equation" or objects with role box.code
- Prefer exact object_id from context when available.

Rules:
- Stay on the lecture's subject.
- Prefer patch_slides for small edits.
- When the educator says "this slide" / "the current slide" / "here", use current_slide_number.
- If they say "all slides", emit one patch_slides entry per slide with the same stage edits.
- visual_type: equation, graph, triangle, circle, trains.
- In message, describe ONLY what you actually did. Be honest.
"""


def _dir_to_east_west(word: str | None) -> str | None:
    if not word:
        return None
    w = word.lower()
    if w in ("east", "right"):
        return "east"
    if w in ("west", "left"):
        return "west"
    return None


_OBJECT_MATCH_ALIASES: dict[str, tuple[str, ...]] = {
    "topic": ("box_title",),
    "title": ("box_title",),
    "topic box": ("box_title",),
    "title box": ("box_title",),
    "equation": ("box_equation",),
    "equation box": ("box_equation",),
    "callout": ("box_callout",),
    "key idea": ("box_explain",),
    "explain": ("box_explain",),
    "explanation": ("box_explain",),
    "role": ("text_role",),
}


def _normalize_match(value: str) -> str:
    return " ".join(value.strip().lower().replace("_", " ").replace(".", " ").split())


def _resolve_object_id(scene: dict[str, Any], *, object_id: str | None, match: str | None) -> str | None:
    objects = [o for o in (scene.get("objects") or []) if isinstance(o, dict)]
    if not objects:
        return None

    by_id = {str(o.get("id")): o for o in objects if o.get("id") is not None}

    if object_id and object_id in by_id:
        return object_id

    needle = _normalize_match(match or object_id or "")
    if not needle:
        return None

    for alias, ids in _OBJECT_MATCH_ALIASES.items():
        if needle == alias or needle == _normalize_match(alias):
            for oid in ids:
                if oid in by_id:
                    return oid

    if needle in by_id:
        return needle

    for oid, obj in by_id.items():
        label = _normalize_match(str(obj.get("label") or ""))
        role = _normalize_match(str(obj.get("role") or ""))
        body = _normalize_match(str(obj.get("body") or ""))
        if needle == label or needle == role:
            return oid
        if needle in label or needle in role:
            return oid
        if needle and needle in body[:80]:
            return oid
        # role like box.title → title
        role_tail = role.split()[-1] if role else ""
        if needle == role_tail:
            return oid

    return None


def _scene_summary(slide: dict[str, Any]) -> dict[str, Any] | None:
    scene = slide.get("scene")
    if not isinstance(scene, dict):
        return None
    stype = scene.get("type")
    if stype == "relative_motion.trains":
        return {
            "type": "trains",
            "train_a": scene.get("train_a"),
            "train_b": scene.get("train_b"),
            "length_km": (scene.get("track") or {}).get("length_km"),
            "objects": [
                {
                    "id": o.get("id"),
                    "label": o.get("label"),
                    "role": o.get("role"),
                    "body": (str(o.get("body") or ""))[:120] or None,
                    "x": o.get("x"),
                    "y": o.get("y"),
                }
                for o in (scene.get("objects") or [])
                if isinstance(o, dict)
            ],
            "hint": "Edit with stage.trains, or update_objects / remove_objects / add_objects.",
        }
    if stype == "basic_boxes":
        return {
            "type": "basic_boxes",
            "objects": [
                {
                    "id": o.get("id"),
                    "label": o.get("label"),
                    "role": o.get("role"),
                    "body": (str(o.get("body") or ""))[:160] or None,
                    "x": o.get("x"),
                    "y": o.get("y"),
                    "width": o.get("width"),
                    "height": o.get("height"),
                }
                for o in (scene.get("objects") or [])
                if isinstance(o, dict)
            ],
            "motionCues": scene.get("motionCues") or [],
            "hint": (
                "To CHANGE an existing box use stage.update_objects. "
                "To DELETE use stage.remove_objects. "
                "To ADD code samples use stage.add_objects [{kind:'code', language:'JavaScript', body:'full source'}]. "
                "kind=text is only for short prose — never for code. "
                "stage.boxes.direction only changes slide-in animation."
            ),
        }
    return {"type": stype}


def _strip_slide(slide: dict[str, Any]) -> dict[str, Any]:
    return {
        "number": slide.get("number"),
        "title": slide.get("title") or "",
        "equation": slide.get("equation") or "",
        "narration": slide.get("narration") or "",
        "explanation": slide.get("explanation") or "",
        "visual_type": slide.get("visual_type") or "equation",
        "stage": _scene_summary(slide),
    }


def _apply_trains_patch(slide: dict[str, Any], patch: TrainsMotionPatch) -> dict[str, Any]:
    scene = slide.get("scene") if isinstance(slide.get("scene"), dict) else {}
    train_a = dict(scene.get("train_a") or {})
    train_b = dict(scene.get("train_b") or {})
    track = dict(scene.get("track") or {})

    dir_a = patch.direction_a or _dir_to_east_west(patch.move_a) or train_a.get("direction") or "east"
    dir_b = patch.direction_b or _dir_to_east_west(patch.move_b) or train_b.get("direction") or "west"
    if dir_a not in ("east", "west"):
        dir_a = "east"
    if dir_b not in ("east", "west"):
        dir_b = "west"

    length = float(patch.length_km if patch.length_km is not None else track.get("length_km") or 200)
    speed_a = float(patch.speed_a if patch.speed_a is not None else train_a.get("speed") or 60)
    speed_b = float(patch.speed_b if patch.speed_b is not None else train_b.get("speed") or 40)

    slide["visual_type"] = "trains"
    slide["scene"] = create_trains_scene(
        length_km=length,
        speed_a=speed_a,
        speed_b=speed_b,
        direction_a=dir_a,
        direction_b=dir_b,
    )
    return slide


def _apply_boxes_patch(slide: dict[str, Any], patch: BoxesMotionPatch) -> dict[str, Any]:
    scene = slide.get("scene") if isinstance(slide.get("scene"), dict) else None
    if not scene or scene.get("type") != "basic_boxes":
        scene = create_basic_boxes_scene(slide)
    slide["visual_type"] = slide.get("visual_type") or "equation"
    if slide["visual_type"] == "trains":
        slide["visual_type"] = "equation"
    slide["scene"] = apply_boxes_slide_direction(
        scene,
        direction=patch.direction,
        distance=float(patch.distance or 120),
        object_id=patch.object_id,
    )
    return slide


def _rebuild_scene_for_text(slide: dict[str, Any]) -> dict[str, Any]:
    visual = str(slide.get("visual_type") or "").lower()
    scene = slide.get("scene") if isinstance(slide.get("scene"), dict) else None
    if visual == "trains" or (scene and scene.get("type") == "relative_motion.trains"):
        train_a = dict((scene or {}).get("train_a") or {})
        train_b = dict((scene or {}).get("train_b") or {})
        track = dict((scene or {}).get("track") or {})
        slide["visual_type"] = "trains"
        slide["scene"] = create_trains_scene(
            length_km=float(track.get("length_km") or 200),
            speed_a=float(train_a.get("speed") or 60),
            speed_b=float(train_b.get("speed") or 40),
            direction_a=str(train_a.get("direction") or "east"),
            direction_b=str(train_b.get("direction") or "west"),
        )
    else:
        # Preserve existing box motion direction if present
        if scene and scene.get("type") == "basic_boxes":
            # Refresh bodies from text but keep motion cue directions by re-deriving from first translate
            old_cues = scene.get("motionCues") or []
            direction = "up"
            for cue in old_cues:
                if isinstance(cue, dict) and cue.get("type") == "translate":
                    fr, to = cue.get("from") or {}, cue.get("to") or {}
                    dx = float(to.get("x", 0)) - float(fr.get("x", 0))
                    dy = float(to.get("y", 0)) - float(fr.get("y", 0))
                    if abs(dx) >= abs(dy) and abs(dx) > 5:
                        direction = "right" if dx > 0 else "left"
                    elif abs(dy) > 5:
                        direction = "down" if dy > 0 else "up"
                    break
            base = create_basic_boxes_scene(slide)
            slide["scene"] = apply_boxes_slide_direction(base, direction=direction, distance=80)
        else:
            slide["scene"] = create_basic_boxes_scene(slide)
    return slide


def _empty_boxes_scene() -> dict[str, Any]:
    return {
        "type": "basic_boxes",
        "width": 900,
        "height": 480,
        "objects": [],
        "motionCues": [],
    }


def _apply_add_objects(slide: dict[str, Any], items: list[AddStageObject]) -> list[str]:
    notes: list[str] = []
    scene = slide.get("scene") if isinstance(slide.get("scene"), dict) else None
    if not scene:
        # Prefer empty canvas over regenerating showcase boxes when adding objects.
        scene = _empty_boxes_scene()
        slide["visual_type"] = slide.get("visual_type") or "equation"
        if slide["visual_type"] == "trains":
            slide["visual_type"] = "equation"

    for item in items:
        if item.kind == "arrow":
            scene = add_arrow_to_scene(
                scene,
                direction=item.direction or "down",
                below_object_id=item.below_object_id,
                above_object_id=item.above_object_id,
                x=item.x,
                y=item.y,
            )
            notes.append(
                f"Added a visible {item.direction or 'down'} arrow on the stage."
            )
        elif item.kind == "code":
            code_body = (item.body or "").strip()
            if not code_body or len(code_body) < 12:
                notes.append(
                    "Skipped code object — body must contain the full source sample."
                )
                continue
            scene = add_code_object_to_scene(
                scene,
                body=code_body,
                language=item.language,
                x=item.x,
                y=item.y,
            )
            notes.append(
                f"Added a {item.language or 'code'} sample panel on the stage."
            )
        elif item.kind == "text":
            # Guardrail: if the model mistakenly used text for source code, promote to code.
            body = item.body or "New text"
            if (
                "function " in body
                or "const " in body
                or "def " in body
                or body.count("\n") >= 2
            ) and any(ch in body for ch in "{};"):
                scene = add_code_object_to_scene(
                    scene,
                    body=body,
                    language=item.language,
                    x=item.x,
                    y=item.y,
                )
                notes.append("Added a code sample panel on the stage (promoted from text).")
            else:
                scene = add_text_object_to_scene(
                    scene,
                    body=body,
                    x=item.x,
                    y=item.y,
                )
                notes.append("Added a text object on the stage.")

    slide["scene"] = scene
    return notes


def _apply_update_objects(slide: dict[str, Any], items: list[UpdateStageObject]) -> list[str]:
    notes: list[str] = []
    scene = slide.get("scene") if isinstance(slide.get("scene"), dict) else None
    if not scene:
        notes.append("Skipped object updates — no stage on this slide.")
        return notes

    for item in items:
        oid = _resolve_object_id(scene, object_id=item.object_id, match=item.match)
        if not oid:
            notes.append(
                f"Could not find stage object to update "
                f"(id={item.object_id!r}, match={item.match!r})."
            )
            continue
        before = next(
            (o for o in (scene.get("objects") or []) if isinstance(o, dict) and o.get("id") == oid),
            None,
        )
        scene = update_object_in_scene(
            scene,
            oid,
            label=item.label,
            body=item.body,
            x=item.x,
            y=item.y,
            width=item.width,
            height=item.height,
        )
        bits: list[str] = []
        if item.label is not None:
            old = (before or {}).get("label")
            bits.append(f"label {old!r} → {item.label!r}")
        if item.body is not None:
            bits.append("body text")
        if any(v is not None for v in (item.x, item.y, item.width, item.height)):
            bits.append("position/size")
        detail = ", ".join(bits) if bits else "fields"
        notes.append(f"Updated stage object '{oid}' ({detail}).")

    slide["scene"] = scene
    return notes


def _apply_remove_objects(slide: dict[str, Any], items: list[RemoveStageObject]) -> list[str]:
    notes: list[str] = []
    scene = slide.get("scene") if isinstance(slide.get("scene"), dict) else None
    if not scene:
        notes.append("Skipped object removals — no stage on this slide.")
        return notes

    for item in items:
        oid = _resolve_object_id(scene, object_id=item.object_id, match=item.match)
        if not oid:
            notes.append(
                f"Could not find stage object to remove "
                f"(id={item.object_id!r}, match={item.match!r})."
            )
            continue
        scene = remove_object_from_scene(scene, oid)
        notes.append(f"Removed stage object '{oid}'.")

    slide["scene"] = scene
    return notes


def _apply_stage_patch(slide: dict[str, Any], stage: StagePatch) -> list[str]:
    notes: list[str] = []
    if stage.use_trains_scene:
        slide["visual_type"] = "trains"
        trains = stage.trains or TrainsMotionPatch()
        _apply_trains_patch(slide, trains)
        notes.append("Switched stage to trains motion.")
    elif stage.use_boxes_scene:
        slide["visual_type"] = "equation"
        slide["scene"] = create_basic_boxes_scene(slide)
        notes.append("Switched stage to basic boxes.")
        if stage.boxes:
            _apply_boxes_patch(slide, stage.boxes)
            notes.append(f"Boxes now slide toward {stage.boxes.direction}.")

    # Prefer mutate-in-place before adds so renames don't get confused with new text.
    if stage.update_objects:
        notes.extend(_apply_update_objects(slide, stage.update_objects))
    if stage.remove_objects:
        notes.extend(_apply_remove_objects(slide, stage.remove_objects))
    if stage.add_objects:
        notes.extend(_apply_add_objects(slide, stage.add_objects))

    if not stage.use_trains_scene and not stage.use_boxes_scene:
        if stage.trains is not None:
            _apply_trains_patch(slide, stage.trains)
            notes.append("Updated trains stage motion.")
        if stage.boxes is not None:
            _apply_boxes_patch(slide, stage.boxes)
            notes.append(f"Updated box stage motion ({stage.boxes.direction}).")
    return notes


def _apply_intent(lecture: Lecture, intent: LectureEditIntent) -> list[str]:
    notes: list[str] = []
    slides: list[dict[str, Any]] = [
        dict(s) for s in (lecture.slides if isinstance(lecture.slides, list) else [])
    ]

    if intent.title and intent.title.strip():
        lecture.title = intent.title.strip()
        notes.append(f'Renamed lecture to "{lecture.title}".')

    if intent.replace_slides is not None:
        slides = []
        for i, draft in enumerate(intent.replace_slides, start=1):
            data = draft.model_dump()
            data["number"] = i
            slides.append(_rebuild_scene_for_text(data))
        notes.append(f"Replaced deck with {len(slides)} slide(s).")
    elif intent.patch_slides:
        by_number = {int(s.get("number") or 0): s for s in slides}
        for patch in intent.patch_slides:
            target = by_number.get(patch.number)
            if not target:
                notes.append(f"Skipped unknown slide #{patch.number}.")
                continue
            text_changed = False
            for field in ("title", "equation", "narration", "explanation", "visual_type"):
                value = getattr(patch, field)
                if value is not None:
                    target[field] = value
                    text_changed = True
            if patch.checkpoint is not None:
                target["checkpoint"] = patch.checkpoint.model_dump()

            stage_notes: list[str] = []
            if patch.stage is not None:
                stage_notes = _apply_stage_patch(target, patch.stage)
            elif patch.trains is not None:
                _apply_trains_patch(target, patch.trains)
                stage_notes = ["Updated trains stage motion."]
            elif text_changed:
                _rebuild_scene_for_text(target)

            notes.append(f"Updated slide #{patch.number}.")
            notes.extend(stage_notes)

    if intent.replace_slides is not None or intent.patch_slides:
        # Keep explicit scenes from patches; only fill missing ones
        lecture.slides = materialize_slides(
            slides,
            subject=normalize_subject(getattr(lecture, "subject", None)),
        )
        flag_modified(lecture, "slides")

    return notes


async def process_lecture_edit(
    lecture: Lecture,
    prompt: str,
    user: User,
    db: AsyncSession,
    *,
    draft_title: str | None = None,
    draft_slides: list[Any] | None = None,
    current_slide: int | None = None,
) -> LectureEditResponse:
    if lecture.owner_id != user.id:
        raise HTTPException(status_code=403, detail="Only the owner can edit this lecture")

    text = (prompt or "").strip()
    if len(text) < 3:
        raise HTTPException(status_code=400, detail="Prompt is too short")

    api_key = _openai_api_key()
    if not api_key:
        raise ValueError("OPENAI_API_KEY is not configured.")

    # Prefer unsaved editor draft so multi-slide stage edits are visible to the model.
    if draft_title is not None and draft_title.strip():
        lecture.title = draft_title.strip()
    if draft_slides is not None:
        lecture.slides = materialize_slides(
            list(draft_slides),
            subject=normalize_subject(getattr(lecture, "subject", None)),
        )
        flag_modified(lecture, "slides")

    subject = normalize_subject(getattr(lecture, "subject", None))
    guidance = SUBJECT_GUIDANCE.get(subject, SUBJECT_GUIDANCE["general"])
    slides = lecture.slides if isinstance(lecture.slides, list) else []
    slide_count = len(slides)
    active_slide = current_slide
    if active_slide is not None and slide_count > 0:
        active_slide = max(1, min(int(active_slide), slide_count))

    context = {
        "lecture_id": str(lecture.id),
        "title": lecture.title,
        "subject": subject,
        "current_slide_number": active_slide,
        "includes_unsaved_draft": draft_slides is not None or draft_title is not None,
        "slides": [_strip_slide(s if isinstance(s, dict) else {}) for s in slides],
        "note": (
            "Each slide has text fields AND a stage with objects (see stage.objects id/label/body). "
            "To CHANGE an existing object use stage.update_objects. "
            "To DELETE use stage.remove_objects. "
            "For programming samples use stage.add_objects with kind=code and FULL source in body "
            "(never kind=text for code). "
            "stage.boxes only changes slide-in motion of existing boxes. "
            "If includes_unsaved_draft is true, this snapshot already includes the educator's "
            "unsaved stage edits — build on them, do not revert them."
        ),
    }

    llm = build_chat_model(temperature=0.3, model=_assistant_model(), api_key=api_key)
    structured = llm.with_structured_output(LectureEditIntent, method="function_calling")

    system = (
        SYSTEM_PROMPT
        + f"\n\nSubject focus for this lecture ({subject}):\n{guidance}"
    )
    intent: LectureEditIntent = await structured.ainvoke(
        [
            SystemMessage(content=system),
            HumanMessage(
                content=(
                    f"Current lecture (includes stage/scene motion):\n"
                    f"{json.dumps(context, indent=2)}\n\n"
                    f"Educator request:\n{text}"
                )
            ),
        ]
    )

    if intent.no_action and not intent.title and not intent.patch_slides and not intent.replace_slides:
        # Still persist draft if one was provided so later AI calls stay in sync.
        if draft_slides is not None or (draft_title is not None and draft_title.strip()):
            db.add(lecture)
            await db.commit()
            await db.refresh(lecture)
            from app.services.lecture_services import to_response

            return LectureEditResponse(
                message=intent.message or "No changes requested. Saved your current draft so it stays in sync.",
                lecture=to_response(lecture, viewer=user),
            )
        return LectureEditResponse(
            message=intent.message or "No changes requested.",
            lecture=None,
        )

    notes = _apply_intent(lecture, intent)
    db.add(lecture)
    await db.commit()
    await db.refresh(lecture)

    message = (intent.message or "").strip() or "Lecture updated."
    if notes:
        logger.info(
            "lecture_edit lecture_id=%s user_id=%s details=%s",
            lecture.id,
            user.id,
            notes,
        )

    from app.services.lecture_services import to_response

    return LectureEditResponse(
        message=message,
        lecture=to_response(lecture, viewer=user),
        details=notes,
    )
