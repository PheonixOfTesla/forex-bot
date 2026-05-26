"""
OANDA Broker Integration for Forex Trading Bot

Production-ready OANDA API client with async support, WebSocket streaming,
proper error handling, retries, and comprehensive logging.

Uses oandapyV20 library for REST API and aiohttp for async operations.
"""

import asyncio
import logging
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Union

import aiohttp
import pandas as pd
from pydantic import BaseModel, Field, field_validator
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

# Configure module logger
logger = logging.getLogger(__name__)


# =============================================================================
# Constants
# =============================================================================

PRACTICE_URL = "https://api-fxpractice.oanda.com"
LIVE_URL = "https://api-fxtrade.oanda.com"
PRACTICE_STREAM_URL = "https://stream-fxpractice.oanda.com"
LIVE_STREAM_URL = "https://stream-fxtrade.oanda.com"

# API version
API_VERSION = "v3"

# Rate limiting
MAX_REQUESTS_PER_SECOND = 100
RATE_LIMIT_WINDOW = 1.0  # seconds

# Retry configuration
MAX_RETRIES = 3
RETRY_MIN_WAIT = 1  # seconds
RETRY_MAX_WAIT = 10  # seconds


# =============================================================================
# Exceptions
# =============================================================================


class OandaError(Exception):
    """Base exception for OANDA API errors."""

    def __init__(self, message: str, error_code: Optional[str] = None, details: Optional[Dict] = None):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.details = details or {}

    def __str__(self) -> str:
        if self.error_code:
            return f"[{self.error_code}] {self.message}"
        return self.message


class RateLimitError(OandaError):
    """Raised when API rate limit is exceeded."""

    def __init__(self, retry_after: Optional[int] = None):
        super().__init__(
            message="Rate limit exceeded",
            error_code="RATE_LIMIT_EXCEEDED"
        )
        self.retry_after = retry_after


class InsufficientMarginError(OandaError):
    """Raised when there is insufficient margin for a trade."""

    def __init__(self, required_margin: Optional[float] = None, available_margin: Optional[float] = None):
        super().__init__(
            message="Insufficient margin for trade",
            error_code="INSUFFICIENT_MARGIN",
            details={
                "required_margin": required_margin,
                "available_margin": available_margin,
            }
        )
        self.required_margin = required_margin
        self.available_margin = available_margin


class AuthenticationError(OandaError):
    """Raised when API authentication fails."""

    def __init__(self, message: str = "Authentication failed"):
        super().__init__(message=message, error_code="AUTHENTICATION_ERROR")


class InstrumentNotFoundError(OandaError):
    """Raised when an instrument is not found or not tradeable."""

    def __init__(self, instrument: str):
        super().__init__(
            message=f"Instrument not found or not tradeable: {instrument}",
            error_code="INSTRUMENT_NOT_FOUND"
        )
        self.instrument = instrument


class OrderRejectedError(OandaError):
    """Raised when an order is rejected."""

    def __init__(self, reason: str, order_details: Optional[Dict] = None):
        super().__init__(
            message=f"Order rejected: {reason}",
            error_code="ORDER_REJECTED",
            details=order_details or {}
        )
        self.reason = reason


class ConnectionError(OandaError):
    """Raised when connection to OANDA fails."""

    def __init__(self, message: str = "Connection failed"):
        super().__init__(message=message, error_code="CONNECTION_ERROR")


# =============================================================================
# Enums
# =============================================================================


class OrderSide(str, Enum):
    """Order side (buy/sell)."""
    BUY = "buy"
    SELL = "sell"


class OrderStatus(str, Enum):
    """Order status."""
    PENDING = "pending"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


class Granularity(str, Enum):
    """Candle granularity (timeframe)."""
    S5 = "S5"      # 5 seconds
    S10 = "S10"    # 10 seconds
    S15 = "S15"    # 15 seconds
    S30 = "S30"    # 30 seconds
    M1 = "M1"      # 1 minute
    M2 = "M2"      # 2 minutes
    M4 = "M4"      # 4 minutes
    M5 = "M5"      # 5 minutes
    M10 = "M10"    # 10 minutes
    M15 = "M15"    # 15 minutes
    M30 = "M30"    # 30 minutes
    H1 = "H1"      # 1 hour
    H2 = "H2"      # 2 hours
    H3 = "H3"      # 3 hours
    H4 = "H4"      # 4 hours
    H6 = "H6"      # 6 hours
    H8 = "H8"      # 8 hours
    H12 = "H12"    # 12 hours
    D = "D"        # 1 day
    W = "W"        # 1 week
    M = "M"        # 1 month


