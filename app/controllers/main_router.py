from fastapi import APIRouter
from .user_router import user_router
from .hello import hello_router

router = APIRouter(prefix="/api")

router.include_router(user_router)