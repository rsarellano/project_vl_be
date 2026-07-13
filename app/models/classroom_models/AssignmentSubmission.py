from sqlalchemy import Column, DateTime, Float, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

from app.connection.database import Base


class AssignmentSubmission(Base):
    __tablename__ = "assignment_submissions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    assignment_id = Column(UUID(as_uuid=True), ForeignKey("assignments.id"), nullable=False)
    student_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    answers = Column(JSONB, nullable=False, default=dict)
    submitted_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    score = Column(Float, nullable=True)

    assignment = relationship("Assignment", back_populates="submissions")
