from fastapi import APIRouter

from .answer_router import answer_router
from .user_router import user_router
from .classroom_router import classroom_router
from .subscription_router import subscription_router
from .admin_router import admin_router
from .presence_router import presence_router
from .lecture_router import lecture_router
from .asset_router import asset_router

router = APIRouter(prefix="/api")

router.include_router(user_router)
router.include_router(answer_router, prefix="/answers", tags=["answers"])
router.include_router(classroom_router)
router.include_router(subscription_router)
router.include_router(admin_router)
router.include_router(presence_router)
router.include_router(lecture_router)
router.include_router(asset_router)
