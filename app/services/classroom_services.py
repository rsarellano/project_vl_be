from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func as sa_func
from sqlalchemy.orm.attributes import flag_modified
from fastapi import HTTPException
import uuid
from typing import Any

from app.models.classroom_models.Classroom import Classroom
from app.models.classroom_models.ClassroomMembership import ClassroomMembership
from app.models.classroom_models.Assignment import Assignment
from app.models.classroom_models.AssignmentSubmission import AssignmentSubmission
from app.models.subscription_models.Subscription import Subscription
from app.schemas.classroom_schemas.classroom_schemas import (
    ClassroomCreate,
    ClassroomJoin,
    ClassroomSettingsUpdate,
    ClassroomResponse,
    AssignmentCreate,
)
from app.schemas.classroom_schemas.exam_schemas import SubmissionCreate
from app.models.user_models.User import User
from app.services.ai_services.exam_generation_service import generate_exam_from_prompt
from app.services.subscription_services.tier_limits import (
    check_limit,
    get_limit_value,
)


# ---------------------------------------------------------------------------
# Subscription / capacity helpers
# ---------------------------------------------------------------------------

async def _get_user_tier(user_id: uuid.UUID, db: AsyncSession) -> str:
    result = await db.execute(
        select(Subscription).where(Subscription.user_id == user_id)
    )
    sub = result.scalars().first()
    return sub.tier if sub else "free"


async def _count_memberships(classroom_id: uuid.UUID, db: AsyncSession) -> int:
    result = await db.execute(
        select(sa_func.count()).where(ClassroomMembership.classroom_id == classroom_id)
    )
    return int(result.scalar() or 0)


async def _count_educator_classrooms(educator_id: uuid.UUID, db: AsyncSession) -> int:
    result = await db.execute(
        select(sa_func.count()).where(Classroom.educator_id == educator_id)
    )
    return int(result.scalar() or 0)


def _settings_dict(classroom: Classroom) -> dict[str, Any]:
    return dict(classroom.settings or {}) if isinstance(classroom.settings, dict) else {}


def resolve_max_students(classroom: Classroom, educator_tier: str) -> int | None:
    """Effective join cap: classroom override clamped to plan limit."""
    plan_cap = get_limit_value(educator_tier, "max_students_per_classroom")
    settings = _settings_dict(classroom)
    raw = settings.get("max_students")
    classroom_cap: int | None = None
    if isinstance(raw, int) and raw > 0:
        classroom_cap = raw
    elif isinstance(raw, str) and raw.isdigit():
        classroom_cap = int(raw)

    if plan_cap is None:
        return classroom_cap
    if classroom_cap is None:
        return plan_cap
    return min(classroom_cap, plan_cap)


def clamp_max_students(value: int, educator_tier: str) -> int:
    plan_cap = get_limit_value(educator_tier, "max_students_per_classroom")
    if value < 1:
        raise HTTPException(status_code=400, detail="max_students must be at least 1")
    if plan_cap is not None and value > plan_cap:
        raise HTTPException(
            status_code=400,
            detail=f"max_students cannot exceed your plan limit ({plan_cap})",
        )
    return value


def _normalize_id_list(ids: Any) -> list[str]:
    if not isinstance(ids, list):
        return []
    out: list[str] = []
    seen: set[str] = set()
    for item in ids:
        sid = str(item).strip()
        if sid and sid not in seen:
            seen.add(sid)
            out.append(sid)
    return out


