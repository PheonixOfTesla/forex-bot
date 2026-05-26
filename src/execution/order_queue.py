"""
Order Queue Manager

Manages a queue of pending orders with rate limiting,
priority handling, and concurrent execution control.

Author: HERMES Trading System
"""

import asyncio
import logging
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Deque, Dict, List, Optional, Protocol
from uuid import uuid4

from .models import (
    ExecutionResult,
    OrderRequest,
    OrderStatus,
    OrderStatusEnum,
)

# Configure logging
logger = logging.getLogger(__name__)


class OrderPriority(int, Enum):
    """Order priority levels."""
    LOW = 0
    NORMAL = 1
    HIGH = 2
    URGENT = 3  # For emergency closes


@dataclass
class QueuedOrder:
    """
    Wrapper for orders in the queue.

    Attributes:
        queue_id: Unique queue identifier
        order_request: The order request
        priority: Order priority
        status: Current status
        result: Execution result (when complete)
        created_at: When added to queue
        started_at: When execution started
        completed_at: When execution completed
        attempts: Number of execution attempts
        max_attempts: Maximum retry attempts
        errors: List of error messages from failed attempts
    """
    queue_id: str
    order_request: OrderRequest
    priority: OrderPriority = OrderPriority.NORMAL
    status: OrderStatusEnum = OrderStatusEnum.QUEUED
    result: Optional[ExecutionResult] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    attempts: int = 0
    max_attempts: int = 3
    errors: List[str] = field(default_factory=list)

    @property
    def wait_time_ms(self) -> float:
        """Get time waiting in queue in milliseconds."""
        if self.started_at:
            return (self.started_at - self.created_at).total_seconds() * 1000
        return (datetime.utcnow() - self.created_at).total_seconds() * 1000

    @property
    def execution_time_ms(self) -> Optional[float]:
        """Get execution time in milliseconds."""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds() * 1000
        return None


class ExecutorProtocol(Protocol):
    """Protocol for OrderExecutor interface."""

    async def execute_signal(
        self,
        signal: Any,
        account_balance: float,
    ) -> ExecutionResult:
        """Execute a trading signal."""
        ...


