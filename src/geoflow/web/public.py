"""Admission policy for the single-process, read-only public demonstration."""

import os
import re
import time

from starlette.responses import JSONResponse

PUBLIC_PATH = re.compile(
    r"/api/v1/(?:mode|health|research|experiments|benchmarks|models"
    r"|demos/(?:gaussian|rotating)/(?:result|field|export)"
    r"|earth(?:/(?:field|eddies|export))?"
    r"|models/(?:cnn|fno)/(?:result|comparison|export)"
    r"|benchmarks/[\w-]+/comparison)"
)


def public_mode():
    return os.getenv("GEOFLOW_READ_ONLY", "0") == "1"


class PublicAdmission:
    """Single event loop owns the bucket and stream counter, including downloads."""

    def __init__(self, app):
        self.app = app
        self.active = 0
        self.tokens = 48.0
        self.updated = time.monotonic()

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or not public_mode():
            return await self.app(scope, receive, send)
        path = scope["path"]
        if scope["method"] not in {"GET", "HEAD"}:
            response = JSONResponse({"detail": "this demonstration is read-only"}, 403)
        elif not PUBLIC_PATH.fullmatch(path):
            response = JSONResponse(
                {"detail": "resource unavailable in public demo"}, 404
            )
        elif path == "/api/v1/health":
            return await self.app(scope, receive, send)
        else:
            now = time.monotonic()
            self.tokens = min(48.0, self.tokens + 16 * (now - self.updated))
            self.updated = now
            if self.active < 8 and self.tokens >= 1:
                self.active += 1
                self.tokens -= 1
                try:
                    return await self.app(scope, receive, send)
                finally:
                    self.active -= 1
            response = JSONResponse(
                {"detail": "demo busy, retry shortly"},
                429,
                headers={"Retry-After": "1"},
            )
        await response(scope, receive, send)
