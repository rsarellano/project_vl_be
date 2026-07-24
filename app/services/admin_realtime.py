"""Push live analytics/presence to Super Admin Access clients over Socket.IO."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


async def broadcast_admin_dashboard() -> None:
    """Send fresh presence + analytics to all SA clients in the admin room."""
    try:
        from app.socket_app import sio
        from app.services.presence_services import ADMIN_ROOM, list_presence
        from app.services.admin_services import get_analytics_snapshot
        from app.connection.database import sessionLocal

        presence = await list_presence()
        await sio.emit("presence:snapshot", presence, room=ADMIN_ROOM)

        async with sessionLocal() as db:
            analytics = await get_analytics_snapshot(db)
        await sio.emit("analytics:snapshot", analytics, room=ADMIN_ROOM)
    except Exception as exc:
        logger.warning("Admin dashboard broadcast failed: %s", exc)