class OrderQueue:
    """
    Order queue manager with concurrent execution control.

    Manages pending orders with:
    - Priority-based ordering
    - Concurrent execution limits
    - Automatic retry on failure
    - Rate limiting between executions
    - Queue persistence (optional)

    Example:
        ```python
        queue = OrderQueue(max_concurrent=3)

        # Enqueue orders
        queue_id = await queue.enqueue(order_request)

        # Process queue (typically run in background)
        asyncio.create_task(queue.process_queue())

        # Check status
        status = queue.get_status(queue_id)
        ```
    """

    def __init__(
        self,
        max_concurrent: int = 3,
        min_interval_ms: float = 100,
        max_queue_size: int = 100,
        on_order_complete: Optional[Callable[[str, ExecutionResult], None]] = None,
        on_queue_empty: Optional[Callable[[], None]] = None,
    ):
        """
        Initialize OrderQueue.

        Args:
            max_concurrent: Maximum concurrent order executions
            min_interval_ms: Minimum interval between executions
            max_queue_size: Maximum queue size
            on_order_complete: Callback when order completes
            on_queue_empty: Callback when queue becomes empty
        """
        self.max_concurrent = max_concurrent
        self.min_interval_ms = min_interval_ms
        self.max_queue_size = max_queue_size
        self.on_order_complete = on_order_complete
        self.on_queue_empty = on_queue_empty

        # Queue storage (priority queues)
        self._urgent_queue: Deque[QueuedOrder] = deque()
        self._high_queue: Deque[QueuedOrder] = deque()
        self._normal_queue: Deque[QueuedOrder] = deque()
        self._low_queue: Deque[QueuedOrder] = deque()

        # Order tracking
        self._orders: Dict[str, QueuedOrder] = {}
        self._processing: Dict[str, QueuedOrder] = {}

        # Control flags
        self._running = False
        self._paused = False
        self._process_task: Optional[asyncio.Task] = None

        # Executor (set via set_executor)
        self._executor: Optional[ExecutorProtocol] = None
        self._account_balance: float = 0.0

        # Synchronization
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._queue_lock = asyncio.Lock()
        self._last_execution_time: float = 0.0

        # Statistics
        self._total_processed = 0
        self._total_successful = 0
        self._total_failed = 0
        self._total_wait_time_ms = 0.0

        logger.info(
            f"OrderQueue initialized - max_concurrent: {max_concurrent}, "
            f"max_queue: {max_queue_size}"
        )

    def set_executor(
        self,
        executor: ExecutorProtocol,
        account_balance: float,
    ) -> None:
        """
        Set the order executor and account balance.

        Args:
            executor: OrderExecutor instance
            account_balance: Current account balance
        """
        self._executor = executor
        self._account_balance = account_balance
        logger.debug(f"Executor set with balance: {account_balance}")

    def update_balance(self, balance: float) -> None:
        """Update account balance for position sizing."""
        self._account_balance = balance

    async def enqueue(
        self,
        order_request: OrderRequest,
        priority: OrderPriority = OrderPriority.NORMAL,
    ) -> str:
        """
        Add order to the queue.

        Args:
            order_request: Order to queue
            priority: Order priority level

        Returns:
            Queue ID for tracking

        Raises:
            ValueError: If queue is full
        """
        async with self._queue_lock:
            # Check queue size
            total_queued = (
                len(self._urgent_queue) +
                len(self._high_queue) +
                len(self._normal_queue) +
                len(self._low_queue)
            )

            if total_queued >= self.max_queue_size:
                raise ValueError(
                    f"Queue full ({total_queued}/{self.max_queue_size})"
                )

            # Create queued order
            queue_id = str(uuid4())
            queued_order = QueuedOrder(
                queue_id=queue_id,
                order_request=order_request,
                priority=priority,
            )

            # Add to appropriate queue
            queue = self._get_queue_for_priority(priority)
            queue.append(queued_order)

            # Track order
            self._orders[queue_id] = queued_order

            logger.info(
                f"Order enqueued: {queue_id} "
                f"({order_request.instrument} {order_request.side}) "
                f"priority={priority.name}"
            )

            return queue_id

    async def process_queue(self) -> None:
        """
        Process orders in the queue.

        This method runs continuously until stopped, processing
        orders respecting priority, concurrency limits, and
        rate limiting.
        """
        if not self._executor:
            raise RuntimeError("Executor not set. Call set_executor() first.")

        self._running = True
        logger.info("Queue processing started")

        try:
            while self._running:
                # Check if paused
                if self._paused:
                    await asyncio.sleep(0.1)
                    continue

                # Get next order to process
                order = await self._get_next_order()

                if order is None:
                    # Queue empty, wait a bit
                    if self.on_queue_empty:
                        if asyncio.iscoroutinefunction(self.on_queue_empty):
                            await self.on_queue_empty()
                        else:
                            self.on_queue_empty()

                    await asyncio.sleep(0.1)
                    continue

                # Process order with concurrency control
                asyncio.create_task(self._process_order(order))

        except asyncio.CancelledError:
            logger.info("Queue processing cancelled")
        except Exception as e:
            logger.error(f"Queue processing error: {e}", exc_info=True)
        finally:
            self._running = False
            logger.info("Queue processing stopped")

    async def _process_order(self, order: QueuedOrder) -> None:
        """Process a single order with semaphore control."""
        async with self._semaphore:
            # Rate limiting
            await self._apply_rate_limit()

            # Update status
            order.status = OrderStatusEnum.PROCESSING
            order.started_at = datetime.utcnow()
            order.attempts += 1

            self._processing[order.queue_id] = order

            logger.debug(
                f"Processing order {order.queue_id} "
                f"(attempt {order.attempts}/{order.max_attempts})"
            )

            try:
                # Execute the order
                result = await self._executor.execute_signal(
                    signal=order.order_request.signal,
                    account_balance=self._account_balance,
                )

                # Update order with result
                order.result = result
                order.completed_at = datetime.utcnow()

                if result.success:
                    order.status = OrderStatusEnum.FILLED
                    self._total_successful += 1
                    logger.info(
                        f"Order filled: {order.queue_id} @ {result.fill_price}"
                    )
                else:
                    # Check if should retry
                    if order.attempts < order.max_attempts:
                        order.errors.append(result.error or "Unknown error")
                        order.status = OrderStatusEnum.PENDING

                        # Re-queue for retry
                        await self._requeue_order(order)

                        logger.warning(
                            f"Order failed, retrying: {order.queue_id} "
                            f"({result.error})"
                        )
                    else:
                        order.status = OrderStatusEnum.FAILED
                        self._total_failed += 1
                        logger.error(
                            f"Order failed permanently: {order.queue_id} "
                            f"({result.error})"
                        )

            except Exception as e:
                order.errors.append(str(e))
                order.completed_at = datetime.utcnow()

                if order.attempts < order.max_attempts:
                    order.status = OrderStatusEnum.PENDING
                    await self._requeue_order(order)
                    logger.warning(f"Order error, retrying: {order.queue_id} ({e})")
                else:
                    order.status = OrderStatusEnum.FAILED
                    order.result = ExecutionResult.failure(str(e))
                    self._total_failed += 1
                    logger.error(f"Order failed permanently: {order.queue_id} ({e})")

            finally:
                # Remove from processing
                if order.queue_id in self._processing:
                    del self._processing[order.queue_id]

                self._total_processed += 1

                # Track wait time
                if order.started_at:
                    self._total_wait_time_ms += order.wait_time_ms

                # Callback
                if self.on_order_complete and order.result:
                    if asyncio.iscoroutinefunction(self.on_order_complete):
                        await self.on_order_complete(order.queue_id, order.result)
                    else:
                        self.on_order_complete(order.queue_id, order.result)

    async def cancel(self, queue_id: str) -> bool:
        """
        Cancel a queued order.

        Args:
            queue_id: Queue ID to cancel

        Returns:
            True if order was cancelled
        """
        async with self._queue_lock:
            order = self._orders.get(queue_id)

            if not order:
                logger.warning(f"Order not found: {queue_id}")
                return False

            if order.status == OrderStatusEnum.PROCESSING:
                logger.warning(f"Cannot cancel processing order: {queue_id}")
                return False

            if order.status in (OrderStatusEnum.FILLED, OrderStatusEnum.CANCELLED):
                logger.warning(f"Order already completed: {queue_id}")
                return False

            # Remove from queue
            for queue in [
                self._urgent_queue,
                self._high_queue,
                self._normal_queue,
                self._low_queue,
            ]:
                try:
                    queue.remove(order)
                    break
                except ValueError:
                    continue

            order.status = OrderStatusEnum.CANCELLED
            order.completed_at = datetime.utcnow()

            logger.info(f"Order cancelled: {queue_id}")
            return True

    def get_pending(self) -> List[OrderRequest]:
        """
        Get all pending order requests.

        Returns:
            List of pending OrderRequest objects
        """
        pending = []

        for queue in [
            self._urgent_queue,
            self._high_queue,
            self._normal_queue,
            self._low_queue,
        ]:
            for order in queue:
                if order.status in (OrderStatusEnum.QUEUED, OrderStatusEnum.PENDING):
                    pending.append(order.order_request)

        return pending

    def get_status(self, queue_id: str) -> Optional[OrderStatus]:
        """
        Get status of a queued order.

        Args:
            queue_id: Queue ID to check

        Returns:
            OrderStatus object or None if not found
        """
        order = self._orders.get(queue_id)

        if not order:
            return None

        # Calculate position in queue
        position = None
        if order.status in (OrderStatusEnum.QUEUED, OrderStatusEnum.PENDING):
            position = self._get_queue_position(order)

        return OrderStatus(
            queue_id=queue_id,
            request_id=order.order_request.request_id,
            status=order.status,
            position_in_queue=position,
            result=order.result,
            created_at=order.created_at,
            updated_at=order.completed_at or datetime.utcnow(),
            attempts=order.attempts,
            error_history=order.errors.copy(),
        )

    def pause(self) -> None:
        """Pause queue processing."""
        self._paused = True
        logger.info("Queue processing paused")

    def resume(self) -> None:
        """Resume queue processing."""
        self._paused = False
        logger.info("Queue processing resumed")

    def stop(self) -> None:
        """Stop queue processing."""
        self._running = False
        if self._process_task:
            self._process_task.cancel()
        logger.info("Queue processing stopped")

    def start_background(self) -> asyncio.Task:
        """
        Start queue processing in background.

        Returns:
            Background task handle
        """
        self._process_task = asyncio.create_task(self.process_queue())
        return self._process_task

    async def clear_queue(self) -> int:
        """
        Clear all pending orders.

        Returns:
            Number of orders cleared
        """
        async with self._queue_lock:
            count = 0

            for queue in [
                self._urgent_queue,
                self._high_queue,
                self._normal_queue,
                self._low_queue,
            ]:
                for order in queue:
                    order.status = OrderStatusEnum.CANCELLED
                    order.completed_at = datetime.utcnow()
                    count += 1
                queue.clear()

            logger.info(f"Cleared {count} orders from queue")
            return count

    async def _get_next_order(self) -> Optional[QueuedOrder]:
        """Get next order to process based on priority."""
        async with self._queue_lock:
            # Check queues in priority order
            for queue in [
                self._urgent_queue,
                self._high_queue,
                self._normal_queue,
                self._low_queue,
            ]:
                if queue:
                    return queue.popleft()

            return None

    async def _requeue_order(self, order: QueuedOrder) -> None:
        """Re-queue an order for retry."""
        async with self._queue_lock:
            queue = self._get_queue_for_priority(order.priority)
            queue.append(order)

    async def _apply_rate_limit(self) -> None:
        """Apply rate limiting between executions."""
        import time

        now = time.time() * 1000  # Current time in ms
        elapsed = now - self._last_execution_time

        if elapsed < self.min_interval_ms:
            wait_time = (self.min_interval_ms - elapsed) / 1000
            await asyncio.sleep(wait_time)

        self._last_execution_time = time.time() * 1000

    def _get_queue_for_priority(
        self,
        priority: OrderPriority,
    ) -> Deque[QueuedOrder]:
        """Get the appropriate queue for a priority level."""
        if priority == OrderPriority.URGENT:
            return self._urgent_queue
        elif priority == OrderPriority.HIGH:
            return self._high_queue
        elif priority == OrderPriority.LOW:
            return self._low_queue
        else:
            return self._normal_queue

    def _get_queue_position(self, order: QueuedOrder) -> int:
        """Calculate position in queue."""
        position = 0

        # Count all higher priority orders
        for queue in [
            self._urgent_queue,
            self._high_queue,
            self._normal_queue,
            self._low_queue,
        ]:
            for queued in queue:
                if queued.queue_id == order.queue_id:
                    return position
                position += 1

        return position

    @property
    def queue_size(self) -> int:
        """Get total queue size."""
        return (
            len(self._urgent_queue) +
            len(self._high_queue) +
            len(self._normal_queue) +
            len(self._low_queue)
        )

    @property
    def processing_count(self) -> int:
        """Get count of currently processing orders."""
        return len(self._processing)

    @property
    def is_running(self) -> bool:
        """Check if queue processing is running."""
        return self._running

    @property
    def is_paused(self) -> bool:
        """Check if queue processing is paused."""
        return self._paused

    @property
    def stats(self) -> Dict[str, Any]:
        """Get queue statistics."""
        avg_wait_time = (
            self._total_wait_time_ms / self._total_processed
            if self._total_processed > 0
            else 0.0
        )

        success_rate = (
            self._total_successful / self._total_processed
            if self._total_processed > 0
            else 0.0
        )

        return {
            "queue_size": self.queue_size,
            "processing": self.processing_count,
            "total_processed": self._total_processed,
            "successful": self._total_successful,
            "failed": self._total_failed,
            "success_rate": success_rate,
            "avg_wait_time_ms": avg_wait_time,
            "is_running": self._running,
            "is_paused": self._paused,
            "urgent_queue": len(self._urgent_queue),
            "high_queue": len(self._high_queue),
            "normal_queue": len(self._normal_queue),
            "low_queue": len(self._low_queue),
        }
