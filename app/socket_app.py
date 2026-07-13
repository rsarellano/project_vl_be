import logging
import socketio
import os
import json
from app.utils.redis_client import redis_client

logger = logging.getLogger(__name__)

# Create the Socket.IO server
redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
mgr = socketio.AsyncRedisManager(redis_url)
sio = socketio.AsyncServer(async_mode='asgi', cors_allowed_origins=[], client_manager=mgr)

# The ASGI application
socket_app = socketio.ASGIApp(sio)

@sio.event
async def connect(sid, environ):
    logger.info(f"Socket connected: {sid}")

@sio.event
async def disconnect(sid):
    logger.info(f"Socket disconnected: {sid}")

@sio.event
async def join_classroom(sid, data):
    classroom_id = data.get("classroom_id")
    user_name = data.get("user_name", "Anonymous")
    
    if not classroom_id:
        return {"error": "classroom_id required"}
        
    # 1. Join the Socket.IO room for broadcasting
    sio.enter_room(sid, str(classroom_id))
    
    # 2. Track presence in Redis Set
    users_key = f"classroom:{classroom_id}:users"
    await redis_client.sadd(users_key, user_name)
    
    # 3. Broadcast updated active user list
    users = await redis_client.smembers(users_key)
    await sio.emit("users_updated", list(users), room=str(classroom_id))
    
    # 4. Fetch the latest Whiteboard State from Redis and send it only to this new user
    state_key = f"classroom:{classroom_id}:state"
    current_state = await redis_client.get(state_key)
    if current_state:
        await sio.emit("whiteboard_state", json.loads(current_state), to=sid)

@sio.event
async def leave_classroom(sid, data):
    classroom_id = data.get("classroom_id")
    user_name = data.get("user_name", "Anonymous")
    
    if classroom_id:
        # 1. Leave the Socket.IO room
        sio.leave_room(sid, str(classroom_id))
        
        # 2. Remove from Redis Set
        users_key = f"classroom:{classroom_id}:users"
        await redis_client.srem(users_key, user_name)
        
        # 3. Broadcast updated active user list
        users = await redis_client.smembers(users_key)
        await sio.emit("users_updated", list(users), room=str(classroom_id))

@sio.event
async def update_whiteboard(sid, data):
    classroom_id = data.get("classroom_id")
    state = data.get("state")
    
    if classroom_id and state:
        # 1. Save latest state as a JSON blob in Redis
        state_key = f"classroom:{classroom_id}:state"
        await redis_client.set(state_key, json.dumps(state))
        
        # 2. Broadcast to everyone else in the room (skip_sid ensures the drawer doesn't get their own event back)
        await sio.emit("whiteboard_state", state, room=str(classroom_id), skip_sid=sid)

@sio.event
async def ping_event(sid, data):
    logger.info(f"Ping received from {sid}: {data}")
    await sio.emit('pong_event', {'response': 'pong'})
