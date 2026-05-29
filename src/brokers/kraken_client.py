from __future__ import annotations

"""
Kraken Futures Client Integration

Production-ready Kraken Futures client with async support,
WebSocket streaming, tiered leverage, and circuit breaker protection.

Author: HERMES Trading System
"""

import asyncio
import base64
import hashlib
import hmac
import logging
import time
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Union
from urllib.parse import urlencode

import aiohttp
import pandas as pd
from pydantic import BaseModel, Field, validator
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)


# =============================================================================
# LOGGING CONFIGURATION
# =============================================================================

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
    )
    logger.addHandler(handler)


# =============================================================================
# CONSTANTS
# =============================================================================

# Kraken Futures URLs
DEMO_URL = "https://demo-futures.kraken.com"
LIVE_URL = "https://futures.kraken.com"

DEMO_WS_URL = "wss://demo-futures.kraken.com/ws/v1"
LIVE_WS_URL = "wss://futures.kraken.com/ws/v1"

# Supported perpetual contracts
SUPPORTED_SYMBOLS = [
    "PF_XBTUSD",   # BTC/USD Perpetual
    "PF_ETHUSD",   # ETH/USD Perpetual
    "PF_XRPUSD",   # XRP/USD Perpetual
    "PF_SOLUSD",   # SOL/USD Perpetual
    "PF_LTCUSD",   # LTC/USD Perpetual
    "PF_BCHUSD",   # BCH/USD Perpetual
    "PF_AVAXUSD",  # AVAX/USD Perpetual
    "PF_DOGEUSD",  # DOGE/USD Perpetual
    "PF_LINKUSD",  # LINK/USD Perpetual
    "PF_MATICUSD", # MATIC/USD Perpetual
]

# API Endpoints
ENDPOINTS = {
    # Account
    "accounts": "/derivatives/api/v3/accounts",
    "openpositions": "/derivatives/api/v3/openpositions",
    "notifications": "/derivatives/api/v3/notifications",

    # Orders
    "sendorder": "/derivatives/api/v3/sendorder",
    "cancelorder": "/derivatives/api/v3/cancelorder",
    "cancelallorders": "/derivatives/api/v3/cancelallorders",
    "openorders": "/derivatives/api/v3/openorders",
    "orders": "/derivatives/api/v3/orders",
    "fills": "/derivatives/api/v3/fills",

    # Market Data
    "tickers": "/derivatives/api/v3/tickers",
    "orderbook": "/derivatives/api/v3/orderbook",
    "history": "/derivatives/api/v3/history",
    "instruments": "/derivatives/api/v3/instruments",

    # Leverage
    "leverage": "/derivatives/api/v3/leveragepreferences",
}

# Interval mappings for candles
INTERVAL_MAP = {
    "1m": "1m",
    "5m": "5m",
    "15m": "15m",
    "30m": "30m",
    "1h": "1h",
    "4h": "4h",
    "12h": "12h",
    "1d": "1d",
    "1w": "1w",
}


# =============================================================================
# ENUMS
# =============================================================================


class OrderSide(str, Enum):
    BUY = "buy"
    SELL = "sell"


class OrderType(str, Enum):
    LIMIT = "lmt"
    MARKET = "mkt"
    STOP = "stp"
    TAKE_PROFIT = "take_profit"
    STOP_LOSS = "stop_loss"
    TRAILING_STOP = "trailing_stop"


class OrderStatus(str, Enum):
    PLACED = "placed"
    UNTOUCHED = "untouched"
    PARTIALLY_FILLED = "partiallyFilled"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


class PositionSide(str, Enum):
    LONG = "long"
    SHORT = "short"


class MarginMode(str, Enum):
    CROSS = "cross"
    ISOLATED = "isolated"


# =============================================================================
# EXCEPTIONS
# =============================================================================


class KrakenError(Exception):
    """Base exception for Kraken-related errors."""

    def __init__(self, message: str, code: Optional[str] = None):
        self.message = message
        self.code = code
        super().__init__(self.message)


class InsufficientMarginError(KrakenError):
    """Raised when account has insufficient margin."""

    def __init__(self, message: str = "Insufficient margin"):
        super().__init__(message, code="insufficientMargin")


class LeverageError(KrakenError):
    """Raised when leverage operation fails."""

    def __init__(self, message: str = "Leverage operation failed"):
        super().__init__(message, code="leverageError")


class InvalidSymbolError(KrakenError):
    """Raised when an invalid symbol is used."""

    def __init__(self, symbol: str):
        super().__init__(f"Invalid symbol: {symbol}", code="invalidSymbol")


class OrderError(KrakenError):
    """Raised when order placement fails."""

    def __init__(self, message: str, code: Optional[str] = None):
        super().__init__(message, code)


