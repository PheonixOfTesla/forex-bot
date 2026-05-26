from __future__ import annotations

"""
Broker Integrations

This module provides unified interfaces to trading brokers:
- OANDA: Forex trading (EUR/USD, GBP/USD, etc.)
- Binance: Cryptocurrency trading (BTC, XRP, ETH, etc.)

Each broker client implements a common interface for:
- Account information retrieval
- Price streaming
- Order placement and management
- Position tracking
"""

from .binance_client import (
    # Main Client
    BinanceClient,
    create_binance_client,
    # Data Models
    Position as BinancePosition,
    Order as BinanceOrder,
    # Enums
    OrderSide as BinanceOrderSide,
    OrderType,
    OrderStatus as BinanceOrderStatus,
    PositionSide,
    # Exceptions
    BinanceError,
    InsufficientBalanceError,
    LeverageError,
    InvalidSymbolError,
    OrderError,
    ConnectionError as BinanceConnectionError,
    RateLimitError as BinanceRateLimitError,
    # Constants
    TESTNET_URL,
    LIVE_URL,
    SUPPORTED_SYMBOLS,
)

from .oanda import (
    # Client
    OandaClient,
    create_oanda_client,
    # Data Models
    Position as OandaPosition,
    Order as OandaOrder,
    Candle,
    PriceUpdate,
    AccountSummary,
    # Enums
    OrderSide as OandaOrderSide,
    OrderStatus as OandaOrderStatus,
    Granularity,
    # Exceptions
    OandaError,
    RateLimitError as OandaRateLimitError,
    InsufficientMarginError,
    AuthenticationError,
    InstrumentNotFoundError,
    OrderRejectedError,
    ConnectionError as OandaConnectionError,
    # Constants
    PRACTICE_URL,
    LIVE_URL as OANDA_LIVE_URL,
    PRACTICE_STREAM_URL,
    LIVE_STREAM_URL,
)

__all__ = [
    # Binance Exports
    "BinanceClient",
    "create_binance_client",
    "BinancePosition",
    "BinanceOrder",
    "BinanceOrderSide",
    "OrderType",
    "BinanceOrderStatus",
    "PositionSide",
    "BinanceError",
    "InsufficientBalanceError",
    "LeverageError",
    "InvalidSymbolError",
    "OrderError",
    "BinanceConnectionError",
    "BinanceRateLimitError",
    "TESTNET_URL",
    "LIVE_URL",
    "SUPPORTED_SYMBOLS",
    # OANDA Exports
    "OandaClient",
    "create_oanda_client",
    "OandaPosition",
    "OandaOrder",
    "Candle",
    "PriceUpdate",
    "AccountSummary",
    "OandaOrderSide",
    "OandaOrderStatus",
    "Granularity",
    "OandaError",
    "OandaRateLimitError",
    "InsufficientMarginError",
    "AuthenticationError",
    "InstrumentNotFoundError",
    "OrderRejectedError",
    "OandaConnectionError",
    "PRACTICE_URL",
    "OANDA_LIVE_URL",
    "PRACTICE_STREAM_URL",
    "LIVE_STREAM_URL",
]
