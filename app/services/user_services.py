from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv
from fastapi import HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.helpers.hash import hash_pass, verify_pass
from app.helpers.security import create_access_token, verify_access_token
from app.models.user_models.Token import Token
from app.models.user_models.User import User
from app.schemas.user_schemas.user_schemas import UserCreate, UserLogin

load_dotenv()

TOKEN_EXPIRE_MINUTES = int(os.getenv("TOKEN_EXPIRE", 60))

async def get_user_by_email(email: str, db:AsyncSession):
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    return user

async def create_user(user: UserCreate, db: AsyncSession): 
    existing_email = await get_user_by_email(user.email, db)

    if existing_email:
        raise HTTPException(
            status_code=409,
            detail="Email already exist!"
        )

    hashed_pass = hash_pass(user.password)
    new_user = User(email=user.email, password=hashed_pass)
    db.add(new_user)
    await db.commit()

async def login_user(user: UserLogin, db:AsyncSession, response: Response):
    existing_user = await get_user_by_email(user.email, db)

    if not existing_user:
        raise HTTPException(
            status_code=404,
            detail="Email does not exist!"
        )
    
    if not verify_pass(user.password, existing_user.password):
        raise HTTPException(
            status_code=401,
            detail="Invalid Password!"
        )
        
    token = create_access_token({"sub": user.email})

    db_token = Token(
        token=token,
        user_id=existing_user.id,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=TOKEN_EXPIRE_MINUTES),
    )

    db.add(db_token)
    await db.commit()
    await db.refresh(db_token)


    response.set_cookie(
        key="token",
        value=token,
        httponly=True,
        samesite="lax",
        secure=False,
        max_age=TOKEN_EXPIRE_MINUTES * 60,
    )

    return {
        "success": True,
        "message": "Login successful!",
    }


async def get_current_user(request: Request, db: AsyncSession) -> dict[str, str]:
    token = request.cookies.get("token")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    payload = verify_access_token(token)
    email = payload.get("sub")
    if not email:
        raise HTTPException(status_code=401, detail="Invalid token")

    user = await get_user_by_email(email, db)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    return {"email": email}


async def logout_user(request: Request, response: Response, db: AsyncSession) -> dict[str, bool]:
    token = request.cookies.get("token")
    if token:
        result = await db.execute(select(Token).where(Token.token == token))
        db_token = result.scalar_one_or_none()
        if db_token:
            await db.delete(db_token)
            await db.commit()

    response.delete_cookie("token")
    return {"success": True}