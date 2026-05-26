from __future__ import annotations

"""
Alert Scheduler for Automated Notifications

Schedules recurring alerts such as:
- Daily summaries at end of trading day
- Weekly reports
- Periodic health checks
"""

import asyncio
import logging
from datetime import datetime, time, timedelta
from typing import Callable, Optional, Any, Awaitable, List
from dataclasses import dataclass, field
from enum import Enum

from .telegram import TelegramAlerts
from .formatter import DailySummary, EngineStatus

logger = logging.getLogger(__name__)


class DayOfWeek(str, Enum):
    """Days of the week for scheduling."""
    MONDAY = "monday"
    TUESDAY = "tuesday"
    WEDNESDAY = "wednesday"
    THURSDAY = "thursday"
    FRIDAY = "friday"
    SATURDAY = "saturday"
    SUNDAY = "sunday"


@dataclass
class ScheduledTask:
    """Represents a scheduled task."""
    name: str
    callback: Callable[[], Awaitable[Any]]
    next_run: datetime
    interval: Optional[timedelta] = None
    enabled: bool = True


class AlertScheduler:
    """
    Scheduler for automated trading alerts.

    Manages scheduled tasks for:
    - Daily trading summaries
    - Weekly performance reports
    - Periodic status updates

    Example usage:
        scheduler = AlertScheduler(telegram_alerts)
        await scheduler.schedule_daily_summary("23:59")
        await scheduler.schedule_weekly_report("sunday", "18:00")
        await scheduler.start()
    """

    def __init__(
        self,
        telegram: TelegramAlerts,
        summary_callback: Optional[Callable[[], Awaitable[DailySummary]]] = None,
        status_callback: Optional[Callable[[], Awaitable[EngineStatus]]] = None
    ):
        """
        Initialize the alert scheduler.

        Args:
            telegram: TelegramAlerts instance for sending notifications
            summary_callback: Optional callback to get daily summary data
            status_callback: Optional callback to get engine status
        """
        self.telegram = telegram
        self.summary_callback = summary_callback
        self.status_callback = status_callback
        self._tasks: List[ScheduledTask] = []
        self._running = False
        self._scheduler_task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()

    def _parse_time(self, time_str: str) -> time:
        """
        Parse a time string into a time object.

        Args:
            time_str: Time string in HH:MM format

        Returns:
            time object
        """
        parts = time_str.split(":")
        hour = int(parts[0])
        minute = int(parts[1]) if len(parts) > 1 else 0
        return time(hour=hour, minute=minute)

    def _get_next_run_time(
        self,
        target_time: time,
        day_of_week: Optional[DayOfWeek] = None
    ) -> datetime:
        """
        Calculate the next run time for a scheduled task.

        Args:
            target_time: Target time of day
            day_of_week: Optional specific day of week

        Returns:
            datetime of next scheduled run
        """
        now = datetime.now()
        target = datetime.combine(now.date(), target_time)

        if day_of_week is not None:
            # Map day names to weekday numbers (0=Monday)
            day_map = {
                DayOfWeek.MONDAY: 0,
                DayOfWeek.TUESDAY: 1,
                DayOfWeek.WEDNESDAY: 2,
                DayOfWeek.THURSDAY: 3,
                DayOfWeek.FRIDAY: 4,
                DayOfWeek.SATURDAY: 5,
                DayOfWeek.SUNDAY: 6,
            }
            target_day = day_map[day_of_week]
            current_day = now.weekday()

            # Days until target day
            days_ahead = target_day - current_day
            if days_ahead < 0:
                days_ahead += 7
            elif days_ahead == 0 and target <= now:
                days_ahead = 7

            target = target + timedelta(days=days_ahead)
        else:
            # Daily task - if time has passed today, schedule for tomorrow
            if target <= now:
                target = target + timedelta(days=1)

        return target

    async def schedule_daily_summary(
        self,
        time_str: str = "23:59",
        enabled: bool = True
    ) -> None:
        """
        Schedule a daily trading summary.

        Args:
            time_str: Time to send summary in HH:MM format (default: 23:59)
            enabled: Whether the schedule is enabled
        """
        target_time = self._parse_time(time_str)
        next_run = self._get_next_run_time(target_time)

        async def send_daily():
            if self.summary_callback:
                try:
                    summary = await self.summary_callback()
                    await self.telegram.send_daily_summary(summary)
                except Exception as e:
                    logger.error(f"Failed to send daily summary: {e}")
            else:
                logger.warning("No summary callback configured, skipping daily summary")

        task = ScheduledTask(
            name="daily_summary",
            callback=send_daily,
            next_run=next_run,
            interval=timedelta(days=1),
            enabled=enabled
        )

        async with self._lock:
            # Remove existing daily summary task if any
            self._tasks = [t for t in self._tasks if t.name != "daily_summary"]
            self._tasks.append(task)

        logger.info(f"Daily summary scheduled for {time_str}, next run: {next_run}")

    async def schedule_weekly_report(
        self,
        day: str = "sunday",
        time_str: str = "18:00",
        enabled: bool = True
    ) -> None:
        """
        Schedule a weekly performance report.

        Args:
            day: Day of week (e.g., 'sunday')
            time_str: Time to send report in HH:MM format
            enabled: Whether the schedule is enabled
        """
        target_time = self._parse_time(time_str)
        day_of_week = DayOfWeek(day.lower())
        next_run = self._get_next_run_time(target_time, day_of_week)

        async def send_weekly():
            if self.summary_callback:
                try:
                    # For weekly, we'd ideally have a separate callback
                    # For now, send a status update
                    if self.status_callback:
                        status = await self.status_callback()
                        await self.telegram.send_engine_status(status)
                    else:
                        summary = await self.summary_callback()
                        await self.telegram.send_daily_summary(summary)
                except Exception as e:
                    logger.error(f"Failed to send weekly report: {e}")
            else:
                logger.warning("No callback configured, skipping weekly report")

        task = ScheduledTask(
            name="weekly_report",
            callback=send_weekly,
            next_run=next_run,
            interval=timedelta(weeks=1),
            enabled=enabled
        )

        async with self._lock:
            # Remove existing weekly report task if any
            self._tasks = [t for t in self._tasks if t.name != "weekly_report"]
            self._tasks.append(task)

        logger.info(f"Weekly report scheduled for {day} at {time_str}, next run: {next_run}")

    async def schedule_status_check(
        self,
        interval_minutes: int = 60,
        enabled: bool = True
    ) -> None:
        """
        Schedule periodic engine status checks.

        Args:
            interval_minutes: Minutes between status checks
            enabled: Whether the schedule is enabled
        """
        next_run = datetime.now() + timedelta(minutes=interval_minutes)

        async def send_status():
            if self.status_callback:
                try:
                    status = await self.status_callback()
                    await self.telegram.send_engine_status(status)
                except Exception as e:
                    logger.error(f"Failed to send status check: {e}")
            else:
                logger.warning("No status callback configured, skipping status check")

        task = ScheduledTask(
            name="status_check",
            callback=send_status,
            next_run=next_run,
            interval=timedelta(minutes=interval_minutes),
            enabled=enabled
        )

        async with self._lock:
            # Remove existing status check task if any
            self._tasks = [t for t in self._tasks if t.name != "status_check"]
            self._tasks.append(task)

        logger.info(f"Status check scheduled every {interval_minutes} minutes")

    async def add_custom_task(
        self,
        name: str,
        callback: Callable[[], Awaitable[Any]],
        interval: timedelta,
        start_time: Optional[datetime] = None
    ) -> None:
        """
        Add a custom scheduled task.

        Args:
            name: Unique task name
            callback: Async function to execute
            interval: Time between executions
            start_time: When to first run (default: now + interval)
        """
        if start_time is None:
            start_time = datetime.now() + interval

        task = ScheduledTask(
            name=name,
            callback=callback,
            next_run=start_time,
            interval=interval,
            enabled=True
        )

        async with self._lock:
            # Remove existing task with same name if any
            self._tasks = [t for t in self._tasks if t.name != name]
            self._tasks.append(task)

        logger.info(f"Custom task '{name}' scheduled, next run: {start_time}")

    async def remove_task(self, name: str) -> bool:
        """
        Remove a scheduled task.

        Args:
            name: Task name to remove

        Returns:
            True if task was removed
        """
        async with self._lock:
            original_count = len(self._tasks)
            self._tasks = [t for t in self._tasks if t.name != name]
            removed = len(self._tasks) < original_count

        if removed:
            logger.info(f"Task '{name}' removed from scheduler")
        return removed

    async def enable_task(self, name: str) -> bool:
        """
        Enable a scheduled task.

        Args:
            name: Task name to enable

        Returns:
            True if task was found and enabled
        """
        async with self._lock:
            for task in self._tasks:
                if task.name == name:
                    task.enabled = True
                    logger.info(f"Task '{name}' enabled")
                    return True
        return False

    async def disable_task(self, name: str) -> bool:
        """
        Disable a scheduled task.

        Args:
            name: Task name to disable

        Returns:
            True if task was found and disabled
        """
        async with self._lock:
            for task in self._tasks:
                if task.name == name:
                    task.enabled = False
                    logger.info(f"Task '{name}' disabled")
                    return True
        return False

    async def _run_scheduler(self) -> None:
        """Main scheduler loop."""
        logger.info("Alert scheduler started")

        while self._running:
            now = datetime.now()

            async with self._lock:
                for task in self._tasks:
                    if not task.enabled:
                        continue

                    if task.next_run <= now:
                        # Execute the task
                        try:
                            logger.debug(f"Executing scheduled task: {task.name}")
                            await task.callback()
                        except Exception as e:
                            logger.error(f"Scheduled task '{task.name}' failed: {e}")

                        # Schedule next run
                        if task.interval:
                            task.next_run = now + task.interval
                            logger.debug(f"Task '{task.name}' next run: {task.next_run}")

            # Sleep for a short interval before checking again
            await asyncio.sleep(10)  # Check every 10 seconds

        logger.info("Alert scheduler stopped")

    async def start(self) -> None:
        """Start the scheduler."""
        if self._running:
            logger.warning("Scheduler is already running")
            return

        self._running = True
        self._scheduler_task = asyncio.create_task(self._run_scheduler())
        logger.info("Alert scheduler starting...")

    async def stop(self) -> None:
        """Stop the scheduler."""
        if not self._running:
            logger.warning("Scheduler is not running")
            return

        self._running = False

        if self._scheduler_task:
            self._scheduler_task.cancel()
            try:
                await self._scheduler_task
            except asyncio.CancelledError:
                pass
            self._scheduler_task = None

        logger.info("Alert scheduler stopped")

    @property
    def is_running(self) -> bool:
        """Check if scheduler is running."""
        return self._running

    def get_scheduled_tasks(self) -> List[dict]:
        """
        Get information about all scheduled tasks.

        Returns:
            List of task information dictionaries
        """
        return [
            {
                "name": task.name,
                "next_run": task.next_run.isoformat(),
                "interval": str(task.interval) if task.interval else None,
                "enabled": task.enabled,
            }
            for task in self._tasks
        ]

    async def run_task_now(self, name: str) -> bool:
        """
        Manually trigger a task to run immediately.

        Args:
            name: Task name to run

        Returns:
            True if task was found and executed
        """
        async with self._lock:
            for task in self._tasks:
                if task.name == name:
                    try:
                        logger.info(f"Manually running task: {name}")
                        await task.callback()
                        return True
                    except Exception as e:
                        logger.error(f"Manual task execution failed: {e}")
                        return False
        logger.warning(f"Task '{name}' not found")
        return False
