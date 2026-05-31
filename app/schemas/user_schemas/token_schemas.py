from pydantic import BaseModel
from datetime import datetime

class TokenBase(BaseModel):
    token: str
    created_at: datetime
    expires_at: datetime

class TokenCreate(BaseModel):
    token: str
    user_id: int
    expires_at: datetime
