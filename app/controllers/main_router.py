from fastapi import APIRouter
from .hello import hello_router

router = APIRouter(prefix="/api")

router.include_router(hello_router)