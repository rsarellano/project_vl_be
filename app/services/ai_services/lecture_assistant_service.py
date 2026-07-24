"""AI edit assistant for existing lectures — NL prompt → allowlisted slide + stage updates."""

from __future__ import annotations

import json
import os
from typing import Any, Literal, Optional

from fastapi import HTTPException
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.models.lecture_models.Lecture import Lecture
from app.models.user_models.User import User
from app.schemas.lecture_schemas import LectureEditRequest, LectureEditResponse
from app.services.lecture_scene import (
    add_arrow_to_scene,
    add_text_object_to_scene,
    apply_boxes_slide_direction,
    create_basic_boxes_scene,
    create_trains_scene,
    materialize_slides,
)
from app.services.lecture_subjects import SUBJECT_GUIDANCE, normalize_subject


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

    kind: Literal["arrow", "text"] = Field(
        description="arrow = visible arrow shape; text = freeform text box"
    )
    direction: Optional[DirectionWord] = Field(
        default="down",
        description="For kind=arrow only: which way the arrow points (down/up/left/right)",
    )
    body: Optional[str] = Field(
        default=None, description="For kind=text: the text content"
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
    add_objects: list[AddStageObject] = Field(
        default_factory=list,
        description=(
            "Add visible graphics onto the stage. "
            "Use for 'add a downward arrow', 'put an arrow below the topic box', 'add text on stage'."
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


class SlideDraft(BaseModel):
    number: int = 1
    title: str = ""
    equation: str = ""
    narration: str = ""
    explanation: str = ""
    visual_type: str = "equation"


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
- "add a downward arrow on the stage" / "put an arrow below the topic box"
- "on page 1, make the boxes slide to the right"
- "make train A go east and faster"
- "shorten the narration on slide 1"

CRITICAL distinction:
- "add an arrow" / "draw an arrow" / "put a downward arrow on the stage" → stage.add_objects with kind="arrow"
  (this creates a VISIBLE arrow graphic). Do NOT use stage.boxes for that.
- "make it move down" / "slide downward" / "animate going down" → stage.boxes.direction="down"
  (this only changes entrance animation of existing boxes).

You may:
1. Rename the lecture (title)
2. Patch slide TEXT: title, equation, narration, explanation, visual_type
3. Patch STAGE via patch_slides[].stage:
   - add_objects: [{kind:"arrow", direction:"down", below_object_id:"box_title"}] etc.
   - add_objects: [{kind:"text", body:"..."}]
   - trains: length_km, speed_a/b, direction_a/b, move_a/move_b
   - boxes: direction left|right|up|down — ONLY for motion of existing boxes
   - use_trains_scene / use_boxes_scene to switch scene type
4. replace_slides only for heavy rebuilds
5. no_action=true if they only ask a question

Placement tips for arrows:
- "below the topic / title box" → below_object_id="box_title" (or matching object id from stage.objects)
- "below the equation" → below_object_id="box_equation"
- "downward arrow" → kind=arrow, direction=down
- If they say "all slides", emit one patch_slides entry per slide number with the same add_objects

Rules:
- Stay on the lecture's subject.
- Prefer patch_slides for small edits.
- When the educator says "this slide" / "the current slide" / "here", use current_slide_number from context.
- visual_type: equation, graph, triangle, circle, trains.
- In message, say clearly whether you ADDED an object or changed MOTION.
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
            "hint": "Edit with stage.trains or trains (direction east/west, speeds).",
        }
    if stype == "basic_boxes":
        return {
            "type": "basic_boxes",
            "objects": [
                {
                    "id": o.get("id"),
                    "label": o.get("label"),
                    "role": o.get("role"),
                    "x": o.get("x"),
                    "y": o.get("y"),
                }
                for o in (scene.get("objects") or [])
                if isinstance(o, dict)
            ],
            "motionCues": scene.get("motionCues") or [],
            "hint": (
                "To ADD a visible arrow use stage.add_objects "
                "[{kind:'arrow', direction:'down', below_object_id:'box_title'}]. "
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


def _apply_add_objects(slide: dict[str, Any], items: list[AddStageObject]) -> list[str]:
    notes: list[str] = []
    scene = slide.get("scene") if isinstance(slide.get("scene"), dict) else None
    if not scene:
        scene = create_basic_boxes_scene(slide)
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
        elif item.kind == "text":
            scene = add_text_object_to_scene(
                scene,
                body=item.body or "New text",
                x=item.x,
                y=item.y,
            )
            notes.append("Added a text object on the stage.")

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
        lecture.slides = materialize_slides(slides)
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
        lecture.slides = materialize_slides(list(draft_slides))
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
            "Each slide has text fields AND a stage with objects. "
            "To ADD a visible arrow/text use stage.add_objects. "
            "stage.boxes only changes slide-in motion of existing boxes. "
            "If includes_unsaved_draft is true, this snapshot already includes the educator's "
            "unsaved stage edits — build on them, do not revert them."
        ),
    }

    llm = ChatOpenAI(temperature=0.3, model=_assistant_model(), api_key=api_key)
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

    message = (intent.message or "").strip()
    if notes:
        message = (message + "\n\n" if message else "") + "\n".join(notes)

    from app.services.lecture_services import to_response

    return LectureEditResponse(
        message=message or "Lecture updated.",
        lecture=to_response(lecture, viewer=user),
    )
