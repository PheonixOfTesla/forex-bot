"""
Lightning Forex Bot - Main Entry Point

This module initializes all components and runs the main trading loop:
1. Connect to OANDA + Binance
2. Start price streaming
3. Run feature engine on new data
4. Get ML predictions
5. Check risk rules
6. Execute trades
7. Log everything
8. Send Telegram alerts

Usage:
    python -m src.main
    python -m src.main --debug
    python -m src.main --dry-run
"""

import asyncio
import logging
import signal
import sys
from datetime import datetime, time, timedelta
from typing import Dict, List, Optional, Any
import argparse

import pandas as pd
import redis.asyncio as redis

from config.settings import settings, get_settings
from src.brokers.oanda import OandaClient, PriceUpdate, create_oanda_client
from src.brokers.binance_client import BinanceClient, create_binance_client
from src.features.indicators import IndicatorEngine, prepare_features
from src.ml.models import Prediction, SignalType


# =============================================================================
# LOGGING SETUP
# =============================================================================

def setup_logging(debug: bool = False) -> logging.Logger:
    """Configure logging for the trading bot."""
    log_level = logging.DEBUG if debug else getattr(logging, settings.logging.level)

    # Configure root logger
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(settings.logging.file, mode='a'),
        ]
    )

    # Reduce noise from third-party libraries
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("aiohttp").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)

    logger = logging.getLogger("forex_bot")
    logger.info(f"Logging initialized at {log_level} level")

    return logger


logger = logging.getLogger("forex_bot")


# =============================================================================
# TRADING BOT CLASS
# =============================================================================