def resolve_test_access(
    classroom: Classroom,
    assignment: Assignment | None = None,
) -> tuple[str, list[str]]:
    """Return (mode, allowlist_ids). Assignment override wins when set."""
    class_settings = _settings_dict(classroom)
    mode = class_settings.get("test_access") or "all_members"
    allowlist = _normalize_id_list(class_settings.get("test_allowed_student_ids"))

    if assignment is not None:
        stage = assignment.stage_data if isinstance(assignment.stage_data, dict) else {}
        asg_settings = stage.get("settings") if isinstance(stage.get("settings"), dict) else {}
        if asg_settings.get("test_access") in ("all_members", "allowlist"):
            mode = asg_settings["test_access"]
            if "allowed_student_ids" in asg_settings:
                allowlist = _normalize_id_list(asg_settings.get("allowed_student_ids"))
            elif mode == "allowlist":
                allowlist = _normalize_id_list(asg_settings.get("allowed_student_ids"))

    if mode not in ("all_members", "allowlist"):
        mode = "all_members"
    return mode, allowlist


def student_can_take_test(
    classroom: Classroom,
    assignment: Assignment,
    student_id: uuid.UUID,
) -> bool:
    mode, allowlist = resolve_test_access(classroom, assignment)
    if mode == "all_members":
        return True
    return str(student_id) in allowlist


async def build_classroom_response(
    classroom: Classroom,
    db: AsyncSession,
) -> ClassroomResponse:
    tier = await _get_user_tier(classroom.educator_id, db)
    count = await _count_memberships(classroom.id, db)
    return ClassroomResponse(
        id=classroom.id,
        name=classroom.name,
        code=classroom.code,
        educator_id=classroom.educator_id,
        settings=_settings_dict(classroom),
        student_count=count,
        plan_max_students=get_limit_value(tier, "max_students_per_classroom"),
    )


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

async def create_classroom(classroom_in: ClassroomCreate, user: User, db: AsyncSession) -> Classroom:
    if user.role != "educator":
        raise HTTPException(status_code=403, detail="Only educators can create classrooms")

    tier = await _get_user_tier(user.id, db)
    existing = await _count_educator_classrooms(user.id, db)
    if not check_limit(tier, "max_classrooms", existing):
        cap = get_limit_value(tier, "max_classrooms")
        raise HTTPException(
            status_code=403,
            detail=f"Classroom limit reached ({cap}). Upgrade your plan to create more.",
        )

    plan_cap = get_limit_value(tier, "max_students_per_classroom")
    default_settings: dict[str, Any] = {
        "test_access": "all_members",
        "test_allowed_student_ids": [],
        "auto_enroll_newcomers": False,
    }
    if plan_cap is not None:
        default_settings["max_students"] = plan_cap

    if classroom_in.description is not None:
        default_settings["description"] = classroom_in.description
    if classroom_in.grading_system is not None:
        default_settings["grading_system"] = classroom_in.grading_system
    if classroom_in.test_access in ("all_members", "allowlist"):
        default_settings["test_access"] = classroom_in.test_access
    if classroom_in.auto_enroll_newcomers is not None:
        default_settings["auto_enroll_newcomers"] = bool(classroom_in.auto_enroll_newcomers)
    if classroom_in.max_students is not None:
        default_settings["max_students"] = clamp_max_students(classroom_in.max_students, tier)

    code = uuid.uuid4().hex[:6].upper()
    new_classroom = Classroom(
        name=classroom_in.name,
        code=code,
        educator_id=user.id,
        settings=default_settings,
    )
    db.add(new_classroom)
    await db.commit()
    await db.refresh(new_classroom)
    try:
        from app.services.admin_realtime import broadcast_admin_dashboard
        await broadcast_admin_dashboard()
    except Exception:
        pass
    return new_classroom


