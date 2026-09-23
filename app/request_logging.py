import json
import logging
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from time import perf_counter
from uuid import UUID, uuid4

from fastapi import Request, Response


class RequestLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return json.dumps({
            "timestamp": datetime.fromtimestamp(record.created, timezone.utc).isoformat(),
            "level": record.levelname,
            "event": record.getMessage(),
            "request_id": record.request_id,
            "method": record.method,
            "status_code": record.status_code,
            "duration_ms": record.duration_ms,
        })


logger = logging.getLogger("email_platform.requests")
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(RequestLogFormatter())
    logger.addHandler(handler)


async def log_request(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    try:
        
        request_id = str(UUID(request.headers.get("X-Request-ID", "")))
    except ValueError:
        request_id = str(uuid4())

    request.state.request_id = request_id
    started = perf_counter()
    status_code = 500
    try:
        response = await call_next(request)
        status_code = response.status_code
        response.headers["X-Request-ID"] = request_id
        print("Response", response.status_code)
        return response
    finally:
        print("Finally Block")
        logger.log(
            logging.ERROR if status_code >= 500 else logging.INFO,
            "http_request",
            extra={
                "request_id": request_id,
                "method": request.method,
                "status_code": status_code,
                "duration_ms": round((perf_counter() - started) * 1000, 3),
            },
        )
