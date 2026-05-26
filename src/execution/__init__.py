from __future__ import annotations

"""
Order Execution Module

This module handles order placement and management:

Order Types:
- Market orders
- Limit orders
- Stop orders
- Stop-limit orders
- Trailing stops

Execution Features:
- Smart order routing
- Slippage monitoring
- Fill confirmation
- Partial fill handling
- Order modification and cancellation

Position Management:
- Entry execution
- Stop-loss placement
- Take-profit placement
- Position scaling (in/out)
- Emergency position closure

Components:
- OrderExecutor: Main execution engine
- TrailingStopManager: ATR-based trailing stop management
- OrderQueue: Concurrent order queue with priority
- Models: Data classes for orders and execution results
"""

from .models import (
    CloseResult,
    ExecutionResult,
    OrderRequest,
    OrderStatus,
    OrderStatusEnum,
    Position,
    Signal,
    SignalType,
)
from .executor import OrderExecutor
from .trailing_stop import TrailingStopManager, TrailConfig, TrailState
from .order_queue import OrderQueue, OrderPriority, QueuedOrder

__all__ = [
    # Main executor
    "OrderExecutor",
    # Trailing stops
    "TrailingStopManager",
    "TrailConfig",
    "TrailState",
    # Order queue
    "OrderQueue",
    "OrderPriority",
    "QueuedOrder",
    # Models
    "Signal",
    "SignalType",
    "OrderRequest",
    "ExecutionResult",
    "OrderStatus",
    "OrderStatusEnum",
    "Position",
    "CloseResult",
]
