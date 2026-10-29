import os
import uuid
import json
from datetime import datetime, timezone
from typing import Literal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from fastapi import HTTPException
from sqlalchemy.orm.attributes import flag_modified
from langchain_core.messages import HumanMessage, SystemMessage

from app.services.ai_services.llm_client import build_chat_model
from pydantic import BaseModel, Field

from app.models.user_models.User import User
from app.models.classroom_models.Assignment import Assignment
from app.models.classroom_models.ClassroomMembership import ClassroomMembership
from app.services.subscription_services.tier_limits import (
    get_limit_value,
    get_remaining,
    check_limit,
)
from app.services.classroom_services import (
    get_classroom_by_id,
    clamp_max_students,
    _normalize_id_list,
    _get_user_tier,
    _settings_dict,
    _count_educator_classrooms,
    create_classroom,
)
from app.schemas.classroom_schemas.assistant_schemas import (
    AssistantResponse,
    DashboardAssistantResponse,
    DashboardAssistantIntent,
    CreatedClassroomSummary,
)
from app.schemas.classroom_schemas.classroom_schemas import ClassroomCreate
from app.services.ai_services.classroom_prompt_features import (
    asks_for_assignment_content,
    asks_to_create_classroom,
    keep_assignment_edits,
    mentions_unsupported_activity,
    prompt_feature_rules,
    sanitize_questions,
    with_feature_guide,
)

SYSTEM_PROMPT = """You are an AI Classroom Assistant. You help educators manage their classrooms using natural language prompts.
You have access to the current classroom details, settings, student roster, and active assignments.

When the educator says "lecture", "exam", "test", or "quiz", map that to an assignment (test) in this classroom.

Based on the educator's prompt, you must execute one or more actions to fulfill their request:
1. "create_assignment": Create a new assignment. Fields: title, prompt, questions (list of question dicts), settings (dict of custom criteria).
2. "update_assignment": Modify an existing assignment (e.g. rename, edit questions, add questions, edit settings). Requires assignment_id.
3. "delete_assignment": Delete an assignment. Requires delete_assignment_id.
4. "update_classroom": Change classroom name, description, grading system, max_students, test_access ("all_members" | "allowlist"),
   test_allowed_student_ids (list of student UUID strings), auto_enroll_newcomers (bool).
5. "set_test_access": Set who can take a test.
   Fields in test_access_data:
   - scope: "classroom" | "assignment"
   - assignment_id: required when scope is assignment
   - test_access: "all_members" | "allowlist"
   - allowed_student_ids: optional list of student UUID strings (for allowlist)
   - auto_enroll_newcomers: optional bool (classroom scope only)
6. "add_students_to_test": Add students to an allowlist (one-shot).
   Fields in test_access_data:
   - scope: "classroom" | "assignment"
   - assignment_id: required when scope is assignment
   - add_mode: "all_members" | "all_newcomers" | "students"
     * all_members = every currently enrolled student
     * all_newcomers = students not already on the allowlist (same as all not-yet-listed members)
     * students = use student_ids
   - student_ids: list of UUID strings when add_mode is "students"
   Also switches test_access to "allowlist" for that scope.
7. "no_action": Use this if the user is just asking a question or if no changes are required.

Rules for questions inside create_assignment / update_assignment:
- Each question must have:
  * "id": string (always generate a fresh uuid string, e.g. "a1b2c3d4-...")
  * "number": integer (1, 2, ...)
  * "prompt": string (the question text)
  * "question_type": "short_answer" or "multiple_choice" only
  * "choices": list of strings or null
  * "correct_answer": string (the correct answer key)
  * "topic": string or null
  * "difficulty": string or null
- Use plain text math notation (x^2, sqrt(x), fractions like 3/4) — no LaTeX delimiters.
- Never use any other question_type.

Always resolve student names/emails from the roster to their id strings.
Always explain clearly in the "message" field what actions you have chosen to perform, so the educator knows what changed.

""" + prompt_feature_rules("classroom")

def _openai_api_key() -> str | None:
    return os.getenv("OPENAI_API_KEY")

def _assistant_model() -> str:
    return os.getenv("OPENAI_ANSWER_MODEL", "gpt-4o-mini")


def _merge_allowlist(existing: list[str], to_add: list[str]) -> list[str]:
    seen = set(existing)
    out = list(existing)
    for sid in to_add:
        if sid and sid not in seen:
            seen.add(sid)
            out.append(sid)
    return out


