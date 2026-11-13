"""Request body size limit (Content-Length + streaming chunked ASGI guard) and security headers."""

from __future__ import annotations

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp, Message, Receive, Scope, Send


class BodySizeLimitMiddleware:
    """Enforces maximum request body size on both Content-Length and chunked/streaming bodies."""

    def __init__(self, app: ASGIApp, max_bytes: int) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = {k.lower(): v for k, v in scope.get("headers", [])}
        cl = headers.get(b"content-length")
        if cl is not None:
            try:
                too_big = int(cl) > self.max_bytes
            except ValueError:
                too_big = True
            if too_big:
                resp = self._error_response()
                await resp(scope, receive, send)
                return

        if scope.get("method", "GET").upper() in {"GET", "HEAD", "OPTIONS"}:
            await self.app(scope, receive, send)
            return

        # Pre-read chunked/streaming body up to max_bytes, aborting immediately if exceeded.
        chunks: list[bytes] = []
        received = 0
        passthrough_messages: list[Message] = []
        while True:
            message = await receive()
            if message["type"] == "http.request":
                piece = message.get("body", b"")
                if piece:
                    received += len(piece)
                    if received > self.max_bytes:
                        resp = self._error_response()
                        await resp(scope, receive, send)
                        return
                    chunks.append(piece)
                if not message.get("more_body", False):
                    break
            else:
                passthrough_messages.append(message)
                break

        buffered_body = b"".join(chunks)
        replayed = False

        async def replay_receive() -> Message:
            nonlocal replayed
            if not replayed:
                replayed = True
                return {"type": "http.request", "body": buffered_body, "more_body": False}
            if passthrough_messages:
                return passthrough_messages.pop(0)
            return await receive()

        await self.app(scope, replay_receive, send)

    @staticmethod
    def _error_response() -> JSONResponse:
        return JSONResponse(
            status_code=413,
            content={
                "error": {
                    "code": "payload_too_large",
                    "message": "Conteúdo excede o limite permitido.",
                }
            },
        )


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("Cache-Control", "no-store")
        return response
