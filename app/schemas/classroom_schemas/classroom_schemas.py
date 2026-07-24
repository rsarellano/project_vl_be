from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, List, Dict, Any, Literal
from uuid import UUID


class ClassroomBase(BaseModel):
    name: str


class ClassroomCreate(ClassroomBase):
    max_students: Optional[int] = Field(default=None, ge=1)
    description: Optional[str] = None
    grading_system: Optional[str] = None
    test_access: Optional[Literal["all_members", "allowlist"]] = None
    auto_enroll_newcomers: Optional[bool] = None


class ClassroomJoin(BaseModel):
    code: str


class ClassroomSettingsUpdate(BaseModel):
    """Educator-editable classroom settings (capacity + test access)."""

    max_students: Optional[int] = Field(default=None, ge=1)
    test_access: Optional[Literal["all_members", "allowlist"]] = None
    test_allowed_student_ids: Optional[List[str]] = None
    auto_enroll_newcomers: Optional[bool] = None
    description: Optional[str] = None
    grading_system: Optional[str] = None
    name: Optional[str] = None


class ClassroomResponse(ClassroomBase):
    id: UUID
    code: str
    educator_id: UUID
    settings: Dict[str, Any] = Field(default_factory=dict)
    student_count: int = 0
    plan_max_students: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


class AssignmentBase(BaseModel):
    prompt: str
    stage_data: Dict[str, Any] = {}


class AssignmentCreate(AssignmentBase):
    generate_exam: bool = True


class AssignmentResponse(AssignmentBase):
    id: UUID
    classroom_id: UUID

    model_config = ConfigDict(from_attributes=True)
