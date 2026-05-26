from __future__ import annotations

"""
Order Executor

Main order execution engine that routes orders to appropriate
brokers (OANDA for forex, Binance for crypto) with comprehensive
error handling, slippage monitoring, and position management.

Author: HERMES Trading System
"""

import asyncio
import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Protocol, Union

from .models import (
    CloseResult,
    ExecutionResult,
    OrderRequest,
    Position,
    Signal,
    SignalType,
)

# Configure logging
logger = logging.getLogger(__name__)


class RiskManagerProtocol(Protocol):
    """Protocol for risk manager interface."""

    def validate_trade(
        self,
        instrument: str,
        side: str,
        quantity: float,
        entry_price: float,
        stop_loss: float,
        account_balance: float,
    ) -> bool:
        """Validate if trade passes risk checks."""
        ...

    def calculate_position_size(
        self,
        account_balance: float,
        risk_per_trade: float,
        entry_price: float,
        stop_loss: float,
        pip_value: Optional[float] = None,
    ) -> float:
        """Calculate appropriate position size."""
        ...

    def get_max_position_size(
        self,
        instrument: str,
        account_balance: float,
    ) -> float:
        """Get maximum allowed position size."""
        ...


class OandaClientProtocol(Protocol):
    """Protocol for OANDA client interface."""

    async def place_order(
        self,
        instrument: str,
        units: float,
        side: str,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        trailing_stop_distance: Optional[float] = None,
    ) -> Any:
        """Place a market order."""
        ...

    async def close_position(self, trade_id: str) -> bool:
        """Close a specific trade."""
        ...

    async def modify_trade(
        self,
        trade_id: str,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        trailing_stop_distance: Optional[float] = None,
    ) -> bool:
        """Modify an existing trade."""
        ...

    async def get_open_positions(self) -> List[Any]:
        """Get all open positions."""
        ...

    async def get_current_price(self, instrument: str) -> Any:
        """Get current price for instrument."""
        ...

    async def get_account_balance(self) -> float:
        """Get account balance."""
        ...


class BinanceClientProtocol(Protocol):
    """Protocol for Binance client interface."""

    async def place_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        leverage: Optional[int] = None,
        order_type: str = "MARKET",
        price: Optional[float] = None,
        reduce_only: bool = False,
    ) -> Any:
        """Place a futures order."""
        ...

    async def close_position(
        self,
        symbol: str,
        quantity: Optional[float] = None,
    ) -> bool:
        """Close a position."""
        ...

    async def set_leverage(self, symbol: str, leverage: int) -> bool:
        """Set leverage for symbol."""
        ...

    async def get_open_positions(
        self,
        symbol: Optional[str] = None,
    ) -> List[Any]:
        """Get open positions."""
        ...

    async def get_account_balance(self, asset: str = "USDT") -> float:
        """Get account balance."""
        ...


