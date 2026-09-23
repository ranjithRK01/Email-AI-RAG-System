from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.emails import router as emails_router
from app.exceptions import EmailNotFoundError
from app.health import router
from app.request_logging import log_request


app = FastAPI()
app.middleware("http")(log_request)
app.include_router(router)
app.include_router(emails_router)


@app.exception_handler(EmailNotFoundError)
async def handle_email_not_found(
    request: Request, exc: EmailNotFoundError
) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": "Email not found"})
