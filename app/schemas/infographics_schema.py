"""Shared visual schemas: legacy ``InfographicBlueprint`` + ``DrawingStage``.

``DrawingStage`` is the AI-generated diagram contract. The model is locked to a
**flag-driven** shape: it never picks coordinates, sizes, or geometry. The
frontend (`boxCreation.tsx`, `textCreation.tsx`, `lineCreation.tsx`) computes
every spatial value from item order and role. The model only emits:

- ``BoxCreation: true`` items with ``id`` + ``text``
- ``TextCreation: true`` items with ``id`` + ``role`` + ``text``
- ``connections`` with ``LineCreation: true`` + ``from`` + ``to``

``InfographicBlueprint`` remains for older rows/API fields (grid + stickers);
the current answer pipeline leaves ``blueprint`` null and only fills ``stage``.

File layout (search for these section headers)
----------------------------------------------
1. **Module internals** — small helpers used by validators.
2. **Legacy InfographicBlueprint** — grid entities, pacing, blueprint root.
3. **DrawingStage primitives** — animation, base object fields.
4. **Flag-driven objects** — ``BoxCreation`` / ``TextCreation`` items.
5. **Object union** — ``DrawingStageObject`` alias.
6. **Connections** — flag-driven connectors between two box ids.
7. **Root stage** — ``DrawingStage`` document.
"""

from typing import Any, Literal, Optional, Union

from pydantic import BaseModel, Field, model_validator

from app.services.ai_services.drawing_stage_objects import patch_llm_objects_before_validation

# =============================================================================
# 1. Module internals — defaults + helpers for validators
# =============================================================================

_MIN_ENTITY_DIM = 0.25
_DEFAULT_STAGE_WIDTH = 1400.0
_DEFAULT_STAGE_HEIGHT = 1250.0
_DEFAULT_STAGE_BACKGROUND = "#ffffff"


def _id_missing(v: object) -> bool:
    """True when an object ``id`` is absent before we synthesize one."""
    return v is None or v == ""


# =============================================================================
# 2. Legacy InfographicBlueprint (grid + entities + pacing)
# =============================================================================


class Keyframe(BaseModel):
    time: float = Field(..., ge=0, le=100)
    x: float
    y: float


class Entity(BaseModel):
    id: str
    label: str
    width: float = Field(..., gt=0)
    height: float = Field(..., gt=0)
    color: str = Field(..., min_length=1)
    shape: Optional[Literal["box", "line", "arrow"]] = "box"
    keyframes: list[Keyframe] = Field(..., min_length=1)


class CanvasConfig(BaseModel):
    minX: float
    maxX: float
    minY: float
    maxY: float


class PacingMarker(BaseModel):
    percent: float = Field(..., ge=0, le=100)
    speedMultiplier: float = Field(..., gt=0)


class InfographicBlueprint(BaseModel):
    config: CanvasConfig
    entities: list[Entity] = Field(..., min_length=1)
    explanation: str = Field(..., min_length=1)
    pacing: list[PacingMarker] = Field(..., min_length=1)


# =============================================================================
# 3. DrawingStage primitives (shared by all flag-driven items)
# =============================================================================


class DrawingStageBaseObject(BaseModel):
    """Every item only has an ``id``. All visual decisions live in the frontend."""

    id: str


# =============================================================================
# 4. Flag-driven objects (frontend computes ALL spatial + visual info)
# =============================================================================


class MathDerivationTransition(BaseModel):
    type: Literal["arrow"] = "arrow"
    direction: Literal["down", "right"] = "down"


class MathDerivationFrame(BaseModel):
    id: str = Field(..., min_length=1)
    note: Optional[str] = None
    expression: Optional[str] = None
    transition: Optional[MathDerivationTransition] = None


class MathDerivationBeatNote(BaseModel):
    type: Literal["note"] = "note"
    text: str = Field(..., min_length=1)


class MathDerivationBeatExpression(BaseModel):
    type: Literal["expression"] = "expression"
    text: str = Field(..., min_length=1)
    id: Optional[str] = None


class MathDerivationBeatArrow(BaseModel):
    type: Literal["arrow"] = "arrow"
    direction: Literal["down", "right"] = "down"


class MathDerivationBeatExplain(BaseModel):
    type: Literal["explain"] = "explain"
    text: str = Field(..., min_length=1)


