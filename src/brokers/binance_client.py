"""
Binance Futures Client Integration

Production-ready Binance Futures client with async support,
WebSocket streaming, and comprehensive error handling.

Author: HERMES Trading System
"""

import asyncio
import hashlib
import hmac
import logging
import time
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

TESTNET_URL = "https://testnet.binancefuture.com"
LIVE_URL = "https://fapi.binance.com"

TESTNET_WS_URL = "wss://stream.binancefuture.com"
LIVE_WS_URL = "wss://fstream.binance.com"

SUPPORTED_SYMBOLS = ["BTCUSDT", "XRPUSDT"]

# API Endpoints
ENDPOINTS = {
    "account": "/fapi/v2/account",
    "balance": "/fapi/v2/balance",
    "positions": "/fapi/v2/positionRisk",
    "klines": "/fapi/v1/klines",
    "order": "/fapi/v1/order",
    "leverage": "/fapi/v1/leverage",
    "funding_rate": "/fapi/v1/fundingRate",
    "exchange_info": "/fapi/v1/exchangeInfo",
    "listen_key": "/fapi/v1/listenKey",
}

# Interval mappings
INTERVAL_MAP = {
    "1m": "1m",
    "3m": "3m",
    "5m": "5m",
    "15m": "15m",
    "30m": "30m",
    "1h": "1h",
    "2h": "2h",
    "4h": "4h",
    "6h": "6h",
    "8h": "8h",
    "12h": "12h",
    "1d": "1d",
    "3d": "3d",
    "1w": "1w",
    "1M": "1M",
}


# =============================================================================
# ENUMS
# =============================================================================


class OrderSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(str, Enum):
    LIMIT = "LIMIT"
    MARKET = "MARKET"
    STOP = "STOP"
    STOP_MARKET = "STOP_MARKET"
    TAKE_PROFIT = "TAKE_PROFIT"
    TAKE_PROFIT_MARKET = "TAKE_PROFIT_MARKET"
    TRAILING_STOP_MARKET = "TRAILING_STOP_MARKET"


class OrderStatus(str, Enum):
    NEW = "NEW"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELED = "CANCELED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