def _limit_classroom_actions(
    actions: list,
    prompt: str,
    unsupported_request: bool,
) -> tuple[list, bool]:
    """Drop assignment edits the product cannot store, and flag the request."""
    unsupported = bool(unsupported_request) or mentions_unsupported_activity(prompt)
    allow_assignments = keep_assignment_edits(prompt)
    kept = []
    for action in actions:
        if action.action_type in ("create_assignment", "update_assignment") and not allow_assignments:
            unsupported = True
            continue
        if action.action_type == "create_assignment" and action.create_assignment_data:
            questions, dropped = sanitize_questions(action.create_assignment_data.get("questions"))
            if dropped:
                unsupported = True
            if not questions:
                continue
            action.create_assignment_data["questions"] = questions
        elif action.action_type == "update_assignment" and action.update_assignment_data:
            data = action.update_assignment_data
            if data.get("questions") is not None:
                questions, dropped = sanitize_questions(data.get("questions"))
                if dropped:
                    unsupported = True
                if questions:
                    data["questions"] = questions
                else:
                    data.pop("questions", None)
                    other = [
                        key
                        for key, value in data.items()
                        if key != "assignment_id" and value not in (None, "", [], {})
                    ]
                    if not other:
                        continue
        kept.append(action)
    return kept, unsupported


