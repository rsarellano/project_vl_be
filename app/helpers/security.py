from datetime import datetime, timedelta, timezone
from typing import Optional
import jwt
import os
from dotenv import load_dotenv
from fastapi.exceptions import HTTPException

load_dotenv()

SECRET_KEY = os.getenv("JWTKEY")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES= int(os.getenv("TOKEN_EXPIRE", 60))

print("EXPIRE", ACCESS_TOKEN_EXPIRE_MINUTES)

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    token = jwt.encode(to_encode, SECRET_KEY, ALGORITHM)
    return token

def verify_access_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")