class ForexTradingBot:
    """
    Main trading bot orchestrator.

    Manages connections, price streaming, signal generation,
    risk management, and trade execution.
    """

    def __init__(
        self,
        dry_run: bool = False,
        debug: bool = False,
    ):
        """
        Initialize the trading bot.

        Args:
            dry_run: If True, don't execute real trades
            debug: Enable debug logging
        """
        self.dry_run = dry_run
        self.debug = debug
        self.settings = get_settings()

        # Broker clients
        self.oanda_client: Optional[OandaClient] = None
        self.binance_client: Optional[BinanceClient] = None

        # Feature engine
        self.indicator_engine = IndicatorEngine(
            lookback_period=self.settings.ml.lookback_period
        )

        # State management
        self._running = False
        self._price_cache: Dict[str, pd.DataFrame] = {}
        self._last_signal_time: Dict[str, datetime] = {}
        self._daily_pnl: float = 0.0
        self._trade_count: int = 0

        # Redis for caching (optional)
        self._redis: Optional[redis.Redis] = None

        # Shutdown signals
        self._shutdown_event = asyncio.Event()

        logger.info(f"ForexTradingBot initialized (dry_run={dry_run}, debug={debug})")

    async def initialize(self) -> None:
        """Initialize all connections and resources."""
        logger.info("Initializing trading bot components...")

        # Initialize Redis connection
        try:
            self._redis = redis.from_url(str(self.settings.redis.url))
            await self._redis.ping()
            logger.info("Redis connection established")
        except Exception as e:
            logger.warning(f"Redis connection failed (non-critical): {e}")
            self._redis = None

        # Initialize OANDA client
        try:
            self.oanda_client = create_oanda_client(
                api_key=self.settings.oanda.access_token,
                account_id=self.settings.oanda.account_id,
                practice=(self.settings.oanda.environment == "practice"),
            )
            await self.oanda_client.connect()
            balance = await self.oanda_client.get_account_balance()
            logger.info(f"OANDA connected - Balance: ${balance:,.2f}")
        except Exception as e:
            logger.error(f"OANDA connection failed: {e}")
            raise

        # Initialize Binance client
        try:
            self.binance_client = create_binance_client(
                api_key=self.settings.binance.api_key,
                api_secret=self.settings.binance.api_secret,
                testnet=self.settings.binance.testnet,
            )
            await self.binance_client.connect()
            balance = await self.binance_client.get_account_balance("USDT")
            logger.info(f"Binance connected - USDT Balance: ${balance:,.2f}")
        except Exception as e:
            logger.error(f"Binance connection failed: {e}")
            raise

        # Load historical data for each instrument
        await self._load_initial_data()

        logger.info("All components initialized successfully")

    async def _load_initial_data(self) -> None:
        """Load initial historical data for all instruments."""
        logger.info("Loading initial market data...")

        # Load OANDA forex pairs
        for pair in self.settings.trading.forex_pairs_list:
            try:
                candles = await self.oanda_client.get_candles(
                    instrument=pair,
                    granularity="H1",
                    count=self.settings.ml.lookback_period + 50,
                )
                if not candles.empty:
                    # Calculate indicators
                    self._price_cache[pair] = self.indicator_engine.calculate_all(candles)
                    logger.debug(f"Loaded {len(candles)} candles for {pair}")
            except Exception as e:
                logger.error(f"Failed to load data for {pair}: {e}")

        # Load Binance crypto pairs
        for pair in self.settings.trading.crypto_pairs_list:
            try:
                candles = await self.binance_client.get_candles(
                    symbol=pair,
                    interval="1h",
                    limit=self.settings.ml.lookback_period + 50,
                )
                if not candles.empty:
                    # Standardize column names
                    candles = candles.rename(columns={
                        'open_time': 'time',
                    })
                    self._price_cache[pair] = self.indicator_engine.calculate_all(candles)
                    logger.debug(f"Loaded {len(candles)} candles for {pair}")
            except Exception as e:
                logger.error(f"Failed to load data for {pair}: {e}")

        logger.info(f"Initial data loaded for {len(self._price_cache)} instruments")

    async def shutdown(self) -> None:
        """Gracefully shutdown all connections."""
        logger.info("Shutting down trading bot...")

        self._running = False
        self._shutdown_event.set()

        # Disconnect OANDA
        if self.oanda_client:
            try:
                await self.oanda_client.disconnect()
                logger.info("OANDA disconnected")
            except Exception as e:
                logger.error(f"Error disconnecting OANDA: {e}")

        # Disconnect Binance
        if self.binance_client:
            try:
                await self.binance_client.disconnect()
                logger.info("Binance disconnected")
            except Exception as e:
                logger.error(f"Error disconnecting Binance: {e}")

        # Close Redis
        if self._redis:
            try:
                await self._redis.close()
                logger.info("Redis disconnected")
            except Exception as e:
                logger.error(f"Error disconnecting Redis: {e}")

        logger.info("Trading bot shutdown complete")

    async def run(self) -> None:
        """Main trading loop."""
        logger.info("Starting main trading loop...")
        self._running = True

        # Start background tasks
        tasks = [
            asyncio.create_task(self._trading_loop()),
            asyncio.create_task(self._health_check_loop()),
            asyncio.create_task(self._daily_report_loop()),
        ]

        # Start price streaming
        if self.oanda_client:
            forex_pairs = self.settings.trading.forex_pairs_list
            tasks.append(
                asyncio.create_task(
                    self.oanda_client.stream_prices(forex_pairs, self._on_forex_price)
                )
            )

        if self.binance_client:
            crypto_pairs = self.settings.trading.crypto_pairs_list
            tasks.append(
                asyncio.create_task(
                    self.binance_client.stream_prices(crypto_pairs, self._on_crypto_price)
                )
            )

        # Wait for shutdown or error
        try:
            await self._shutdown_event.wait()
        except asyncio.CancelledError:
            logger.info("Trading loop cancelled")
        finally:
            # Cancel all tasks
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _on_forex_price(self, price: PriceUpdate) -> None:
        """Handle incoming forex price update."""
        try:
            logger.debug(f"Forex price: {price.instrument} bid={price.bid:.5f} ask={price.ask:.5f}")

            # Update price cache
            await self._update_price_cache(price.instrument, price)

            # Check for trading signals
            await self._check_trading_signal(price.instrument, "OANDA")

        except Exception as e:
            logger.error(f"Error processing forex price {price.instrument}: {e}")

    async def _on_crypto_price(self, symbol: str, price: float, timestamp: int) -> None:
        """Handle incoming crypto price update."""
        try:
            logger.debug(f"Crypto price: {symbol} price={price:.2f}")

            # Check for trading signals
            await self._check_trading_signal(symbol, "BINANCE")

        except Exception as e:
            logger.error(f"Error processing crypto price {symbol}: {e}")

    async def _update_price_cache(self, instrument: str, price: PriceUpdate) -> None:
        """Update the price cache with new price data."""
        if instrument not in self._price_cache:
            return

        df = self._price_cache[instrument]

        # Add new price to cache (simplified - in production, aggregate to candles)
        new_row = pd.DataFrame({
            'open': [price.mid],
            'high': [price.ask],
            'low': [price.bid],
            'close': [price.mid],
            'volume': [0],
        }, index=[price.time])

        # Append and recalculate indicators
        df = pd.concat([df, new_row])
        df = df.tail(self.settings.ml.lookback_period + 50)

        self._price_cache[instrument] = self.indicator_engine.calculate_all(df)

    async def _check_trading_signal(self, instrument: str, broker: str) -> None:
        """Check if we should generate a trading signal."""
        # Rate limit signals
        min_signal_interval = timedelta(minutes=5)
        last_signal = self._last_signal_time.get(instrument)

        if last_signal and datetime.utcnow() - last_signal < min_signal_interval:
            return

        # Check trading session
        if not self._is_trading_session_active(instrument):
            return

        # Get features and generate prediction
        try:
            prediction = await self._generate_prediction(instrument)

            if prediction and prediction.is_tradeable:
                logger.info(
                    f"SIGNAL: {prediction.signal} {instrument} "
                    f"(confidence={prediction.confidence:.1%})"
                )

                # Check risk rules
                if await self._check_risk_rules(instrument, prediction):
                    # Execute trade
                    if not self.dry_run:
                        await self._execute_trade(instrument, prediction, broker)
                    else:
                        logger.info(f"DRY RUN: Would execute {prediction.signal} on {instrument}")

                    self._last_signal_time[instrument] = datetime.utcnow()

                    # Send Telegram alert
                    await self._send_trade_alert(instrument, prediction, broker)

        except Exception as e:
            logger.error(f"Error checking signal for {instrument}: {e}")

    async def _generate_prediction(self, instrument: str) -> Optional[Prediction]:
        """Generate ML prediction for an instrument."""
        if instrument not in self._price_cache:
            return None

        df = self._price_cache[instrument]

        if df.empty or len(df) < self.settings.ml.lookback_period:
            return None

        # Prepare features
        features = prepare_features(df, lookback=self.settings.ml.lookback_period)

        if features.empty:
            return None

        # Get latest feature row
        latest_features = features.iloc[-1].to_dict()

        # Get indicator signals
        signals = self.indicator_engine.get_latest_signals(df)

        # Simple rule-based prediction (placeholder for ML model)
        # In production, this would call an actual trained model
        signal = self._simple_signal_logic(signals)
        confidence = self._calculate_confidence(signals)

        if signal == "SKIP":
            return None

        return Prediction(
            signal=signal,
            confidence=confidence,
            features_used=latest_features,
        )

    def _simple_signal_logic(self, signals: Dict[str, Any]) -> str:
        """Simple rule-based signal logic (placeholder for ML)."""
        # Bullish conditions
        bullish_count = sum([
            signals.get('macd_bullish', False),
            signals.get('macd_crossover', False),
            signals.get('above_ema_20', False),
            signals.get('rsi', 50) < 30,  # Oversold
            signals.get('bb_position', 0.5) < 0.2,  # Near lower band
        ])

        # Bearish conditions
        bearish_count = sum([
            not signals.get('macd_bullish', True),
            signals.get('macd_crossunder', False),
            not signals.get('above_ema_20', True),
            signals.get('rsi', 50) > 70,  # Overbought
            signals.get('bb_position', 0.5) > 0.8,  # Near upper band
        ])

        if bullish_count >= 3 and bullish_count > bearish_count:
            return "BUY"
        elif bearish_count >= 3 and bearish_count > bullish_count:
            return "SELL"
        else:
            return "SKIP"

    def _calculate_confidence(self, signals: Dict[str, Any]) -> float:
        """Calculate confidence score from signals."""
        # Base confidence
        confidence = 0.5

        # RSI strength
        rsi = signals.get('rsi', 50)
        if rsi < 30 or rsi > 70:
            confidence += 0.1

        # MACD crossover
        if signals.get('macd_crossover') or signals.get('macd_crossunder'):
            confidence += 0.15

        # EMA alignment
        if signals.get('above_ema_20') == signals.get('above_ema_50'):
            confidence += 0.1

        # Volume confirmation
        volume_ratio = signals.get('volume_ratio', 1.0)
        if volume_ratio > 1.5:
            confidence += 0.1

        # Session bonus
        if signals.get('session') in ['london', 'overlap']:
            confidence += 0.05

        return min(confidence, 0.95)

    def _is_trading_session_active(self, instrument: str) -> bool:
        """Check if we should trade during current session."""
        now = datetime.utcnow().time()

        # Forex: Trade during London session
        if "_" in instrument:  # OANDA format
            london_open = time(7, 0)
            london_close = time(16, 0)
            return london_open <= now <= london_close

        # Crypto: Trade 24/7 but avoid low volume hours
        return True

    async def _check_risk_rules(self, instrument: str, prediction: Prediction) -> bool:
        """Check if trade passes risk management rules."""
        risk = self.settings.risk

        # Check confidence threshold
        if prediction.confidence < (risk.min_confidence_threshold / 100):
            logger.debug(f"Skipping {instrument}: confidence too low")
            return False

        # Check daily loss limit
        if self._daily_pnl < -(risk.daily_loss_limit_pct / 100):
            logger.warning(f"Daily loss limit reached: {self._daily_pnl:.2%}")
            return False

        # Check max open positions
        if self.oanda_client:
            positions = await self.oanda_client.get_open_positions()
            if len(positions) >= risk.max_open_positions:
                logger.debug(f"Max positions ({risk.max_open_positions}) reached")
                return False

        return True

    async def _execute_trade(
        self,
        instrument: str,
        prediction: Prediction,
        broker: str,
    ) -> None:
        """Execute a trade based on prediction."""
        try:
            # Calculate position size
            position_size = await self._calculate_position_size(instrument, prediction)

            if position_size <= 0:
                logger.warning(f"Invalid position size for {instrument}")
                return

            # Get current price for SL/TP calculation
            df = self._price_cache.get(instrument)
            if df is None or df.empty:
                return

            current_price = df['close'].iloc[-1]
            atr = df['atr_14'].iloc[-1]

            # Calculate stop loss and take profit
            if prediction.signal == "BUY":
                stop_loss = current_price - (atr * 2)
                take_profit = current_price + (atr * 3)
            else:
                stop_loss = current_price + (atr * 2)
                take_profit = current_price - (atr * 3)

            # Execute on appropriate broker
            if broker == "OANDA" and self.oanda_client:
                order = await self.oanda_client.place_order(
                    instrument=instrument,
                    units=position_size,
                    side=prediction.signal.lower(),
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                )
                logger.info(
                    f"OANDA order executed: {order.id} {prediction.signal} "
                    f"{position_size} {instrument} @ {order.fill_price}"
                )

            elif broker == "BINANCE" and self.binance_client:
                order = await self.binance_client.place_order(
                    symbol=instrument,
                    side=prediction.signal,
                    quantity=position_size,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                )
                logger.info(
                    f"Binance order executed: {order.id} {prediction.signal} "
                    f"{position_size} {instrument}"
                )

            self._trade_count += 1

        except Exception as e:
            logger.error(f"Trade execution failed for {instrument}: {e}")

    async def _calculate_position_size(
        self,
        instrument: str,
        prediction: Prediction,
    ) -> float:
        """Calculate position size using Kelly Criterion or fixed percentage."""
        risk = self.settings.risk

        # Get account balance
        if "_" in instrument:  # Forex
            balance = await self.oanda_client.get_account_balance()
        else:  # Crypto
            balance = await self.binance_client.get_account_balance("USDT")

        # Risk amount
        risk_amount = balance * (risk.risk_per_trade_pct / 100)

        # Get ATR for position sizing
        df = self._price_cache.get(instrument)
        if df is None or df.empty:
            return 0

        atr = df['atr_14'].iloc[-1]
        current_price = df['close'].iloc[-1]

        # Calculate position size based on ATR stop
        stop_distance = atr * 2
        if stop_distance <= 0:
            return 0

        # Position size = Risk Amount / Stop Distance (in price)
        if "_" in instrument:  # Forex (units)
            position_size = risk_amount / stop_distance
            position_size = int(position_size / 1000) * 1000  # Round to 1000 units
        else:  # Crypto
            position_size = risk_amount / stop_distance
            position_size = round(position_size, 3)

        # Apply Kelly fraction if enabled
        if risk.use_kelly_criterion:
            # Simplified Kelly - in production, use actual win rate and reward/risk
            win_rate = 0.55
            reward_risk = 1.5
            kelly = (win_rate * reward_risk - (1 - win_rate)) / reward_risk
            kelly = max(0, min(kelly, 1)) * risk.kelly_fraction
            position_size *= kelly

        return max(0, position_size)

    async def _send_trade_alert(
        self,
        instrument: str,
        prediction: Prediction,
        broker: str,
    ) -> None:
        """Send trade alert via Telegram."""
        if not self.settings.telegram.is_configured:
            return

        # Build alert message
        message = (
            f"{'BUY' if prediction.signal == 'BUY' else 'SELL'} Signal\n"
            f"Instrument: {instrument}\n"
            f"Confidence: {prediction.confidence:.1%}\n"
            f"Broker: {broker}\n"
            f"Time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC"
        )

        # Send via Telegram (placeholder - implement actual sending)
        logger.info(f"Telegram alert: {message}")

    async def _trading_loop(self) -> None:
        """Background trading loop for periodic checks."""
        while self._running:
            try:
                # Periodic position check
                if self.oanda_client:
                    positions = await self.oanda_client.get_open_positions()
                    for pos in positions:
                        logger.debug(
                            f"Position: {pos.instrument} {pos.side.value} "
                            f"units={pos.units} pnl={pos.unrealized_pnl:.2f}"
                        )

                await asyncio.sleep(60)  # Check every minute

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in trading loop: {e}")
                await asyncio.sleep(5)

    async def _health_check_loop(self) -> None:
        """Background health check loop."""
        while self._running:
            try:
                # Check OANDA connection
                if self.oanda_client:
                    await self.oanda_client.get_account_balance()

                # Check Binance connection
                if self.binance_client:
                    await self.binance_client.get_account_balance()

                # Check Redis
                if self._redis:
                    await self._redis.ping()

                logger.debug("Health check passed")
                await asyncio.sleep(300)  # Every 5 minutes

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Health check failed: {e}")
                await asyncio.sleep(30)

    async def _daily_report_loop(self) -> None:
        """Send daily performance report."""
        while self._running:
            try:
                now = datetime.utcnow()

                # Wait until end of trading day (16:00 UTC)
                target = now.replace(hour=16, minute=0, second=0, microsecond=0)
                if now >= target:
                    target += timedelta(days=1)

                wait_seconds = (target - now).total_seconds()
                await asyncio.sleep(wait_seconds)

                # Generate and send daily report
                await self._send_daily_report()

                # Reset daily counters
                self._daily_pnl = 0.0
                self._trade_count = 0

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in daily report: {e}")
                await asyncio.sleep(3600)

    async def _send_daily_report(self) -> None:
        """Generate and send daily performance report."""
        logger.info("Generating daily performance report...")

        # Get account summary
        summary = None
        if self.oanda_client:
            summary = await self.oanda_client.get_account_summary()

        report = f"""
Daily Performance Report
========================
Date: {datetime.utcnow().strftime('%Y-%m-%d')}
Trades: {self._trade_count}
Daily P&L: {self._daily_pnl:.2%}
"""

        if summary:
            report += f"""
Account Balance: ${summary.balance:,.2f}
Unrealized P&L: ${summary.unrealized_pnl:,.2f}
Open Positions: {summary.open_trade_count}
"""

        logger.info(report)


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