async def process_classroom_command(
    classroom_id: uuid.UUID,
    prompt: str,
    user: User,
    db: AsyncSession
) -> AssistantResponse:
    if user.role != "educator":
        raise HTTPException(status_code=403, detail="Only educators can use the Classroom AI Assistant")

    classroom = await get_classroom_by_id(classroom_id, user, db)
    tier = await _get_user_tier(user.id, db)

    # Gather active assignments
    assignments_res = await db.execute(
        select(Assignment).where(Assignment.classroom_id == classroom.id)
    )
    assignments = list(assignments_res.scalars().all())

    assignments_context = []
    for a in assignments:
        stage = a.stage_data if isinstance(a.stage_data, dict) else {}
        assignments_context.append({
            "id": str(a.id),
            "prompt": a.prompt,
            "title": stage.get("title") if isinstance(stage, dict) else "Assignment",
            "questions_count": len(stage.get("questions") or []) if isinstance(stage, dict) else 0,
            "questions": stage.get("questions") if isinstance(stage, dict) else [],
            "settings": stage.get("settings") if isinstance(stage, dict) else {},
        })

    students_res = await db.execute(
        select(User)
        .join(ClassroomMembership, User.id == ClassroomMembership.student_id)
        .where(ClassroomMembership.classroom_id == classroom.id)
    )
    students = list(students_res.scalars().all())
    roster = [{"id": str(s.id), "email": s.email} for s in students]
    roster_ids = [s["id"] for s in roster]

    classroom_context = {
        "classroom_id": str(classroom.id),
        "name": classroom.name,
        "settings": classroom.settings or {},
        "students": roster,
        "assignments": assignments_context,
        "plan_max_students": get_limit_value(tier, "max_students_per_classroom"),
    }

    api_key = _openai_api_key()
    if not api_key:
        raise ValueError("OPENAI_API_KEY is not configured.")

    llm = build_chat_model(temperature=0.3, model=_assistant_model(), api_key=api_key)
    structured = llm.with_structured_output(AssistantResponse, method="function_calling")

    human_content = f"Current Classroom Context:\n{json.dumps(classroom_context, indent=2)}\n\nEducator Prompt:\n{prompt}"

    response: AssistantResponse = await structured.ainvoke([
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=human_content)
    ])

    response.actions, response.unsupported_request = _limit_classroom_actions(
        response.actions,
        prompt,
        response.unsupported_request,
    )

    # Apply database changes based on AI structured actions
    for action in response.actions:
        if action.action_type == "update_classroom" and action.update_classroom_data:
            data = action.update_classroom_data
            if "name" in data and data["name"]:
                classroom.name = data["name"]
            settings = _settings_dict(classroom)
            if "description" in data:
                settings["description"] = data["description"]
            if "grading_system" in data:
                settings["grading_system"] = data["grading_system"]
            if "max_students" in data and data["max_students"] is not None:
                try:
                    settings["max_students"] = clamp_max_students(int(data["max_students"]), tier)
                except (TypeError, ValueError):
                    pass
            if data.get("test_access") in ("all_members", "allowlist"):
                settings["test_access"] = data["test_access"]
            if "test_allowed_student_ids" in data and data["test_allowed_student_ids"] is not None:
                settings["test_allowed_student_ids"] = _normalize_id_list(
                    data["test_allowed_student_ids"]
                )
            if "auto_enroll_newcomers" in data and data["auto_enroll_newcomers"] is not None:
                settings["auto_enroll_newcomers"] = bool(data["auto_enroll_newcomers"])
            classroom.settings = settings
            flag_modified(classroom, "settings")
            db.add(classroom)

        elif action.action_type == "set_test_access" and action.test_access_data:
            data = action.test_access_data
            scope = data.get("scope") or "classroom"
            mode = data.get("test_access") or "all_members"
            if mode not in ("all_members", "allowlist"):
                mode = "all_members"
            ids = _normalize_id_list(data.get("allowed_student_ids"))

            if scope == "assignment" and data.get("assignment_id"):
                try:
                    asg_id = uuid.UUID(str(data["assignment_id"]))
                except ValueError:
                    asg_id = None
                assignment = next((a for a in assignments if a.id == asg_id), None)
                if assignment:
                    stage = dict(assignment.stage_data or {}) if isinstance(assignment.stage_data, dict) else {}
                    asg_settings = dict(stage.get("settings") or {}) if isinstance(stage.get("settings"), dict) else {}
                    asg_settings["test_access"] = mode
                    if mode == "allowlist":
                        asg_settings["allowed_student_ids"] = ids
                    stage["settings"] = asg_settings
                    assignment.stage_data = stage
                    flag_modified(assignment, "stage_data")
                    db.add(assignment)
            else:
                settings = _settings_dict(classroom)
                settings["test_access"] = mode
                if mode == "allowlist":
                    settings["test_allowed_student_ids"] = ids
                if "auto_enroll_newcomers" in data and data["auto_enroll_newcomers"] is not None:
                    settings["auto_enroll_newcomers"] = bool(data["auto_enroll_newcomers"])
                classroom.settings = settings
                flag_modified(classroom, "settings")
                db.add(classroom)

        elif action.action_type == "add_students_to_test" and action.test_access_data:
            data = action.test_access_data
            scope = data.get("scope") or "classroom"
            add_mode = data.get("add_mode") or "all_members"
            if add_mode == "students":
                to_add = _normalize_id_list(data.get("student_ids"))
            elif add_mode in ("all_members", "all_newcomers"):
                to_add = list(roster_ids)
            else:
                to_add = list(roster_ids)

            if scope == "assignment" and data.get("assignment_id"):
                try:
                    asg_id = uuid.UUID(str(data["assignment_id"]))
                except ValueError:
                    asg_id = None
                assignment = next((a for a in assignments if a.id == asg_id), None)
                if assignment:
                    stage = dict(assignment.stage_data or {}) if isinstance(assignment.stage_data, dict) else {}
                    asg_settings = dict(stage.get("settings") or {}) if isinstance(stage.get("settings"), dict) else {}
                    existing = _normalize_id_list(asg_settings.get("allowed_student_ids"))
                    if add_mode == "all_newcomers":
                        to_add = [sid for sid in roster_ids if sid not in existing]
                    asg_settings["test_access"] = "allowlist"
                    asg_settings["allowed_student_ids"] = _merge_allowlist(existing, to_add)
                    stage["settings"] = asg_settings
                    assignment.stage_data = stage
                    flag_modified(assignment, "stage_data")
                    db.add(assignment)
            else:
                settings = _settings_dict(classroom)
                existing = _normalize_id_list(settings.get("test_allowed_student_ids"))
                if add_mode == "all_newcomers":
                    to_add = [sid for sid in roster_ids if sid not in existing]
                settings["test_access"] = "allowlist"
                settings["test_allowed_student_ids"] = _merge_allowlist(existing, to_add)
                classroom.settings = settings
                flag_modified(classroom, "settings")
                db.add(classroom)

        elif action.action_type == "delete_assignment" and action.delete_assignment_id:
            try:
                asg_id = uuid.UUID(action.delete_assignment_id)
                stmt = select(Assignment).where(
                    Assignment.id == asg_id,
                    Assignment.classroom_id == classroom.id
                )
                res = await db.execute(stmt)
                assignment = res.scalars().first()
                if assignment:
                    await db.delete(assignment)
            except ValueError:
                pass

        elif action.action_type == "create_assignment" and action.create_assignment_data:
            data = action.create_assignment_data
            questions = []
            raw_questions, _dropped = sanitize_questions(data.get("questions"))
            if not raw_questions:
                continue
            for idx, q in enumerate(raw_questions, start=1):
                questions.append({
                    "id": q.get("id") or str(uuid.uuid4()),
                    "number": idx,
                    "prompt": q.get("prompt"),
                    "question_type": q.get("question_type") or "short_answer",
                    "choices": q.get("choices"),
                    "correct_answer": q.get("correct_answer"),
                    "topic": q.get("topic"),
                    "difficulty": q.get("difficulty")
                })
            
            stage_data = {
                "type": "exam",
                "title": data.get("title") or "Generated Exam",
                "questions": questions,
                "generated_at": datetime.now(timezone.utc).isoformat()
            }
            if "settings" in data:
                stage_data["settings"] = data["settings"]

            new_assignment = Assignment(
                classroom_id=classroom.id,
                prompt=data.get("prompt") or prompt,
                stage_data=stage_data
            )
            db.add(new_assignment)

        elif action.action_type == "update_assignment" and action.update_assignment_data:
            data = action.update_assignment_data
            if "assignment_id" in data:
                try:
                    asg_id = uuid.UUID(data["assignment_id"])
                    stmt = select(Assignment).where(
                        Assignment.id == asg_id,
                        Assignment.classroom_id == classroom.id
                    )
                    res = await db.execute(stmt)
                    assignment = res.scalars().first()
                    if assignment:
                        if "prompt" in data and data["prompt"]:
                            assignment.prompt = data["prompt"]
                        
                        stage_data = dict(assignment.stage_data or {})
                        if "title" in data and data["title"]:
                            stage_data["title"] = data["title"]
                        if "questions" in data and data["questions"] is not None:
                            questions = []
                            raw_questions, _dropped = sanitize_questions(data["questions"])
                            for idx, q in enumerate(raw_questions, start=1):
                                questions.append({
                                    "id": q.get("id") or str(uuid.uuid4()),
                                    "number": idx,
                                    "prompt": q.get("prompt"),
                                    "question_type": q.get("question_type") or "short_answer",
                                    "choices": q.get("choices"),
                                    "correct_answer": q.get("correct_answer"),
                                    "topic": q.get("topic"),
                                    "difficulty": q.get("difficulty")
                                })
                            stage_data["questions"] = questions
                        if "settings" in data and data["settings"] is not None:
                            stage_data["settings"] = data["settings"]
                        
                        assignment.stage_data = stage_data
                        flag_modified(assignment, "stage_data")
                        db.add(assignment)
                except ValueError:
                    pass

    await db.commit()
    # Ensure current settings are updated in response
    await db.refresh(classroom)
    response.classroom_settings = classroom.settings or {}
    if response.unsupported_request:
        applied = any(action.action_type != "no_action" for action in response.actions)
        response.message = with_feature_guide(
            response.message if applied else "",
            "classroom",
        )
    return response