async def join_classroom(join_in: ClassroomJoin, user: User, db: AsyncSession) -> Classroom:
    if user.role != "student":
        raise HTTPException(status_code=403, detail="Only students can join classrooms via code")

    result = await db.execute(select(Classroom).where(Classroom.code == join_in.code))
    classroom = result.scalars().first()
    if not classroom:
        raise HTTPException(status_code=404, detail="Classroom not found")

    membership_result = await db.execute(
        select(ClassroomMembership).where(
            ClassroomMembership.classroom_id == classroom.id,
            ClassroomMembership.student_id == user.id,
        )
    )
    if membership_result.scalars().first():
        raise HTTPException(status_code=400, detail="Already joined this classroom")

    educator_tier = await _get_user_tier(classroom.educator_id, db)
    max_students = resolve_max_students(classroom, educator_tier)
    current = await _count_memberships(classroom.id, db)
    if max_students is not None and current >= max_students:
        raise HTTPException(
            status_code=403,
            detail=f"This classroom is full ({max_students} students).",
        )

    membership = ClassroomMembership(classroom_id=classroom.id, student_id=user.id)
    db.add(membership)

    settings = _settings_dict(classroom)
    auto_enroll = bool(settings.get("auto_enroll_newcomers"))
    if auto_enroll and settings.get("test_access") == "allowlist":
        allowlist = _normalize_id_list(settings.get("test_allowed_student_ids"))
        sid = str(user.id)
        if sid not in allowlist:
            allowlist.append(sid)
            settings["test_allowed_student_ids"] = allowlist
            classroom.settings = settings
            flag_modified(classroom, "settings")
            db.add(classroom)

        # Also append to assignment-level allowlists that override to allowlist
        asg_result = await db.execute(
            select(Assignment).where(Assignment.classroom_id == classroom.id)
        )
        for assignment in asg_result.scalars().all():
            stage = dict(assignment.stage_data or {}) if isinstance(assignment.stage_data, dict) else {}
            asg_settings = dict(stage.get("settings") or {}) if isinstance(stage.get("settings"), dict) else {}
            if asg_settings.get("test_access") != "allowlist":
                continue
            ids = _normalize_id_list(asg_settings.get("allowed_student_ids"))
            if sid not in ids:
                ids.append(sid)
                asg_settings["allowed_student_ids"] = ids
                stage["settings"] = asg_settings
                assignment.stage_data = stage
                flag_modified(assignment, "stage_data")
                db.add(assignment)

    await db.commit()
    await db.refresh(classroom)
    try:
        from app.services.admin_realtime import broadcast_admin_dashboard
        await broadcast_admin_dashboard()
    except Exception:
        pass
    return classroom


async def update_classroom_settings(
    classroom_id: uuid.UUID,
    settings_in: ClassroomSettingsUpdate,
    user: User,
    db: AsyncSession,
) -> Classroom:
    classroom = await get_classroom_by_id(classroom_id, user, db)
    if user.role != "educator":
        raise HTTPException(status_code=403, detail="Only educators can update classroom settings")

    tier = await _get_user_tier(user.id, db)
    settings = _settings_dict(classroom)

    if settings_in.name is not None and settings_in.name.strip():
        classroom.name = settings_in.name.strip()

    if settings_in.description is not None:
        settings["description"] = settings_in.description
    if settings_in.grading_system is not None:
        settings["grading_system"] = settings_in.grading_system
    if settings_in.max_students is not None:
        settings["max_students"] = clamp_max_students(settings_in.max_students, tier)
    if settings_in.test_access is not None:
        settings["test_access"] = settings_in.test_access
    if settings_in.test_allowed_student_ids is not None:
        settings["test_allowed_student_ids"] = _normalize_id_list(
            settings_in.test_allowed_student_ids
        )
    if settings_in.auto_enroll_newcomers is not None:
        settings["auto_enroll_newcomers"] = bool(settings_in.auto_enroll_newcomers)

    classroom.settings = settings
    flag_modified(classroom, "settings")
    db.add(classroom)
    await db.commit()
    await db.refresh(classroom)
    return classroom


async def get_classrooms_for_user(user: User, db: AsyncSession) -> list[Classroom]:
    if user.role == "educator":
        result = await db.execute(select(Classroom).where(Classroom.educator_id == user.id))
        return list(result.scalars().all())
    result = await db.execute(
        select(Classroom)
        .join(ClassroomMembership)
        .where(ClassroomMembership.student_id == user.id)
    )
    return list(result.scalars().all())


