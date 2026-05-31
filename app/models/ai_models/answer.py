import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, JSON, Text
from sqlalchemy.dialects.postgresql import UUID

from app.connection.database import Base


class Answer(Base):
    __tablename__ = "answers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    prompt = Column(Text, nullable=False)
    answer = Column(Text, nullable=False)
    blueprint = Column(JSON, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
