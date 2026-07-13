from fastapi import Request, HTTPException
from app.utils.redis_client import redis_client

class RateLimiter:
    def __init__(self, requests: int, window: int):
        self.requests = requests
        self.window = window

    async def __call__(self, request: Request):
        # We use the client IP as the rate limiting key.
        # If behind a proxy like Nginx or Docker, you might need to check headers like X-Forwarded-For instead.
        client_ip = request.client.host if request.client else "unknown"
        
        # You could also use a user ID if you have an authenticated route
        # user = getattr(request.state, "user", None)
        # key_id = user.id if user else client_ip
        
        # Construct the Redis key for this endpoint and IP
        key = f"rate_limit:{request.url.path}:{client_ip}"

        # Increment the request count
        current_requests = await redis_client.incr(key)
        
        if current_requests == 1:
            # First request, set the expiration window
            await redis_client.expire(key, self.window)
            
        if current_requests > self.requests:
            # Limit exceeded
            raise HTTPException(
                status_code=429,
                detail=f"Too many requests. Limit is {self.requests} requests per {self.window} seconds."
            )