class PositionSide(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"
    BOTH = "BOTH"


# =============================================================================
# EXCEPTIONS
# =============================================================================


class BinanceError(Exception):
    """Base exception for Binance-related errors."""

    def __init__(self, message: str, code: Optional[int] = None):
        self.message = message
        self.code = code
        super().__init__(self.message)


class InsufficientBalanceError(BinanceError):
    """Raised when account has insufficient balance for operation."""

    def __init__(self, message: str = "Insufficient balance"):
        super().__init__(message, code=-2019)


class LeverageError(BinanceError):
    """Raised when leverage operation fails."""

    def __init__(self, message: str = "Leverage operation failed"):
        super().__init__(message, code=-4028)


class InvalidSymbolError(BinanceError):
    """Raised when an invalid or unsupported symbol is used."""

    def __init__(self, symbol: str):
        super().__init__(f"Invalid or unsupported symbol: {symbol}", code=-1121)


class OrderError(BinanceError):
    """Raised when order placement fails."""

    def __init__(self, message: str, code: Optional[int] = None):
        super().__init__(message, code)


class ConnectionError(BinanceError):
    """Raised when connection to Binance fails."""

    def __init__(self, message: str = "Connection failed"):
        super().__init__(message, code=-1001)


class RateLimitError(BinanceError):
    """Raised when rate limit is exceeded."""

    def __init__(self, message: str = "Rate limit exceeded"):
        super().__init__(message, code=-1015)


# =============================================================================
# DATA MODELS
# =============================================================================


class Position(BaseModel):
    """Represents an open futures position."""

    symbol: str = Field(..., description="Trading pair symbol")
    side: PositionSide = Field(..., description="Position side (LONG/SHORT)")
    entry_price: float = Field(..., ge=0, description="Average entry price")
    quantity: float = Field(..., description="Position size")
    unrealized_pnl: float = Field(default=0.0, description="Unrealized PnL in USDT")
    leverage: int = Field(default=1, ge=1, le=125, description="Leverage multiplier")
    liquidation_price: float = Field(
        default=0.0, ge=0, description="Estimated liquidation price"
    )
    mark_price: float = Field(default=0.0, ge=0, description="Current mark price")
    margin_type: str = Field(default="cross", description="Margin type (cross/isolated)")
    notional: float = Field(default=0.0, description="Position notional value")

    @validator("symbol")
    def validate_symbol(cls, v):
        if v not in SUPPORTED_SYMBOLS:
            logger.warning(f"Symbol {v} not in supported symbols list")
        return v.upper()

    @property
    def is_long(self) -> bool:
        return self.side == PositionSide.LONG

    @property
    def is_short(self) -> bool:
        return self.side == PositionSide.SHORT

    @property
    def pnl_percentage(self) -> float:
        if self.entry_price == 0 or self.quantity == 0:
            return 0.0
        cost = abs(self.entry_price * self.quantity)
        return (self.unrealized_pnl / cost) * 100 if cost > 0 else 0.0

    class Config:
        use_enum_values = True


class Order(BaseModel):
    """Represents a trading order."""

    id: str = Field(..., description="Order ID")
    symbol: str = Field(..., description="Trading pair symbol")
    side: OrderSide = Field(..., description="Order side (BUY/SELL)")
    quantity: float = Field(..., gt=0, description="Order quantity")
    status: OrderStatus = Field(..., description="Order status")
    fill_price: Optional[float] = Field(None, ge=0, description="Average fill price")
    order_type: OrderType = Field(default=OrderType.MARKET, description="Order type")
    client_order_id: Optional[str] = Field(None, description="Client order ID")
    stop_price: Optional[float] = Field(None, ge=0, description="Stop price")
    time_in_force: str = Field(default="GTC", description="Time in force")
    reduce_only: bool = Field(default=False, description="Reduce only flag")
    created_at: Optional[int] = Field(None, description="Creation timestamp")
    updated_at: Optional[int] = Field(None, description="Update timestamp")

    @property
    def is_filled(self) -> bool:
        return self.status == OrderStatus.FILLED

    @property
    def is_active(self) -> bool:
        return self.status in [OrderStatus.NEW, OrderStatus.PARTIALLY_FILLED]

    class Config:
        use_enum_values = True


# =============================================================================
# BINANCE CLIENT
# =============================================================================


class BinanceClient:
    """
    Production-ready Binance Futures client with async support.

    Features:
        - Full async/await support
        - Automatic retry with exponential backoff
        - WebSocket price streaming
        - Comprehensive error handling
        - Support for testnet and live environments

    Example:
        >>> client = BinanceClient(api_key, api_secret, testnet=True)
        >>> await client.connect()
        >>> balance = await client.get_account_balance()
        >>> print(f"USDT Balance: {balance}")
    """

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        testnet: bool = True,
        recv_window: int = 5000,
    ):
        """
        Initialize Binance Futures client.

        Args:
            api_key: Binance API key
            api_secret: Binance API secret
            testnet: Use testnet environment (default: True)
            recv_window: Request receive window in ms (default: 5000)
        """
        self.api_key = api_key
        self.api_secret = api_secret
        self.testnet = testnet
        self.recv_window = recv_window

        # Set URLs based on environment
        self.base_url = TESTNET_URL if testnet else LIVE_URL
        self.ws_url = TESTNET_WS_URL if testnet else LIVE_WS_URL

        # Session management
        self._session: Optional[aiohttp.ClientSession] = None
        self._ws_connections: Dict[str, aiohttp.ClientWebSocketResponse] = {}
        self._listen_key: Optional[str] = None
        self._listen_key_task: Optional[asyncio.Task] = None

        # Rate limiting
        self._last_request_time: float = 0
        self._min_request_interval: float = 0.1  # 100ms minimum between requests

        # Connection state
        self._connected: bool = False

        logger.info(
            f"BinanceClient initialized - Environment: {'TESTNET' if testnet else 'LIVE'}"
        )

    # =========================================================================
    # CONNECTION MANAGEMENT
    # =========================================================================

    async def connect(self) -> None:
        """
        Initialize connection to Binance.

        Creates HTTP session and validates API credentials.

        Raises:
            ConnectionError: If connection fails
            BinanceError: If API credentials are invalid
        """
        if self._connected:
            logger.warning("Client already connected")
            return

        try:
            # Create session with headers
            headers = {
                "X-MBX-APIKEY": self.api_key,
                "Content-Type": "application/json",
            }

            timeout = aiohttp.ClientTimeout(total=30)
            self._session = aiohttp.ClientSession(headers=headers, timeout=timeout)

            # Validate connection by fetching account info
            await self._validate_connection()

            self._connected = True
            logger.info("Successfully connected to Binance")

        except Exception as e:
            logger.error(f"Connection failed: {e}")
            await self.disconnect()
            raise ConnectionError(f"Failed to connect: {e}")

    async def disconnect(self) -> None:
        """Close all connections and cleanup resources."""
        # Cancel listen key refresh task
        if self._listen_key_task:
            self._listen_key_task.cancel()
            try:
                await self._listen_key_task
            except asyncio.CancelledError:
                pass
            self._listen_key_task = None

        # Close WebSocket connections
        for symbol, ws in list(self._ws_connections.items()):
            try:
                await ws.close()
                logger.debug(f"Closed WebSocket for {symbol}")
            except Exception as e:
                logger.warning(f"Error closing WebSocket for {symbol}: {e}")
        self._ws_connections.clear()

        # Close HTTP session
        if self._session:
            await self._session.close()
            self._session = None

        self._connected = False
        logger.info("Disconnected from Binance")

    async def _validate_connection(self) -> None:
        """Validate API connection by fetching account info."""
        try:
            await self._signed_request("GET", ENDPOINTS["account"])
            logger.debug("API credentials validated")
        except BinanceError as e:
            if e.code == -2015:
                raise BinanceError("Invalid API key or secret", e.code)
            raise

    # =========================================================================
    # REQUEST HANDLING
    # =========================================================================

    def _generate_signature(self, params: Dict[str, Any]) -> str:
        """Generate HMAC SHA256 signature for request."""
        query_string = urlencode(params)
        signature = hmac.new(
            self.api_secret.encode("utf-8"),
            query_string.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return signature

    async def _rate_limit(self) -> None:
        """Enforce rate limiting between requests."""
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
        """
        Make HTTP request to Binance API.

        Args:
            method: HTTP method (GET, POST, DELETE)
            endpoint: API endpoint
            params: Request parameters
            signed: Whether request requires signature

        Returns:
            API response as dictionary

        Raises:
            BinanceError: If request fails
        """
        if not self._session:
            raise ConnectionError("Client not connected. Call connect() first.")

        await self._rate_limit()

        params = params or {}

        if signed:
            params["timestamp"] = int(time.time() * 1000)
            params["recvWindow"] = self.recv_window
            params["signature"] = self._generate_signature(params)

        url = f"{self.base_url}{endpoint}"

        try:
            if method == "GET":
                async with self._session.get(url, params=params) as response:
                    return await self._handle_response(response)
            elif method == "POST":
                async with self._session.post(url, params=params) as response:
                    return await self._handle_response(response)
            elif method == "DELETE":
                async with self._session.delete(url, params=params) as response:
                    return await self._handle_response(response)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")

        except aiohttp.ClientError as e:
            logger.error(f"Request failed: {e}")
            raise

    async def _handle_response(
        self, response: aiohttp.ClientResponse
    ) -> Dict[str, Any]:
        """Handle API response and raise appropriate exceptions."""
        try:
            data = await response.json()
        except Exception:
            text = await response.text()
            logger.error(f"Failed to parse response: {text}")
            raise BinanceError(f"Failed to parse response: {text}")

        if response.status == 200:
            return data

        # Handle error responses
        error_code = data.get("code", -1)
        error_msg = data.get("msg", "Unknown error")

        logger.error(f"API Error [{error_code}]: {error_msg}")

        # Map error codes to specific exceptions
        if error_code == -2019:
            raise InsufficientBalanceError(error_msg)
        elif error_code == -4028:
            raise LeverageError(error_msg)
        elif error_code == -1121:
            raise InvalidSymbolError(error_msg)
        elif error_code == -1015:
            raise RateLimitError(error_msg)
        elif error_code in [-2010, -2011, -2013, -2014, -2021, -2022]:
            raise OrderError(error_msg, error_code)
        else:
            raise BinanceError(error_msg, error_code)

    async def _signed_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Make signed request to Binance API."""
        return await self._request(method, endpoint, params, signed=True)

    async def _public_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Make public (unsigned) request to Binance API."""
        return await self._request(method, endpoint, params, signed=False)

    # =========================================================================
    # ACCOUNT METHODS
    # =========================================================================

    async def get_account_balance(self, asset: str = "USDT") -> float:
        """
        Get account balance for specified asset.

        Args:
            asset: Asset symbol (default: USDT)

        Returns:
            Available balance as float

        Raises:
            BinanceError: If request fails
        """
        balances = await self._signed_request("GET", ENDPOINTS["balance"])

        for balance in balances:
            if balance["asset"] == asset:
                available = float(balance["availableBalance"])
                total = float(balance["balance"])
                logger.debug(
                    f"{asset} Balance - Available: {available}, Total: {total}"
                )
                return available

        logger.warning(f"Asset {asset} not found in balances")
        return 0.0

    async def get_open_positions(
        self, symbol: Optional[str] = None
    ) -> List[Position]:
        """
        Get all open positions.

        Args:
            symbol: Optional symbol filter

        Returns:
            List of Position objects

        Raises:
            BinanceError: If request fails
        """
        params = {}
        if symbol:
            params["symbol"] = symbol.upper()

        positions_data = await self._signed_request(
            "GET", ENDPOINTS["positions"], params
        )

        positions = []
        for pos in positions_data:
            # Skip positions with zero quantity
            quantity = float(pos["positionAmt"])
            if quantity == 0:
                continue

            # Determine side based on position amount
            side = PositionSide.LONG if quantity > 0 else PositionSide.SHORT

            position = Position(
                symbol=pos["symbol"],
                side=side,
                entry_price=float(pos["entryPrice"]),
                quantity=abs(quantity),
                unrealized_pnl=float(pos["unRealizedProfit"]),
                leverage=int(pos["leverage"]),
                liquidation_price=float(pos["liquidationPrice"]),
                mark_price=float(pos["markPrice"]),
                margin_type=pos["marginType"],
                notional=abs(float(pos["notional"])),
            )
            positions.append(position)
            logger.debug(f"Position: {position.symbol} {position.side} qty={position.quantity}")

        return positions

    # =========================================================================
    # MARKET DATA METHODS
    # =========================================================================

    async def get_candles(
        self,
        symbol: str,
        interval: str,
        limit: int = 500,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
    ) -> pd.DataFrame:
        """
        Get candlestick/kline data.

        Args:
            symbol: Trading pair symbol
            interval: Candlestick interval (1m, 5m, 15m, 1h, 4h, 1d, etc.)
            limit: Number of candles (max 1500)
            start_time: Start time in milliseconds
            end_time: End time in milliseconds

        Returns:
            DataFrame with OHLCV data

        Raises:
            InvalidSymbolError: If symbol is invalid
            BinanceError: If request fails
        """
        if interval not in INTERVAL_MAP:
            raise ValueError(f"Invalid interval: {interval}")

        params = {
            "symbol": symbol.upper(),
            "interval": INTERVAL_MAP[interval],
            "limit": min(limit, 1500),
        }

        if start_time:
            params["startTime"] = start_time
        if end_time:
            params["endTime"] = end_time

        klines = await self._public_request("GET", ENDPOINTS["klines"], params)

        # Parse klines into DataFrame
        df = pd.DataFrame(
            klines,
            columns=[
                "open_time",
                "open",
                "high",
                "low",
                "close",
                "volume",
                "close_time",
                "quote_volume",
                "trades",
                "taker_buy_base",
                "taker_buy_quote",
                "ignore",
            ],
        )

        # Convert types
        df["open_time"] = pd.to_datetime(df["open_time"], unit="ms")
        df["close_time"] = pd.to_datetime(df["close_time"], unit="ms")

        for col in ["open", "high", "low", "close", "volume", "quote_volume"]:
            df[col] = df[col].astype(float)

        df["trades"] = df["trades"].astype(int)

        # Set index and drop unnecessary columns
        df.set_index("open_time", inplace=True)
        df.drop(columns=["ignore"], inplace=True)

        logger.debug(f"Fetched {len(df)} candles for {symbol} {interval}")
        return df

    async def get_funding_rate(self, symbol: str) -> float:
        """
        Get current funding rate for symbol.

        Args:
            symbol: Trading pair symbol

        Returns:
            Funding rate as float (negative = shorts pay longs)

        Raises:
            InvalidSymbolError: If symbol is invalid
            BinanceError: If request fails
        """
        params = {"symbol": symbol.upper(), "limit": 1}

        data = await self._public_request("GET", ENDPOINTS["funding_rate"], params)

        if not data:
            logger.warning(f"No funding rate data for {symbol}")
            return 0.0

        rate = float(data[0]["fundingRate"])
        logger.debug(f"Funding rate for {symbol}: {rate * 100:.4f}%")
        return rate

    # =========================================================================
    # ORDER METHODS
    # =========================================================================

    async def place_order(
        self,
        symbol: str,
        side: Union[OrderSide, str],
        quantity: float,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        leverage: Optional[int] = None,
        order_type: Union[OrderType, str] = OrderType.MARKET,
        price: Optional[float] = None,
        reduce_only: bool = False,
    ) -> Order:
        """
        Place a futures order with optional stop loss and take profit.

        Args:
            symbol: Trading pair symbol
            side: Order side (BUY/SELL)
            quantity: Order quantity
            stop_loss: Stop loss price (optional)
            take_profit: Take profit price (optional)
            leverage: Leverage to set before order (optional)
            order_type: Order type (default: MARKET)
            price: Limit price for limit orders
            reduce_only: Reduce only flag

        Returns:
            Order object

        Raises:
            InvalidSymbolError: If symbol is invalid
            InsufficientBalanceError: If balance is insufficient
            OrderError: If order fails
        """
        symbol = symbol.upper()

        # Validate and convert enums
        if isinstance(side, str):
            side = OrderSide(side.upper())
        if isinstance(order_type, str):
            order_type = OrderType(order_type.upper())

        # Set leverage if specified
        if leverage:
            await self.set_leverage(symbol, leverage)

        # Build order parameters
        params = {
            "symbol": symbol,
            "side": side.value,
            "type": order_type.value,
            "quantity": str(quantity),
        }

        if reduce_only:
            params["reduceOnly"] = "true"

        if order_type == OrderType.LIMIT:
            if not price:
                raise OrderError("Limit orders require a price")
            params["price"] = str(price)
            params["timeInForce"] = "GTC"

        # Place main order
        logger.info(f"Placing {order_type.value} {side.value} order: {symbol} qty={quantity}")
        response = await self._signed_request("POST", ENDPOINTS["order"], params)

        order = Order(
            id=str(response["orderId"]),
            symbol=response["symbol"],
            side=OrderSide(response["side"]),
            quantity=float(response["origQty"]),
            status=OrderStatus(response["status"]),
            fill_price=float(response.get("avgPrice", 0)) or None,
            order_type=OrderType(response["type"]),
            client_order_id=response.get("clientOrderId"),
            created_at=response.get("updateTime"),
        )

        logger.info(f"Order placed: {order.id} status={order.status}")

        # Place stop loss if specified
        if stop_loss:
            await self._place_stop_order(
                symbol=symbol,
                side=OrderSide.SELL if side == OrderSide.BUY else OrderSide.BUY,
                quantity=quantity,
                stop_price=stop_loss,
                order_type=OrderType.STOP_MARKET,
            )
            logger.info(f"Stop loss placed at {stop_loss}")

        # Place take profit if specified
        if take_profit:
            await self._place_stop_order(
                symbol=symbol,
                side=OrderSide.SELL if side == OrderSide.BUY else OrderSide.BUY,
                quantity=quantity,
                stop_price=take_profit,
                order_type=OrderType.TAKE_PROFIT_MARKET,
            )
            logger.info(f"Take profit placed at {take_profit}")

        return order

    async def _place_stop_order(
        self,
        symbol: str,
        side: OrderSide,
        quantity: float,
        stop_price: float,
        order_type: OrderType,
    ) -> Dict[str, Any]:
        """Place a stop loss or take profit order."""
        params = {
            "symbol": symbol,
            "side": side.value,
            "type": order_type.value,
            "quantity": str(quantity),
            "stopPrice": str(stop_price),
            "reduceOnly": "true",
        }

        return await self._signed_request("POST", ENDPOINTS["order"], params)

    async def close_position(
        self, symbol: str, quantity: Optional[float] = None
    ) -> bool:
        """
        Close an open position.

        Args:
            symbol: Trading pair symbol
            quantity: Quantity to close (default: entire position)

        Returns:
            True if successful

        Raises:
            BinanceError: If operation fails
        """
        symbol = symbol.upper()

        # Get current position
        positions = await self.get_open_positions(symbol)

        if not positions:
            logger.warning(f"No open position for {symbol}")
            return False

        position = positions[0]
        close_qty = quantity or position.quantity

        # Determine close side (opposite of position)
        close_side = OrderSide.SELL if position.is_long else OrderSide.BUY

        # Place market order to close
        params = {
            "symbol": symbol,
            "side": close_side.value,
            "type": OrderType.MARKET.value,
            "quantity": str(close_qty),
            "reduceOnly": "true",
        }

        logger.info(f"Closing position: {symbol} qty={close_qty}")
        await self._signed_request("POST", ENDPOINTS["order"], params)

        logger.info(f"Position closed: {symbol}")
        return True

    async def set_leverage(self, symbol: str, leverage: int) -> bool:
        """
        Set leverage for a symbol.

        Args:
            symbol: Trading pair symbol
            leverage: Leverage value (1-125)

        Returns:
            True if successful

        Raises:
            LeverageError: If leverage change fails
        """
        if not 1 <= leverage <= 125:
            raise LeverageError(f"Leverage must be between 1 and 125, got {leverage}")

        params = {"symbol": symbol.upper(), "leverage": leverage}

        try:
            response = await self._signed_request("POST", ENDPOINTS["leverage"], params)
            actual_leverage = response.get("leverage", leverage)
            logger.info(f"Leverage set: {symbol} = {actual_leverage}x")
            return True
        except BinanceError as e:
            if e.code == -4028:
                raise LeverageError(str(e))
            raise

    # =========================================================================
    # WEBSOCKET STREAMING
    # =========================================================================

    async def stream_prices(
        self,
        symbols: List[str],
        callback: Callable[[str, float, float], None],
    ) -> None:
        """
        Stream real-time price updates via WebSocket.

        Args:
            symbols: List of symbols to stream
            callback: Async callback function(symbol, price, timestamp)

        Example:
            async def on_price(symbol, price, timestamp):
                print(f"{symbol}: {price}")

            await client.stream_prices(["BTCUSDT"], on_price)
        """
        # Build combined stream URL
        streams = [f"{s.lower()}@markPrice" for s in symbols]
        stream_name = "/".join(streams)
        ws_url = f"{self.ws_url}/stream?streams={stream_name}"

        logger.info(f"Starting price stream for: {symbols}")

        try:
            async with aiohttp.ClientSession() as session:
                async with session.ws_connect(ws_url) as ws:
                    self._ws_connections["prices"] = ws

                    async for msg in ws:
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            data = msg.json()

                            if "data" in data:
                                stream_data = data["data"]
                                symbol = stream_data["s"]
                                price = float(stream_data["p"])
                                timestamp = stream_data["E"]

                                # Call callback (support both sync and async)
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
            if "prices" in self._ws_connections:
                del self._ws_connections["prices"]

    async def stream_user_data(
        self,
        on_order: Optional[Callable[[Order], None]] = None,
        on_position: Optional[Callable[[Position], None]] = None,
        on_balance: Optional[Callable[[str, float], None]] = None,
    ) -> None:
        """
        Stream user data updates (orders, positions, balance).

        Args:
            on_order: Callback for order updates
            on_position: Callback for position updates
            on_balance: Callback for balance updates
        """
        # Get listen key
        response = await self._signed_request("POST", ENDPOINTS["listen_key"])
        self._listen_key = response["listenKey"]

        # Start keep-alive task
        self._listen_key_task = asyncio.create_task(self._keep_alive_listen_key())

        ws_url = f"{self.ws_url}/ws/{self._listen_key}"

        logger.info("Starting user data stream")

        try:
            async with aiohttp.ClientSession() as session:
                async with session.ws_connect(ws_url) as ws:
                    self._ws_connections["user_data"] = ws

                    async for msg in ws:
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            data = msg.json()
                            event_type = data.get("e")

                            if event_type == "ORDER_TRADE_UPDATE" and on_order:
                                order_data = data["o"]
                                order = Order(
                                    id=str(order_data["i"]),
                                    symbol=order_data["s"],
                                    side=OrderSide(order_data["S"]),
                                    quantity=float(order_data["q"]),
                                    status=OrderStatus(order_data["X"]),
                                    fill_price=float(order_data.get("ap", 0)) or None,
                                    order_type=OrderType(order_data["o"]),
                                )
                                if asyncio.iscoroutinefunction(on_order):
                                    await on_order(order)
                                else:
                                    on_order(order)

                            elif event_type == "ACCOUNT_UPDATE":
                                # Handle position updates
                                if on_position and "P" in data.get("a", {}):
                                    for pos_data in data["a"]["P"]:
                                        qty = float(pos_data["pa"])
                                        if qty != 0:
                                            position = Position(
                                                symbol=pos_data["s"],
                                                side=PositionSide.LONG if qty > 0 else PositionSide.SHORT,
                                                entry_price=float(pos_data["ep"]),
                                                quantity=abs(qty),
                                                unrealized_pnl=float(pos_data["up"]),
                                            )
                                            if asyncio.iscoroutinefunction(on_position):
                                                await on_position(position)
                                            else:
                                                on_position(position)

                                # Handle balance updates
                                if on_balance and "B" in data.get("a", {}):
                                    for bal_data in data["a"]["B"]:
                                        asset = bal_data["a"]
                                        balance = float(bal_data["wb"])
                                        if asyncio.iscoroutinefunction(on_balance):
                                            await on_balance(asset, balance)
                                        else:
                                            on_balance(asset, balance)

        except asyncio.CancelledError:
            logger.info("User data stream cancelled")
        except Exception as e:
            logger.error(f"User data stream error: {e}")
            raise
        finally:
            if "user_data" in self._ws_connections:
                del self._ws_connections["user_data"]

    async def _keep_alive_listen_key(self) -> None:
        """Keep listen key alive by sending heartbeat every 30 minutes."""
        while True:
            try:
                await asyncio.sleep(30 * 60)  # 30 minutes
                if self._listen_key:
                    await self._signed_request(
                        "PUT",
                        ENDPOINTS["listen_key"],
                        {"listenKey": self._listen_key},
                    )
                    logger.debug("Listen key renewed")
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning(f"Failed to renew listen key: {e}")

    # =========================================================================
    # UTILITY METHODS
    # =========================================================================

    async def get_exchange_info(
        self, symbol: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get exchange information and trading rules."""
        params = {}
        if symbol:
            params["symbol"] = symbol.upper()

        return await self._public_request("GET", ENDPOINTS["exchange_info"], params)

    async def get_symbol_info(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get trading rules for a specific symbol."""
        info = await self.get_exchange_info()
        for s in info.get("symbols", []):
            if s["symbol"] == symbol.upper():
                return s
        return None

    def is_connected(self) -> bool:
        """Check if client is connected."""
        return self._connected

    async def __aenter__(self) -> "BinanceClient":
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.disconnect()


# =============================================================================
# FACTORY FUNCTION
# =============================================================================


def create_binance_client(
    api_key: Optional[str] = None,
    api_secret: Optional[str] = None,
    testnet: bool = True,
) -> BinanceClient:
    """
    Factory function to create BinanceClient with environment variables fallback.

    Args:
        api_key: API key (falls back to BINANCE_API_KEY env var)
        api_secret: API secret (falls back to BINANCE_API_SECRET env var)
        testnet: Use testnet environment

    Returns:
        BinanceClient instance

    Raises:
        ValueError: If credentials not provided
    """
    import os

    key = api_key or os.environ.get("BINANCE_API_KEY")
    secret = api_secret or os.environ.get("BINANCE_API_SECRET")

    if not key or not secret:
        raise ValueError(
            "API credentials required. Provide api_key/api_secret or set "
            "BINANCE_API_KEY/BINANCE_API_SECRET environment variables."
        )

    return BinanceClient(api_key=key, api_secret=secret, testnet=testnet)


# =============================================================================
# EXAMPLE USAGE
# =============================================================================

if __name__ == "__main__":
    import os

    async def main():
        # Example usage
        client = BinanceClient(
            api_key=os.getenv("BINANCE_API_KEY", "test_key"),
            api_secret=os.getenv("BINANCE_API_SECRET", "test_secret"),
            testnet=True,
        )

        async with client:
            # Get balance
            balance = await client.get_account_balance()
            print(f"USDT Balance: {balance}")

            # Get candles
            candles = await client.get_candles("BTCUSDT", "1h", limit=10)
            print(f"\nBTCUSDT Last 10 Hourly Candles:\n{candles.tail()}")

            # Get funding rate
            funding = await client.get_funding_rate("BTCUSDT")
            print(f"\nBTCUSDT Funding Rate: {funding * 100:.4f}%")

            # Get positions
            positions = await client.get_open_positions()
            print(f"\nOpen Positions: {len(positions)}")
            for pos in positions:
                print(f"  {pos.symbol} {pos.side} qty={pos.quantity} PnL={pos.unrealized_pnl}")

    asyncio.run(main())
