"""
Lightning Bot API Module

FastAPI-based REST API for the automated trading bot, providing:

Endpoints:
- /api/v1/dashboard: Dashboard overview with balance, P/L, positions
- /api/v1/balance-history: Historical balance data
- /api/v1/signals: ML trading signals with execute/skip actions
- /api/v1/engine: Engine status, pause, resume, emergency stop
- /api/v1/trades: Trade history with filters
- /api/v1/performance: Performance analytics
- /api/v1/settings: Bot configuration

WebSocket:
- /ws: Real-time price updates, signals, positions, balance

Features:
- CORS enabled for React Native
- Pydantic request/response validation
- OpenAPI documentation at /docs
- WebSocket for real-time streaming
"""

from typing import TYPE_CHECKING

# Import main app
from .main import app, create_app

# Import schemas for external use
from .schemas import (
    # Dashboard
    DashboardResponse,
    BalancePoint,
    MLSignal,
    OpenPosition,
    # Signals
    SignalResponse,
    SignalDetailResponse,
    ExecutionResponse,
    SkipResponse,
    # Engine
    EngineStatusResponse,
    EngineComponent,
    StatusResponse,
    # Trades
    TradeResponse,
    TradeDetailResponse,
    PerformanceResponse,
    PerformanceMetrics,
    # Settings
    SettingsResponse,
    SettingsUpdate,
    RiskSettings,
    NotificationSettings,
    TradingSettings,
    AssetSetting,
    # WebSocket
    WSMessageType,
    WSPriceUpdate,
    WSBalanceUpdate,
)

# Import routes
from .routes import dashboard, signals, engine, history, settings

# Import WebSocket utilities
from .websocket import (
    manager as ws_manager,
    broadcast_price_update,
    broadcast_new_signal,
    broadcast_position_update,
    broadcast_balance_update,
    broadcast_engine_status,
)

__all__ = [
    # Application
    "app",
    "create_app",
    # Dashboard schemas
    "DashboardResponse",
    "BalancePoint",
    "MLSignal",
    "OpenPosition",
    # Signal schemas
    "SignalResponse",
    "SignalDetailResponse",
    "ExecutionResponse",
    "SkipResponse",
    # Engine schemas
    "EngineStatusResponse",
    "EngineComponent",
    "StatusResponse",
    # Trade schemas
    "TradeResponse",
    "TradeDetailResponse",
    "PerformanceResponse",
    "PerformanceMetrics",
    # Settings schemas
    "SettingsResponse",
    "SettingsUpdate",
    "RiskSettings",
    "NotificationSettings",
    "TradingSettings",
    "AssetSetting",
    # WebSocket
    "WSMessageType",
    "WSPriceUpdate",
    "WSBalanceUpdate",
    "ws_manager",
    "broadcast_price_update",
    "broadcast_new_signal",
    "broadcast_position_update",
    "broadcast_balance_update",
    "broadcast_engine_status",
    # Route modules
    "dashboard",
    "signals",
    "engine",
    "history",
    "settings",
]
