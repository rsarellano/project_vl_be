from fastapi import APIRouter, Depends, Response
from app.connection.database import get_db
from app.schemas.user_schemas.user_schemas import UserCreate, UserLogin
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.user_services import create_user, login_user

user_router = APIRouter(prefix="/users")

@user_router.post("/create", status_code=200)
async def user_create(user: UserCreate, db: AsyncSession=Depends(get_db)):
    await create_user(user, db)

    return {
        "success": True,
        "message": "User created successfully!"
    }

@user_router.post("/login")
async def user_login(user:UserLogin, response: Response, db: AsyncSession=Depends(get_db)):
    return await login_user(user, db, response)