class AuthenticationError(KrakenError):
    """Raised when authentication fails."""

    def __init__(self, message: str = "Authentication failed"):
        super().__init__(message, code="authenticationError")


class RateLimitError(KrakenError):
    """Raised when rate limit is exceeded."""

    def __init__(self, message: str = "Rate limit exceeded"):
        super().__init__(message, code="rateLimitExceeded")


class ConnectionError(KrakenError):
    """Raised when connection fails."""

    def __init__(self, message: str = "Connection failed"):
        super().__init__(message, code="connectionError")


# =============================================================================
# DATA MODELS
# =============================================================================


class Position(BaseModel):
    """Represents an open futures position."""

    symbol: str = Field(..., description="Trading pair symbol")
    side: PositionSide = Field(..., description="Position side (long/short)")
    size: float = Field(..., description="Position size in contracts")
    entry_price: float = Field(..., ge=0, description="Average entry price")
    mark_price: float = Field(default=0.0, ge=0, description="Current mark price")
    liquidation_price: float = Field(default=0.0, ge=0, description="Liquidation price")
    unrealized_pnl: float = Field(default=0.0, description="Unrealized PnL in USD")
    realized_pnl: float = Field(default=0.0, description="Realized PnL in USD")
    leverage: float = Field(default=1.0, ge=1, description="Effective leverage")
    margin: float = Field(default=0.0, description="Position margin")
    margin_mode: MarginMode = Field(default=MarginMode.CROSS, description="Margin mode")

    @property
    def is_long(self) -> bool:
        return self.side == PositionSide.LONG

    @property
    def is_short(self) -> bool:
        return self.side == PositionSide.SHORT

    @property
    def notional_value(self) -> float:
        return abs(self.size * self.mark_price)

    @property
    def pnl_percentage(self) -> float:
        if self.entry_price == 0 or self.size == 0:
            return 0.0
        if self.is_long:
            return ((self.mark_price - self.entry_price) / self.entry_price) * 100
        else:
            return ((self.entry_price - self.mark_price) / self.entry_price) * 100

    class Config:
        use_enum_values = True


class Order(BaseModel):
    """Represents a trading order."""

    id: str = Field(..., description="Order ID")
    symbol: str = Field(..., description="Trading pair symbol")
    side: OrderSide = Field(..., description="Order side")
    size: float = Field(..., gt=0, description="Order size")
    status: OrderStatus = Field(..., description="Order status")
    order_type: OrderType = Field(..., description="Order type")
    limit_price: Optional[float] = Field(None, ge=0, description="Limit price")
    stop_price: Optional[float] = Field(None, ge=0, description="Stop price")
    fill_price: Optional[float] = Field(None, ge=0, description="Average fill price")
    filled_size: float = Field(default=0.0, description="Filled quantity")
    reduce_only: bool = Field(default=False, description="Reduce only flag")
    client_order_id: Optional[str] = Field(None, description="Client order ID")
    created_at: Optional[datetime] = Field(None, description="Creation time")
    updated_at: Optional[datetime] = Field(None, description="Last update time")

    @property
    def is_filled(self) -> bool:
        return self.status == OrderStatus.FILLED

    @property
    def is_active(self) -> bool:
        return self.status in [OrderStatus.PLACED, OrderStatus.UNTOUCHED, OrderStatus.PARTIALLY_FILLED]

    class Config:
        use_enum_values = True


class Ticker(BaseModel):
    """Real-time ticker data."""

    symbol: str
    bid: float
    ask: float
    last: float
    mark_price: float
    index_price: float
    funding_rate: float
    open_interest: float
    volume_24h: float
    change_24h: float
    timestamp: datetime


class AccountSummary(BaseModel):
    """Account summary with balance and margin info."""

    balance: float = Field(..., description="Total balance in USD")
    available_margin: float = Field(..., description="Available margin")
    initial_margin: float = Field(default=0.0, description="Initial margin used")
    maintenance_margin: float = Field(default=0.0, description="Maintenance margin")
    unrealized_pnl: float = Field(default=0.0, description="Total unrealized PnL")
    realized_pnl: float = Field(default=0.0, description="Total realized PnL")
    collateral: float = Field(default=0.0, description="Collateral value")
    margin_ratio: float = Field(default=0.0, description="Margin ratio percentage")


# =============================================================================
# CIRCUIT BREAKER
# =============================================================================