DASHBOARD_SYSTEM_PROMPT = """You are an AI Classroom Assistant for the classrooms dashboard.
Educators ask you to create classrooms with optional settings (seat limits, description, grading, test access).

You may ONLY choose these actions:
1. "create_classroom": Create a new classroom.
   Fields in create_classroom_data:
   - name (required string)
   - max_students (optional int)
   - description (optional string)
   - grading_system (optional string)
   - test_access: "all_members" | "allowlist" (optional)
   - auto_enroll_newcomers (optional bool)
2. "no_action": Use when the user is only asking a question, or when creating is not allowed.

Plan limits (authoritative — also enforced by the server):
- You will receive the educator's tier, current classroom count, classroom cap, remaining slots, and max students per classroom.
- If remaining classrooms is 0 (or they are at the classroom cap), do NOT create. Use "no_action" and clearly explain they must upgrade to create more.
- If they ask for more students than plan_max_students allows, still use create_classroom but set max_students to the plan max (or omit it), and warn in "message" that Free/their plan capped seats and Pro unlocks higher limits.
- If they ask for a valid create within limits, create it and confirm what was set.

Always explain clearly in "message" what you did (or why you could not).
Mention upgrade when a Free-tier limit blocks or reduces their request.
Quizzes, exams, and questions are not created here. If they ask for those, set unsupported_request to true, use "no_action", and tell them to open the classroom.

""" + prompt_feature_rules("create")


