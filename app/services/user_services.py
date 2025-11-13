from app.schemas.user_schemas.user_schemas import UserCreate, UserLogin
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user_models.User import User
from app.models.user_models.Token import Token
from app.helpers.hash import hash_pass
from sqlalchemy import select
from fastapi import HTTPException, Response
from app.helpers.hash import verify_pass
from app.helpers.security import create_access_token
from datetime import timedelta, datetime, timezone
import os
from dotenv import load_dotenv

load_dotenv()

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
    token_expire = int(os.getenv("TOKEN_EXPIRE"))

    db_token = Token(token=token, user_id=existing_user.id, expires_at=datetime.now(timezone.utc) + timedelta(minutes=token_expire))

    db.add(db_token)
    await db.commit()
    await db.refresh(db_token)


    response.set_cookie(
        key="token",
        value=token,
        httponly=True,
        samesite="lax",
        secure=False,  # True in production with HTTPS
        max_age=os.getenv("TOKEN_EXPIRE") * 60
    )
    
    return {
        "success": True,
        "message": "Login successful!"
}