from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from fastapi import HTTPException
import uuid

from app.models.classroom_models.Classroom import Classroom
from app.models.classroom_models.ClassroomMembership import ClassroomMembership
from app.models.classroom_models.Assignment import Assignment
from app.models.classroom_models.AssignmentSubmission import AssignmentSubmission
from app.schemas.classroom_schemas.classroom_schemas import (
    ClassroomCreate,
    ClassroomJoin,
    AssignmentCreate,
)
from app.schemas.classroom_schemas.exam_schemas import SubmissionCreate
from app.models.user_models.User import User
from app.services.ai_services.exam_generation_service import generate_exam_from_prompt


async def create_classroom(classroom_in: ClassroomCreate, user: User, db: AsyncSession) -> Classroom:
    if user.role != "educator":
        raise HTTPException(status_code=403, detail="Only educators can create classrooms")
    
    code = uuid.uuid4().hex[:6].upper()
    new_classroom = Classroom(
        name=classroom_in.name,
        code=code,
        educator_id=user.id
    )
    db.add(new_classroom)
    await db.commit()
    await db.refresh(new_classroom)
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
            ClassroomMembership.student_id == user.id
        )
    )
    if membership_result.scalars().first():
        raise HTTPException(status_code=400, detail="Already joined this classroom")
    
    membership = ClassroomMembership(classroom_id=classroom.id, student_id=user.id)
    db.add(membership)
    await db.commit()
    return classroom

async def get_classrooms_for_user(user: User, db: AsyncSession) -> list[Classroom]:
    if user.role == "educator":
        result = await db.execute(select(Classroom).where(Classroom.educator_id == user.id))
        return result.scalars().all()
    else:
        result = await db.execute(
            select(Classroom)
            .join(ClassroomMembership)
            .where(ClassroomMembership.student_id == user.id)
        )
        return result.scalars().all()

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
                ClassroomMembership.student_id == user.id
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


async def create_assignment(classroom_id: uuid.UUID, assignment_in: AssignmentCreate, user: User, db: AsyncSession) -> Assignment:
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

async def get_assignments_for_classroom(classroom_id: uuid.UUID, user: User, db: AsyncSession) -> list[Assignment]:
    await get_classroom_by_id(classroom_id, user, db)
    result = await db.execute(select(Assignment).where(Assignment.classroom_id == classroom_id))
    assignments = result.scalars().all()

    if user.role == "student":
        for assignment in assignments:
            assignment.stage_data = _strip_exam_answers(assignment.stage_data or {})
    return assignments

async def get_assignment_by_id(classroom_id: uuid.UUID, assignment_id: uuid.UUID, user: User, db: AsyncSession) -> Assignment:
    await get_classroom_by_id(classroom_id, user, db)
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

    result = await db.execute(
        select(Assignment).where(
            Assignment.id == assignment_id,
            Assignment.classroom_id == classroom_id,
        )
    )
    assignment = result.scalars().first()
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")

    await get_classroom_by_id(classroom_id, user, db)

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
