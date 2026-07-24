from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv
from fastapi import HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.helpers.hash import hash_pass, verify_pass
from app.helpers.security import create_access_token, verify_access_token
from app.models.user_models.Token import Token
from app.models.user_models.User import User
from app.models.subscription_models.Subscription import Subscription
from app.schemas.user_schemas.user_schemas import UserCreate, UserLogin, UserResetPassword

load_dotenv()

TOKEN_EXPIRE_MINUTES = int(os.getenv("TOKEN_EXPIRE", 60))
ALLOWED_SIGNUP_ROLES = frozenset({"student", "educator"})

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

    role = (user.role or "student").strip().lower()
    if role not in ALLOWED_SIGNUP_ROLES:
        raise HTTPException(
            status_code=400,
            detail="Invalid role. Use student or educator.",
        )

    hashed_pass = hash_pass(user.password)
    new_user = User(email=user.email, password=hashed_pass, role=role, sa_access=False)
    db.add(new_user)
    await db.flush()

    # Auto-create free subscription for every new user
    free_sub = Subscription(user_id=new_user.id, tier="free")
    db.add(free_sub)
    await db.commit()
    try:
        from app.services.admin_realtime import broadcast_admin_dashboard
        await broadcast_admin_dashboard()
    except Exception:
        pass

async def reset_password(data: UserResetPassword, db: AsyncSession):
    existing_user = await get_user_by_email(data.email, db)
    if not existing_user:
        raise HTTPException(
            status_code=404,
            detail="Email does not exist!"
        )
    
    hashed_pass = hash_pass(data.new_password)
    existing_user.password = hashed_pass
    await db.commit()
    return {"success": True, "message": "Password reset successfully!"}

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

    # Eagerly load subscription so we can return the tier
    result = await db.execute(
        select(User).where(User.email == email).options(selectinload(User.subscription))
    )
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    subscription_tier = "free"
    if user.subscription:
        subscription_tier = user.subscription.tier

    return {
        "email": email,
        "role": user.role,
        "id": str(user.id),
        "subscription_tier": subscription_tier,
        "sa_access": bool(user.sa_access),
    }


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