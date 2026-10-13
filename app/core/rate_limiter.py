import time
import threading
from collections import defaultdict, deque
from typing import Dict, Deque, Tuple
from fastapi import Request, HTTPException, status
from app.config import settings


class InMemoryRateLimiter:
    """
    In-memory sliding window rate limiter using the standard library.
    
    Tracks request timestamps per client identifier (IP address) within a sliding
    time window to prevent abusive submissions and runaway LLM costs without
    requiring external services or dependencies for local/single-worker operation.
    """

    def __init__(self, default_window_seconds: int = 60):
        self.default_window_seconds = default_window_seconds
        self._history: Dict[str, Deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def is_allowed(
        self, client_id: str, limit: int, window_seconds: int = 60
    ) -> Tuple[bool, int]:
        """
        Check if a client is within their rate limit.
        
        Returns:
            (allowed: bool, retry_after: int)
        """
        now = time.time()
        window_start = now - window_seconds

        with self._lock:
            timestamps = self._history[client_id]

            # Evict timestamps outside the sliding window
            while timestamps and timestamps[0] < window_start:
                timestamps.popleft()

            if len(timestamps) < limit:
                timestamps.append(now)
                return True, 0

            # Calculate retry after seconds based on earliest request
            earliest = timestamps[0]
            retry_after = max(1, int(earliest + window_seconds - now))
            return False, retry_after

    def reset(self):
        """Reset all tracked client history (used during testing)."""
        with self._lock:
            self._history.clear()


audit_rate_limiter = InMemoryRateLimiter(default_window_seconds=60)


async def check_audit_rate_limit(request: Request) -> None:
    """
    FastAPI dependency enforcing rate limits on audit creation.
    
    Derives client identifier from client IP (or X-Forwarded-For if available)
    and validates against settings.AUDIT_RATE_LIMIT_PER_MINUTE.
    """
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        client_id = forwarded_for.split(",")[0].strip()
    elif request.client and request.client.host:
        client_id = request.client.host
    else:
        client_id = "unknown"

    limit = settings.AUDIT_RATE_LIMIT_PER_MINUTE
    allowed, retry_after = audit_rate_limiter.is_allowed(client_id, limit=limit, window_seconds=60)

    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded. Maximum {limit} audit requests per minute allowed.",
            headers={"Retry-After": str(retry_after)},
        )
