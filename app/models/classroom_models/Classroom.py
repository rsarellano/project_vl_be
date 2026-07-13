from sqlalchemy import Column, String, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid
from app.connection.database import Base

class Classroom(Base):
    __tablename__ = 'classrooms'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(200), nullable=False)
    code = Column(String(10), nullable=False, unique=True)
    educator_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False)

    educator = relationship("User")
    memberships = relationship("ClassroomMembership", back_populates="classroom", cascade="all, delete-orphan")
    assignments = relationship("Assignment", back_populates="classroom", cascade="all, delete-orphan")
