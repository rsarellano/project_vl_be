import logging
import socketio
import os
import json
from http.cookies import SimpleCookie

from app.utils.redis_client import redis_client
from app.helpers.security import verify_access_token
from app.services.presence_services import (
    ADMIN_ROOM,
    area_from_path,
    list_presence,
    remove_presence,
    set_presence,
)

logger = logging.getLogger(__name__)

# Redis fan-out is opt-in. Local/dev without Redis stays single-process (still real-time).
redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
_use_redis = os.getenv("SOCKETIO_USE_REDIS", "").strip().lower() in ("1", "true", "yes")
_client_manager = None
if _use_redis:
    try:
        _client_manager = socketio.AsyncRedisManager(redis_url)
        logger.info("Socket.IO using Redis manager at %s", redis_url)
    except Exception as exc:
        logger.warning("Socket.IO Redis manager unavailable (%s); using in-process only", exc)

sio = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    client_manager=_client_manager,
    logger=False,
    engineio_logger=False,
    allow_upgrades=True,
    ping_timeout=60,
    ping_interval=25,
)

_sid_identity: dict[str, dict] = {}


def _cookie_token(environ: dict) -> str | None:
    raw = environ.get("HTTP_COOKIE") or ""
    if not raw:
        return None
    cookie = SimpleCookie()
    try:
        cookie.load(raw)
    except Exception:
        return None
    morsel = cookie.get("token")
    return morsel.value if morsel else None


async def _resolve_user_from_environ(environ: dict) -> dict | None:
    token = _cookie_token(environ)
    if not token:
        return None
    try:
        payload = verify_access_token(token)
    except Exception:
        return None
    email = payload.get("sub")
    if not email:
        return None

    try:
        from app.connection.database import sessionLocal
        from app.models.user_models.User import User
        from sqlalchemy import select

        async with sessionLocal() as db:
            result = await db.execute(select(User).where(User.email == email))
            user = result.scalars().first()
            if not user:
                return None
            return {
                "user_id": str(user.id),
                "email": user.email,
                "role": user.role,
                "sa_access": bool(user.sa_access),
            }
    except Exception as exc:
        logger.warning("Socket auth DB lookup failed: %s", exc)
        return None


async def _broadcast_admin() -> None:
    from app.services.admin_realtime import broadcast_admin_dashboard

    await broadcast_admin_dashboard()


@sio.event
async def connect(sid, environ):
    logger.info("Socket connected: %s", sid)
    identity = await _resolve_user_from_environ(environ)
    if identity:
        _sid_identity[sid] = identity
        path = "/"
        area = "home"
        await set_presence(
            sid,
            {
                **identity,
                "path": path,
                "area": area,
            },
        )
        try:
            from app.services.usage_time_services import touch_usage_segment

            await touch_usage_segment(identity["user_id"], area, path)
        except Exception as exc:
            logger.warning("usage segment on connect failed: %s", exc)
        await _broadcast_admin()


@sio.event
async def disconnect(sid):
    logger.info("Socket disconnected: %s", sid)
    identity = _sid_identity.pop(sid, None)
    await remove_presence(sid)
    if identity:
        try:
            from app.services.usage_time_services import touch_usage_segment

            await touch_usage_segment(
                identity["user_id"],
                "other",
                "/",
                closing=True,
            )
        except Exception as exc:
            logger.warning("usage segment on disconnect failed: %s", exc)
    await _broadcast_admin()


@sio.event
async def presence_update(sid, data):
    identity = _sid_identity.get(sid)
    if not identity:
        return {"error": "unauthenticated"}
    path = "/"
    if isinstance(data, dict):
        path = str(data.get("path") or "/")
    area = area_from_path(path)
    await set_presence(
        sid,
        {
            **identity,
            "path": path,
            "area": area,
        },
    )
    try:
        from app.services.usage_time_services import touch_usage_segment, resolve_subject

        await touch_usage_segment(identity["user_id"], area, path)
        subject = await resolve_subject(area, path)
    except Exception as exc:
        logger.warning("usage segment on update failed: %s", exc)
        subject = area
    await _broadcast_admin()
    return {"ok": True, "area": area, "subject": subject}


@sio.event
async def admin_subscribe(sid, data=None):
    identity = _sid_identity.get(sid)
    if not identity or not identity.get("sa_access"):
        return {"error": "Super Admin Access required"}
    await sio.enter_room(sid, ADMIN_ROOM)
    await _broadcast_admin()
    # Also send directly to this sid in case room emit races
    presence = await list_presence()
    await sio.emit("presence:snapshot", presence, to=sid)
    try:
        from app.connection.database import sessionLocal
        from app.services.admin_services import get_analytics_snapshot

        async with sessionLocal() as db:
            analytics = await get_analytics_snapshot(db)
        await sio.emit("analytics:snapshot", analytics, to=sid)
    except Exception as exc:
        logger.warning("admin_subscribe analytics failed: %s", exc)
    return {"ok": True}


@sio.event
async def join_classroom(sid, data):
    classroom_id = data.get("classroom_id")
    user_name = data.get("user_name", "Anonymous")

    if not classroom_id:
        return {"error": "classroom_id required"}

    sio.enter_room(sid, str(classroom_id))

    users_key = f"classroom:{classroom_id}:users"
    try:
        await redis_client.sadd(users_key, user_name)
        users = await redis_client.smembers(users_key)
        await sio.emit("users_updated", list(users), room=str(classroom_id))
        state_key = f"classroom:{classroom_id}:state"
        current_state = await redis_client.get(state_key)
        if current_state:
            await sio.emit("whiteboard_state", json.loads(current_state), to=sid)
    except Exception as exc:
        logger.warning("join_classroom redis failed: %s", exc)


@sio.event
async def leave_classroom(sid, data):
    classroom_id = data.get("classroom_id")
    user_name = data.get("user_name", "Anonymous")

    if classroom_id:
        sio.leave_room(sid, str(classroom_id))
        users_key = f"classroom:{classroom_id}:users"
        try:
            await redis_client.srem(users_key, user_name)
            users = await redis_client.smembers(users_key)
            await sio.emit("users_updated", list(users), room=str(classroom_id))
        except Exception as exc:
            logger.warning("leave_classroom redis failed: %s", exc)


@sio.event
async def update_whiteboard(sid, data):
    classroom_id = data.get("classroom_id")
    state = data.get("state")

    if classroom_id and state:
        state_key = f"classroom:{classroom_id}:state"
        try:
            await redis_client.set(state_key, json.dumps(state))
        except Exception as exc:
            logger.warning("update_whiteboard redis failed: %s", exc)
        await sio.emit("whiteboard_state", state, room=str(classroom_id), skip_sid=sid)


@sio.event
async def ping_event(sid, data):
    await sio.emit("pong_event", {"response": "pong"})
