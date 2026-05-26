from __future__ import annotations

"""
Pydantic Schemas for Lightning Bot API

All request/response models matching the UI spec screens.
"""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


# =============================================================================
# Enums
# =============================================================================


class SignalDirection(str, Enum):
    """Signal direction (buy/sell)."""
    BUY = "buy"
    SELL = "sell"
    LONG = "long"
    SHORT = "short"


class SignalStatus(str, Enum):
    """Signal status."""
    ACTIVE = "active"
    EXECUTED = "executed"
    SKIPPED = "skipped"
    EXPIRED = "expired"


class TradeStatus(str, Enum):
    """Trade status."""
    OPEN = "open"
    CLOSED = "closed"
    PENDING = "pending"
    CANCELLED = "cancelled"


class TradeResult(str, Enum):
    """Trade result."""
    WIN = "win"
    LOSS = "loss"
    BREAKEVEN = "breakeven"


class EngineComponentStatus(str, Enum):
    """Engine component status."""
    RUNNING = "running"
    STOPPED = "stopped"
    ERROR = "error"
    DEGRADED = "degraded"


class EngineStatus(str, Enum):
    """Overall engine status."""
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"
    EMERGENCY_STOP = "emergency_stop"


# =============================================================================
# Dashboard Schemas
# =============================================================================


class MLSignal(BaseModel):
    """ML signal for dashboard display."""
    pair: str = Field(..., description="Trading pair (e.g., EUR/USD)")
    direction: SignalDirection = Field(..., description="Signal direction")
    confidence: float = Field(..., ge=0, le=100, description="Confidence percentage")
    entry_price: float = Field(..., description="Suggested entry price")
    stop_loss: float = Field(..., description="Suggested stop loss")
    take_profit: float = Field(..., description="Suggested take profit")
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class OpenPosition(BaseModel):
    """Open position for dashboard display."""
    id: str = Field(..., description="Position ID")
    pair: str = Field(..., description="Trading pair")
    direction: SignalDirection = Field(..., description="Position direction")
    entry_price: float = Field(..., description="Entry price")
    current_price: float = Field(..., description="Current market price")
    units: float = Field(..., description="Position size in units")
    unrealized_pnl: float = Field(..., description="Unrealized P/L")
    unrealized_pnl_pct: float = Field(..., description="Unrealized P/L percentage")
    stop_loss: Optional[float] = Field(None, description="Stop loss price")
    take_profit: Optional[float] = Field(None, description="Take profit price")
    opened_at: datetime = Field(..., description="Position open time")


class BalancePoint(BaseModel):
    """Balance history data point."""
    timestamp: datetime = Field(..., description="Data point timestamp")
    balance: float = Field(..., description="Account balance")
    equity: float = Field(..., description="Account equity (balance + unrealized P/L)")


class DashboardResponse(BaseModel):
    """Dashboard overview response."""
    balance: float = Field(..., description="Current account balance")
    equity: float = Field(..., description="Account equity")
    today_pnl: float = Field(..., description="Today's realized P/L")
    today_pnl_pct: float = Field(..., description="Today's P/L as percentage")
    win_rate: float = Field(..., ge=0, le=100, description="Win rate percentage")
    total_trades: int = Field(..., ge=0, description="Total trades today")
    open_positions_count: int = Field(..., ge=0, description="Number of open positions")
    ml_signals: List[MLSignal] = Field(default_factory=list, description="Active ML signals")
    open_positions: List[OpenPosition] = Field(default_factory=list, description="Open positions")
    last_updated: datetime = Field(default_factory=datetime.utcnow)


# =============================================================================
# Signal Schemas
# =============================================================================


class SignalResponse(BaseModel):
    """Signal summary response."""
    id: str = Field(..., description="Signal ID")
    pair: str = Field(..., description="Trading pair")
    direction: SignalDirection = Field(..., description="Signal direction")
    confidence: float = Field(..., ge=0, le=100, description="ML confidence")
    entry_price: float = Field(..., description="Entry price")
    stop_loss: float = Field(..., description="Stop loss")
    take_profit: float = Field(..., description="Take profit")
    risk_reward_ratio: float = Field(..., description="Risk/reward ratio")
    status: SignalStatus = Field(..., description="Signal status")
    strategy: str = Field(..., description="Strategy that generated the signal")
    created_at: datetime = Field(..., description="Signal creation time")
    expires_at: Optional[datetime] = Field(None, description="Signal expiration time")