def setup_signal_handlers(bot: ForexTradingBot) -> None:
    """Setup signal handlers for graceful shutdown."""
    loop = asyncio.get_event_loop()

    def handle_signal(sig: signal.Signals) -> None:
        logger.info(f"Received signal {sig.name}, initiating shutdown...")
        asyncio.create_task(bot.shutdown())

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, handle_signal, sig)


async def main(args: argparse.Namespace) -> int:
    """Main async entry point."""
    # Setup logging
    setup_logging(debug=args.debug)

    logger.info("=" * 60)
    logger.info("LIGHTNING FOREX BOT")
    logger.info("=" * 60)
    logger.info(f"Mode: {'DRY RUN' if args.dry_run else 'LIVE TRADING'}")
    logger.info(f"Debug: {args.debug}")

    # Create bot instance
    bot = ForexTradingBot(
        dry_run=args.dry_run,
        debug=args.debug,
    )

    try:
        # Setup signal handlers
        setup_signal_handlers(bot)

        # Initialize
        await bot.initialize()

        # Run main loop
        await bot.run()

        return 0

    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        return 0

    except Exception as e:
        logger.exception(f"Fatal error: {e}")
        return 1

    finally:
        await bot.shutdown()


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Lightning Forex Bot - Automated Trading System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run without executing real trades",
    )

    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging",
    )

    parser.add_argument(
        "--config",
        type=str,
        help="Path to custom config file",
    )

    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    exit_code = asyncio.run(main(args))
    sys.exit(exit_code)
