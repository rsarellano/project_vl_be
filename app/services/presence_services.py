"""Live presence for Super Admin Access (Redis + in-memory fallback)."""

from __future__ import annotations

import json
import logging
import time
from typing import Any

from app.utils.redis_client import redis_client

logger = logging.getLogger(__name__)

PRESENCE_HASH = "presence:sessions"  # sid -> JSON (socket)
PRESENCE_USER_PREFIX = "presence:user:"  # user_id -> JSON (HTTP heartbeat)
PRESENCE_TTL_SECONDS = 45
STALE_AFTER_SECONDS = 60
ADMIN_ROOM = "admin:presence"

_memory_sid: dict[str, dict[str, Any]] = {}
_memory_user: dict[str, dict[str, Any]] = {}


def area_from_path(path: str) -> str:
    p = (path or "/").split("?")[0]
    if p.startswith("/admin"):
        return "admin"
    if p.startswith("/classrooms"):
        return "classrooms"
    if p.startswith("/lectures"):
        return "lectures"
    if p.startswith("/app") or p.startswith("/sandbox"):
        return "tutor"
    if p.startswith("/pricing"):
        return "pricing"
    if p.startswith("/login"):
        return "login"
    if p == "/" or p == "":
        return "home"
    return "other"


async def set_presence(sid: str, payload: dict[str, Any]) -> None:
    data = {
        **payload,
        "sid": sid,
        "source": "socket",
        "last_seen": time.time(),
    }
    raw = json.dumps(data)
    _memory_sid[sid] = data
    try:
        await redis_client.hset(PRESENCE_HASH, sid, raw)
    except Exception as exc:
        logger.warning("Redis presence set failed, using memory: %s", exc)


async def remove_presence(sid: str) -> None:
    _memory_sid.pop(sid, None)
    try:
        await redis_client.hdel(PRESENCE_HASH, sid)
    except Exception as exc:
        logger.warning("Redis presence delete failed: %s", exc)


async def heartbeat_presence(
    *,
    user_id: str,
    email: str,
    role: str,
    path: str,
) -> dict[str, Any]:
    """HTTP heartbeat — reliable 'who's online' without depending on socket client state."""
    area = area_from_path(path)
    data = {
        "user_id": user_id,
        "email": email,
        "role": role,
        "path": path or "/",
        "area": area,
        "source": "http",
        "last_seen": time.time(),
    }
    key = f"{PRESENCE_USER_PREFIX}{user_id}"
    _memory_user[user_id] = data
    try:
        await redis_client.setex(key, PRESENCE_TTL_SECONDS, json.dumps(data))
    except Exception as exc:
        logger.warning("Redis heartbeat set failed, using memory: %s", exc)

    try:
        from app.services.usage_time_services import touch_usage_segment

        await touch_usage_segment(user_id, area, path or "/")
    except Exception as exc:
        logger.warning("usage segment from heartbeat failed: %s", exc)

    return {"ok": True, "area": area}


async def _collect_sessions() -> list[dict[str, Any]]:
    sessions: list[dict[str, Any]] = []

    # Socket sessions
    try:
        raw_map = await redis_client.hgetall(PRESENCE_HASH)
        for raw in raw_map.values():
            try:
                sessions.append(json.loads(raw))
            except json.JSONDecodeError:
                continue
    except Exception as exc:
        logger.warning("Redis presence list failed: %s", exc)

    sessions.extend(_memory_sid.values())

    # HTTP heartbeats
    try:
        async for key in redis_client.scan_iter(match=f"{PRESENCE_USER_PREFIX}*"):
            raw = await redis_client.get(key)
            if not raw:
                continue
            try:
                sessions.append(json.loads(raw))
            except json.JSONDecodeError:
                continue
    except Exception as exc:
        logger.warning("Redis heartbeat scan failed: %s", exc)

    sessions.extend(_memory_user.values())
    return sessions


async def list_presence() -> dict[str, Any]:
    now = time.time()
    sessions = await _collect_sessions()

    by_user: dict[str, dict[str, Any]] = {}
    for item in sessions:
        uid = str(item.get("user_id") or "")
        if not uid:
            continue
        last_seen = float(item.get("last_seen") or 0)
        if last_seen and (now - last_seen) > STALE_AFTER_SECONDS:
            continue
        prev = by_user.get(uid)
        if prev is None or last_seen >= float(prev.get("last_seen") or 0):
            by_user[uid] = item

    users = list(by_user.values())
    by_area: dict[str, int] = {}
    for u in users:
        area = str(u.get("area") or "other")
        by_area[area] = by_area.get(area, 0) + 1

    return {
        "online_count": len(users),
        "by_area": by_area,
        "users": [
            {
                "user_id": u.get("user_id"),
                "email": u.get("email"),
                "role": u.get("role"),
                "area": u.get("area"),
                "path": u.get("path"),
                "last_seen": u.get("last_seen"),
            }
            for u in sorted(users, key=lambda x: str(x.get("email") or ""))
        ],
    }