class SignalFeatures(BaseModel):
    """ML features that contributed to the signal."""
    rsi: Optional[float] = Field(None, description="RSI value")
    macd: Optional[float] = Field(None, description="MACD value")
    macd_signal: Optional[float] = Field(None, description="MACD signal line")
    bb_position: Optional[float] = Field(None, description="Bollinger Band position")
    atr: Optional[float] = Field(None, description="ATR value")
    volume_ratio: Optional[float] = Field(None, description="Volume ratio")
    trend_strength: Optional[float] = Field(None, description="Trend strength score")
    support_level: Optional[float] = Field(None, description="Nearest support level")
    resistance_level: Optional[float] = Field(None, description="Nearest resistance level")


class SignalDetailResponse(BaseModel):
    """Detailed signal information."""
    id: str
    pair: str
    direction: SignalDirection
    confidence: float
    entry_price: float
    stop_loss: float
    take_profit: float
    risk_reward_ratio: float
    status: SignalStatus
    strategy: str
    created_at: datetime
    expires_at: Optional[datetime] = None

    # Additional details
    features: SignalFeatures = Field(..., description="ML features")
    model_version: str = Field(..., description="ML model version used")
    feature_importance: dict = Field(default_factory=dict, description="Feature importance scores")
    similar_historical_trades: int = Field(0, description="Count of similar historical trades")
    historical_win_rate: Optional[float] = Field(None, description="Win rate of similar trades")
    notes: Optional[str] = Field(None, description="Additional notes")


class ExecutionRequest(BaseModel):
    """Signal execution request."""
    position_size: Optional[float] = Field(None, description="Override position size")
    adjust_stop_loss: Optional[float] = Field(None, description="Custom stop loss")
    adjust_take_profit: Optional[float] = Field(None, description="Custom take profit")


class ExecutionResponse(BaseModel):
    """Signal execution response."""
    success: bool = Field(..., description="Whether execution succeeded")
    signal_id: str = Field(..., description="Signal ID")
    trade_id: Optional[str] = Field(None, description="Resulting trade ID")
    executed_price: Optional[float] = Field(None, description="Actual execution price")
    slippage: Optional[float] = Field(None, description="Slippage from entry price")
    message: str = Field(..., description="Execution message")
    executed_at: Optional[datetime] = Field(None, description="Execution timestamp")


class SkipResponse(BaseModel):
    """Skip signal response."""
    success: bool = Field(..., description="Whether skip succeeded")
    signal_id: str = Field(..., description="Signal ID")
    message: str = Field(..., description="Skip message")


# =============================================================================
# Engine Schemas
# =============================================================================


class EngineComponent(BaseModel):
    """Engine component status."""
    name: str = Field(..., description="Component name")
    status: EngineComponentStatus = Field(..., description="Component status")
    last_heartbeat: Optional[datetime] = Field(None, description="Last heartbeat time")
    message: Optional[str] = Field(None, description="Status message")
    metrics: dict = Field(default_factory=dict, description="Component metrics")


class EngineStatusResponse(BaseModel):
    """Engine status response."""
    status: EngineStatus = Field(..., description="Overall engine status")
    uptime_seconds: int = Field(..., description="Engine uptime in seconds")
    started_at: Optional[datetime] = Field(None, description="Engine start time")

    # Component statuses
    websocket_feed: EngineComponent = Field(..., description="WebSocket feed status")
    feature_engine: EngineComponent = Field(..., description="Feature engine status")
    ml_classifier: EngineComponent = Field(..., description="ML classifier status")
    risk_manager: EngineComponent = Field(..., description="Risk manager status")
    order_executor: EngineComponent = Field(..., description="Order executor status")
    logger: EngineComponent = Field(..., description="Logger status")

    # Overall metrics
    signals_generated_today: int = Field(0, description="Signals generated today")
    trades_executed_today: int = Field(0, description="Trades executed today")
    errors_today: int = Field(0, description="Errors encountered today")
    last_signal_at: Optional[datetime] = Field(None, description="Last signal timestamp")
    last_trade_at: Optional[datetime] = Field(None, description="Last trade timestamp")


class StatusResponse(BaseModel):
    """Generic status response."""
    success: bool = Field(..., description="Operation success")
    status: EngineStatus = Field(..., description="Current engine status")
    message: str = Field(..., description="Status message")
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# =============================================================================
# Trade History Schemas
# =============================================================================


class TradeResponse(BaseModel):
    """Trade summary response."""
    id: str = Field(..., description="Trade ID")
    pair: str = Field(..., description="Trading pair")
    direction: SignalDirection = Field(..., description="Trade direction")
    status: TradeStatus = Field(..., description="Trade status")
    entry_price: float = Field(..., description="Entry price")
    exit_price: Optional[float] = Field(None, description="Exit price")
    units: float = Field(..., description="Position size")
    pnl: Optional[float] = Field(None, description="Realized P/L")
    pnl_pct: Optional[float] = Field(None, description="P/L percentage")
    result: Optional[TradeResult] = Field(None, description="Trade result")
    opened_at: datetime = Field(..., description="Trade open time")
    closed_at: Optional[datetime] = Field(None, description="Trade close time")
    signal_id: Optional[str] = Field(None, description="Originating signal ID")


