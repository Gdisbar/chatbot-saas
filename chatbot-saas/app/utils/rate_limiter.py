# =============================================================================
# app/utils/rate_limiter.py - Rate Limiting Utilities
# =============================================================================
import time
import json
from typing import Optional, Dict, Any
from fastapi import HTTPException, status, Request
from app.config import settings
from app.database import get_redis
import redis.asyncio as redis

class RateLimiter:
    """Redis-based rate limiter for API endpoints."""
    
    def __init__(self, redis_client: Optional[redis.Redis] = None):
        self.redis_client = redis_client
        
    async def _get_redis(self) -> redis.Redis:
        """Get Redis client instance."""
        if self.redis_client is None:
            return await get_redis()
        return self.redis_client
    
    async def is_allowed(
        self,
        key: str,
        limit: int,
        window: int,
        cost: int = 1
    ) -> Dict[str, Any]:
        """
        Check if request is allowed based on rate limit.
        
        Args:
            key: Unique identifier for rate limiting (e.g., user_id, IP)
            limit: Maximum number of requests allowed
            window: Time window in seconds
            cost: Cost of this request (default 1)
            
        Returns:
            Dict with allowed status and metadata
        """
        redis_client = await self._get_redis()
        current_time = int(time.time())
        window_start = current_time - window
        
        # Use sliding window log approach
        pipe = redis_client.pipeline()
        
        # Remove old entries
        pipe.zremrangebyscore(key, 0, window_start)
        
        # Count current requests
        pipe.zcard(key)
        
        # Add current request
        pipe.zadd(key, {str(current_time): current_time})
        
        # Set expiration
        pipe.expire(key, window)
        
        results = await pipe.execute()
        current_requests = results[1]
        
        allowed = (current_requests + cost) <= limit
        
        if not allowed:
            # Remove the request we just added since it's not allowed
            await redis_client.zrem(key, str(current_time))
        
        # Calculate reset time
        reset_time = current_time + window
        
        return {
            "allowed": allowed,
            "limit": limit,
            "remaining": max(0, limit - current_requests - (cost if allowed else 0)),
            "reset": reset_time,
            "retry_after": window if not allowed else None
        }
    
    async def check_rate_limit(
        self,
        request: Request,
        identifier: Optional[str] = None,
        limit: Optional[int] = None,
        window: int = 60,
        cost: int = 1
    ) -> None:
        """
        Check rate limit and raise exception if exceeded.
        
        Args:
            request: FastAPI request object
            identifier: Custom identifier (defaults to IP address)
            limit: Rate limit (defaults to settings.RATE_LIMIT_PER_MINUTE)
            window: Time window in seconds (default 60)
            cost: Cost of this request
            
        Raises:
            HTTPException: If rate limit exceeded
        """
        if limit is None:
            limit = settings.RATE_LIMIT_PER_MINUTE
            
        if identifier is None:
            # Use client IP as default identifier
            identifier = request.client.host if request.client else "unknown"
        
        # Create rate limit key
        rate_limit_key = f"rate_limit:{identifier}:{window}"
        
        result = await self.is_allowed(rate_limit_key, limit, window, cost)
        
        if not result["allowed"]:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "message": "Rate limit exceeded",
                    "limit": result["limit"],
                    "window": window,
                    "retry_after": result["retry_after"]
                },
                headers={
                    "X-RateLimit-Limit": str(result["limit"]),
                    "X-RateLimit-Remaining": str(result["remaining"]),
                    "X-RateLimit-Reset": str(result["reset"]),
                    "Retry-After": str(result["retry_after"])
                }
            )
    
    async def get_rate_limit_info(
        self,
        identifier: str,
        limit: int,
        window: int = 60
    ) -> Dict[str, Any]:
        """Get current rate limit information for an identifier."""
        rate_limit_key = f"rate_limit:{identifier}:{window}"
        result = await self.is_allowed(rate_limit_key, limit, window, 0)  # Cost 0 to just check
        
        return {
            "limit": result["limit"],
            "remaining": result["remaining"],
            "reset": result["reset"],
            "window": window
        }

# Global rate limiter instance
rate_limiter = RateLimiter()

# Convenience functions for common rate limiting patterns
async def check_user_rate_limit(request: Request, user_id: int, cost: int = 1) -> None:
    """Rate limit per user."""
    await rate_limiter.check_rate_limit(
        request, 
        identifier=f"user:{user_id}",
        limit=settings.RATE_LIMIT_PER_MINUTE,
        cost=cost
    )

async def check_ip_rate_limit(request: Request, cost: int = 1) -> None:
    """Rate limit per IP address."""
    await rate_limiter.check_rate_limit(request, cost=cost)

async def check_hourly_rate_limit(request: Request, user_id: Optional[int] = None, cost: int = 1) -> None:
    """Hourly rate limit."""
    identifier = f"user:{user_id}" if user_id else request.client.host
    await rate_limiter.check_rate_limit(
        request,
        identifier=identifier,
        limit=settings.RATE_LIMIT_PER_HOUR,
        window=3600,  # 1 hour
        cost=cost
    )