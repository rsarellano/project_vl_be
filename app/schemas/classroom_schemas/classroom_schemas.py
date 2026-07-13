from pydantic import BaseModel, ConfigDict
from typing import Optional, List, Dict, Any
from uuid import UUID

class ClassroomBase(BaseModel):
    name: str

class ClassroomCreate(ClassroomBase):
    pass

class ClassroomJoin(BaseModel):
    code: str

class ClassroomResponse(ClassroomBase):
    id: UUID
    code: str
    educator_id: UUID

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
