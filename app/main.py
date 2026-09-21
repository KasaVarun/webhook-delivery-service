import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from app.config import get_settings
from app.database import Base, engine
from app.routes import api_router

settings = get_settings()
logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    logger.info("database_schema_ready")
    yield
    await engine.dispose()


app = FastAPI(
    title="Webhook Delivery Service",
    version="0.1.0",
    description="Registers webhook destinations, accepts idempotent events, and performs persisted asynchronous delivery retries.",
    lifespan=lifespan,
)
app.include_router(api_router)


@app.middleware("http")
async def log_request_latency(request: Request, call_next):
    started_at = time.perf_counter()
    response = await call_next(request)
    latency_ms = (time.perf_counter() - started_at) * 1000
    logger.info(
        "request_complete method=%s path=%s status=%s latency_ms=%.2f",
        request.method,
        request.url.path,
        response.status_code,
        latency_ms,
    )
    return response


@app.exception_handler(SQLAlchemyError)
async def handle_database_error(_: Request, exc: SQLAlchemyError) -> JSONResponse:
    logger.error("database_error type=%s", type(exc).__name__)
    return JSONResponse(status_code=503, content={"detail": "database unavailable"})