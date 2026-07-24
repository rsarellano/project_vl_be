from sqlalchemy import Column, String, Text, ForeignKey, DateTime, Boolean
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

from app.connection.database import Base


class Lecture(Base):
    __tablename__ = "lectures"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    title = Column(String(300), nullable=False)
    subject = Column(String(50), nullable=False, default="general", server_default="general")
    prompt = Column(Text, nullable=True)
    slides = Column(JSONB, nullable=False, default=list)
    is_published = Column(Boolean, nullable=False, default=False, server_default="false")
    published_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    owner = relationship("User")
