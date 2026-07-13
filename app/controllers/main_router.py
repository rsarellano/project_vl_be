from fastapi import APIRouter

from .answer_router import answer_router
from .user_router import user_router
from .classroom_router import classroom_router
from .subscription_router import subscription_router

router = APIRouter(prefix="/api")

router.include_router(user_router)
router.include_router(answer_router, prefix="/answers", tags=["answers"])
router.include_router(classroom_router)
router.include_router(subscription_router)