async def process_dashboard_command(
    prompt: str,
    user: User,
    db: AsyncSession,
) -> DashboardAssistantResponse:
    """Dashboard no longer creates classrooms via AI. Create first, then use /{id}/assistant."""
    _ = (prompt, db)
    if user.role != "educator":
        raise HTTPException(
            status_code=403,
            detail="Only educators can use the Classroom AI Assistant",
        )

    return DashboardAssistantResponse(
        message=(
            "Create a classroom first (name only), then open it. "
            "The Classroom Setup Assistant is available on that classroom page."
        ),
        actions=[],
        created_classrooms=[],
        upgrade_required=False,
        unsupported_request=False,
    )


class SceneHintDraft(BaseModel):
    """Semantic scene plan. The lecture scene registry owns all layout values."""

    archetype: Literal[
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
    ] = "basic_boxes"
    focus: str = ""
    concepts: list[str] = Field(default_factory=list)
    code_language: str | None = None
    variables: dict[str, str] = Field(default_factory=dict)
    motion: str | None = None
    emphasis: str | None = None


class CodePortionDraft(BaseModel):
    """One highlighted block of a coding sample + its explanation (AI Tutor style)."""

    id: str = ""
    label: str = ""
    start_line: int = 0
    end_line: int = 0
    short: str = ""
    detail: str = ""


class CheckpointChoiceDraft(BaseModel):
    id: str = "a"
    text: str = ""
    correct: bool = False


class CheckpointDraft(BaseModel):
    prompt: str = ""
    kind: Literal["multiple_choice", "numeric"] = "multiple_choice"
    choices: list[CheckpointChoiceDraft] = Field(default_factory=list)
    numericAnswer: str = ""
    explanation: str = ""


class SlideDraft(BaseModel):
    number: int
    title: str
    equation: str
    narration: str
    explanation: str
    visual_type: str = "equation"
    slide_role: str = "concept"
    callout: str = ""
    steps: list[str] = Field(default_factory=list)
    scene_hint: SceneHintDraft = Field(default_factory=SceneHintDraft)
    # Coding / AI Tutor parity — preferred over equation alone when present.
    code_lines: list[str] = Field(default_factory=list)
    code_portions: list[CodePortionDraft] = Field(default_factory=list)
    checkpoint: CheckpointDraft | None = None


class LectureDraft(BaseModel):
    title: str
    slides: list[SlideDraft]