class MathDerivationBeatMotion(BaseModel):
    type: Literal["motion"] = "motion"
    text: str = Field(..., min_length=1)
    id: Optional[str] = None
    term: str = Field(..., min_length=1)
    motion: Literal["slide_right", "slide_left", "highlight", "fade_in"] = "slide_right"


class MathDerivationMotionStep(BaseModel):
    label: Optional[str] = None
    expression: str = Field(..., min_length=1)
    term: Optional[str] = None
    motion: Literal["slide_right", "slide_left", "highlight", "fade_in"] = "highlight"


class MathDerivationBeatMotionStage(BaseModel):
    type: Literal["motion_stage"] = "motion_stage"
    id: Optional[str] = None
    steps: list[MathDerivationMotionStep] = Field(default_factory=list)
    # Animated yellow box (katex-simulator morph). When omitted, the frontend
    # derives from/to from the surrounding ``expression`` beats.
    from_: Optional[str] = Field(default=None, alias="from")
    to: Optional[str] = None
    frames: Optional[list[str]] = None
    operation: Optional[str] = None

    model_config = {"populate_by_name": True}


MathDerivationBeat = Union[
    MathDerivationBeatNote,
    MathDerivationBeatExpression,
    MathDerivationBeatArrow,
    MathDerivationBeatExplain,
    MathDerivationBeatMotion,
    MathDerivationBeatMotionStage,
]


class MathStepDerivation(BaseModel):
    """Layer 2: how the previous step box became this step (beat script)."""

    fromStepId: Optional[str] = None
    beats: list[MathDerivationBeat] = Field(default_factory=list)
    frames: list[MathDerivationFrame] = Field(default_factory=list)


class DrawingStageBoxCreationObject(DrawingStageBaseObject):
    """Step card. AI supplies ``BoxCreation: true`` + ``text`` (+ optional ``derivation``).

    The frontend (``boxCreation.tsx``) owns position, size, radius, fill,
    stroke, padding, fontSize, lineHeight, animation timing — everything
    visual. The model is not allowed to set any of those fields.

    For math layout, emit ``derivation.beats`` on each step that changes the math
    (layer-2 "How we got here" panel).

    In ``code-map`` layout, optional ``linkedPortion`` ties the box to a
    ``CodeDisplay.portions[]`` entry; the frontend positions it beside that
    highlighted code region.
    """

    BoxCreation: Literal[True]
    text: Optional[Union[str, list[str]]] = None
    linkedPortion: Optional[str] = None
    derivation: Optional[MathStepDerivation] = None


class CodePortion(BaseModel):
    """Semantic grouping of code lines for highlight + explanation pairing."""

    id: str = Field(..., min_length=1)
    lines: list[int] = Field(..., min_length=2, max_length=2)
    label: Optional[str] = None

    @model_validator(mode="after")
    def validate_line_range(self) -> "CodePortion":
        start, end = self.lines[0], self.lines[1]
        if start < 0 or end < start:
            raise ValueError("portion lines must be [start, end] with 0 <= start <= end")
        return self


class DrawingStageCodeDisplayObject(DrawingStageBaseObject):
    """Source code panel for ``code-map`` layout.

    AI supplies ``CodeDisplay: true``, ``text`` (one string per code line),
    and ``portions`` (line-index groupings). The frontend computes highlight
    rects and positions linked explanation boxes.
    """

    CodeDisplay: Literal[True]
    language: Optional[str] = "javascript"
    text: Optional[Union[str, list[str]]] = None
    portions: list[CodePortion] = Field(default_factory=list)


class DrawingStageTextCreationObject(DrawingStageBaseObject):
    """Role-driven label. AI supplies ``TextCreation: true`` + ``role`` + ``text``.

    ``role`` must be one of ``"code-title"`` / ``"objective"`` / ``"console"``
    and selects a preset in ``textCreation.tsx``. The frontend owns position,
    fontSize, lineHeight, color, animation timing, etc.

    The final answer / result of the question MUST live in the last
    ``BoxCreation`` step, not as a free-floating ``TextCreation``. That is
    enforced by the prompt and by the schema only accepting these three roles.
    """

    TextCreation: Literal[True]
    role: Literal["code-title", "objective", "console"]
    text: Optional[Union[str, list[str]]] = None


# =============================================================================
# 5. Object union — flag-driven only (typed shapes are intentionally rejected)
# =============================================================================