class CircuitBreaker:
    """
    Circuit breaker for risk management.

    Trips when:
    - Daily loss exceeds threshold
    - Consecutive losses exceed limit
    - Drawdown exceeds maximum
    """

    def __init__(
        self,
        max_daily_loss_pct: float = 5.0,
        max_consecutive_losses: int = 5,
        max_drawdown_pct: float = 15.0,
        cooldown_minutes: int = 30,
    ):
        self.max_daily_loss_pct = max_daily_loss_pct
        self.max_consecutive_losses = max_consecutive_losses
        self.max_drawdown_pct = max_drawdown_pct
        self.cooldown_minutes = cooldown_minutes

        self._tripped = False
        self._trip_reason: Optional[str] = None
        self._trip_time: Optional[datetime] = None
        self._consecutive_losses = 0
        self._daily_pnl = 0.0
        self._peak_balance = 0.0
        self._current_balance = 0.0
        self._day_start = datetime.utcnow().date()

    def update(self, balance: float, trade_pnl: Optional[float] = None) -> None:
        """Update circuit breaker state."""
        # Reset daily stats at day change
        today = datetime.utcnow().date()
        if today != self._day_start:
            self._daily_pnl = 0.0
            self._day_start = today
            self._consecutive_losses = 0

        self._current_balance = balance
        self._peak_balance = max(self._peak_balance, balance)

        if trade_pnl is not None:
            self._daily_pnl += trade_pnl
            if trade_pnl < 0:
                self._consecutive_losses += 1
            else:
                self._consecutive_losses = 0

        self._check_triggers()

    def _check_triggers(self) -> None:
        """Check if circuit breaker should trip."""
        if self._tripped:
            # Check if cooldown has passed
            if self._trip_time and datetime.utcnow() - self._trip_time > timedelta(minutes=self.cooldown_minutes):
                self._tripped = False
                self._trip_reason = None
                self._trip_time = None
                logger.info("Circuit breaker reset after cooldown")
            return

        # Check daily loss
        if self._current_balance > 0:
            daily_loss_pct = abs(self._daily_pnl / self._current_balance) * 100
            if self._daily_pnl < 0 and daily_loss_pct >= self.max_daily_loss_pct:
                self._trip(f"Daily loss limit reached: {daily_loss_pct:.2f}%")
                return

        # Check consecutive losses
        if self._consecutive_losses >= self.max_consecutive_losses:
            self._trip(f"Consecutive losses: {self._consecutive_losses}")
            return

        # Check drawdown
        if self._peak_balance > 0:
            drawdown_pct = ((self._peak_balance - self._current_balance) / self._peak_balance) * 100
            if drawdown_pct >= self.max_drawdown_pct:
                self._trip(f"Maximum drawdown reached: {drawdown_pct:.2f}%")
                return

    def _trip(self, reason: str) -> None:
        """Trip the circuit breaker."""
        self._tripped = True
        self._trip_reason = reason
        self._trip_time = datetime.utcnow()
        logger.warning(f"CIRCUIT BREAKER TRIPPED: {reason}")

    @property
    def is_tripped(self) -> bool:
        return self._tripped

    @property
    def trip_reason(self) -> Optional[str]:
        return self._trip_reason

    def reset(self) -> None:
        """Manually reset the circuit breaker."""
        self._tripped = False
        self._trip_reason = None
        self._trip_time = None
        self._consecutive_losses = 0
        logger.info("Circuit breaker manually reset")


# =============================================================================
# TIERED LEVERAGE MANAGER
# =============================================================================


class TieredLeverage:
    """
    Manages tiered leverage based on signal confidence.

    Higher confidence signals get higher leverage for better risk-adjusted returns.
    """

    def __init__(
        self,
        tiers: Optional[List[Dict[str, Any]]] = None,
        base_risk_pct: float = 1.0,
    ):
        """
        Initialize tiered leverage.

        Args:
            tiers: List of tier configs [{min_confidence, max_confidence, leverage, risk_pct}]
            base_risk_pct: Base risk percentage per trade
        """
        self.base_risk_pct = base_risk_pct

        # Default tiers: Conservative -> Moderate -> Aggressive
        self.tiers = tiers or [
            {"min_confidence": 0, "max_confidence": 65, "leverage": 10, "risk_pct": 1.0, "name": "Conservative"},
            {"min_confidence": 65, "max_confidence": 80, "leverage": 25, "risk_pct": 2.0, "name": "Moderate"},
            {"min_confidence": 80, "max_confidence": 90, "leverage": 35, "risk_pct": 3.0, "name": "Aggressive"},
            {"min_confidence": 90, "max_confidence": 100, "leverage": 50, "risk_pct": 4.0, "name": "Max"},
        ]

    def get_tier(self, confidence: float) -> Dict[str, Any]:
        """Get the appropriate tier for a confidence level."""
        for tier in self.tiers:
            if tier["min_confidence"] <= confidence < tier["max_confidence"]:
                return tier
        # Return highest tier for 100% confidence
        return self.tiers[-1]

    def calculate_leverage(self, confidence: float) -> int:
        """Calculate leverage for a given confidence."""
        tier = self.get_tier(confidence)
        return tier["leverage"]

    def calculate_risk_pct(self, confidence: float) -> float:
        """Calculate risk percentage for a given confidence."""
        tier = self.get_tier(confidence)
        return tier["risk_pct"]

    def calculate_position_size(
        self,
        balance: float,
        confidence: float,
        entry_price: float,
        stop_loss: float,
    ) -> float:
        """
        Calculate position size based on confidence tier.

        Uses the formula: Position Size = (Balance * Risk%) / (Entry - StopLoss)
        """
        tier = self.get_tier(confidence)
        risk_amount = balance * (tier["risk_pct"] / 100)
        stop_distance = abs(entry_price - stop_loss)

        if stop_distance == 0:
            return 0.0

        position_size = risk_amount / stop_distance

        logger.info(
            f"Position sizing: confidence={confidence}%, tier={tier['name']}, "
            f"leverage={tier['leverage']}x, risk={tier['risk_pct']}%, size={position_size:.4f}"
        )

        return position_size


