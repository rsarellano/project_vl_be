from pydantic import BaseModel
from uuid import UUID
from typing import Optional, Dict, Any

class PromptReceiverBase(BaseModel):
    prompt: str
    

class PromptReceiverCreate(PromptReceiverBase):
    pass

class PromptReceiverRead(PromptReceiverBase):
    id: UUID
    
    
class Config:
    orm_mode = True
    