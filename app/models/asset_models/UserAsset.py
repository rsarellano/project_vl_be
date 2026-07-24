from sqlalchemy import Column, String, ForeignKey, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

from app.connection.database import Base


class UserAsset(Base):
    __tablename__ = "user_assets"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    name = Column(String(300), nullable=False)
    mime_type = Column(String(100), nullable=False)
    file_path = Column(String(500), nullable=False)
    kind = Column(String(50), nullable=False, default="sticker", server_default="sticker")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    owner = relationship("User")
