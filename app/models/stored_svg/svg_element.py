from sqlalchemy import Column, String, Float, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID
import uuid
from app.connection.database import Base


class SVGElement(Base):
    __tablename__="svg_element"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # scene_id = Column(UUID(as_uuid=True), ForeignKey("svg_scenes.id", ondelete="Cascade"), nullable=False)
    type = Column(String, nullable=False)
    position = Column(JSON, nullable=True)
    size = Column(JSON, nullable=True)
    # rotation = Column(Float, default = 0.0)
    color = Column(String, default="#000000")
    width = Column(String, default = "200" )
    height = Column(String, default = "260")
    # stroke = Column(String, default="#000000")
    # stroke_width = Column(Float, default=1.5)
    # opacity = Column(Float, default = 1.0)
    # metadata = Column(JSON, nullable=True) 