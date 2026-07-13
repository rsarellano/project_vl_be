from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.connection.database import get_db
from app.schemas.user_schemas.user_schemas import UserCreate, UserLogin, UserResetPassword
from app.services.user_services import (
    create_user,
    get_current_user,
    login_user,
    logout_user,
    reset_password,
)

user_router = APIRouter(prefix="/users", tags=["users"])


@user_router.post("/create", status_code=200)
async def user_create(user: UserCreate, db: AsyncSession = Depends(get_db)):
    await create_user(user, db)
    return {"success": True, "message": "User created successfully!"}

@user_router.post("/reset-password", status_code=200)
async def user_reset_password(data: UserResetPassword, db: AsyncSession = Depends(get_db)):
    return await reset_password(data, db)


@user_router.post("/login")
async def user_login(
    user: UserLogin,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    return await login_user(user, db, response)


@user_router.get("/me")
async def user_me(request: Request, db: AsyncSession = Depends(get_db)):
    return await get_current_user(request, db)


@user_router.post("/logout")
async def user_logout(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    return await logout_user(request, response, db)