# =============================================================================
# KRAKEN FUTURES CLIENT
# =============================================================================


class KrakenClient:
    """
    Production-ready Kraken Futures client.

    Features:
        - Full async/await support
        - Automatic retry with exponential backoff
        - WebSocket price streaming
        - Tiered leverage based on confidence
        - Circuit breaker protection
        - Comprehensive error handling

    Example:
        >>> client = KrakenClient(api_key, api_secret, demo=True)
        >>> await client.connect()
        >>> balance = await client.get_account_balance()
        >>> print(f"Balance: ${balance}")
    """

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        demo: bool = True,
        tiered_leverage: Optional[TieredLeverage] = None,
        circuit_breaker: Optional[CircuitBreaker] = None,
    ):
        """
        Initialize Kraken Futures client.

        Args:
            api_key: Kraken API key
            api_secret: Kraken API secret (base64 encoded)
            demo: Use demo environment (default: True)
            tiered_leverage: Custom tiered leverage config
            circuit_breaker: Custom circuit breaker config
        """
        self.api_key = api_key
        self.api_secret = api_secret
        self.demo = demo

        # Set URLs based on environment
        self.base_url = DEMO_URL if demo else LIVE_URL
        self.ws_url = DEMO_WS_URL if demo else LIVE_WS_URL

        # Risk management
        self.tiered_leverage = tiered_leverage or TieredLeverage()
        self.circuit_breaker = circuit_breaker or CircuitBreaker()

        # Session management
        self._session: Optional[aiohttp.ClientSession] = None
        self._ws_connection: Optional[aiohttp.ClientWebSocketResponse] = None

        # Rate limiting
        self._last_request_time: float = 0
        self._min_request_interval: float = 0.1  # 100ms

        # Connection state
        self._connected: bool = False

        logger.info(
            f"KrakenClient initialized - Environment: {'DEMO' if demo else 'LIVE'}"
        )

    # =========================================================================
    # CONNECTION MANAGEMENT
    # =========================================================================

    async def connect(self) -> None:
        """Initialize connection to Kraken."""
        if self._connected:
            logger.warning("Client already connected")
            return

        try:
            timeout = aiohttp.ClientTimeout(total=30)
            self._session = aiohttp.ClientSession(timeout=timeout)

            # Validate connection
            await self._validate_connection()

            self._connected = True
            logger.info("Successfully connected to Kraken Futures")

        except Exception as e:
            logger.error(f"Connection failed: {e}")
            await self.disconnect()
            raise ConnectionError(f"Failed to connect: {e}")

    async def disconnect(self) -> None:
        """Close all connections."""
        if self._ws_connection:
            await self._ws_connection.close()
            self._ws_connection = None

        if self._session:
            await self._session.close()
            self._session = None

        self._connected = False
        logger.info("Disconnected from Kraken Futures")

    async def _validate_connection(self) -> None:
        """Validate API credentials."""
        try:
            await self.get_accounts()
            logger.debug("API credentials validated")
        except KrakenError as e:
            if "authentication" in str(e).lower():
                raise AuthenticationError("Invalid API credentials")
            raise

    # =========================================================================
    # REQUEST HANDLING
    # =========================================================================

    def _generate_signature(self, endpoint: str, nonce: str, post_data: str) -> str:
        """Generate API signature for authenticated requests."""
        # Kraken signature: HMAC-SHA512 of (endpoint + SHA256(nonce + postdata))
        sha256_hash = hashlib.sha256((nonce + post_data).encode()).digest()
        message = endpoint.encode() + sha256_hash

        secret_decoded = base64.b64decode(self.api_secret)
        signature = hmac.new(secret_decoded, message, hashlib.sha512)

        return base64.b64encode(signature.digest()).decode()

    async def _rate_limit(self) -> None:
        """Enforce rate limiting."""
        now = time.time()
        elapsed = now - self._last_request_time
        if elapsed < self._min_request_interval:
            await asyncio.sleep(self._min_request_interval - elapsed)
        self._last_request_time = time.time()

    @retry(
        retry=retry_if_exception_type((aiohttp.ClientError, asyncio.TimeoutError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True,
    )
    async def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        signed: bool = False,
    ) -> Dict[str, Any]:
        """Make HTTP request to Kraken API."""
        if not self._session:
            raise ConnectionError("Client not connected")

        await self._rate_limit()

        params = params or {}
        url = f"{self.base_url}{endpoint}"
        headers = {}

        if signed:
            nonce = str(int(time.time() * 1000))
            params["nonce"] = nonce
            post_data = urlencode(params)

            signature = self._generate_signature(endpoint, nonce, post_data)
            headers = {
                "API-Key": self.api_key,
                "API-Sign": signature,
                "Content-Type": "application/x-www-form-urlencoded",
            }

        try:
            if method == "GET":
                async with self._session.get(url, params=params, headers=headers) as response:
                    return await self._handle_response(response)
            elif method == "POST":
                async with self._session.post(url, data=params, headers=headers) as response:
                    return await self._handle_response(response)
            else:
                raise ValueError(f"Unsupported method: {method}")

        except aiohttp.ClientError as e:
            logger.error(f"Request failed: {e}")
            raise

    async def _handle_response(self, response: aiohttp.ClientResponse) -> Dict[str, Any]:
        """Handle API response."""
        try:
            data = await response.json()
        except Exception:
            text = await response.text()
            raise KrakenError(f"Failed to parse response: {text}")

        if response.status != 200:
            error = data.get("error", "Unknown error")
            raise KrakenError(str(error))

        # Check for API-level errors
        result = data.get("result", data)
        error = data.get("error")

        if error:
            error_str = str(error)
            if "insufficient" in error_str.lower():
                raise InsufficientMarginError(error_str)
            elif "invalid" in error_str.lower() and "symbol" in error_str.lower():
                raise InvalidSymbolError(error_str)
            elif "rate" in error_str.lower():
                raise RateLimitError(error_str)
            else:
                raise KrakenError(error_str)

        return result

    async def _signed_request(
        self, method: str, endpoint: str, params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Make signed request."""
        return await self._request(method, endpoint, params, signed=True)

    async def _public_request(
        self, method: str, endpoint: str, params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Make public request."""
        return await self._request(method, endpoint, params, signed=False)

    # =========================================================================
    # ACCOUNT METHODS
    # =========================================================================

    async def get_accounts(self) -> Dict[str, Any]:
        """Get account information."""
        return await self._signed_request("GET", ENDPOINTS["accounts"])

    async def get_account_balance(self) -> float:
        """Get total account balance in USD."""
        data = await self.get_accounts()
        accounts = data.get("accounts", {})

        # Get cash account (flex or fi_xbtusd)
        for acc_type in ["cash", "flex", "fi_xbtusd"]:
            if acc_type in accounts:
                balance = accounts[acc_type].get("balances", {})
                return float(balance.get("xbt", 0)) * await self._get_btc_price()

        return 0.0

    async def get_account_summary(self) -> AccountSummary:
        """Get comprehensive account summary."""
        data = await self.get_accounts()
        accounts = data.get("accounts", {})

        # Aggregate across account types
        total_balance = 0.0
        available_margin = 0.0
        initial_margin = 0.0
        maintenance_margin = 0.0
        unrealized_pnl = 0.0

        btc_price = await self._get_btc_price()

        for acc_type, acc_data in accounts.items():
            balances = acc_data.get("balances", {})
            xbt_balance = float(balances.get("xbt", 0))
            total_balance += xbt_balance * btc_price

            available_margin += float(acc_data.get("availableMargin", 0)) * btc_price
            initial_margin += float(acc_data.get("initialMargin", 0)) * btc_price
            maintenance_margin += float(acc_data.get("maintenanceMargin", 0)) * btc_price
            unrealized_pnl += float(acc_data.get("unrealizedFunding", 0)) * btc_price

        margin_ratio = (maintenance_margin / total_balance * 100) if total_balance > 0 else 0

        return AccountSummary(
            balance=total_balance,
            available_margin=available_margin,
            initial_margin=initial_margin,
            maintenance_margin=maintenance_margin,
            unrealized_pnl=unrealized_pnl,
            margin_ratio=margin_ratio,
        )

    async def _get_btc_price(self) -> float:
        """Get current BTC/USD price for conversions."""
        try:
            tickers = await self.get_tickers()
            for ticker in tickers:
                if ticker.get("symbol") == "PF_XBTUSD" or ticker.get("symbol") == "pi_xbtusd":
                    return float(ticker.get("markPrice", ticker.get("last", 50000)))
        except Exception:
            pass
        return 50000.0  # Fallback

    async def get_open_positions(self, symbol: Optional[str] = None) -> List[Position]:
        """Get all open positions."""
        data = await self._signed_request("GET", ENDPOINTS["openpositions"])
        positions_data = data.get("openPositions", [])

        positions = []
        for pos in positions_data:
            pos_symbol = pos.get("symbol", "")
            if symbol and pos_symbol.upper() != symbol.upper():
                continue

            size = float(pos.get("size", 0))
            if size == 0:
                continue

            side = PositionSide.LONG if size > 0 else PositionSide.SHORT

            position = Position(
                symbol=pos_symbol,
                side=side,
                size=abs(size),
                entry_price=float(pos.get("price", 0)),
                mark_price=float(pos.get("markPrice", 0)),
                liquidation_price=float(pos.get("liquidationThreshold", 0)),
                unrealized_pnl=float(pos.get("unrealizedFunding", 0)),
                leverage=float(pos.get("effectiveLeverage", 1)),
            )
            positions.append(position)

        return positions

    # =========================================================================
    # MARKET DATA
    # =========================================================================

    async def get_tickers(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get ticker data."""
        data = await self._public_request("GET", ENDPOINTS["tickers"])
        tickers = data.get("tickers", [])

        if symbol:
            return [t for t in tickers if t.get("symbol", "").upper() == symbol.upper()]
        return tickers

    async def get_ticker(self, symbol: str) -> Ticker:
        """Get ticker for a specific symbol."""
        tickers = await self.get_tickers(symbol)
        if not tickers:
            raise InvalidSymbolError(symbol)

        t = tickers[0]
        return Ticker(
            symbol=t.get("symbol"),
            bid=float(t.get("bid", 0)),
            ask=float(t.get("ask", 0)),
            last=float(t.get("last", 0)),
            mark_price=float(t.get("markPrice", 0)),
            index_price=float(t.get("indexPrice", 0)),
            funding_rate=float(t.get("fundingRate", 0)),
            open_interest=float(t.get("openInterest", 0)),
            volume_24h=float(t.get("vol24h", 0)),
            change_24h=float(t.get("change24h", 0)),
            timestamp=datetime.utcnow(),
        )

    async def get_candles(
        self,
        symbol: str,
        interval: str = "1h",
        limit: int = 100,
    ) -> pd.DataFrame:
        """Get candlestick data."""
        if interval not in INTERVAL_MAP:
            raise ValueError(f"Invalid interval: {interval}")

        params = {
            "symbol": symbol.upper(),
            "resolution": INTERVAL_MAP[interval],
            "from": int((datetime.utcnow() - timedelta(days=30)).timestamp()),
            "to": int(datetime.utcnow().timestamp()),
        }

        data = await self._public_request("GET", ENDPOINTS["history"], params)
        candles = data.get("candles", [])

        if not candles:
            return pd.DataFrame()

        df = pd.DataFrame(candles)
        df.columns = ["time", "open", "high", "low", "close", "volume"]
        df["time"] = pd.to_datetime(df["time"], unit="ms")
        df.set_index("time", inplace=True)

        for col in ["open", "high", "low", "close", "volume"]:
            df[col] = df[col].astype(float)

        return df.tail(limit)

    async def get_funding_rate(self, symbol: str) -> float:
        """Get current funding rate."""
        ticker = await self.get_ticker(symbol)
        return ticker.funding_rate

    # =========================================================================
    # ORDER METHODS
    # =========================================================================

    async def place_order(
        self,
        symbol: str,
        side: Union[OrderSide, str],
        size: float,
        order_type: Union[OrderType, str] = OrderType.MARKET,
        limit_price: Optional[float] = None,
        stop_price: Optional[float] = None,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        reduce_only: bool = False,
        confidence: Optional[float] = None,
    ) -> Order:
        """
        Place a futures order.

        Args:
            symbol: Trading pair symbol
            side: Order side
            size: Order size in contracts
            order_type: Order type
            limit_price: Limit price for limit orders
            stop_price: Stop trigger price
            stop_loss: Stop loss price (places separate order)
            take_profit: Take profit price (places separate order)
            reduce_only: Reduce only flag
            confidence: Signal confidence (for tiered leverage)
        """
        # Check circuit breaker
        if self.circuit_breaker.is_tripped:
            raise OrderError(f"Circuit breaker tripped: {self.circuit_breaker.trip_reason}")

        # Convert enums
        if isinstance(side, str):
            side = OrderSide(side.lower())
        if isinstance(order_type, str):
            order_type = OrderType(order_type.lower())

        # Apply tiered leverage if confidence provided
        if confidence is not None:
            leverage = self.tiered_leverage.calculate_leverage(confidence)
            await self.set_leverage(symbol, leverage)

        # Build order params
        params = {
            "orderType": order_type.value,
            "symbol": symbol.upper(),
            "side": side.value,
            "size": str(size),
        }

        if limit_price and order_type == OrderType.LIMIT:
            params["limitPrice"] = str(limit_price)

        if stop_price:
            params["stopPrice"] = str(stop_price)

        if reduce_only:
            params["reduceOnly"] = "true"

        logger.info(f"Placing order: {side.value} {size} {symbol} @ {order_type.value}")

        response = await self._signed_request("POST", ENDPOINTS["sendorder"], params)

        order_result = response.get("sendStatus", {})
        order_id = order_result.get("order_id", str(time.time()))

        order = Order(
            id=order_id,
            symbol=symbol,
            side=side,
            size=size,
            status=OrderStatus.PLACED,
            order_type=order_type,
            limit_price=limit_price,
            stop_price=stop_price,
            created_at=datetime.utcnow(),
        )

        logger.info(f"Order placed: {order.id}")

        # Place stop loss if specified
        if stop_loss:
            await self._place_bracket_order(
                symbol=symbol,
                side=OrderSide.SELL if side == OrderSide.BUY else OrderSide.BUY,
                size=size,
                stop_price=stop_loss,
                order_type=OrderType.STOP,
            )

        # Place take profit if specified
        if take_profit:
            await self._place_bracket_order(
                symbol=symbol,
                side=OrderSide.SELL if side == OrderSide.BUY else OrderSide.BUY,
                size=size,
                limit_price=take_profit,
                order_type=OrderType.LIMIT,
                reduce_only=True,
            )

        return order

    async def _place_bracket_order(
        self,
        symbol: str,
        side: OrderSide,
        size: float,
        stop_price: Optional[float] = None,
        limit_price: Optional[float] = None,
        order_type: OrderType = OrderType.STOP,
        reduce_only: bool = True,
    ) -> None:
        """Place a bracket order (SL/TP)."""
        params = {
            "orderType": order_type.value,
            "symbol": symbol.upper(),
            "side": side.value,
            "size": str(size),
            "reduceOnly": "true" if reduce_only else "false",
        }

        if stop_price:
            params["stopPrice"] = str(stop_price)
        if limit_price:
            params["limitPrice"] = str(limit_price)

        await self._signed_request("POST", ENDPOINTS["sendorder"], params)

    async def cancel_order(self, order_id: str) -> bool:
        """Cancel an order."""
        params = {"order_id": order_id}
        await self._signed_request("POST", ENDPOINTS["cancelorder"], params)
        logger.info(f"Order cancelled: {order_id}")
        return True

    async def cancel_all_orders(self, symbol: Optional[str] = None) -> int:
        """Cancel all open orders."""
        params = {}
        if symbol:
            params["symbol"] = symbol.upper()

        response = await self._signed_request("POST", ENDPOINTS["cancelallorders"], params)
        cancelled = response.get("cancelStatus", {}).get("cancelledOrders", [])
        count = len(cancelled)
        logger.info(f"Cancelled {count} orders")
        return count

    async def close_position(self, symbol: str, size: Optional[float] = None) -> bool:
        """Close an open position."""
        positions = await self.get_open_positions(symbol)
        if not positions:
            logger.warning(f"No open position for {symbol}")
            return False

        position = positions[0]
        close_size = size or position.size
        close_side = OrderSide.SELL if position.is_long else OrderSide.BUY

        await self.place_order(
            symbol=symbol,
            side=close_side,
            size=close_size,
            order_type=OrderType.MARKET,
            reduce_only=True,
        )

        # Update circuit breaker with P&L
        self.circuit_breaker.update(
            await self.get_account_balance(),
            position.unrealized_pnl
        )

        logger.info(f"Position closed: {symbol}")
        return True

    async def set_leverage(self, symbol: str, leverage: int) -> bool:
        """Set leverage for a symbol."""
        params = {
            "symbol": symbol.upper(),
            "maxLeverage": str(leverage),
        }

        try:
            await self._signed_request("POST", ENDPOINTS["leverage"], params)
            logger.info(f"Leverage set: {symbol} = {leverage}x")
            return True
        except KrakenError as e:
            raise LeverageError(str(e))

    # =========================================================================
    # WEBSOCKET STREAMING
    # =========================================================================

    async def stream_prices(
        self,
        symbols: List[str],
        callback: Callable[[str, float, datetime], None],
    ) -> None:
        """Stream real-time prices via WebSocket."""
        logger.info(f"Starting price stream for: {symbols}")

        try:
            async with aiohttp.ClientSession() as session:
                async with session.ws_connect(self.ws_url) as ws:
                    self._ws_connection = ws

                    # Subscribe to ticker feed
                    subscribe_msg = {
                        "event": "subscribe",
                        "feed": "ticker",
                        "product_ids": [s.upper() for s in symbols],
                    }
                    await ws.send_json(subscribe_msg)

                    async for msg in ws:
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            data = msg.json()

                            if data.get("feed") == "ticker":
                                symbol = data.get("product_id", "")
                                price = float(data.get("markPrice", data.get("last", 0)))
                                timestamp = datetime.utcnow()

                                if asyncio.iscoroutinefunction(callback):
                                    await callback(symbol, price, timestamp)
                                else:
                                    callback(symbol, price, timestamp)

                        elif msg.type == aiohttp.WSMsgType.ERROR:
                            logger.error(f"WebSocket error: {msg.data}")
                            break

        except asyncio.CancelledError:
            logger.info("Price stream cancelled")
        except Exception as e:
            logger.error(f"Price stream error: {e}")
            raise
        finally:
            self._ws_connection = None

    # =========================================================================
    # UTILITY METHODS
    # =========================================================================

    async def get_instruments(self) -> List[Dict[str, Any]]:
        """Get available trading instruments."""
        data = await self._public_request("GET", ENDPOINTS["instruments"])
        return data.get("instruments", [])

    def is_connected(self) -> bool:
        """Check if client is connected."""
        return self._connected

    async def __aenter__(self) -> "KrakenClient":
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.disconnect()


# =============================================================================
# FACTORY FUNCTION
# =============================================================================


def create_kraken_client(
    api_key: Optional[str] = None,
    api_secret: Optional[str] = None,
    demo: bool = True,
    tiered_leverage_config: Optional[List[Dict[str, Any]]] = None,
    circuit_breaker_config: Optional[Dict[str, Any]] = None,
) -> KrakenClient:
    """
    Factory function to create KrakenClient.

    Args:
        api_key: API key (falls back to KRAKEN_API_KEY env var)
        api_secret: API secret (falls back to KRAKEN_API_SECRET env var)
        demo: Use demo environment
        tiered_leverage_config: Custom leverage tiers
        circuit_breaker_config: Custom circuit breaker settings

    Returns:
        KrakenClient instance
    """
    import os

    key = api_key or os.environ.get("KRAKEN_API_KEY")
    secret = api_secret or os.environ.get("KRAKEN_API_SECRET")

    if not key or not secret:
        raise ValueError(
            "API credentials required. Provide api_key/api_secret or set "
            "KRAKEN_API_KEY/KRAKEN_API_SECRET environment variables."
        )

    tiered_leverage = TieredLeverage(tiers=tiered_leverage_config) if tiered_leverage_config else None
    circuit_breaker = CircuitBreaker(**circuit_breaker_config) if circuit_breaker_config else None

    return KrakenClient(
        api_key=key,
        api_secret=secret,
        demo=demo,
        tiered_leverage=tiered_leverage,
        circuit_breaker=circuit_breaker,
    )


# =============================================================================
# EXAMPLE USAGE
# =============================================================================

if __name__ == "__main__":
    import os

    async def main():
        client = KrakenClient(
            api_key=os.getenv("KRAKEN_API_KEY", "test_key"),
            api_secret=os.getenv("KRAKEN_API_SECRET", "test_secret"),
            demo=True,
        )

        async with client:
            # Get balance
            balance = await client.get_account_balance()
            print(f"Balance: ${balance:,.2f}")

            # Get tickers
            tickers = await client.get_tickers()
            print(f"\nAvailable tickers: {len(tickers)}")

            # Get BTC ticker
            btc = await client.get_ticker("PF_XBTUSD")
            print(f"\nBTC/USD: ${btc.last:,.2f} (funding: {btc.funding_rate*100:.4f}%)")

            # Get positions
            positions = await client.get_open_positions()
            print(f"\nOpen positions: {len(positions)}")

            # Test tiered leverage
            leverage_mgr = client.tiered_leverage
            print("\nTiered Leverage:")
            for conf in [50, 70, 85, 95]:
                tier = leverage_mgr.get_tier(conf)
                print(f"  {conf}% confidence -> {tier['name']}: {tier['leverage']}x, {tier['risk_pct']}% risk")

    asyncio.run(main())
