from sqlalchemy import Column, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid
from app.connection.database import Base

class ClassroomMembership(Base):
    __tablename__ = 'classroom_memberships'
    __table_args__ = (
        UniqueConstraint('classroom_id', 'student_id', name='uq_classroom_student'),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    classroom_id = Column(UUID(as_uuid=True), ForeignKey('classrooms.id'), nullable=False)
    student_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False)

    classroom = relationship("Classroom", back_populates="memberships")
    student = relationship("User")
