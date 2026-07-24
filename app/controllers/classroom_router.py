from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
import uuid

from app.connection.database import get_db
from app.schemas.classroom_schemas.classroom_schemas import (
    ClassroomCreate,
    ClassroomJoin,
    ClassroomResponse,
    ClassroomSettingsUpdate,
    AssignmentCreate,
    AssignmentResponse,
)
from app.schemas.classroom_schemas.exam_schemas import (
    AssignmentDetailResponse,
    SubmissionCreate,
    SubmissionResponse,
    ClassroomStudentResponse,
    EducatorSubmissionResponse,
)
from app.schemas.classroom_schemas.assistant_schemas import (
    AssistantPromptRequest,
    AssistantResponse,
    DashboardAssistantResponse,
)
from app.services.user_services import get_current_user
from app.models.user_models.User import User
from app.services import classroom_services
from app.services.ai_services.classroom_assistant_service import (
    process_classroom_command,
    process_dashboard_command,
)

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
    classroom = await classroom_services.create_classroom(classroom_in, user, db)
    return await classroom_services.build_classroom_response(classroom, db)

@classroom_router.post("/join", response_model=ClassroomResponse)
async def join_classroom(
    join_in: ClassroomJoin,
    user: User = Depends(get_user_from_request),
    db: AsyncSession = Depends(get_db)
):
    classroom = await classroom_services.join_classroom(join_in, user, db)
    return await classroom_services.build_classroom_response(classroom, db)

@classroom_router.get("/list", response_model=List[ClassroomResponse])
async def list_classrooms(
    user: User = Depends(get_user_from_request),
    db: AsyncSession = Depends(get_db)
):
    classrooms = await classroom_services.get_classrooms_for_user(user, db)
    return [
        await classroom_services.build_classroom_response(c, db)
        for c in classrooms
    ]


@classroom_router.post("/assistant", response_model=DashboardAssistantResponse)
async def use_dashboard_assistant(
    request_in: AssistantPromptRequest,
    user: User = Depends(get_user_from_request),
    db: AsyncSession = Depends(get_db),
):
    return await process_dashboard_command(request_in.prompt, user, db)


@classroom_router.get("/{classroom_id}", response_model=ClassroomResponse)
async def get_classroom(
    classroom_id: uuid.UUID,
    user: User = Depends(get_user_from_request),
    db: AsyncSession = Depends(get_db)
):
    classroom = await classroom_services.get_classroom_by_id(classroom_id, user, db)
    return await classroom_services.build_classroom_response(classroom, db)


@classroom_router.patch("/{classroom_id}/settings", response_model=ClassroomResponse)
async def update_classroom_settings(
    classroom_id: uuid.UUID,
    settings_in: ClassroomSettingsUpdate,
    user: User = Depends(get_user_from_request),
    db: AsyncSession = Depends(get_db),
):
    classroom = await classroom_services.update_classroom_settings(
        classroom_id, settings_in, user, db
    )
    return await classroom_services.build_classroom_response(classroom, db)

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


@classroom_router.post(
    "/{classroom_id}/assistant",
    response_model=AssistantResponse,
)
async def use_assistant(
    classroom_id: uuid.UUID,
    request_in: AssistantPromptRequest,
    user: User = Depends(get_user_from_request),
    db: AsyncSession = Depends(get_db),
):
    return await process_classroom_command(classroom_id, request_in.prompt, user, db)


@classroom_router.get(
    "/{classroom_id}/students",
    response_model=List[ClassroomStudentResponse],
)
async def get_students(
    classroom_id: uuid.UUID,
    user: User = Depends(get_user_from_request),
    db: AsyncSession = Depends(get_db),
):
    return await classroom_services.get_classroom_students(classroom_id, user, db)


@classroom_router.get(
    "/{classroom_id}/assignments/{assignment_id}/submissions",
    response_model=List[EducatorSubmissionResponse],
)
async def get_assignment_submissions(
    classroom_id: uuid.UUID,
    assignment_id: uuid.UUID,
    user: User = Depends(get_user_from_request),
    db: AsyncSession = Depends(get_db),
):
    return await classroom_services.get_submissions_for_assignment_list(
        classroom_id, assignment_id, user, db
    )


@classroom_router.post("/lectures/generate")
async def generate_lecture_legacy(
    request_in: AssistantPromptRequest,
    user: User = Depends(get_user_from_request),
    db: AsyncSession = Depends(get_db),
):
    """Deprecated: use POST /api/lectures/generate (saves to library)."""
    from app.services.lecture_services import generate_and_save_lecture, to_response

    lecture = await generate_and_save_lecture(request_in.prompt, user, db)
    return to_response(lecture, viewer=user)
