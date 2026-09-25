from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.emails import router as emails_router
from app.exceptions import EmailNotFoundError, InvalidEmailQueryError
from app.health import router
from app.request_logging import log_request
from app.config import settings
from app.database import dispose_database, get_session_factory
from app.async_database import dispose_async_database


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    try:
        if settings.database_url is not None:
            get_session_factory()
        yield
    finally:
        try:
            dispose_database()
        finally:
            await dispose_async_database()


app = FastAPI(lifespan=lifespan)
app.middleware("http")(log_request)
app.include_router(router)
app.include_router(emails_router)


@app.exception_handler(EmailNotFoundError)
async def handle_email_not_found(
    request: Request, exc: EmailNotFoundError
) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": "Email not found"})


@app.exception_handler(InvalidEmailQueryError)
async def handle_invalid_email_query(
    request: Request, exc: InvalidEmailQueryError
) -> JSONResponse:
    # Use a fixed public message rather than exposing exception internals.
    return JSONResponse(status_code=422, content={"detail": "Invalid email search parameters"})
