from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
import uuid

from app.connection.database import get_db
from app.schemas.classroom_schemas.classroom_schemas import (
    ClassroomCreate,
    ClassroomJoin,
    ClassroomResponse,
    AssignmentCreate,
    AssignmentResponse,
)
from app.schemas.classroom_schemas.exam_schemas import (
    AssignmentDetailResponse,
    SubmissionCreate,
    SubmissionResponse,
)
from app.services.user_services import get_current_user
from app.models.user_models.User import User
from app.services import classroom_services

classroom_router = APIRouter(prefix="/classrooms", tags=["classrooms"])

async def get_user_from_request(request: Request, db: AsyncSession = Depends(get_db)) -> User:
    user_dict = await get_current_user(request, db)
    from sqlalchemy.future import select
    result = await db.execute(select(User).where(User.id == user_dict["id"]))
    user = result.scalars().first()
    if not user:
        from fastapi import HTTPException
        raise HTTPException(status_code=401, detail="User not found")
    return user

@classroom_router.post("/create", response_model=ClassroomResponse)
async def create_classroom(
    classroom_in: ClassroomCreate,
    user: User = Depends(get_user_from_request),
    db: AsyncSession = Depends(get_db)
):
    return await classroom_services.create_classroom(classroom_in, user, db)

@classroom_router.post("/join", response_model=ClassroomResponse)
async def join_classroom(
    join_in: ClassroomJoin,
    user: User = Depends(get_user_from_request),
    db: AsyncSession = Depends(get_db)
):
    return await classroom_services.join_classroom(join_in, user, db)

@classroom_router.get("/list", response_model=List[ClassroomResponse])
async def list_classrooms(
    user: User = Depends(get_user_from_request),
    db: AsyncSession = Depends(get_db)
):
    return await classroom_services.get_classrooms_for_user(user, db)

@classroom_router.get("/{classroom_id}", response_model=ClassroomResponse)
async def get_classroom(
    classroom_id: uuid.UUID,
    user: User = Depends(get_user_from_request),
    db: AsyncSession = Depends(get_db)
):
    return await classroom_services.get_classroom_by_id(classroom_id, user, db)

@classroom_router.post("/{classroom_id}/assignments/create", response_model=AssignmentResponse)
async def create_assignment(
    classroom_id: uuid.UUID,
    assignment_in: AssignmentCreate,
    user: User = Depends(get_user_from_request),
    db: AsyncSession = Depends(get_db)
):
    return await classroom_services.create_assignment(classroom_id, assignment_in, user, db)

@classroom_router.get("/{classroom_id}/assignments/list", response_model=List[AssignmentResponse])
async def list_assignments(
    classroom_id: uuid.UUID,
    user: User = Depends(get_user_from_request),
    db: AsyncSession = Depends(get_db)
):
    return await classroom_services.get_assignments_for_classroom(classroom_id, user, db)

@classroom_router.get("/{classroom_id}/assignments/{assignment_id}", response_model=AssignmentDetailResponse)
async def get_assignment(
    classroom_id: uuid.UUID,
    assignment_id: uuid.UUID,
    user: User = Depends(get_user_from_request),
    db: AsyncSession = Depends(get_db)
):
    assignment = await classroom_services.get_assignment_by_id(classroom_id, assignment_id, user, db)
    submission = await classroom_services.get_submission_for_assignment(
        classroom_id, assignment_id, user, db
    )
    return AssignmentDetailResponse(
        id=assignment.id,
        classroom_id=assignment.classroom_id,
        prompt=assignment.prompt,
        stage_data=assignment.stage_data or {},
        submission=SubmissionResponse.model_validate(submission) if submission else None,
    )

@classroom_router.post(
    "/{classroom_id}/assignments/{assignment_id}/submit",
    response_model=SubmissionResponse,
)
async def submit_assignment(
    classroom_id: uuid.UUID,
    assignment_id: uuid.UUID,
    submission_in: SubmissionCreate,
    user: User = Depends(get_user_from_request),
    db: AsyncSession = Depends(get_db),
):
    return await classroom_services.submit_assignment(
        classroom_id, assignment_id, submission_in, user, db
    )
