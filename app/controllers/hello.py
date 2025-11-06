from fastapi import APIRouter, Depends
from app.connection.database import get_db
from app.models.User import User

hello_router = APIRouter(prefix="/me")

@hello_router.get("/")
async def hello(db = Depends(get_db)):
    return "Hello world"