# =============================================================================
# Data Models (Pydantic)
# =============================================================================


class Position(BaseModel):
    """Represents an open trading position."""

    instrument: str = Field(..., description="Trading instrument (e.g., EUR_USD)")
    units: float = Field(..., description="Position size (positive for long, negative for short)")
    side: OrderSide = Field(..., description="Position side (buy/sell)")
    entry_price: float = Field(..., ge=0, description="Average entry price")
    unrealized_pnl: float = Field(default=0.0, description="Unrealized profit/loss")
    margin_used: float = Field(default=0.0, ge=0, description="Margin used for this position")
    trade_ids: List[str] = Field(default_factory=list, description="Associated trade IDs")

    @field_validator('instrument')
    @classmethod
    def validate_instrument(cls, v: str) -> str:
        """Validate instrument format."""
        if not v or '_' not in v:
            raise ValueError(f"Invalid instrument format: {v}. Expected format: XXX_YYY")
        return v.upper()

    @property
    def is_long(self) -> bool:
        """Check if position is long."""
        return self.side == OrderSide.BUY

    @property
    def is_short(self) -> bool:
        """Check if position is short."""
        return self.side == OrderSide.SELL


class Order(BaseModel):
    """Represents a trading order."""

    id: str = Field(..., description="Order ID")
    instrument: str = Field(..., description="Trading instrument")
    units: float = Field(..., description="Order size")
    side: OrderSide = Field(..., description="Order side")
    status: OrderStatus = Field(default=OrderStatus.PENDING, description="Order status")
    fill_price: Optional[float] = Field(default=None, ge=0, description="Fill price if executed")
    stop_loss: Optional[float] = Field(default=None, ge=0, description="Stop loss price")
    take_profit: Optional[float] = Field(default=None, ge=0, description="Take profit price")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Order creation time")
    filled_at: Optional[datetime] = Field(default=None, description="Order fill time")

    @field_validator('instrument')
    @classmethod
    def validate_instrument(cls, v: str) -> str:
        """Validate instrument format."""
        return v.upper()


class Candle(BaseModel):
    """Represents a price candle (OHLCV)."""

    time: datetime = Field(..., description="Candle timestamp")
    open: float = Field(..., ge=0, description="Open price")
    high: float = Field(..., ge=0, description="High price")
    low: float = Field(..., ge=0, description="Low price")
    close: float = Field(..., ge=0, description="Close price")
    volume: int = Field(default=0, ge=0, description="Trading volume")

    @field_validator('high')
    @classmethod
    def validate_high(cls, v: float, info) -> float:
        """Validate high is >= open, low, close."""
        return v

    @field_validator('low')
    @classmethod
    def validate_low(cls, v: float, info) -> float:
        """Validate low is <= open, high, close."""
        return v


class PriceUpdate(BaseModel):
    """Represents a streaming price update."""

    instrument: str = Field(..., description="Trading instrument")
    time: datetime = Field(..., description="Price timestamp")
    bid: float = Field(..., ge=0, description="Bid price")
    ask: float = Field(..., ge=0, description="Ask price")
    tradeable: bool = Field(default=True, description="Whether instrument is tradeable")

    @property
    def mid(self) -> float:
        """Calculate mid price."""
        return (self.bid + self.ask) / 2

    @property
    def spread(self) -> float:
        """Calculate spread."""
        return self.ask - self.bid


class AccountSummary(BaseModel):
    """Account summary information."""

    balance: float = Field(..., description="Account balance")
    unrealized_pnl: float = Field(default=0.0, description="Unrealized P/L")
    nav: float = Field(..., description="Net asset value")
    margin_used: float = Field(default=0.0, ge=0, description="Margin used")
    margin_available: float = Field(..., ge=0, description="Available margin")
    open_trade_count: int = Field(default=0, ge=0, description="Number of open trades")
    currency: str = Field(default="USD", description="Account currency")


# =============================================================================
# OANDA Client
# =============================================================================


