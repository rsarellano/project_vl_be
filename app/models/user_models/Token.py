from app.connection.database import Base
from sqlalchemy import Column, UUID, String, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import uuid

class Token(Base):
    __tablename__ = "tokens"

    id = Column(UUID, primary_key=True, nullable=False, default=lambda : uuid.uuid4())
    token = Column(String, unique=True)
    user_id = Column(UUID, ForeignKey("users.id"))
    created_at = Column(DateTime(timezone=True), default=datetime.now(timezone.utc))
    expires_at = Column(DateTime(timezone=True))

    owner = relationship("User", back_populates="tokens")
