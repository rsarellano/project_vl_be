"""Local disk sticker / asset library for testing (swap to R2/Supabase later)."""

from __future__ import annotations

import os
import re
import uuid
from pathlib import Path
from typing import Any
from uuid import UUID

from fastapi import HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.models.asset_models.UserAsset import UserAsset
from app.models.user_models.User import User

ALLOWED_MIME = {
    "image/png",
    "image/jpeg",
    "image/jpg",
    "image/webp",
    "image/gif",
    "image/svg+xml",
}
MAX_BYTES = 2 * 1024 * 1024  # 2MB
EXT_FOR_MIME = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/webp": ".webp",
    "image/gif": ".gif",
    "image/svg+xml": ".svg",
}


def upload_root() -> Path:
    raw = (os.getenv("ASSET_UPLOAD_DIR") or "uploads").strip() or "uploads"
    root = Path(raw)
    if not root.is_absolute():
        # project_vl_be/ as cwd when running uvicorn
        root = Path.cwd() / root
    return root.resolve()


def _safe_name(name: str) -> str:
    base = Path(name or "sticker").stem
    cleaned = re.sub(r"[^\w\s\-]+", "", base, flags=re.UNICODE).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)[:80]
    return cleaned or "sticker"


def asset_public_url(asset_id: UUID | str) -> str:
    return f"/api/assets/{asset_id}/file"


def to_response(asset: UserAsset) -> dict[str, Any]:
    return {
        "id": str(asset.id),
        "name": asset.name,
        "mime_type": asset.mime_type,
        "kind": asset.kind,
        "url": asset_public_url(asset.id),
        "created_at": asset.created_at.isoformat() if asset.created_at else None,
    }


async def list_assets_for_user(user: User, db: AsyncSession) -> list[UserAsset]:
    result = await db.execute(
        select(UserAsset)
        .where(UserAsset.owner_id == user.id)
        .order_by(UserAsset.created_at.desc())
    )
    return list(result.scalars().all())


async def get_owned_asset(
    asset_id: UUID, user: User, db: AsyncSession
) -> UserAsset:
    result = await db.execute(
        select(UserAsset).where(
            UserAsset.id == asset_id, UserAsset.owner_id == user.id
        )
    )
    asset = result.scalars().first()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    return asset


async def create_sticker_from_upload(
    user: User,
    file: UploadFile,
    db: AsyncSession,
) -> UserAsset:
    mime = (file.content_type or "").split(";")[0].strip().lower()
    if mime not in ALLOWED_MIME:
        raise HTTPException(
            status_code=400,
            detail="Only PNG, JPEG, WebP, GIF, or SVG images are allowed",
        )

    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty file")
    if len(data) > MAX_BYTES:
        raise HTTPException(status_code=400, detail="File too large (max 2MB)")

    asset_id = uuid.uuid4()
    ext = EXT_FOR_MIME.get(mime, ".bin")
    rel_dir = Path("stickers") / str(user.id)
    abs_dir = upload_root() / rel_dir
    abs_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{asset_id}{ext}"
    abs_path = abs_dir / filename
    abs_path.write_bytes(data)

    rel_path = (rel_dir / filename).as_posix()
    display_name = _safe_name(file.filename or "sticker")

    asset = UserAsset(
        id=asset_id,
        owner_id=user.id,
        name=display_name,
        mime_type=mime,
        file_path=rel_path,
        kind="sticker",
    )
    db.add(asset)
    await db.commit()
    await db.refresh(asset)
    return asset


def resolve_absolute_path(asset: UserAsset) -> Path:
    path = upload_root() / asset.file_path
    root = upload_root()
    try:
        path.resolve().relative_to(root)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid asset path") from exc
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Asset file missing on disk")
    return path