class TradeDetailResponse(BaseModel):
    """Detailed trade information."""
    id: str
    pair: str
    direction: SignalDirection
    status: TradeStatus
    entry_price: float
    exit_price: Optional[float] = None
    units: float
    pnl: Optional[float] = None
    pnl_pct: Optional[float] = None
    result: Optional[TradeResult] = None
    opened_at: datetime
    closed_at: Optional[datetime] = None
    signal_id: Optional[str] = None

    # Additional details
    stop_loss: Optional[float] = Field(None, description="Stop loss price")
    take_profit: Optional[float] = Field(None, description="Take profit price")
    initial_stop_loss: Optional[float] = Field(None, description="Initial stop loss")
    initial_take_profit: Optional[float] = Field(None, description="Initial take profit")
    max_favorable_excursion: Optional[float] = Field(None, description="Maximum favorable price movement")
    max_adverse_excursion: Optional[float] = Field(None, description="Maximum adverse price movement")
    slippage: Optional[float] = Field(None, description="Entry slippage")
    fees: Optional[float] = Field(None, description="Trading fees")
    strategy: Optional[str] = Field(None, description="Strategy used")
    notes: Optional[str] = Field(None, description="Trade notes")

    # Signal details
    signal_confidence: Optional[float] = Field(None, description="Original signal confidence")
    signal_features: Optional[SignalFeatures] = Field(None, description="Signal features")


class PerformanceMetrics(BaseModel):
    """Performance metrics."""
    total_trades: int = Field(0, description="Total number of trades")
    winning_trades: int = Field(0, description="Number of winning trades")
    losing_trades: int = Field(0, description="Number of losing trades")
    breakeven_trades: int = Field(0, description="Number of breakeven trades")

    win_rate: float = Field(0, description="Win rate percentage")
    profit_factor: Optional[float] = Field(None, description="Profit factor")

    total_pnl: float = Field(0, description="Total realized P/L")
    average_win: Optional[float] = Field(None, description="Average winning trade P/L")
    average_loss: Optional[float] = Field(None, description="Average losing trade P/L")
    largest_win: Optional[float] = Field(None, description="Largest winning trade")
    largest_loss: Optional[float] = Field(None, description="Largest losing trade")

    average_trade_duration_minutes: Optional[float] = Field(None, description="Avg trade duration")
    max_consecutive_wins: int = Field(0, description="Max consecutive wins")
    max_consecutive_losses: int = Field(0, description="Max consecutive losses")

    max_drawdown: Optional[float] = Field(None, description="Maximum drawdown")
    max_drawdown_pct: Optional[float] = Field(None, description="Maximum drawdown percentage")
    sharpe_ratio: Optional[float] = Field(None, description="Sharpe ratio")


class PerformanceByPair(BaseModel):
    """Performance metrics by trading pair."""
    pair: str = Field(..., description="Trading pair")
    total_trades: int = Field(0)
    win_rate: float = Field(0)
    total_pnl: float = Field(0)
    profit_factor: Optional[float] = None


class PerformanceByStrategy(BaseModel):
    """Performance metrics by strategy."""
    strategy: str = Field(..., description="Strategy name")
    total_trades: int = Field(0)
    win_rate: float = Field(0)
    total_pnl: float = Field(0)
    profit_factor: Optional[float] = None


class PerformanceResponse(BaseModel):
    """Performance overview response."""
    period_days: int = Field(..., description="Performance period in days")
    start_date: datetime = Field(..., description="Period start date")
    end_date: datetime = Field(..., description="Period end date")

    overall: PerformanceMetrics = Field(..., description="Overall performance metrics")
    by_pair: List[PerformanceByPair] = Field(default_factory=list, description="Performance by pair")
    by_strategy: List[PerformanceByStrategy] = Field(default_factory=list, description="Performance by strategy")

    equity_curve: List[BalancePoint] = Field(default_factory=list, description="Equity curve data")
    daily_pnl: List[dict] = Field(default_factory=list, description="Daily P/L data")


# =============================================================================
# Settings Schemas
# =============================================================================


