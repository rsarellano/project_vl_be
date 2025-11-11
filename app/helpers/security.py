from datetime import datetime, timedelta, timezone
from jose import JWTError, jwt
from typing import Optional
import os
from dotenv import load_dotenv

load_dotenv()

SECRET_KEY = os.getenv("JWTKEY")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES=30

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    token = jwt.encode(to_encode, SECRET_KEY, ALGORITHM)
    return token

def verify_access_token(token: str):
    try:
        payload = jwt.encode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None