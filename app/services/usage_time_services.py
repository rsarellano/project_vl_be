"""Accumulate minutes/hours spent per area and subject for SA analytics."""

from __future__ import annotations

import json
import logging
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func as sa_func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.connection.database import sessionLocal
from app.models.analytics_models.UsageTimeSlice import UsageTimeSlice
from app.models.classroom_models.Classroom import Classroom
from app.utils.redis_client import redis_client

logger = logging.getLogger(__name__)

SEGMENT_PREFIX = "presence:segment:"
MIN_SLICE_SECONDS = 3
# While a user stays on one page, flush a slice this often so totals keep moving.
CHECKPOINT_SECONDS = 30
_memory_segments: dict[str, dict[str, Any]] = {}

AREA_SUBJECT_FALLBACK = {
    "tutor": "AI Tutor",
    "classrooms": "Classrooms",
    "lectures": "Lectures",
    "pricing": "Pricing",
    "home": "Home",
    "login": "Login",
    "admin": "Admin",
    "other": "Other",
}


def _segment_key(user_id: str) -> str:
    return f"{SEGMENT_PREFIX}{user_id}"


async def _get_segment(user_id: str) -> dict[str, Any] | None:
    key = _segment_key(user_id)
    try:
        raw = await redis_client.get(key)
        if raw:
            data = json.loads(raw)
            _memory_segments[user_id] = data
            return data
    except Exception:
        pass
    return _memory_segments.get(user_id)


async def _set_segment(user_id: str, data: dict[str, Any]) -> None:
    key = _segment_key(user_id)
    raw = json.dumps(data)
    _memory_segments[user_id] = data
    try:
        await redis_client.set(key, raw)
    except Exception as exc:
        logger.debug("Redis segment set failed: %s", exc)


async def _clear_segment(user_id: str) -> None:
    key = _segment_key(user_id)
    _memory_segments.pop(user_id, None)
    try:
        await redis_client.delete(key)
    except Exception:
        pass


async def resolve_subject(area: str, path: str) -> str:
    p = (path or "/").split("?")[0].strip("/")
    parts = p.split("/") if p else []

    if area == "classrooms" and len(parts) >= 2 and parts[0] == "classrooms":
        cid = parts[1]
        try:
            classroom_id = uuid.UUID(cid)
        except ValueError:
            return AREA_SUBJECT_FALLBACK.get(area, area)
        try:
            async with sessionLocal() as db:
                result = await db.execute(
                    select(Classroom.name).where(Classroom.id == classroom_id)
                )
                name = result.scalar_one_or_none()
                if name:
                    return str(name)
        except Exception as exc:
            logger.debug("resolve classroom subject failed: %s", exc)
        return f"Classroom {cid[:8]}"

    if area == "lectures" and len(parts) >= 2 and parts[0] == "lectures":
        return f"Lecture {parts[1][:12]}"

    return AREA_SUBJECT_FALLBACK.get(area, area.title() if area else "Other")


async def _persist_slice(
    user_id: str,
    area: str,
    subject: str,
    path: str | None,
    started_at: float,
    ended_at: float,
) -> None:
    duration = int(max(0, ended_at - started_at))
    if duration < MIN_SLICE_SECONDS:
        return
    try:
        uid = uuid.UUID(user_id)
    except ValueError:
        return

    start_dt = datetime.fromtimestamp(started_at, tz=timezone.utc)
    end_dt = datetime.fromtimestamp(ended_at, tz=timezone.utc)

    try:
        async with sessionLocal() as db:
            db.add(
                UsageTimeSlice(
                    user_id=uid,
                    area=area or "other",
                    subject=(subject or "General")[:200],
                    path=(path or "")[:500] or None,
                    started_at=start_dt,
                    ended_at=end_dt,
                    duration_seconds=duration,
                )
            )
            await db.commit()
    except Exception as exc:
        logger.warning("Failed to persist usage slice: %s", exc)


async def touch_usage_segment(
    user_id: str,
    area: str,
    path: str,
    *,
    closing: bool = False,
) -> None:
    """
    Keep an open time segment for the user.
    On area/subject change, close, or checkpoint interval → flush to DB.
    """
    if not user_id:
        return

    now = time.time()
    subject = await resolve_subject(area, path)
    prev = await _get_segment(user_id)

    if prev:
        same = (
            prev.get("area") == area
            and prev.get("subject") == subject
            and not closing
        )
        started = float(prev.get("started_at") or now)
        elapsed = now - started

        if same and elapsed < CHECKPOINT_SECONDS:
            prev["path"] = path
            prev["last_seen"] = now
            await _set_segment(user_id, prev)
            return

        # Area changed, closing, or checkpoint due — persist what we have.
        await _persist_slice(
            user_id,
            str(prev.get("area") or "other"),
            str(prev.get("subject") or "General"),
            prev.get("path"),
            started,
            now,
        )

        if closing:
            await _clear_segment(user_id)
            return

        if same:
            # Checkpoint: start a fresh open segment in the same place.
            await _set_segment(
                user_id,
                {
                    "user_id": user_id,
                    "area": area,
                    "subject": subject,
                    "path": path,
                    "started_at": now,
                    "last_seen": now,
                },
            )
            return

    if closing:
        await _clear_segment(user_id)
        return

    await _set_segment(
        user_id,
        {
            "user_id": user_id,
            "area": area,
            "subject": subject,
            "path": path,
            "started_at": now,
            "last_seen": now,
        },
    )