class OrderExecutor:
    """
    Main order execution engine.

    Handles order routing, execution, and position management
    across multiple brokers (OANDA for forex, Binance for crypto).

    Features:
        - Unified interface for both forex and crypto
        - Risk validation before execution
        - Slippage monitoring and reporting
        - Automatic stop-loss and take-profit placement
        - Position modification and closure
        - Execution latency tracking

    Example:
        ```python
        executor = OrderExecutor(
            oanda_client=oanda,
            binance_client=binance,
            risk_manager=risk_mgr,
        )

        result = await executor.execute_signal(signal, account_balance=10000)
        if result.success:
            print(f"Order filled at {result.fill_price}")
        ```
    """

    def __init__(
        self,
        oanda_client: Optional[OandaClientProtocol] = None,
        binance_client: Optional[BinanceClientProtocol] = None,
        risk_manager: Optional[RiskManagerProtocol] = None,
        max_slippage_pct: float = 0.5,
        default_leverage: int = 10,
    ):
        """
        Initialize OrderExecutor.

        Args:
            oanda_client: OANDA client for forex trading
            binance_client: Binance client for crypto trading
            risk_manager: Risk manager for trade validation
            max_slippage_pct: Maximum acceptable slippage percentage
            default_leverage: Default leverage for crypto trades
        """
        self.oanda_client = oanda_client
        self.binance_client = binance_client
        self.risk_manager = risk_manager
        self.max_slippage_pct = max_slippage_pct
        self.default_leverage = default_leverage

        # Execution statistics
        self._execution_count = 0
        self._successful_executions = 0
        self._total_slippage = 0.0
        self._execution_times: List[float] = []

        logger.info(
            f"OrderExecutor initialized - "
            f"OANDA: {'enabled' if oanda_client else 'disabled'}, "
            f"Binance: {'enabled' if binance_client else 'disabled'}"
        )

    async def execute_signal(
        self,
        signal: Signal,
        account_balance: float,
    ) -> ExecutionResult:
        """
        Execute a trading signal.

        Routes the signal to the appropriate broker based on
        the signal's broker attribute and validates risk limits
        before execution.

        Args:
            signal: Trading signal to execute
            account_balance: Current account balance for position sizing

        Returns:
            ExecutionResult with fill details or error

        Raises:
            ValueError: If broker is not supported or client not configured
        """
        start_time = time.time()
        self._execution_count += 1

        logger.info(
            f"Executing signal: {signal.signal_type.value} {signal.instrument} "
            f"@ {signal.entry_price} (confidence: {signal.confidence:.2%})"
        )

        try:
            # Validate we have the required client
            if signal.broker == "oanda" and not self.oanda_client:
                return ExecutionResult.failure(
                    error="OANDA client not configured",
                    broker="oanda",
                    instrument=signal.instrument,
                )

            if signal.broker == "binance" and not self.binance_client:
                return ExecutionResult.failure(
                    error="Binance client not configured",
                    broker="binance",
                    instrument=signal.instrument,
                )

            # Calculate position size
            position_size = self._calculate_position_size(
                signal=signal,
                account_balance=account_balance,
            )

            if position_size <= 0:
                return ExecutionResult.failure(
                    error="Invalid position size calculated",
                    broker=signal.broker,
                    instrument=signal.instrument,
                )

            # Validate risk limits
            if self.risk_manager:
                is_valid = self.risk_manager.validate_trade(
                    instrument=signal.instrument,
                    side=signal.side,
                    quantity=position_size,
                    entry_price=signal.entry_price,
                    stop_loss=signal.stop_loss,
                    account_balance=account_balance,
                )

                if not is_valid:
                    return ExecutionResult.failure(
                        error="Trade rejected by risk manager",
                        broker=signal.broker,
                        instrument=signal.instrument,
                    )

            # Route to appropriate broker
            if signal.broker == "oanda":
                result = await self.place_forex_order(
                    instrument=signal.instrument,
                    units=int(position_size),
                    side=signal.side,
                    stop_loss=signal.stop_loss,
                    take_profit=signal.take_profit,
                )
            else:
                leverage = signal.metadata.get("leverage", self.default_leverage)
                result = await self.place_crypto_order(
                    symbol=signal.instrument,
                    quantity=position_size,
                    side=signal.side,
                    stop_loss=signal.stop_loss,
                    take_profit=signal.take_profit,
                    leverage=leverage,
                )

            # Calculate execution time
            execution_time_ms = (time.time() - start_time) * 1000
            self._execution_times.append(execution_time_ms)

            if result.success:
                self._successful_executions += 1
                if result.slippage:
                    self._total_slippage += abs(result.slippage)

                # Check for excessive slippage
                if result.slippage_pct and abs(result.slippage_pct) > self.max_slippage_pct:
                    logger.warning(
                        f"High slippage detected: {result.slippage_pct:.3f}% "
                        f"on {signal.instrument}"
                    )

            result.execution_time_ms = execution_time_ms
            return result

        except Exception as e:
            logger.error(f"Execution failed: {e}", exc_info=True)
            return ExecutionResult.failure(
                error=str(e),
                broker=signal.broker,
                instrument=signal.instrument,
            )

    async def place_forex_order(
        self,
        instrument: str,
        units: int,
        side: str,
        stop_loss: float,
        take_profit: float,
    ) -> ExecutionResult:
        """
        Place a forex order via OANDA.

        Args:
            instrument: Trading instrument (e.g., EUR_USD)
            units: Number of units to trade
            side: Order side (BUY, SELL)
            stop_loss: Stop loss price
            take_profit: Take profit price

        Returns:
            ExecutionResult with order details
        """
        if not self.oanda_client:
            return ExecutionResult.failure(
                error="OANDA client not configured",
                broker="oanda",
                instrument=instrument,
            )

        logger.info(f"Placing forex order: {side} {units} {instrument}")

        try:
            # Get current price for slippage calculation
            price_data = await self.oanda_client.get_current_price(instrument)
            expected_price = price_data.ask if side == "BUY" else price_data.bid

            # Place order
            order = await self.oanda_client.place_order(
                instrument=instrument,
                units=abs(units),
                side=side.lower(),
                stop_loss=stop_loss,
                take_profit=take_profit,
            )

            # Calculate slippage
            fill_price = order.fill_price if order.fill_price else expected_price
            slippage = fill_price - expected_price
            slippage_pct = (slippage / expected_price) * 100 if expected_price > 0 else 0.0

            logger.info(
                f"Forex order filled: {order.id} @ {fill_price} "
                f"(slippage: {slippage_pct:.4f}%)"
            )

            return ExecutionResult(
                success=True,
                order_id=order.id,
                fill_price=fill_price,
                slippage=slippage,
                slippage_pct=slippage_pct,
                broker="oanda",
                instrument=instrument,
                side=side,
                quantity=abs(units),
                timestamp=datetime.utcnow(),
            )

        except Exception as e:
            logger.error(f"Forex order failed: {e}")
            return ExecutionResult.failure(
                error=str(e),
                broker="oanda",
                instrument=instrument,
            )

    async def place_crypto_order(
        self,
        symbol: str,
        quantity: float,
        side: str,
        stop_loss: float,
        take_profit: float,
        leverage: int,
    ) -> ExecutionResult:
        """
        Place a crypto futures order via Binance.

        Args:
            symbol: Trading symbol (e.g., BTCUSDT)
            quantity: Order quantity
            side: Order side (BUY, SELL)
            stop_loss: Stop loss price
            take_profit: Take profit price
            leverage: Leverage multiplier

        Returns:
            ExecutionResult with order details
        """
        if not self.binance_client:
            return ExecutionResult.failure(
                error="Binance client not configured",
                broker="binance",
                instrument=symbol,
            )

        logger.info(f"Placing crypto order: {side} {quantity} {symbol} @ {leverage}x")

        try:
            # Place order with stop loss and take profit
            order = await self.binance_client.place_order(
                symbol=symbol,
                side=side.upper(),
                quantity=quantity,
                stop_loss=stop_loss,
                take_profit=take_profit,
                leverage=leverage,
            )

            # Get fill price
            fill_price = order.fill_price if order.fill_price else 0.0

            logger.info(
                f"Crypto order filled: {order.id} @ {fill_price}"
            )

            return ExecutionResult(
                success=True,
                order_id=order.id,
                fill_price=fill_price,
                slippage=None,  # Binance doesn't provide expected price easily
                slippage_pct=None,
                broker="binance",
                instrument=symbol,
                side=side,
                quantity=quantity,
                timestamp=datetime.utcnow(),
            )

        except Exception as e:
            logger.error(f"Crypto order failed: {e}")
            return ExecutionResult.failure(
                error=str(e),
                broker="binance",
                instrument=symbol,
            )

    async def close_position(
        self,
        position_id: str,
        broker: str,
    ) -> bool:
        """
        Close a specific position.

        Args:
            position_id: Position/trade ID to close
            broker: Broker name (oanda, binance)

        Returns:
            True if position closed successfully
        """
        logger.info(f"Closing position {position_id} on {broker}")

        try:
            if broker == "oanda":
                if not self.oanda_client:
                    logger.error("OANDA client not configured")
                    return False
                return await self.oanda_client.close_position(position_id)

            elif broker == "binance":
                if not self.binance_client:
                    logger.error("Binance client not configured")
                    return False
                # For Binance, position_id is typically the symbol
                return await self.binance_client.close_position(position_id)

            else:
                logger.error(f"Unknown broker: {broker}")
                return False

        except Exception as e:
            logger.error(f"Failed to close position: {e}")
            return False

    async def modify_stop_loss(
        self,
        position_id: str,
        new_stop: float,
        broker: str,
    ) -> bool:
        """
        Modify stop loss for an existing position.

        Args:
            position_id: Position/trade ID
            new_stop: New stop loss price
            broker: Broker name

        Returns:
            True if modification succeeded
        """
        logger.info(f"Modifying stop loss for {position_id} to {new_stop}")

        try:
            if broker == "oanda":
                if not self.oanda_client:
                    logger.error("OANDA client not configured")
                    return False
                return await self.oanda_client.modify_trade(
                    trade_id=position_id,
                    stop_loss=new_stop,
                )

            elif broker == "binance":
                # Binance requires canceling existing stop and placing new one
                # This is handled differently - would need symbol info
                logger.warning(
                    "Binance stop loss modification requires order management"
                )
                return False

            else:
                logger.error(f"Unknown broker: {broker}")
                return False

        except Exception as e:
            logger.error(f"Failed to modify stop loss: {e}")
            return False

    async def close_all_positions(self) -> List[CloseResult]:
        """
        Close all open positions across all configured brokers.

        This is typically used for:
        - End of trading session
        - Emergency risk management
        - System shutdown

        Returns:
            List of CloseResult for each position
        """
        logger.warning("Closing ALL positions across all brokers")
        results: List[CloseResult] = []

        # Close OANDA positions
        if self.oanda_client:
            try:
                positions = await self.oanda_client.get_open_positions()
                for pos in positions:
                    for trade_id in pos.trade_ids:
                        try:
                            success = await self.oanda_client.close_position(trade_id)
                            results.append(
                                CloseResult(
                                    success=success,
                                    position_id=trade_id,
                                    broker="oanda",
                                    instrument=pos.instrument,
                                )
                            )
                        except Exception as e:
                            results.append(
                                CloseResult.failure(
                                    position_id=trade_id,
                                    broker="oanda",
                                    error=str(e),
                                )
                            )
            except Exception as e:
                logger.error(f"Failed to get OANDA positions: {e}")

        # Close Binance positions
        if self.binance_client:
            try:
                positions = await self.binance_client.get_open_positions()
                for pos in positions:
                    try:
                        success = await self.binance_client.close_position(pos.symbol)
                        results.append(
                            CloseResult(
                                success=success,
                                position_id=pos.symbol,
                                broker="binance",
                                instrument=pos.symbol,
                            )
                        )
                    except Exception as e:
                        results.append(
                            CloseResult.failure(
                                position_id=pos.symbol,
                                broker="binance",
                                error=str(e),
                            )
                        )
            except Exception as e:
                logger.error(f"Failed to get Binance positions: {e}")

        successful = sum(1 for r in results if r.success)
        logger.info(f"Closed {successful}/{len(results)} positions")

        return results

    def _calculate_position_size(
        self,
        signal: Signal,
        account_balance: float,
    ) -> float:
        """
        Calculate position size based on signal and risk parameters.

        Uses risk manager if available, otherwise uses default
        2% risk per trade calculation.

        Args:
            signal: Trading signal
            account_balance: Account balance

        Returns:
            Position size in units/contracts
        """
        if self.risk_manager:
            return self.risk_manager.calculate_position_size(
                account_balance=account_balance,
                risk_per_trade=0.02,  # 2% default
                entry_price=signal.entry_price,
                stop_loss=signal.stop_loss,
            )

        # Default position sizing: 2% risk
        risk_amount = account_balance * 0.02
        stop_distance = abs(signal.entry_price - signal.stop_loss)

        if stop_distance == 0:
            logger.warning("Stop distance is zero, using minimum position")
            return 0.0

        position_size = risk_amount / stop_distance

        # Apply confidence scaling
        position_size *= signal.confidence

        return position_size

    @property
    def execution_stats(self) -> Dict[str, Any]:
        """Get execution statistics."""
        avg_execution_time = (
            sum(self._execution_times) / len(self._execution_times)
            if self._execution_times
            else 0.0
        )

        success_rate = (
            self._successful_executions / self._execution_count
            if self._execution_count > 0
            else 0.0
        )

        avg_slippage = (
            self._total_slippage / self._successful_executions
            if self._successful_executions > 0
            else 0.0
        )

        return {
            "total_executions": self._execution_count,
            "successful_executions": self._successful_executions,
            "success_rate": success_rate,
            "avg_execution_time_ms": avg_execution_time,
            "avg_slippage": avg_slippage,
            "total_slippage": self._total_slippage,
        }

    def reset_stats(self) -> None:
        """Reset execution statistics."""
        self._execution_count = 0
        self._successful_executions = 0
        self._total_slippage = 0.0
        self._execution_times.clear()
        logger.info("Execution statistics reset")