class RiskSettings(BaseModel):
    """Risk management settings."""
    risk_per_trade_pct: float = Field(2.0, ge=0.1, le=10.0, description="Risk per trade %")
    max_leverage: int = Field(10, ge=1, le=100, description="Maximum leverage")
    min_confidence_threshold: float = Field(70.0, ge=0, le=100, description="Min confidence %")
    max_drawdown_pct: float = Field(20.0, ge=1, le=50, description="Max drawdown %")
    max_open_positions: int = Field(5, ge=1, le=20, description="Max open positions")
    daily_loss_limit_pct: float = Field(5.0, ge=1, le=20, description="Daily loss limit %")


class NotificationSettings(BaseModel):
    """Notification settings."""
    telegram_enabled: bool = Field(True, description="Enable Telegram notifications")
    telegram_chat_id: Optional[str] = Field(None, description="Telegram chat ID")
    notify_on_signal: bool = Field(True, description="Notify on new signals")
    notify_on_trade: bool = Field(True, description="Notify on trade execution")
    notify_on_close: bool = Field(True, description="Notify on position close")
    notify_on_error: bool = Field(True, description="Notify on errors")


class TradingSettings(BaseModel):
    """Trading behavior settings."""
    auto_execute: bool = Field(False, description="Auto-execute signals")
    trading_hours_only: bool = Field(True, description="Trade only during market hours")
    market_hours_start: str = Field("08:00", description="Market hours start (UTC)")
    market_hours_end: str = Field("20:00", description="Market hours end (UTC)")
    avoid_news_events: bool = Field(True, description="Avoid trading during news")
    default_position_size_pct: float = Field(1.0, ge=0.1, le=10, description="Default position size %")


class SettingsResponse(BaseModel):
    """Full settings response."""
    risk: RiskSettings = Field(..., description="Risk settings")
    notifications: NotificationSettings = Field(..., description="Notification settings")
    trading: TradingSettings = Field(..., description="Trading settings")
    last_updated: datetime = Field(default_factory=datetime.utcnow)


class SettingsUpdate(BaseModel):
    """Settings update request."""
    risk: Optional[RiskSettings] = Field(None, description="Risk settings to update")
    notifications: Optional[NotificationSettings] = Field(None, description="Notification settings to update")
    trading: Optional[TradingSettings] = Field(None, description="Trading settings to update")


class AssetSetting(BaseModel):
    """Asset trading settings."""
    asset: str = Field(..., description="Asset/pair name")
    enabled: bool = Field(True, description="Whether trading is enabled")
    max_position_size: Optional[float] = Field(None, description="Max position size")
    custom_risk_pct: Optional[float] = Field(None, description="Custom risk percentage")
    strategies: List[str] = Field(default_factory=list, description="Enabled strategies")


class AssetToggleRequest(BaseModel):
    """Asset toggle request."""
    enabled: bool = Field(..., description="Enable or disable trading")


# =============================================================================
# WebSocket Schemas
# =============================================================================


class WSMessageType(str, Enum):
    """WebSocket message types."""
    PRICE_UPDATE = "price_update"
    SIGNAL_NEW = "signal_new"
    SIGNAL_UPDATE = "signal_update"
    POSITION_OPEN = "position_open"
    POSITION_UPDATE = "position_update"
    POSITION_CLOSE = "position_close"
    BALANCE_UPDATE = "balance_update"
    ENGINE_STATUS = "engine_status"
    ERROR = "error"
    HEARTBEAT = "heartbeat"


class WSPriceUpdate(BaseModel):
    """WebSocket price update message."""
    type: WSMessageType = WSMessageType.PRICE_UPDATE
    pair: str
    bid: float
    ask: float
    timestamp: datetime


class WSSignalMessage(BaseModel):
    """WebSocket signal message."""
    type: WSMessageType
    signal: SignalResponse


class WSPositionMessage(BaseModel):
    """WebSocket position message."""
    type: WSMessageType
    position: OpenPosition


class WSBalanceUpdate(BaseModel):
    """WebSocket balance update message."""
    type: WSMessageType = WSMessageType.BALANCE_UPDATE
    balance: float
    equity: float
    unrealized_pnl: float
    timestamp: datetime


class WSEngineStatus(BaseModel):
    """WebSocket engine status message."""
    type: WSMessageType = WSMessageType.ENGINE_STATUS
    status: EngineStatus
    message: Optional[str] = None
    timestamp: datetime


class WSError(BaseModel):
    """WebSocket error message."""
    type: WSMessageType = WSMessageType.ERROR
    error: str
    code: Optional[str] = None
    timestamp: datetime


class WSHeartbeat(BaseModel):
    """WebSocket heartbeat message."""
    type: WSMessageType = WSMessageType.HEARTBEAT
    timestamp: datetime