def _fmt_duration(seconds: int) -> str:
    seconds = int(seconds or 0)
    if seconds < 60:
        return f"{seconds}s"
    minutes = seconds // 60
    if minutes < 60:
        rem_s = seconds % 60
        if rem_s and minutes < 10:
            return f"{minutes}m {rem_s}s"
        return f"{minutes}m"
    hours = minutes // 60
    rem_m = minutes % 60
    if rem_m == 0:
        return f"{hours}h"
    return f"{hours}h {rem_m}m"


async def _load_open_segments() -> list[dict[str, Any]]:
    segments: list[dict[str, Any]] = []
    seen_users: set[str] = set()

    # Memory first
    for uid, seg in list(_memory_segments.items()):
        segments.append({**seg, "user_id": seg.get("user_id") or uid})
        seen_users.add(uid)

    try:
        async for key in redis_client.scan_iter(match=f"{SEGMENT_PREFIX}*"):
            uid = str(key).replace(SEGMENT_PREFIX, "")
            if uid in seen_users:
                continue
            raw = await redis_client.get(key)
            if not raw:
                continue
            try:
                seg = json.loads(raw)
                seg["user_id"] = seg.get("user_id") or uid
                segments.append(seg)
                seen_users.add(uid)
            except json.JSONDecodeError:
                continue
    except Exception as exc:
        logger.debug("open segment scan failed: %s", exc)

    return segments


async def get_usage_time_stats(
    db: AsyncSession,
    *,
    days: int = 7,
) -> dict[str, Any]:
    since = datetime.now(timezone.utc) - timedelta(days=days)
    now = time.time()

    by_subject_rows = (
        await db.execute(
            select(
                UsageTimeSlice.subject,
                UsageTimeSlice.area,
                sa_func.sum(UsageTimeSlice.duration_seconds),
            )
            .where(UsageTimeSlice.ended_at >= since)
            .group_by(UsageTimeSlice.subject, UsageTimeSlice.area)
            .order_by(sa_func.sum(UsageTimeSlice.duration_seconds).desc())
        )
    ).all()

    by_subject_map: dict[tuple[str, str], int] = {
        (str(subject), str(area)): int(total or 0)
        for subject, area, total in by_subject_rows
    }

    by_area_map: dict[str, int] = {}
    by_area_rows = (
        await db.execute(
            select(
                UsageTimeSlice.area,
                sa_func.sum(UsageTimeSlice.duration_seconds),
            )
            .where(UsageTimeSlice.ended_at >= since)
            .group_by(UsageTimeSlice.area)
        )
    ).all()
    for area, total in by_area_rows:
        by_area_map[str(area)] = int(total or 0)

    by_user_map: dict[tuple[str, str], int] = {}
    by_user_rows = (
        await db.execute(
            select(
                UsageTimeSlice.user_id,
                UsageTimeSlice.subject,
                sa_func.sum(UsageTimeSlice.duration_seconds),
            )
            .where(UsageTimeSlice.ended_at >= since)
            .group_by(UsageTimeSlice.user_id, UsageTimeSlice.subject)
        )
    ).all()
    for uid, subject, total in by_user_rows:
        by_user_map[(str(uid), str(subject))] = int(total or 0)

    # Add live open-segment time so numbers move while users stay on a page.
    open_segments = await _load_open_segments()
    for seg in open_segments:
        uid = str(seg.get("user_id") or "")
        area = str(seg.get("area") or "other")
        subject = str(seg.get("subject") or AREA_SUBJECT_FALLBACK.get(area, area))
        started = float(seg.get("started_at") or 0)
        if not uid or not started:
            continue
        live = int(max(0, now - started))
        if live < 1:
            continue
        by_subject_map[(subject, area)] = by_subject_map.get((subject, area), 0) + live
        by_area_map[area] = by_area_map.get(area, 0) + live
        by_user_map[(uid, subject)] = by_user_map.get((uid, subject), 0) + live

    from app.models.user_models.User import User

    user_ids: list[uuid.UUID] = []
    for uid, _ in by_user_map.keys():
        try:
            user_ids.append(uuid.UUID(uid))
        except (ValueError, TypeError):
            continue
    email_map: dict[str, str] = {}
    if user_ids:
        users = (
            await db.execute(select(User).where(User.id.in_(user_ids)))
        ).scalars().all()
        email_map = {str(u.id): u.email for u in users}

    by_subject = [
        {
            "subject": subject,
            "area": area,
            "seconds": seconds,
            "label": _fmt_duration(seconds),
        }
        for (subject, area), seconds in sorted(
            by_subject_map.items(), key=lambda x: x[1], reverse=True
        )
    ][:40]

    by_area = [
        {
            "area": area,
            "seconds": seconds,
            "label": _fmt_duration(seconds),
        }
        for area, seconds in sorted(by_area_map.items(), key=lambda x: x[1], reverse=True)
    ]

    by_user_subject = [
        {
            "user_id": uid,
            "email": email_map.get(uid, uid[:8]),
            "subject": subject,
            "seconds": seconds,
            "label": _fmt_duration(seconds),
        }
        for (uid, subject), seconds in sorted(
            by_user_map.items(), key=lambda x: x[1], reverse=True
        )[:50]
    ]

    total_seconds = sum(by_area_map.values())

    return {
        "window_days": days,
        "total_seconds": total_seconds,
        "total_label": _fmt_duration(total_seconds),
        "by_subject": by_subject,
        "by_area": by_area,
        "by_user_subject": by_user_subject,
    }
