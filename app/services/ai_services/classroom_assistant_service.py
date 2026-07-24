import os
import uuid
import json
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from fastapi import HTTPException
from sqlalchemy.orm.attributes import flag_modified
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
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
  * "question_type": "short_answer" or "multiple_choice"
  * "choices": list of strings or null
  * "correct_answer": string (the correct answer key)
  * "topic": string or null
  * "difficulty": string or null
- Use plain text math notation (x^2, sqrt(x), fractions like 3/4) — no LaTeX delimiters.

Always resolve student names/emails from the roster to their id strings.
Always explain clearly in the "message" field what actions you have chosen to perform, so the educator knows what changed.
"""

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

    llm = ChatOpenAI(temperature=0.3, model=_assistant_model(), api_key=api_key)
    structured = llm.with_structured_output(AssistantResponse, method="function_calling")

    human_content = f"Current Classroom Context:\n{json.dumps(classroom_context, indent=2)}\n\nEducator Prompt:\n{prompt}"

    response: AssistantResponse = await structured.ainvoke([
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=human_content)
    ])

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
            for idx, q in enumerate(data.get("questions") or [], start=1):
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
                            for idx, q in enumerate(data["questions"], start=1):
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
"""


async def process_dashboard_command(
    prompt: str,
    user: User,
    db: AsyncSession,
) -> DashboardAssistantResponse:
    if user.role != "educator":
        raise HTTPException(
            status_code=403,
            detail="Only educators can use the Classroom AI Assistant",
        )

    tier = await _get_user_tier(user.id, db)
    existing = await _count_educator_classrooms(user.id, db)
    classroom_cap = get_limit_value(tier, "max_classrooms")
    student_cap = get_limit_value(tier, "max_students_per_classroom")
    remaining = get_remaining(tier, "max_classrooms", existing)
    can_create = check_limit(tier, "max_classrooms", existing)

    plan_context = {
        "tier": tier,
        "classrooms_used": existing,
        "max_classrooms": classroom_cap,
        "classrooms_remaining": remaining,
        "can_create_classroom": can_create,
        "plan_max_students": student_cap,
        "notes": [
            "Server enforces all limits even if you ignore them.",
            "Free tier: typically 5 classrooms and 20 students each.",
            "Pro tier: unlimited classrooms and students.",
        ],
    }

    api_key = _openai_api_key()
    if not api_key:
        raise ValueError("OPENAI_API_KEY is not configured.")

    llm = ChatOpenAI(temperature=0.3, model=_assistant_model(), api_key=api_key)
    structured = llm.with_structured_output(
        DashboardAssistantIntent, method="function_calling"
    )

    human_content = (
        f"Educator plan & usage:\n{json.dumps(plan_context, indent=2)}\n\n"
        f"Educator Prompt:\n{prompt}"
    )

    intent: DashboardAssistantIntent = await structured.ainvoke([
        SystemMessage(content=DASHBOARD_SYSTEM_PROMPT),
        HumanMessage(content=human_content),
    ])

    created: list[CreatedClassroomSummary] = []
    upgrade_required = False
    notes: list[str] = []

    for action in intent.actions:
        if action.action_type != "create_classroom" or not action.create_classroom_data:
            continue

        data = action.create_classroom_data
        name = str(data.get("name") or "").strip()
        if not name:
            notes.append("Skipped a create request because no classroom name was provided.")
            continue

        # Re-check quota at apply time (source of truth)
        current = await _count_educator_classrooms(user.id, db)
        if not check_limit(tier, "max_classrooms", current):
            upgrade_required = True
            notes.append(
                f"Could not create \"{name}\": your {tier} plan classroom limit "
                f"({classroom_cap}) is reached. Upgrade to Pro to create more."
            )
            continue

        requested_max = data.get("max_students")
        clamped_note = None
        max_students_val: int | None = None
        if requested_max is not None:
            try:
                requested_int = int(requested_max)
                if student_cap is not None and requested_int > student_cap:
                    clamped_note = (
                        f"Requested {requested_int} seats for \"{name}\", but your "
                        f"{tier} plan allows up to {student_cap}. Created with {student_cap}."
                    )
                    # Soft over-ask: still create; do not force upgrade modal
                max_students_val = clamp_max_students(requested_int, tier)
            except (TypeError, ValueError, HTTPException) as exc:
                if isinstance(exc, HTTPException):
                    notes.append(exc.detail if isinstance(exc.detail, str) else str(exc.detail))
                    upgrade_required = True
                    continue
                notes.append(f"Ignored invalid max_students for \"{name}\".")

        create_in = ClassroomCreate(
            name=name,
            max_students=max_students_val,
            description=data.get("description"),
            grading_system=data.get("grading_system"),
            test_access=data.get("test_access")
            if data.get("test_access") in ("all_members", "allowlist")
            else None,
            auto_enroll_newcomers=data.get("auto_enroll_newcomers")
            if data.get("auto_enroll_newcomers") is not None
            else None,
        )

        try:
            classroom = await create_classroom(create_in, user, db)
        except HTTPException as exc:
            detail = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
            notes.append(detail)
            if "limit" in detail.lower() or "upgrade" in detail.lower():
                upgrade_required = True
            continue

        settings = classroom.settings or {}
        created.append(
            CreatedClassroomSummary(
                id=str(classroom.id),
                name=classroom.name,
                code=classroom.code,
                max_students=settings.get("max_students"),
            )
        )
        if clamped_note:
            notes.append(clamped_note)

    message = (intent.message or "").strip()
    if notes:
        message = (message + "\n\n" if message else "") + "\n".join(notes)

    asked_create = any(a.action_type == "create_classroom" for a in intent.actions)
    message_l = message.lower()
    mentions_upgrade = any(
        token in message_l
        for token in (
            "upgrade",
            "pro tier",
            "free plan",
            "maximum number of classrooms",
            "limit reached",
        )
    )

    # AI often returns no_action + warning when at cap — still flag upgrade CTA.
    if not created and not can_create and (asked_create or mentions_upgrade):
        upgrade_required = True

    return DashboardAssistantResponse(
        message=message or "No changes were made.",
        actions=intent.actions,
        created_classrooms=created,
        upgrade_required=upgrade_required,
    )


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


