from sqlalchemy import Column, String, Text, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
import uuid
from app.connection.database import Base

class Assignment(Base):
    __tablename__ = 'assignments'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    classroom_id = Column(UUID(as_uuid=True), ForeignKey('classrooms.id'), nullable=False)
    prompt = Column(Text, nullable=False)
    stage_data = Column(JSONB, nullable=False, default=dict)

    classroom = relationship("Classroom", back_populates="assignments")
    submissions = relationship("AssignmentSubmission", back_populates="assignment")
