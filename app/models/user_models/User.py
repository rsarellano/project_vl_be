from app.connection.database import Base
from sqlalchemy import Column, UUID, String, Boolean
from sqlalchemy.orm import relationship
import uuid

class User(Base):
    __tablename__ = 'users'

    id = Column(UUID, primary_key=True, nullable=False, default=lambda : uuid.uuid4())
    email = Column(String(200), nullable=False)
    password = Column(String(300), nullable=False)
    role = Column(String(50), nullable=False, default="student")
    # Super Admin Access — set TRUE manually in DB only (not via signup/API).
    sa_access = Column(Boolean, nullable=False, default=False)

    tokens = relationship("Token", back_populates="owner")
    subscription = relationship("Subscription", back_populates="user", uselist=False)