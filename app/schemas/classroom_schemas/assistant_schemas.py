from pydantic import BaseModel, Field
from typing import Literal, Optional, List, Dict, Any


class AssistantPromptRequest(BaseModel):
    prompt: str


class AssistantAction(BaseModel):
    action_type: Literal[
        "create_assignment",
        "update_assignment",
        "delete_assignment",
        "update_classroom",
        "set_test_access",
        "add_students_to_test",
        "no_action",
    ]
    create_assignment_data: Optional[Dict[str, Any]] = None
    update_assignment_data: Optional[Dict[str, Any]] = None
    delete_assignment_id: Optional[str] = None
    update_classroom_data: Optional[Dict[str, Any]] = None
    # set_test_access / add_students_to_test payload
    test_access_data: Optional[Dict[str, Any]] = None


class AssistantResponse(BaseModel):
    message: str
    actions: List[AssistantAction]
    classroom_settings: Dict[str, Any] = Field(default_factory=dict)


class DashboardAssistantAction(BaseModel):
    action_type: Literal["create_classroom", "no_action"]
    create_classroom_data: Optional[Dict[str, Any]] = None


class DashboardAssistantIntent(BaseModel):
    """LLM-structured output only — server applies creates and fills the real response."""

    message: str
    actions: List[DashboardAssistantAction]


class CreatedClassroomSummary(BaseModel):
    id: str
    name: str
    code: str
    max_students: Optional[int] = None


class DashboardAssistantResponse(BaseModel):
    message: str
    actions: List[DashboardAssistantAction]
    created_classrooms: List[CreatedClassroomSummary] = Field(default_factory=list)
    upgrade_required: bool = False
