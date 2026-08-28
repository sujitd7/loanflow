"""Application error types and their HTTP mapping.

Services and routers raise these instead of `fastapi.HTTPException`; a single
handler registered by `install_error_handlers()` renders them as
`{"detail": ...}` with the right status code.
"""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class AppError(Exception):
    """Base class for expected, client-facing errors."""

    status_code = 400
    detail = "Bad request"

    def __init__(self, detail: str | None = None) -> None:
        self.detail = detail or type(self).detail
        super().__init__(self.detail)


class Unauthorized(AppError):
    status_code = 401
    detail = "Not authenticated"


class Forbidden(AppError):
    status_code = 403
    detail = "Insufficient permissions"


class NotFound(AppError):
    status_code = 404
    detail = "Not found"


class Conflict(AppError):
    status_code = 409
    detail = "Conflict"


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _handle_app_error(_request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
