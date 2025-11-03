from pydantic import BaseModel
from uuid import UUID
from typing import Optional, Dict, Any
# from .svg_scene import SVGScene

class SVGElementBase(BaseModel):
    type: str
    position: dict | None = None
    size: dict | None = None
    rotation: float = 0.0
    color: str = "#000000"
    stroke: str = "#000000"
    stroke_width: float = 1.5
    opacity: float = 1.0
    # metadata: dict | None = None
    
    
class SVGElementCreate(SVGElementBase):
    pass

class SVGElementRead(SVGElementBase):
    id: UUID
    
    class Config:
        orm_mode = True
    