"""Fixed error envelope: {code, message, correlation_id}.

Nothing in the API returns a bare string or a framework-specific error body, so a client
can branch on `code` instead of parsing prose.
"""
from __future__ import annotations

import uuid
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

CODE_BY_STATUS: dict[int, str] = {
    400: "bad_request",
    401: "unauthenticated",
    403: "forbidden",
    404: "not_found",
    409: "conflict",
    422: "validation_error",
    429: "rate_limited",
    500: "internal_error",
    503: "unavailable",
}

CORRELATION_HEADER = "X-Correlation-ID"


def correlation_id(request: Request) -> str:
    """Reuse the caller's id when present, otherwise mint one for this request."""
    return request.headers.get(CORRELATION_HEADER) or f"CORR-{uuid.uuid4().hex[:12]}"


def envelope(status_code: int, message: str, request: Request, code: str | None = None) -> dict[str, Any]:
    return {
        "error": {
            "code": code or CODE_BY_STATUS.get(status_code, "error"),
            "message": message,
            "correlation_id": correlation_id(request),
        }
    }


class ApiError(Exception):
    """Raised by handlers to produce a contract-shaped error response."""

    def __init__(self, status_code: int, message: str, code: str | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.message = message
        self.code = code


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api_error(request: Request, exc: ApiError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content=envelope(exc.status_code, exc.message, request, exc.code))

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError) -> JSONResponse:
        first = exc.errors()[0] if exc.errors() else {}
        loc = ".".join(str(p) for p in first.get("loc", ()) if p != "body")
        message = f"{loc}: {first.get('msg', 'invalid request')}" if loc else str(first.get("msg", "invalid request"))
        return JSONResponse(status_code=422, content=envelope(422, message, request))

    @app.exception_handler(StarletteHTTPException)
    async def _http(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content=envelope(exc.status_code, str(exc.detail), request))
