from __future__ import annotations

"""
Lightning Bot API - FastAPI Application

Main FastAPI application with CORS middleware and route registration.
"""

import logging
from contextlib import asynccontextmanager
from datetime import datetime
from typing import AsyncGenerator

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from .routes import autopilot, dashboard, engine, history, intelligence, lab, learning, live_trading, paper_trading, predictions, settings, signals, wallet
from .websocket import router as websocket_router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


# =============================================================================
# Application State
# =============================================================================


class AppState:
    """Application state container."""

    def __init__(self):
        self.started_at: datetime = datetime.utcnow()
        self.engine_status: str = "stopped"
        self.connected_websockets: list = []

    @property
    def uptime_seconds(self) -> int:
        """Get uptime in seconds."""
        return int((datetime.utcnow() - self.started_at).total_seconds())


app_state = AppState()


# =============================================================================
# Lifespan Management
# =============================================================================


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """
    Application lifespan manager.

    Handles startup and shutdown events.
    """
    # Startup
    logger.info("Lightning Bot API starting up...")
    app_state.started_at = datetime.utcnow()
    app_state.engine_status = "running"

    # Start the autopilot self-testing loop (disable with AUTOPILOT_ENABLED=false)
    from ..services.autopilot import get_autopilot

    autopilot_engine = get_autopilot()
    if autopilot_engine.enabled:
        autopilot_engine.start()

    logger.info("Lightning Bot API ready")

    yield

    # Shutdown
    logger.info("Lightning Bot API shutting down...")

    await autopilot_engine.stop()

    # Close all WebSocket connections
    for ws in app_state.connected_websockets:
        try:
            await ws.close()
        except Exception:
            pass

    # TODO: Close database connections
    # TODO: Close broker connections
    # TODO: Stop background tasks

    logger.info("Lightning Bot API shutdown complete")


# =============================================================================
# FastAPI Application
# =============================================================================


app = FastAPI(
    title="Lightning Bot API",
    description="""
    REST API for Lightning Bot - Automated Trading System

    ## Features
    - Real-time dashboard with balance, P/L, and open positions
    - ML-powered trading signals with execution
    - Engine status monitoring and control
    - Trade history and performance analytics
    - Configurable settings and risk management
    - WebSocket for real-time updates

    ## Authentication
    Currently using CORS with allowed origins. JWT authentication planned.
    """,
    version="1.0.1",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)


# =============================================================================
# CORS Middleware
# =============================================================================


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "*",  # Allow all origins for React Native development
        "http://localhost:3000",
        "http://localhost:8081",
        "http://localhost:19000",
        "http://localhost:19006",
        "exp://localhost:19000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)


# =============================================================================
# Exception Handlers
# =============================================================================


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "detail": str(exc) if app.debug else "An unexpected error occurred",
            "timestamp": datetime.utcnow().isoformat(),
        },
    )


# =============================================================================
# Root Endpoints
# =============================================================================


HUB_HTML = Path(__file__).parent / "static" / "hub.html"


@app.get("/", tags=["Hub"], include_in_schema=False)
async def root():
    """Serve the Clockwork trading hub."""
    return FileResponse(HUB_HTML, media_type="text/html")


@app.get("/hub", tags=["Hub"], include_in_schema=False)
async def hub():
    """Serve the Clockwork trading hub (alias)."""
    return FileResponse(HUB_HTML, media_type="text/html")


@app.get("/api", tags=["Health"])
async def api_info():
    """API information."""
    return {
        "name": "Clockwork Trading API",
        "version": "1.0.0",
        "status": "operational",
        "docs": "/docs",
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "uptime_seconds": app_state.uptime_seconds,
        "engine_status": app_state.engine_status,
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.get("/ping", tags=["Health"])
async def ping():
    """Simple ping endpoint for connectivity check."""
    return {"pong": True, "timestamp": datetime.utcnow().isoformat()}


# =============================================================================
# Route Registration
# =============================================================================


# Dashboard routes
app.include_router(
    dashboard.router,
    prefix="/api/v1",
    tags=["Dashboard"],
)

# Signal routes
app.include_router(
    signals.router,
    prefix="/api/v1",
    tags=["Signals"],
)

# Engine routes
app.include_router(
    engine.router,
    prefix="/api/v1",
    tags=["Engine"],
)

# History routes
app.include_router(
    history.router,
    prefix="/api/v1",
    tags=["History"],
)

# Settings routes
app.include_router(
    settings.router,
    prefix="/api/v1",
    tags=["Settings"],
)

# Wallet routes
app.include_router(
    wallet.router,
    prefix="/api/v1",
    tags=["Wallet"],
)

# Predictions routes
app.include_router(
    predictions.router,
    prefix="/api/v1",
    tags=["Predictions"],
)

# Intelligence routes
app.include_router(
    intelligence.router,
    prefix="/api/v1",
    tags=["Intelligence"],
)

# Paper Trading routes
app.include_router(
    paper_trading.router,
    prefix="/api/v1",
    tags=["Paper Trading"],
)

# Live Trading routes (OANDA)
app.include_router(
    live_trading.router,
    prefix="/api/v1",
    tags=["Live Trading"],
)

# Learning routes
app.include_router(
    learning.router,
    prefix="/api/v1",
    tags=["Learning"],
)

# Autopilot routes (autonomous self-testing)
app.include_router(
    autopilot.router,
    prefix="/api/v1",
    tags=["Autopilot"],
)

# Strategy Lab routes (mass strategy testing)
app.include_router(
    lab.router,
    prefix="/api/v1",
    tags=["Strategy Lab"],
)

# WebSocket routes
app.include_router(
    websocket_router,
    tags=["WebSocket"],
)


# =============================================================================
# Application Factory
# =============================================================================


def create_app() -> FastAPI:
    """
    Application factory function.

    Returns:
        Configured FastAPI application instance.
    """
    return app


# =============================================================================
# Run Configuration
# =============================================================================


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )
