from sqlalchemy import Column, Integer, Boolean, String, ForeignKey
from app.db.database import Base
from sqlalchemy.dialects.postgresql import UUID
import uuid



class Property(Base):
    __tablename__ = "svg_scenes"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    background_color = Column(String, default="#ffffff")
    width = Column(String, default="800")
    height = Column(String, default="600")
    
    
    
    
    