async def generate_lecture_from_prompt(
    prompt: str,
    *,
    subject: str | None = None,
    topic: str | None = None,
    clarifications: list[dict] | None = None,
) -> dict:
    from app.services.lecture_subjects import SUBJECT_GUIDANCE, normalize_subject
    from app.services.lecture_pedagogy import (
        MATH_TOPIC_LABELS,
        resolve_lecture_pedagogy,
    )

    api_key = _openai_api_key()
    if not api_key:
        raise ValueError("OPENAI_API_KEY is not configured.")

    subject_key = normalize_subject(subject)
    guidance = SUBJECT_GUIDANCE.get(subject_key, SUBJECT_GUIDANCE["general"])
    pedagogy_block, topic_slug = resolve_lecture_pedagogy(
        subject=subject_key,
        prompt=prompt,
        topic=topic,
    )
    topic_note = ""
    if topic_slug:
        topic_note = (
            f"\nInferred/selected math topic pack: "
            f"{MATH_TOPIC_LABELS.get(topic_slug, topic_slug)} ({topic_slug}).\n"
        )

    coding_extra = ""
    if subject_key == "coding":
        coding_extra = """
## CODING SLIDE FIELDS (mandatory on concept / worked_example / practice / check)
10. equation — full runnable program as multiline plain text (no fences).
11. code_lines — optional mirror of equation (one source line per list entry).
12. scene_hint.archetype — always code_walkthrough unless Input→code→Output (then code_flow).
13. steps — portion-aware labels for stage boxes ("Setup — …"); never "Frame the hook".
"""

    interview_block = _format_clarifications(clarifications)

    llm = build_chat_model(temperature=0.55, model=_assistant_model(), api_key=api_key)
    structured = llm.with_structured_output(LectureDraft, method="function_calling")

    system_prompt = f"""You are an AI Lecture Builder for Project VL educators.
Your first draft must feel OVER-THE-TOP capable: rich teaching arc, concrete worked content,
and stage-ready pieces (callouts + short steps) so educators immediately see what the visual stage can do.

{pedagogy_block}

{guidance}
{topic_note}
Each slide MUST contain:
1. title — specific, classroom-ready (not generic "Introduction").
2. equation — formula / key expression / full code when coding; otherwise "".
   Prefer clean KaTeX for math (e.g. "s = v_{{0}} t + \\frac{{1}}{{2}} a t^{{2}}").
   NEVER wrap variables in \\text{{…}}. Do not use markdown $ delimiters.
   For coding: multiline source matching code_lines (no fences).
3. narration — detailed spoken script for the educator (3–6 sentences).
4. explanation — short on-screen teaching point (1–3 sentences).
5. visual_type — one of "equation", "graph", "triangle", "circle", "trains".
6. slide_role — one of hook, concept, worked_example, practice, check, summary.
7. callout — one punchy tip/warning for a stage callout box (not empty when possible).
8. steps — 2–3 ultra-short stage steps (≤12 words). Required for worked_example and practice.
   Coding exception: up to ~20 words; must name real code blocks.
9. scene_hint — a semantic, layout-free visual plan. Choose exactly one archetype:
   - Math: math_worked_example, math_graph, math_geometry
   - Coding: code_walkthrough, code_flow
   - Science: science_process, science_force_vector, relative_motion_trains
   - General: concept_comparison or basic_boxes
   Fill focus, up to four concepts, optional code_language, variables, motion, and emphasis
   only when useful. Never include coordinates, SVG, object IDs, styling, or arbitrary shapes.
10. checkpoint — REQUIRED when slide_role is "check". Leave null on other slides.
    prompt: a real subject question (algebra solve for math; concept MCQ otherwise).
    kind: "numeric" or "multiple_choice" for math; "multiple_choice" for coding/science/general.
    choices: 2–4 items, exactly one correct=true (when multiple_choice).
    numericAnswer: the key when kind is numeric (e.g. "3" or "x = 3").
    explanation: the correct fix, 1–2 sentences, shown after they try.
{coding_extra}
When educator interview answers are provided, treat them as hard requirements for focus,
depth, language, structure, and which parts of the topic to emphasize.
Stay on-subject and on-topic-pack. Make the draft feel premium and demo-worthy on first open.
"""

    draft: LectureDraft = await structured.ainvoke([
        SystemMessage(content=system_prompt),
        HumanMessage(
            content=(
                f"Subject: {subject_key}\n"
                f"Topic pack: {topic_slug or 'n/a'}\n"
                f"Educator topic / instructions:\n{prompt}\n"
                f"{interview_block}\n"
                "Produce a showcase-quality first draft with a full pedagogical arc."
            )
        ),
    ])

    payload = draft.model_dump()
    _ensure_check_checkpoints(payload.get("slides") or [], subject_key)
    return payload


def _ensure_check_checkpoints(slides: list, subject: str) -> None:
    """Guarantee every check slide has a usable subject-matched checkpoint."""
    for slide in slides:
        if not isinstance(slide, dict):
            continue
        if str(slide.get("slide_role") or "") != "check":
            continue
        checkpoint = slide.get("checkpoint")
        if isinstance(checkpoint, dict) and str(checkpoint.get("prompt") or "").strip():
            _normalize_checkpoint(checkpoint, subject)
            slide["checkpoint"] = checkpoint
            continue
        slide["checkpoint"] = _fallback_checkpoint(slide, subject)


def _normalize_checkpoint(checkpoint: dict, subject: str) -> None:
    kind = str(checkpoint.get("kind") or "multiple_choice")
    if subject != "math":
        kind = "multiple_choice"
        checkpoint["kind"] = kind
        checkpoint["numericAnswer"] = ""
    if kind == "numeric":
        checkpoint["kind"] = "numeric"
        if str(checkpoint.get("numericAnswer") or "").strip():
            return
        checkpoint.update(
            _fallback_checkpoint({"explanation": checkpoint.get("explanation")}, subject)
        )
        return
    checkpoint["kind"] = "multiple_choice"
    choices = checkpoint.get("choices")
    if not isinstance(choices, list):
        choices = []
    cleaned = []
    for index, raw in enumerate(choices[:4]):
        if not isinstance(raw, dict):
            continue
        text = str(raw.get("text") or "").strip()
        if not text:
            continue
        cleaned.append(
            {
                "id": str(raw.get("id") or chr(97 + index)),
                "text": text,
                "correct": bool(raw.get("correct")),
            }
        )
    if len(cleaned) < 2:
        checkpoint.update(_fallback_checkpoint({"explanation": checkpoint.get("explanation")}, subject))
        return
    if sum(1 for item in cleaned if item["correct"]) != 1:
        cleaned[0]["correct"] = True
        for item in cleaned[1:]:
            item["correct"] = False
    checkpoint["choices"] = cleaned


