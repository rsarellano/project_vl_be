"""Per-user sticker / asset library (local disk for testing)."""

from __future__ import annotations

import uuid
from typing import List

from fastapi import APIRouter, Depends, File, Request, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.connection.database import get_db
from app.models.user_models.User import User
from app.services import asset_services
from app.services.user_services import get_current_user

asset_router = APIRouter(prefix="/assets", tags=["assets"])


class AssetResponse(BaseModel):
    id: str
    name: str
    mime_type: str
    kind: str
    url: str
    created_at: str | None = None


async def get_user_from_request(
    request: Request, db: AsyncSession = Depends(get_db)
) -> User:
    user_dict = await get_current_user(request, db)
    result = await db.execute(select(User).where(User.id == user_dict["id"]))
    user = result.scalars().first()
    if not user:
        from fastapi import HTTPException

        raise HTTPException(status_code=401, detail="User not found")
    return user


@asset_router.get("", response_model=List[AssetResponse])
async def list_assets(
    user: User = Depends(get_user_from_request),
    db: AsyncSession = Depends(get_db),
):
    assets = await asset_services.list_assets_for_user(user, db)
    return [AssetResponse(**asset_services.to_response(a)) for a in assets]


@asset_router.post("", response_model=AssetResponse)
async def upload_asset(
    file: UploadFile = File(...),
    user: User = Depends(get_user_from_request),
    db: AsyncSession = Depends(get_db),
):
    asset = await asset_services.create_sticker_from_upload(user, file, db)
    return AssetResponse(**asset_services.to_response(asset))


@asset_router.get("/{asset_id}/file")
async def get_asset_file(
    asset_id: uuid.UUID,
    user: User = Depends(get_user_from_request),
    db: AsyncSession = Depends(get_db),
):
    asset = await asset_services.get_owned_asset(asset_id, user, db)
    path = asset_services.resolve_absolute_path(asset)
    return FileResponse(
        path,
        media_type=asset.mime_type,
        filename=f"{asset.name}{path.suffix}",
    )