async def get_classroom_by_id(classroom_id: uuid.UUID, user: User, db: AsyncSession) -> Classroom:
    result = await db.execute(select(Classroom).where(Classroom.id == classroom_id))
    classroom = result.scalars().first()
    if not classroom:
        raise HTTPException(status_code=404, detail="Classroom not found")

    if user.role == "educator":
        if classroom.educator_id != user.id:
            raise HTTPException(status_code=403, detail="Not your classroom")
    else:
        membership_result = await db.execute(
            select(ClassroomMembership).where(
                ClassroomMembership.classroom_id == classroom.id,
                ClassroomMembership.student_id == user.id,
            )
        )
        if not membership_result.scalars().first():
            raise HTTPException(status_code=403, detail="Not a member of this classroom")

    return classroom


def _strip_exam_answers(stage_data: dict) -> dict:
    if not isinstance(stage_data, dict) or stage_data.get("type") != "exam":
        return stage_data

    questions = stage_data.get("questions")
    if not isinstance(questions, list):
        return stage_data

    sanitized_questions = []
    for item in questions:
        if not isinstance(item, dict):
            continue
        sanitized_questions.append(
            {
                key: value
                for key, value in item.items()
                if key != "correct_answer"
            }
        )

    return {
        **stage_data,
        "questions": sanitized_questions,
    }


def _compute_exam_score(stage_data: dict, answers: dict[str, str]) -> float | None:
    if stage_data.get("type") != "exam":
        return None

    questions = stage_data.get("questions")
    if not isinstance(questions, list) or not questions:
        return None

    gradable = 0
    correct = 0
    for item in questions:
        if not isinstance(item, dict):
            continue
        correct_answer = item.get("correct_answer")
        if not isinstance(correct_answer, str) or not correct_answer.strip():
            continue
        qid = item.get("id")
        if not isinstance(qid, str):
            continue
        gradable += 1
        student_answer = (answers.get(qid) or "").strip().lower()
        if student_answer == correct_answer.strip().lower():
            correct += 1

    if gradable == 0:
        return None
    return round((correct / gradable) * 100, 1)


async def create_assignment(
    classroom_id: uuid.UUID,
    assignment_in: AssignmentCreate,
    user: User,
    db: AsyncSession,
) -> Assignment:
    classroom = await get_classroom_by_id(classroom_id, user, db)
    if user.role != "educator":
        raise HTTPException(status_code=403, detail="Only educators can create assignments")

    stage_data = assignment_in.stage_data or {}

    if assignment_in.generate_exam:
        try:
            exam = await generate_exam_from_prompt(assignment_in.prompt)
            stage_data = exam.model_dump()
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=502, detail="Failed to generate exam questions") from exc

    new_assignment = Assignment(
        classroom_id=classroom.id,
        prompt=assignment_in.prompt,
        stage_data=stage_data,
    )
    db.add(new_assignment)
    await db.commit()
    await db.refresh(new_assignment)
    return new_assignment


async def get_assignments_for_classroom(
    classroom_id: uuid.UUID,
    user: User,
    db: AsyncSession,
) -> list[Assignment]:
    await get_classroom_by_id(classroom_id, user, db)
    result = await db.execute(select(Assignment).where(Assignment.classroom_id == classroom_id))
    assignments = list(result.scalars().all())

    if user.role == "student":
        for assignment in assignments:
            assignment.stage_data = _strip_exam_answers(assignment.stage_data or {})
    return assignments


