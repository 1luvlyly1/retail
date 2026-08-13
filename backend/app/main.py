"""
FastAPI application entry point — không có auth.
"""
from __future__ import annotations

from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.db.database import engine

structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer(),
    ],
    logger_factory=structlog.stdlib.LoggerFactory(),
)
logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 Starting", app=settings.APP_NAME, env=settings.APP_ENV)
    settings.TMP_DIR.mkdir(parents=True, exist_ok=True)
    settings.MEDIA_ROOT.mkdir(parents=True, exist_ok=True)
    yield
    await engine.dispose()
    logger.info("👋 Shutdown")


app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(GZipMiddleware, minimum_size=1000)

# ── Routers ───────────────────────────────────────────────────────────────────
from app.api.v1.endpoints import (  # noqa: E402
    companies,
    conversations,
    photos,
    reports,
    skills,
    visits,
    websocket,
)

API = "/api/v1"

app.include_router(companies.router,     prefix=f"{API}/companies",     tags=["Companies"])
app.include_router(visits.router,        prefix=f"{API}/visits",        tags=["Visits"])
app.include_router(photos.router,        prefix=f"{API}",               tags=["Photos"])
app.include_router(conversations.router, prefix=f"{API}/conversations",  tags=["Conversations"])
app.include_router(skills.router,        prefix=f"{API}/skills",        tags=["Skills"])
app.include_router(reports.router,       prefix=f"{API}/visits",        tags=["Reports"])
app.include_router(websocket.router,     prefix="/ws",                   tags=["WebSocket"])


app.mount("/media", StaticFiles(directory=str(settings.MEDIA_ROOT)), name="media")


@app.get("/health", tags=["Health"])
async def health():
    return {"status": "ok", "app": settings.APP_NAME}


@app.exception_handler(Exception)
async def global_exc(request, exc):
    logger.error("Unhandled", error=str(exc), path=request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})