def _fallback_checkpoint(slide: dict, subject: str) -> dict:
    explanation = str(slide.get("explanation") or slide.get("callout") or "").strip()
    equation = str(slide.get("equation") or "").strip()
    if subject == "math" and equation:
        return {
            "prompt": f"What is the result of {equation}?",
            "kind": "multiple_choice",
            "choices": [
                {"id": "a", "text": equation, "correct": True},
                {"id": "b", "text": "The expression cannot be simplified", "correct": False},
            ],
            "numericAnswer": "",
            "explanation": explanation or "Use the method from the worked example.",
        }
    prompt = explanation or "Which statement matches this slide?"
    correct = explanation or "The idea taught on this slide"
    return {
        "prompt": prompt if len(prompt) < 180 else "Which statement is correct?",
        "kind": "multiple_choice",
        "choices": [
            {"id": "a", "text": correct[:200] or "The key idea from this slide", "correct": True},
            {"id": "b", "text": "None of these ideas apply here", "correct": False},
        ],
        "numericAnswer": "",
        "explanation": explanation or "Review the worked example, then continue.",
    }


def _format_clarifications(clarifications: list[dict] | None) -> str:
    if not clarifications:
        return ""
    lines = [
        "",
        "## Educator interview answers (follow these closely)",
    ]
    for item in clarifications:
        if not isinstance(item, dict):
            continue
        question = str(item.get("question") or item.get("question_id") or "").strip()
        answer = str(item.get("answer") or "").strip()
        if not answer:
            continue
        lines.append(f"- Q: {question}")
        lines.append(f"  A: {answer}")
    if len(lines) <= 2:
        return ""
    return "\n".join(lines)


class ClarifyOptionDraft(BaseModel):
    id: str = ""
    label: str = ""


class ClarifyQuestionDraft(BaseModel):
    id: str = ""
    prompt: str = ""
    options: list[ClarifyOptionDraft] = Field(default_factory=list)


class ClarifyInterviewDraft(BaseModel):
    topic_summary: str = ""
    questions: list[ClarifyQuestionDraft] = Field(default_factory=list)


async def propose_lecture_clarifications(
    prompt: str,
    *,
    subject: str | None = None,
) -> dict:
    """Ask 3–5 focused questions so generation has enough teaching context."""
    from app.services.lecture_subjects import SUBJECT_LABELS, normalize_subject

    api_key = _openai_api_key()
    if not api_key:
        raise ValueError("OPENAI_API_KEY is not configured.")

    subject_key = normalize_subject(subject)
    subject_label = SUBJECT_LABELS.get(subject_key, subject_key)

    subject_hints = {
        "coding": (
            "Ask about: language; which angle to emphasize (intuition vs complexity vs code walkthrough); "
            "algorithm approach (e.g. brute force vs hash map / two pointers); "
            "what to show as class vs function vs method; which edge cases or complexity to include."
        ),
        "math": (
            "Ask about: learner level; which representation to prioritize (symbols vs graphs vs worked numbers); "
            "whether to include proofs vs computation; common mistakes to highlight."
        ),
        "science": (
            "Ask about: subfield focus; qualitative vs quantitative; real-world demo vs formula; "
            "lab/safety or misconceptions to include."
        ),
        "general": (
            "Ask about: audience level; outcome goals; examples vs definitions; "
            "what to skip so the lecture stays focused."
        ),
    }

    llm = build_chat_model(temperature=0.4, model=_assistant_model(), api_key=api_key)
    structured = llm.with_structured_output(
        ClarifyInterviewDraft, method="function_calling"
    )

    system = f"""You design a short pre-lecture interview for Project VL educators.
Subject: {subject_label} ({subject_key}).

Return 3–5 clarifying questions that unlock a better lecture draft.
Rules:
- Each question must be specific to THIS topic (not generic "what is your audience?" unless needed).
- Prefer concrete choices educators can tap quickly.
- Every question needs 2–4 short option labels (id + label). Educators may still type a custom answer later.
- Cover the decisions that most affect content quality for this subject.
- {subject_hints.get(subject_key, subject_hints["general"])}
- topic_summary: one sentence restating what you think they want to teach.
- question ids: short slugs (focus, language, algorithm, structure, depth, …).
- Do NOT generate the lecture yet. Only the interview.
"""

    draft: ClarifyInterviewDraft = await structured.ainvoke([
        SystemMessage(content=system),
        HumanMessage(
            content=(
                f"Subject: {subject_key}\n"
                f"Educator topic:\n{prompt.strip()}\n\n"
                "Propose the interview questions now."
            )
        ),
    ])

    # Sanitize / clamp for the API response shape.
    questions: list[dict] = []
    for index, q in enumerate(draft.questions[:5]):
        qid = (q.id or f"q{index + 1}").strip()[:40] or f"q{index + 1}"
        prompt_text = (q.prompt or "").strip()[:280]
        if not prompt_text:
            continue
        options = []
        for oi, opt in enumerate(q.options[:6]):
            label = (opt.label or "").strip()[:160]
            if not label:
                continue
            oid = (opt.id or f"opt{oi + 1}").strip()[:40] or f"opt{oi + 1}"
            options.append({"id": oid, "label": label})
        questions.append(
            {
                "id": qid,
                "prompt": prompt_text,
                "options": options,
            }
        )

    if len(questions) < 2:
        # Deterministic fallback so the UI never dead-ends.
        questions = _fallback_clarify_questions(subject_key, prompt)

    return {
        "topic_summary": (draft.topic_summary or "").strip()[:280],
        "questions": questions,
    }