class LectureDraft(BaseModel):
    title: str
    slides: list[SlideDraft]


async def generate_lecture_from_prompt(
    prompt: str,
    *,
    subject: str | None = None,
    topic: str | None = None,
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

    llm = ChatOpenAI(temperature=0.55, model=_assistant_model(), api_key=api_key)
    structured = llm.with_structured_output(LectureDraft, method="function_calling")

    system_prompt = f"""You are an AI Lecture Builder for Project VL educators.
Your first draft must feel OVER-THE-TOP capable: rich teaching arc, concrete worked content,
and stage-ready pieces (callouts + short steps) so educators immediately see what the visual stage can do.

{pedagogy_block}

{guidance}
{topic_note}
Each slide MUST contain:
1. title — specific, classroom-ready (not generic "Introduction").
2. equation — formula / key expression / short code when relevant; otherwise "".
   Prefer clean KaTeX for math (e.g. "s = v_{{0}} t + \\frac{{1}}{{2}} a t^{{2}}").
   NEVER wrap variables in \\text{{…}}. Do not use markdown $ delimiters.
3. narration — detailed spoken script for the educator (3–6 sentences).
4. explanation — short on-screen teaching point (1–3 sentences).
5. visual_type — one of "equation", "graph", "triangle", "circle", "trains".
6. slide_role — one of hook, concept, worked_example, practice, check, summary.
7. callout — one punchy tip/warning for a stage callout box (not empty when possible).
8. steps — 2–3 ultra-short stage steps (≤12 words). Required for worked_example and practice.

Stay on-subject and on-topic-pack. Make the draft feel premium and demo-worthy on first open.
"""

    draft: LectureDraft = await structured.ainvoke([
        SystemMessage(content=system_prompt),
        HumanMessage(
            content=(
                f"Subject: {subject_key}\n"
                f"Topic pack: {topic_slug or 'n/a'}\n"
                f"Educator topic / instructions:\n{prompt}\n\n"
                "Produce a showcase-quality first draft with a full pedagogical arc."
            )
        ),
    ])

    return draft.model_dump()
