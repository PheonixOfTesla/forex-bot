from __future__ import annotations

"""
Forex Bot Configuration Settings

Uses Pydantic Settings for type-safe configuration management with
environment variable support and validation.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field, PostgresDsn, RedisDsn, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class OANDASettings(BaseSettings):
    """OANDA Broker Configuration"""

    model_config = SettingsConfigDict(env_prefix="OANDA_")

    account_id: str = Field(default="", description="OANDA account ID")
    access_token: str = Field(default="", description="OANDA API access token")
    environment: Literal["practice", "live"] = Field(
        default="practice", description="Trading environment"
    )

    @property
    def api_url(self) -> str:
        """Get the appropriate API URL based on environment"""
        if self.environment == "live":
            return "https://api-fxtrade.oanda.com"
        return "https://api-fxpractice.oanda.com"

    @property
    def stream_url(self) -> str:
        """Get the appropriate streaming URL based on environment"""
        if self.environment == "live":
            return "https://stream-fxtrade.oanda.com"
        return "https://stream-fxpractice.oanda.com"


class BinanceSettings(BaseSettings):
    """Binance Exchange Configuration"""

    model_config = SettingsConfigDict(env_prefix="BINANCE_")

    api_key: str = Field(default="", description="Binance API key")
    api_secret: str = Field(default="", description="Binance API secret")
    testnet: bool = Field(default=True, description="Use testnet environment")

    @property
    def base_url(self) -> str:
        """Get the appropriate API URL based on environment"""
        if self.testnet:
            return "https://testnet.binance.vision"
        return "https://api.binance.com"


class RiskSettings(BaseSettings):
    """Risk Management Configuration"""

    model_config = SettingsConfigDict(env_prefix="")

    # Per-trade risk
    risk_per_trade_pct: float = Field(
        default=2.0,
        ge=0.1,
        le=10.0,
        description="Maximum risk per trade as percentage of account",
    )

    # Leverage
    max_leverage: int = Field(
        default=10, ge=1, le=100, description="Maximum leverage to use"
    )

    # Confidence threshold
    min_confidence_threshold: float = Field(
        default=70.0,
        ge=0.0,
        le=100.0,
        description="Minimum ML model confidence to enter trade",
    )

    # Drawdown limits
    max_drawdown_pct: float = Field(
        default=20.0,
        ge=1.0,
        le=50.0,
        description="Maximum drawdown before stopping",
    )

    # Position limits
    max_open_positions: int = Field(
        default=5, ge=1, le=20, description="Maximum concurrent positions"
    )

    # Daily loss limit
    daily_loss_limit_pct: float = Field(
        default=5.0, ge=1.0, le=20.0, description="Daily loss limit percentage"
    )

    # Kelly Criterion
    use_kelly_criterion: bool = Field(
        default=True, description="Use Kelly Criterion for position sizing"
    )
    kelly_fraction: float = Field(
        default=0.25,
        ge=0.1,
        le=1.0,
        description="Kelly fraction multiplier (0.25 = quarter Kelly)",
    )

    # Spread limits
    max_spread_pips: float = Field(
        default=3.0, ge=0.1, le=10.0, description="Maximum acceptable spread in pips"
    )


class TradingSettings(BaseSettings):
    """Trading Parameters Configuration"""

    model_config = SettingsConfigDict(env_prefix="")

    # Instruments
    forex_pairs: str = Field(
        default="EUR_USD,GBP_USD,USD_JPY,AUD_USD",
        description="Comma-separated forex pairs to trade",
    )
    crypto_pairs: str = Field(
        default="BTCUSDT,XRPUSDT,ETHUSDT",
        description="Comma-separated crypto pairs to trade",
    )

    # Trading sessions (UTC)
    london_session_start: str = Field(
        default="07:00", description="London session start time UTC"
    )
    london_session_end: str = Field(
        default="16:00", description="London session end time UTC"
    )

    @property
    def forex_pairs_list(self) -> list[str]:
        """Get forex pairs as a list"""
        return [p.strip() for p in self.forex_pairs.split(",")]

    @property
    def crypto_pairs_list(self) -> list[str]:
        """Get crypto pairs as a list"""
        return [p.strip() for p in self.crypto_pairs.split(",")]


class MLSettings(BaseSettings):
    """Machine Learning Model Configuration"""

    model_config = SettingsConfigDict(env_prefix="")

    model_path: str = Field(
        default="./data/models/", description="Path to store/load trained models"
    )
    lookback_period: int = Field(
        default=50, ge=10, le=200, description="Feature lookback period in candles"
    )
    retrain_interval_hours: int = Field(
        default=24, ge=1, le=168, description="Model retraining interval in hours"
    )
    min_samples_for_retrain: int = Field(
        default=1000, ge=100, le=100000, description="Minimum samples for retraining"
    )


class TelegramSettings(BaseSettings):
    """Telegram Alerts Configuration"""

    model_config = SettingsConfigDict(env_prefix="TELEGRAM_")

    bot_token: str = Field(default="", description="Telegram bot token")
    chat_id: str = Field(default="", description="Telegram chat ID for alerts")

    @property
    def is_configured(self) -> bool:
        """Check if Telegram is properly configured"""
        return bool(self.bot_token and self.chat_id)


class DatabaseSettings(BaseSettings):
    """Database Configuration"""

    model_config = SettingsConfigDict(env_prefix="DATABASE_")

    url: PostgresDsn = Field(
        default="postgresql+asyncpg://user:password@localhost:5432/forex_bot",
        description="PostgreSQL connection URL",
    )
    pool_size: int = Field(default=10, ge=1, le=50, description="Connection pool size")
    max_overflow: int = Field(
        default=20, ge=0, le=100, description="Max overflow connections"
    )


class RedisSettings(BaseSettings):
    """Redis Configuration"""

    model_config = SettingsConfigDict(env_prefix="REDIS_")

    url: RedisDsn = Field(
        default="redis://localhost:6379/0", description="Redis connection URL"
    )


class APISettings(BaseSettings):
    """FastAPI Server Configuration"""

    model_config = SettingsConfigDict(env_prefix="API_")

    host: str = Field(default="0.0.0.0", description="API server host")
    port: int = Field(default=8000, ge=1, le=65535, description="API server port")
    debug: bool = Field(default=False, description="Enable debug mode")
    secret_key: str = Field(
        default="change-this-in-production", description="API secret key for JWT"
    )
    cors_origins: str = Field(
        default="http://localhost:3000,http://localhost:8080",
        description="Comma-separated CORS origins",
    )

    @property
    def cors_origins_list(self) -> list[str]:
        """Get CORS origins as a list"""
        return [o.strip() for o in self.cors_origins.split(",")]


class LoggingSettings(BaseSettings):
    """Logging Configuration"""

    model_config = SettingsConfigDict(env_prefix="LOG_")

    level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO", description="Log level"
    )
    format: Literal["json", "text"] = Field(
        default="json", description="Log format"
    )
    file: str = Field(
        default="./logs/forex_bot.log", description="Log file path"
    )


class BacktestSettings(BaseSettings):
    """Backtesting Configuration"""

    model_config = SettingsConfigDict(env_prefix="BACKTEST_")

    start_date: str = Field(
        default="2023-01-01", description="Backtest start date"
    )
    end_date: str = Field(default="2024-01-01", description="Backtest end date")
    initial_capital: float = Field(
        default=10000.0, ge=100.0, description="Initial capital for backtesting"
    )


class Settings(BaseSettings):
    """
    Main Settings Class

    Aggregates all configuration sections and provides a single
    point of access for the entire application configuration.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Sub-configurations
    oanda: OANDASettings = Field(default_factory=OANDASettings)
    binance: BinanceSettings = Field(default_factory=BinanceSettings)
    risk: RiskSettings = Field(default_factory=RiskSettings)
    trading: TradingSettings = Field(default_factory=TradingSettings)
    ml: MLSettings = Field(default_factory=MLSettings)
    telegram: TelegramSettings = Field(default_factory=TelegramSettings)
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    api: APISettings = Field(default_factory=APISettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)
    backtest: BacktestSettings = Field(default_factory=BacktestSettings)

    def __init__(self, **kwargs):
        """Initialize with nested settings objects"""
        super().__init__(**kwargs)
        # Initialize nested settings from environment
        object.__setattr__(self, "oanda", OANDASettings())
        object.__setattr__(self, "binance", BinanceSettings())
        object.__setattr__(self, "risk", RiskSettings())
        object.__setattr__(self, "trading", TradingSettings())
        object.__setattr__(self, "ml", MLSettings())
        object.__setattr__(self, "telegram", TelegramSettings())
        object.__setattr__(self, "database", DatabaseSettings())
        object.__setattr__(self, "redis", RedisSettings())
        object.__setattr__(self, "api", APISettings())
        object.__setattr__(self, "logging", LoggingSettings())
        object.__setattr__(self, "backtest", BacktestSettings())


@lru_cache
def get_settings() -> Settings:
    """
    Get cached settings instance.

    Uses lru_cache to ensure settings are only loaded once
    and reused throughout the application lifecycle.

    Returns:
        Settings: The application settings instance
    """
    return Settings()


# Convenience export
settings = get_settings()