DrawingStageObject = Union[
    DrawingStageBoxCreationObject,
    DrawingStageTextCreationObject,
    DrawingStageCodeDisplayObject,
]


# =============================================================================
# 6. Connections — flag-driven connectors (FE resolves geometry)
# =============================================================================


class DrawingStageConnection(BaseModel):
    """Flag-driven connector between two ``BoxCreation`` ids. FE resolves geometry."""

    id: Optional[Union[str, int]] = None
    LineCreation: Literal[True]
    from_: Union[str, int] = Field(..., alias="from")
    to: Union[str, int]

    model_config = {"populate_by_name": True}


# =============================================================================
# 7. Root ``DrawingStage`` document
# =============================================================================


class DrawingStage(BaseModel):
    """Flag-driven drawing stage. The FE owns every coordinate.

    Fixed canvas: ``width=1400``, ``height=1250``, ``background="#ffffff"``.
    ``layoutMode`` selects the renderer:

    - ``code-map`` — code panel + portion highlights (coding domain)
    - ``math`` / ``science`` / ``trunk`` — horizontal step row (non-code domains)
    """

    width: float = Field(_DEFAULT_STAGE_WIDTH, gt=0)
    height: float = Field(_DEFAULT_STAGE_HEIGHT, gt=0)
    background: Optional[str] = _DEFAULT_STAGE_BACKGROUND
    layoutMode: Optional[Literal["trunk", "code-map", "math", "science"]] = None
    objects: list[DrawingStageObject] = Field(..., min_length=1)
    connections: list[DrawingStageConnection] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def patch_objects_llm_omissions(cls, data: Any) -> Any:
        """Synthesize stable ids on flag-driven items when the model omits them."""
        if not isinstance(data, dict):
            return data
        out = dict(data)
        if out.get("width") in (None, "", 0):
            out["width"] = _DEFAULT_STAGE_WIDTH
        if out.get("height") in (None, "", 0):
            out["height"] = _DEFAULT_STAGE_HEIGHT
        if out.get("background") in (None, ""):
            out["background"] = _DEFAULT_STAGE_BACKGROUND

        raw_objects = out.get("objects")
        if not isinstance(raw_objects, list):
            return out
        sanitized = patch_llm_objects_before_validation(raw_objects)
        patched: list[Any] = []
        for idx, item in enumerate(sanitized):
            if not isinstance(item, dict):
                patched.append(item)
                continue
            o = dict(item)
            if o.get("BoxCreation") is True and _id_missing(o.get("id")):
                o["id"] = f"box-{idx}"
            elif o.get("TextCreation") is True and _id_missing(o.get("id")):
                o["id"] = f"text-{idx}"
            elif o.get("CodeDisplay") is True and _id_missing(o.get("id")):
                o["id"] = "source"
            patched.append(o)
        out["objects"] = patched
        return out

    @model_validator(mode="after")
    def validate_code_map_contract(self) -> "DrawingStage":
        """Ensure code-map payloads have one CodeDisplay and valid portion links."""
        code_displays = [
            obj for obj in self.objects if isinstance(obj, DrawingStageCodeDisplayObject)
        ]
        if not code_displays:
            return self

        if len(code_displays) > 1:
            raise ValueError("code-map stage must contain exactly one CodeDisplay item")

        code_display = code_displays[0]
        line_count = 0
        if isinstance(code_display.text, list):
            line_count = len(code_display.text)
        elif isinstance(code_display.text, str) and code_display.text.strip():
            line_count = 1

        portion_ids: set[str] = set()
        for portion in code_display.portions:
            if portion.id in portion_ids:
                raise ValueError(f"duplicate portion id: {portion.id}")
            portion_ids.add(portion.id)
            start, end = portion.lines
            if line_count and end >= line_count:
                raise ValueError(
                    f"portion {portion.id} lines [{start}, {end}] exceed code line count {line_count}"
                )

        linked_boxes = [
            obj
            for obj in self.objects
            if isinstance(obj, DrawingStageBoxCreationObject) and obj.linkedPortion
        ]
        for box in linked_boxes:
            if box.linkedPortion not in portion_ids:
                raise ValueError(
                    f"BoxCreation {box.id} linkedPortion {box.linkedPortion!r} "
                    "does not match any CodeDisplay portion id"
                )

        if self.layoutMode not in (None, "code-map"):
            raise ValueError("layoutMode must be code-map when CodeDisplay is present")

        return self