def _fallback_clarify_questions(subject: str, prompt: str) -> list[dict]:
    topic = " ".join((prompt or "").split())[:80] or "this topic"
    if subject == "coding":
        return [
            {
                "id": "language",
                "prompt": f"Which language should the {topic} sample use?",
                "options": [
                    {"id": "js", "label": "JavaScript"},
                    {"id": "py", "label": "Python"},
                    {"id": "ts", "label": "TypeScript"},
                ],
            },
            {
                "id": "focus",
                "prompt": "What should the lecture emphasize most?",
                "options": [
                    {"id": "intuition", "label": "Core intuition / mental model"},
                    {"id": "algorithm", "label": "Fastest practical algorithm"},
                    {"id": "walkthrough", "label": "Line-by-line code walkthrough"},
                ],
            },
            {
                "id": "structure",
                "prompt": "How should the working code be structured on stage?",
                "options": [
                    {"id": "function", "label": "Single function / method"},
                    {"id": "class", "label": "Class with methods"},
                    {"id": "steps", "label": "Helper functions by step"},
                ],
            },
        ]
    if subject == "math":
        return [
            {
                "id": "level",
                "prompt": f"What learner level is {topic} for?",
                "options": [
                    {"id": "intro", "label": "Intro / first exposure"},
                    {"id": "practice", "label": "Practice / exam prep"},
                    {"id": "advanced", "label": "Deeper / stretch"},
                ],
            },
            {
                "id": "focus",
                "prompt": "What should we emphasize?",
                "options": [
                    {"id": "worked", "label": "Worked numerical example"},
                    {"id": "symbolic", "label": "Symbolic moves / algebra"},
                    {"id": "graph", "label": "Graph / visual intuition"},
                ],
            },
            {
                "id": "pitfalls",
                "prompt": "Should we include common mistakes?",
                "options": [
                    {"id": "yes", "label": "Yes — dedicate a check slide"},
                    {"id": "light", "label": "Light callouts only"},
                    {"id": "no", "label": "Skip mistakes"},
                ],
            },
        ]
    return [
        {
            "id": "focus",
            "prompt": f"What is the main goal for teaching {topic}?",
            "options": [
                {"id": "intro", "label": "Introduce the idea clearly"},
                {"id": "apply", "label": "Apply with a concrete example"},
                {"id": "review", "label": "Review / check understanding"},
            ],
        },
        {
            "id": "depth",
            "prompt": "How deep should the lecture go?",
            "options": [
                {"id": "short", "label": "Short overview (4–5 slides)"},
                {"id": "standard", "label": "Standard classroom arc"},
                {"id": "rich", "label": "Rich with extra practice"},
            ],
        },
    ]
