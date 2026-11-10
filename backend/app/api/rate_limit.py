"""In-memory sliding-window rate limit for the endpoints that call the LLM.

The service runs as a single Cloud Run instance, so per-process state is enough to protect
the LLM quota. With several instances this would move to Redis.
"""

import math
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request, status

from app.core.config import get_settings


class RateLimiter:
    def __init__(self, limit: int, window_seconds: float = 3600) -> None:
        self.limit = limit
        self.window = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def hit(self, key: str, now: float | None = None) -> float | None:
        """Record a request; return seconds to wait if the key is over the limit."""
        now = time.monotonic() if now is None else now
        hits = self._hits[key]
        while hits and hits[0] <= now - self.window:
            hits.popleft()
        if len(hits) >= self.limit:
            return hits[0] + self.window - now
        hits.append(now)
        return None

    def reset(self) -> None:
        self._hits.clear()


limiter = RateLimiter(get_settings().rate_limit_per_hour)


def client_ip(request: Request) -> str:
    """Client address behind Cloud Run.

    Google's front end appends the real client address to ``X-Forwarded-For``; earlier
    entries can be set by the client, so only the last one is trusted.
    """
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[-1].strip()
    return request.client.host if request.client else "unknown"


async def llm_rate_limit(request: Request) -> None:
    retry_after = limiter.hit(client_ip(request))
    if retry_after is not None:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Too many AI requests from your address. Try again later.",
            headers={"Retry-After": str(math.ceil(retry_after))},
        )
