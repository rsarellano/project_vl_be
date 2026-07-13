from pydantic import BaseModel
class UserCreate(BaseModel):
    email: str
    password: str
    role: str = "student"

class UserLogin(BaseModel):
    email: str
    password: str

class UserResetPassword(BaseModel):
    email: str
    new_password: str