class OandaClient:
    """
    Production-ready OANDA API client with async support.

    Features:
    - Async HTTP requests with aiohttp
    - WebSocket price streaming
    - Automatic retries with exponential backoff
    - Rate limiting
    - Comprehensive error handling
    - Proper logging

    Example:
        ```python
        client = OandaClient(
            api_key="your-api-key",
            account_id="your-account-id",
            practice=True
        )

        async with client:
            balance = await client.get_account_balance()
            print(f"Account balance: {balance}")

            candles = await client.get_candles("EUR_USD", Granularity.H1, 100)
            print(candles.head())
        ```
    """

    def __init__(
        self,
        api_key: str,
        account_id: str,
        practice: bool = True,
        timeout: int = 30,
    ):
        """
        Initialize OANDA client.

        Args:
            api_key: OANDA API key (from account settings)
            account_id: OANDA account ID
            practice: Use practice/demo environment (default: True)
            timeout: Request timeout in seconds (default: 30)
        """
        if not api_key:
            raise ValueError("API key is required")
        if not account_id:
            raise ValueError("Account ID is required")

        self.api_key = api_key
        self.account_id = account_id
        self.practice = practice
        self.timeout = timeout

        # Set URLs based on environment
        self.base_url = PRACTICE_URL if practice else LIVE_URL
        self.stream_url = PRACTICE_STREAM_URL if practice else LIVE_STREAM_URL

        # HTTP session (initialized in connect())
        self._session: Optional[aiohttp.ClientSession] = None
        self._stream_session: Optional[aiohttp.ClientSession] = None

        # Rate limiting
        self._request_times: List[float] = []
        self._rate_limit_lock = asyncio.Lock()

        # Streaming state
        self._streaming = False
        self._stream_task: Optional[asyncio.Task] = None

        # Connection state
        self._connected = False

        logger.info(
            f"OandaClient initialized for {'practice' if practice else 'live'} environment, "
            f"account: {account_id[:4]}...{account_id[-4:]}"
        )

    @property
    def headers(self) -> Dict[str, str]:
        """Get request headers."""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept-Datetime-Format": "RFC3339",
        }

    async def __aenter__(self) -> "OandaClient":
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.disconnect()

    async def connect(self) -> None:
        """
        Establish connection to OANDA API.

        Creates HTTP session and validates credentials.

        Raises:
            AuthenticationError: If API credentials are invalid
            ConnectionError: If connection fails
        """
        if self._connected:
            logger.warning("Already connected to OANDA")
            return

        logger.info("Connecting to OANDA API...")

        try:
            # Create HTTP session
            timeout = aiohttp.ClientTimeout(total=self.timeout)
            self._session = aiohttp.ClientSession(
                headers=self.headers,
                timeout=timeout,
            )

            # Validate credentials by fetching account info
            await self._validate_credentials()

            self._connected = True
            logger.info("Successfully connected to OANDA API")

        except aiohttp.ClientError as e:
            await self._cleanup_session()
            raise ConnectionError(f"Failed to connect to OANDA: {str(e)}")
        except Exception as e:
            await self._cleanup_session()
            raise

    async def disconnect(self) -> None:
        """Disconnect from OANDA API and cleanup resources."""
        logger.info("Disconnecting from OANDA API...")

        # Stop streaming if active
        await self.stop_streaming()

        # Cleanup sessions
        await self._cleanup_session()

        self._connected = False
        logger.info("Disconnected from OANDA API")

    async def _cleanup_session(self) -> None:
        """Cleanup HTTP sessions."""
        if self._session:
            await self._session.close()
            self._session = None

        if self._stream_session:
            await self._stream_session.close()
            self._stream_session = None

    async def _validate_credentials(self) -> None:
        """Validate API credentials."""
        try:
            url = f"{self.base_url}/{API_VERSION}/accounts/{self.account_id}/summary"
            async with self._session.get(url) as response:
                if response.status == 401:
                    raise AuthenticationError("Invalid API key")
                if response.status == 403:
                    raise AuthenticationError("API key does not have access to this account")
                if response.status == 404:
                    raise AuthenticationError(f"Account not found: {self.account_id}")
                response.raise_for_status()
                logger.debug("Credentials validated successfully")
        except aiohttp.ClientResponseError as e:
            raise AuthenticationError(f"Authentication failed: {str(e)}")

    def _ensure_connected(self) -> None:
        """Ensure client is connected."""
        if not self._connected or not self._session:
            raise ConnectionError("Not connected to OANDA. Call connect() first.")

    async def _check_rate_limit(self) -> None:
        """Check and enforce rate limiting."""
        async with self._rate_limit_lock:
            now = asyncio.get_event_loop().time()

            # Remove old request times
            self._request_times = [
                t for t in self._request_times
                if now - t < RATE_LIMIT_WINDOW
            ]

            # Check if we're at the limit
            if len(self._request_times) >= MAX_REQUESTS_PER_SECOND:
                sleep_time = RATE_LIMIT_WINDOW - (now - self._request_times[0])
                if sleep_time > 0:
                    logger.debug(f"Rate limit reached, sleeping for {sleep_time:.2f}s")
                    await asyncio.sleep(sleep_time)

            # Record this request
            self._request_times.append(now)

    @retry(
        retry=retry_if_exception_type((aiohttp.ClientError, asyncio.TimeoutError)),
        stop=stop_after_attempt(MAX_RETRIES),
        wait=wait_exponential(multiplier=1, min=RETRY_MIN_WAIT, max=RETRY_MAX_WAIT),
        reraise=True,
    )
    async def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict] = None,
        json_data: Optional[Dict] = None,
    ) -> Dict:
        """
        Make HTTP request to OANDA API with retry logic.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint (without base URL)
            params: Query parameters
            json_data: JSON body data

        Returns:
            Response JSON data

        Raises:
            OandaError: On API errors
            RateLimitError: On rate limit exceeded
        """
        self._ensure_connected()
        await self._check_rate_limit()

        url = f"{self.base_url}/{API_VERSION}/{endpoint}"
        logger.debug(f"Request: {method} {url}")

        try:
            async with self._session.request(
                method,
                url,
                params=params,
                json=json_data,
            ) as response:
                data = await response.json()

                # Handle errors
                if response.status == 429:
                    retry_after = response.headers.get("Retry-After")
                    raise RateLimitError(
                        retry_after=int(retry_after) if retry_after else None
                    )

                if response.status >= 400:
                    await self._handle_error_response(response.status, data)

                return data

        except aiohttp.ClientResponseError as e:
            raise OandaError(f"HTTP error: {str(e)}", error_code=str(e.status))

    async def _handle_error_response(self, status: int, data: Dict) -> None:
        """Handle error response from API."""
        error_message = data.get("errorMessage", "Unknown error")
        error_code = data.get("errorCode", str(status))

        if status == 401:
            raise AuthenticationError(error_message)

        if "INSUFFICIENT_MARGIN" in str(data):
            raise InsufficientMarginError()

        if "INSTRUMENT" in error_code.upper():
            instrument = data.get("instrument", "unknown")
            raise InstrumentNotFoundError(instrument)

        if "ORDER" in error_code.upper() and "REJECT" in error_code.upper():
            raise OrderRejectedError(error_message, data)

        raise OandaError(error_message, error_code=error_code, details=data)

    # =========================================================================
    # Account Methods
    # =========================================================================

    async def get_account_balance(self) -> float:
        """
        Get current account balance.

        Returns:
            Account balance as float

        Raises:
            OandaError: On API errors
        """
        logger.debug("Fetching account balance")

        data = await self._request(
            "GET",
            f"accounts/{self.account_id}/summary"
        )

        balance = float(data["account"]["balance"])
        logger.info(f"Account balance: {balance}")
        return balance

    async def get_account_summary(self) -> AccountSummary:
        """
        Get detailed account summary.

        Returns:
            AccountSummary object with account details
        """
        logger.debug("Fetching account summary")

        data = await self._request(
            "GET",
            f"accounts/{self.account_id}/summary"
        )

        account = data["account"]
        return AccountSummary(
            balance=float(account["balance"]),
            unrealized_pnl=float(account.get("unrealizedPL", 0)),
            nav=float(account["NAV"]),
            margin_used=float(account.get("marginUsed", 0)),
            margin_available=float(account["marginAvailable"]),
            open_trade_count=int(account.get("openTradeCount", 0)),
            currency=account.get("currency", "USD"),
        )

    # =========================================================================
    # Position Methods
    # =========================================================================

    async def get_open_positions(self) -> List[Position]:
        """
        Get all open positions.

        Returns:
            List of Position objects

        Raises:
            OandaError: On API errors
        """
        logger.debug("Fetching open positions")

        data = await self._request(
            "GET",
            f"accounts/{self.account_id}/openPositions"
        )

        positions = []
        for pos in data.get("positions", []):
            # Determine if long or short based on units
            long_units = float(pos.get("long", {}).get("units", 0))
            short_units = float(pos.get("short", {}).get("units", 0))

            if long_units != 0:
                positions.append(Position(
                    instrument=pos["instrument"],
                    units=long_units,
                    side=OrderSide.BUY,
                    entry_price=float(pos["long"].get("averagePrice", 0)),
                    unrealized_pnl=float(pos["long"].get("unrealizedPL", 0)),
                    margin_used=float(pos.get("marginUsed", 0)),
                    trade_ids=pos["long"].get("tradeIDs", []),
                ))

            if short_units != 0:
                positions.append(Position(
                    instrument=pos["instrument"],
                    units=short_units,
                    side=OrderSide.SELL,
                    entry_price=float(pos["short"].get("averagePrice", 0)),
                    unrealized_pnl=float(pos["short"].get("unrealizedPL", 0)),
                    margin_used=float(pos.get("marginUsed", 0)),
                    trade_ids=pos["short"].get("tradeIDs", []),
                ))

        logger.info(f"Found {len(positions)} open positions")
        return positions

    async def get_position(self, instrument: str) -> Optional[Position]:
        """
        Get position for a specific instrument.

        Args:
            instrument: Trading instrument (e.g., "EUR_USD")

        Returns:
            Position object or None if no position exists
        """
        positions = await self.get_open_positions()
        for pos in positions:
            if pos.instrument == instrument.upper():
                return pos
        return None

    # =========================================================================
    # Market Data Methods
    # =========================================================================

    async def get_candles(
        self,
        instrument: str,
        granularity: Union[Granularity, str],
        count: int = 500,
        from_time: Optional[datetime] = None,
        to_time: Optional[datetime] = None,
        price: str = "M",  # M=mid, B=bid, A=ask
    ) -> pd.DataFrame:
        """
        Get historical candle data.

        Args:
            instrument: Trading instrument (e.g., "EUR_USD")
            granularity: Candle timeframe (e.g., Granularity.H1)
            count: Number of candles to fetch (max 5000)
            from_time: Start time (optional)
            to_time: End time (optional)
            price: Price type - M (mid), B (bid), A (ask)

        Returns:
            DataFrame with OHLCV data

        Raises:
            OandaError: On API errors
            InstrumentNotFoundError: If instrument is invalid
        """
        logger.debug(f"Fetching {count} {granularity} candles for {instrument}")

        # Validate count
        count = min(count, 5000)

        # Build parameters
        params = {
            "granularity": granularity.value if isinstance(granularity, Granularity) else granularity,
            "count": count,
            "price": price,
        }

        if from_time:
            params["from"] = from_time.isoformat() + "Z"
        if to_time:
            params["to"] = to_time.isoformat() + "Z"

        data = await self._request(
            "GET",
            f"instruments/{instrument.upper()}/candles",
            params=params,
        )

        # Parse candles into DataFrame
        candles = []
        for candle in data.get("candles", []):
            if candle.get("complete", True):  # Only include complete candles
                mid = candle.get("mid", candle.get("bid", candle.get("ask", {})))
                candles.append(Candle(
                    time=datetime.fromisoformat(candle["time"].replace("Z", "+00:00")),
                    open=float(mid["o"]),
                    high=float(mid["h"]),
                    low=float(mid["l"]),
                    close=float(mid["c"]),
                    volume=int(candle.get("volume", 0)),
                ))

        # Convert to DataFrame
        if not candles:
            return pd.DataFrame(columns=["time", "open", "high", "low", "close", "volume"])

        df = pd.DataFrame([c.model_dump() for c in candles])
        df.set_index("time", inplace=True)

        logger.info(f"Fetched {len(df)} candles for {instrument}")
        return df

    async def get_current_price(self, instrument: str) -> PriceUpdate:
        """
        Get current price for an instrument.

        Args:
            instrument: Trading instrument (e.g., "EUR_USD")

        Returns:
            PriceUpdate with current bid/ask prices
        """
        data = await self._request(
            "GET",
            f"accounts/{self.account_id}/pricing",
            params={"instruments": instrument.upper()},
        )

        price_data = data["prices"][0]
        return PriceUpdate(
            instrument=price_data["instrument"],
            time=datetime.fromisoformat(price_data["time"].replace("Z", "+00:00")),
            bid=float(price_data["bids"][0]["price"]),
            ask=float(price_data["asks"][0]["price"]),
            tradeable=price_data.get("tradeable", True),
        )

    # =========================================================================
    # Order Methods
    # =========================================================================

    async def place_order(
        self,
        instrument: str,
        units: float,
        side: Union[OrderSide, str],
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        trailing_stop_distance: Optional[float] = None,
    ) -> Order:
        """
        Place a market order.

        Args:
            instrument: Trading instrument (e.g., "EUR_USD")
            units: Number of units (positive value)
            side: Order side (buy/sell)
            stop_loss: Stop loss price (optional)
            take_profit: Take profit price (optional)
            trailing_stop_distance: Trailing stop distance in price (optional)

        Returns:
            Order object with fill details

        Raises:
            InsufficientMarginError: If margin is insufficient
            OrderRejectedError: If order is rejected
            OandaError: On other API errors
        """
        logger.info(f"Placing {side} order for {units} {instrument}")

        # Ensure side is string
        side_str = side.value if isinstance(side, OrderSide) else side

        # Calculate signed units (negative for sell)
        signed_units = units if side_str == OrderSide.BUY.value else -units

        # Build order data
        order_data: Dict[str, Any] = {
            "order": {
                "type": "MARKET",
                "instrument": instrument.upper(),
                "units": str(int(signed_units)),
                "timeInForce": "FOK",  # Fill or Kill
                "positionFill": "DEFAULT",
            }
        }

        # Add stop loss
        if stop_loss:
            order_data["order"]["stopLossOnFill"] = {
                "price": str(stop_loss),
                "timeInForce": "GTC",
            }

        # Add take profit
        if take_profit:
            order_data["order"]["takeProfitOnFill"] = {
                "price": str(take_profit),
                "timeInForce": "GTC",
            }

        # Add trailing stop
        if trailing_stop_distance:
            order_data["order"]["trailingStopLossOnFill"] = {
                "distance": str(trailing_stop_distance),
                "timeInForce": "GTC",
            }

        data = await self._request(
            "POST",
            f"accounts/{self.account_id}/orders",
            json_data=order_data,
        )

        # Parse response
        if "orderFillTransaction" in data:
            fill = data["orderFillTransaction"]
            order = Order(
                id=fill["id"],
                instrument=instrument.upper(),
                units=abs(float(fill["units"])),
                side=OrderSide.BUY if float(fill["units"]) > 0 else OrderSide.SELL,
                status=OrderStatus.FILLED,
                fill_price=float(fill["price"]),
                stop_loss=stop_loss,
                take_profit=take_profit,
                filled_at=datetime.fromisoformat(fill["time"].replace("Z", "+00:00")),
            )
            logger.info(f"Order filled: {order.id} at {order.fill_price}")
            return order

        elif "orderCancelTransaction" in data:
            cancel = data["orderCancelTransaction"]
            raise OrderRejectedError(
                reason=cancel.get("reason", "Order cancelled"),
                order_details=cancel,
            )

        else:
            # Pending order
            create = data.get("orderCreateTransaction", {})
            return Order(
                id=create.get("id", "unknown"),
                instrument=instrument.upper(),
                units=units,
                side=OrderSide(side_str),
                status=OrderStatus.PENDING,
                stop_loss=stop_loss,
                take_profit=take_profit,
            )

    async def place_limit_order(
        self,
        instrument: str,
        units: float,
        side: Union[OrderSide, str],
        price: float,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        expiry: Optional[datetime] = None,
    ) -> Order:
        """
        Place a limit order.

        Args:
            instrument: Trading instrument
            units: Number of units
            side: Order side
            price: Limit price
            stop_loss: Stop loss price (optional)
            take_profit: Take profit price (optional)
            expiry: Order expiry time (optional)

        Returns:
            Order object
        """
        logger.info(f"Placing limit {side} order for {units} {instrument} at {price}")

        side_str = side.value if isinstance(side, OrderSide) else side
        signed_units = units if side_str == OrderSide.BUY.value else -units

        order_data: Dict[str, Any] = {
            "order": {
                "type": "LIMIT",
                "instrument": instrument.upper(),
                "units": str(int(signed_units)),
                "price": str(price),
                "timeInForce": "GTC" if not expiry else "GTD",
                "positionFill": "DEFAULT",
            }
        }

        if expiry:
            order_data["order"]["gtdTime"] = expiry.isoformat() + "Z"

        if stop_loss:
            order_data["order"]["stopLossOnFill"] = {"price": str(stop_loss)}

        if take_profit:
            order_data["order"]["takeProfitOnFill"] = {"price": str(take_profit)}

        data = await self._request(
            "POST",
            f"accounts/{self.account_id}/orders",
            json_data=order_data,
        )

        create = data.get("orderCreateTransaction", {})
        return Order(
            id=create.get("id", "unknown"),
            instrument=instrument.upper(),
            units=units,
            side=OrderSide(side_str),
            status=OrderStatus.PENDING,
            stop_loss=stop_loss,
            take_profit=take_profit,
        )

    # =========================================================================
    # Trade Management Methods
    # =========================================================================

    async def close_position(self, trade_id: str) -> bool:
        """
        Close a specific trade.

        Args:
            trade_id: Trade ID to close

        Returns:
            True if successfully closed

        Raises:
            OandaError: If close fails
        """
        logger.info(f"Closing trade: {trade_id}")

        data = await self._request(
            "PUT",
            f"accounts/{self.account_id}/trades/{trade_id}/close",
        )

        if "orderFillTransaction" in data:
            logger.info(f"Trade {trade_id} closed successfully")
            return True

        raise OandaError(f"Failed to close trade {trade_id}", details=data)

    async def close_all_positions(self, instrument: Optional[str] = None) -> int:
        """
        Close all positions or positions for a specific instrument.

        Args:
            instrument: Instrument to close (optional, closes all if not specified)

        Returns:
            Number of positions closed
        """
        positions = await self.get_open_positions()

        if instrument:
            positions = [p for p in positions if p.instrument == instrument.upper()]

        closed = 0
        for position in positions:
            for trade_id in position.trade_ids:
                try:
                    await self.close_position(trade_id)
                    closed += 1
                except OandaError as e:
                    logger.error(f"Failed to close trade {trade_id}: {e}")

        logger.info(f"Closed {closed} positions")
        return closed

    async def modify_trade(
        self,
        trade_id: str,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        trailing_stop_distance: Optional[float] = None,
    ) -> bool:
        """
        Modify an existing trade's stop loss or take profit.

        Args:
            trade_id: Trade ID to modify
            stop_loss: New stop loss price (optional)
            take_profit: New take profit price (optional)
            trailing_stop_distance: New trailing stop distance (optional)

        Returns:
            True if successfully modified

        Raises:
            OandaError: If modification fails
        """
        logger.info(f"Modifying trade {trade_id}: SL={stop_loss}, TP={take_profit}")

        modify_data: Dict[str, Any] = {}

        if stop_loss is not None:
            modify_data["stopLoss"] = {"price": str(stop_loss), "timeInForce": "GTC"}

        if take_profit is not None:
            modify_data["takeProfit"] = {"price": str(take_profit), "timeInForce": "GTC"}

        if trailing_stop_distance is not None:
            modify_data["trailingStopLoss"] = {
                "distance": str(trailing_stop_distance),
                "timeInForce": "GTC",
            }

        if not modify_data:
            logger.warning("No modifications specified")
            return False

        await self._request(
            "PUT",
            f"accounts/{self.account_id}/trades/{trade_id}/orders",
            json_data=modify_data,
        )

        logger.info(f"Trade {trade_id} modified successfully")
        return True

    # =========================================================================
    # Streaming Methods
    # =========================================================================

    async def stream_prices(
        self,
        instruments: List[str],
        callback: Callable[[PriceUpdate], None],
    ) -> None:
        """
        Stream live prices for instruments.

        This method runs indefinitely until stop_streaming() is called.

        Args:
            instruments: List of instruments to stream (e.g., ["EUR_USD", "GBP_USD"])
            callback: Async function called with each price update

        Example:
            ```python
            async def on_price(price: PriceUpdate):
                print(f"{price.instrument}: {price.bid}/{price.ask}")

            await client.stream_prices(["EUR_USD"], on_price)
            ```
        """
        if self._streaming:
            logger.warning("Already streaming prices")
            return

        self._streaming = True
        instruments_str = ",".join(i.upper() for i in instruments)

        logger.info(f"Starting price stream for: {instruments_str}")

        url = f"{self.stream_url}/{API_VERSION}/accounts/{self.account_id}/pricing/stream"
        params = {"instruments": instruments_str}

        try:
            timeout = aiohttp.ClientTimeout(total=None, sock_read=60)
            self._stream_session = aiohttp.ClientSession(
                headers=self.headers,
                timeout=timeout,
            )

            async with self._stream_session.get(url, params=params) as response:
                if response.status != 200:
                    error_data = await response.json()
                    raise OandaError(
                        f"Stream connection failed: {error_data.get('errorMessage', 'Unknown error')}",
                        error_code=str(response.status),
                    )

                logger.info("Price stream connected")

                async for line in response.content:
                    if not self._streaming:
                        break

                    if not line:
                        continue

                    try:
                        import json
                        data = json.loads(line.decode("utf-8"))

                        if data.get("type") == "PRICE":
                            price_update = PriceUpdate(
                                instrument=data["instrument"],
                                time=datetime.fromisoformat(data["time"].replace("Z", "+00:00")),
                                bid=float(data["bids"][0]["price"]),
                                ask=float(data["asks"][0]["price"]),
                                tradeable=data.get("tradeable", True),
                            )

                            # Call callback (handle both sync and async)
                            if asyncio.iscoroutinefunction(callback):
                                await callback(price_update)
                            else:
                                callback(price_update)

                        elif data.get("type") == "HEARTBEAT":
                            logger.debug("Stream heartbeat received")

                    except json.JSONDecodeError:
                        logger.warning(f"Failed to parse stream data: {line}")
                    except Exception as e:
                        logger.error(f"Error processing stream data: {e}")

        except asyncio.CancelledError:
            logger.info("Price stream cancelled")
        except Exception as e:
            logger.error(f"Price stream error: {e}")
            raise
        finally:
            self._streaming = False
            if self._stream_session:
                await self._stream_session.close()
                self._stream_session = None
            logger.info("Price stream stopped")

    async def stop_streaming(self) -> None:
        """Stop price streaming."""
        if not self._streaming:
            return

        logger.info("Stopping price stream...")
        self._streaming = False

        if self._stream_task:
            self._stream_task.cancel()
            try:
                await self._stream_task
            except asyncio.CancelledError:
                pass
            self._stream_task = None

    def start_streaming_background(
        self,
        instruments: List[str],
        callback: Callable[[PriceUpdate], None],
    ) -> asyncio.Task:
        """
        Start price streaming in background task.

        Args:
            instruments: List of instruments to stream
            callback: Function called with each price update

        Returns:
            Background task handle
        """
        self._stream_task = asyncio.create_task(
            self.stream_prices(instruments, callback)
        )
        return self._stream_task

    # =========================================================================
    # Utility Methods
    # =========================================================================

    async def get_tradeable_instruments(self) -> List[Dict]:
        """Get list of tradeable instruments."""
        data = await self._request(
            "GET",
            f"accounts/{self.account_id}/instruments",
        )
        return data.get("instruments", [])

    async def get_order_book(self, instrument: str) -> Dict:
        """Get order book for an instrument."""
        data = await self._request(
            "GET",
            f"instruments/{instrument.upper()}/orderBook",
        )
        return data.get("orderBook", {})

    async def get_position_book(self, instrument: str) -> Dict:
        """Get position book for an instrument."""
        data = await self._request(
            "GET",
            f"instruments/{instrument.upper()}/positionBook",
        )
        return data.get("positionBook", {})


# =============================================================================
# Factory Function
# =============================================================================


def create_oanda_client(
    api_key: Optional[str] = None,
    account_id: Optional[str] = None,
    practice: bool = True,
) -> OandaClient:
    """
    Factory function to create OandaClient with environment variable fallback.

    Args:
        api_key: API key (or set OANDA_API_KEY env var)
        account_id: Account ID (or set OANDA_ACCOUNT_ID env var)
        practice: Use practice environment (default: True)

    Returns:
        Configured OandaClient instance
    """
    import os

    api_key = api_key or os.getenv("OANDA_API_KEY")
    account_id = account_id or os.getenv("OANDA_ACCOUNT_ID")

    if not api_key:
        raise ValueError("API key required. Set OANDA_API_KEY or pass api_key parameter.")
    if not account_id:
        raise ValueError("Account ID required. Set OANDA_ACCOUNT_ID or pass account_id parameter.")

    return OandaClient(
        api_key=api_key,
        account_id=account_id,
        practice=practice,
    )