async def get_assignment_by_id(
    classroom_id: uuid.UUID,
    assignment_id: uuid.UUID,
    user: User,
    db: AsyncSession,
) -> Assignment:
    classroom = await get_classroom_by_id(classroom_id, user, db)
    result = await db.execute(
        select(Assignment).where(
            Assignment.id == assignment_id,
            Assignment.classroom_id == classroom_id,
        )
    )
    assignment = result.scalars().first()
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")

    if user.role == "student":
        if not student_can_take_test(classroom, assignment, user.id):
            raise HTTPException(
                status_code=403,
                detail="You're not eligible for this test",
            )
        sub_result = await db.execute(
            select(AssignmentSubmission).where(
                AssignmentSubmission.assignment_id == assignment_id,
                AssignmentSubmission.student_id == user.id,
            )
        )
        has_submitted = sub_result.scalars().first() is not None
        if not has_submitted:
            assignment.stage_data = _strip_exam_answers(assignment.stage_data or {})
    return assignment


async def get_submission_for_assignment(
    classroom_id: uuid.UUID,
    assignment_id: uuid.UUID,
    user: User,
    db: AsyncSession,
) -> AssignmentSubmission | None:
    assignment = await get_assignment_by_id(classroom_id, assignment_id, user, db)
    if user.role != "student":
        return None

    result = await db.execute(
        select(AssignmentSubmission).where(
            AssignmentSubmission.assignment_id == assignment.id,
            AssignmentSubmission.student_id == user.id,
        )
    )
    return result.scalars().first()


async def submit_assignment(
    classroom_id: uuid.UUID,
    assignment_id: uuid.UUID,
    submission_in: SubmissionCreate,
    user: User,
    db: AsyncSession,
) -> AssignmentSubmission:
    if user.role != "student":
        raise HTTPException(status_code=403, detail="Only students can submit assignments")

    classroom = await get_classroom_by_id(classroom_id, user, db)

    result = await db.execute(
        select(Assignment).where(
            Assignment.id == assignment_id,
            Assignment.classroom_id == classroom_id,
        )
    )
    assignment = result.scalars().first()
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")

    if not student_can_take_test(classroom, assignment, user.id):
        raise HTTPException(
            status_code=403,
            detail="You're not eligible for this test",
        )

    existing = await db.execute(
        select(AssignmentSubmission).where(
            AssignmentSubmission.assignment_id == assignment.id,
            AssignmentSubmission.student_id == user.id,
        )
    )
    if existing.scalars().first():
        raise HTTPException(status_code=400, detail="You already submitted this assignment")

    answers = {
        str(key): str(value).strip()
        for key, value in (submission_in.answers or {}).items()
        if str(value).strip()
    }
    score = _compute_exam_score(assignment.stage_data or {}, answers)

    submission = AssignmentSubmission(
        assignment_id=assignment.id,
        student_id=user.id,
        answers=answers,
        score=score,
    )
    db.add(submission)
    await db.commit()
    await db.refresh(submission)
    return submission


async def get_classroom_students(classroom_id: uuid.UUID, user: User, db: AsyncSession) -> list[User]:
    await get_classroom_by_id(classroom_id, user, db)
    result = await db.execute(
        select(User)
        .join(ClassroomMembership, User.id == ClassroomMembership.student_id)
        .where(ClassroomMembership.classroom_id == classroom_id)
    )
    return list(result.scalars().all())


async def get_submissions_for_assignment_list(
    classroom_id: uuid.UUID,
    assignment_id: uuid.UUID,
    user: User,
    db: AsyncSession,
) -> list[dict]:
    await get_classroom_by_id(classroom_id, user, db)
    if user.role != "educator":
        raise HTTPException(status_code=403, detail="Only educators can view all submissions")

    result = await db.execute(
        select(AssignmentSubmission, User.email)
        .join(User, AssignmentSubmission.student_id == User.id)
        .where(AssignmentSubmission.assignment_id == assignment_id)
    )
    submissions_with_emails = []
    for sub, email in result.all():
        submissions_with_emails.append({
            "id": sub.id,
            "student_id": sub.student_id,
            "student_email": email,
            "answers": sub.answers,
            "submitted_at": sub.submitted_at,
            "score": sub.score,
        })
    return submissions_with_emails
