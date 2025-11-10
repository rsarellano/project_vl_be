from sqlalchemy import Column, String, Float, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID
import uuid
from app.db.database.database import Base


class PromptReceiver(Base):
    __tablename__ = "prompt_receiver"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    prompt = Column(String, nullable=False)
    # response = Column(Text, nullable=True)