from app.schemas.user_schemas import UserCreate, UserLogin
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.User import User
from app.helpers.hash import hash_pass
from sqlalchemy import select
from fastapi import HTTPException
from app.helpers.hash import verify_pass

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

async def login_user(user: UserLogin, db:AsyncSession):
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
    
    return {
        "success": True,
        "message": "Login successful!"
}