"""
Pydantic Models for Lightning Bot Database Documents

Defines the data structures for MongoDB documents with validation.
"""
from datetime import datetime
from typing import Optional, Literal
from enum import Enum

from pydantic import BaseModel, Field, ConfigDict
from bson import ObjectId


class PyObjectId(str):
    """Custom type for MongoDB ObjectId serialization."""

    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v, handler):
        if isinstance(v, ObjectId):
            return str(v)
        if isinstance(v, str):
            if ObjectId.is_valid(v):
                return v
            raise ValueError("Invalid ObjectId")
        raise ValueError("Invalid ObjectId type")


class TradeStatus(str, Enum):
    """Trade status enumeration."""
    OPEN = "open"
    CLOSED = "closed"
    CANCELLED = "cancelled"


class TradeDirection(str, Enum):
    """Trade direction enumeration."""
    LONG = "long"
    SHORT = "short"


class AccountMode(str, Enum):
    """Account mode enumeration."""
    PAPER = "paper"
    LIVE = "live"


class SignalStatus(str, Enum):
    """Signal status enumeration."""
    ACTIVE = "active"
    EXECUTED = "executed"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


# =============================================================================
# Trade Document
# =============================================================================

class TradeBase(BaseModel):
    """Base trade fields."""
    user_id: str = Field(..., description="User identifier")
    pair: str = Field(..., description="Trading pair (e.g., EUR/USD)")
    direction: TradeDirection = Field(..., description="Trade direction")
    entry_price: float = Field(..., gt=0, description="Entry price")
    quantity: float = Field(..., gt=0, description="Position size/quantity")
    stop_loss: Optional[float] = Field(None, description="Stop loss price")
    take_profit: Optional[float] = Field(None, description="Take profit price")
    signal_id: Optional[str] = Field(None, description="Associated signal ID")


class TradeCreate(TradeBase):
    """Model for creating a new trade."""
    pass


class TradeDocument(TradeBase):
    """
    Complete trade document as stored in MongoDB.

    Represents both open and closed trades with full history.
    """
    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str, datetime: lambda v: v.isoformat()},
    )

    id: Optional[str] = Field(None, alias="_id", description="MongoDB document ID")
    exit_price: Optional[float] = Field(None, description="Exit price (when closed)")
    pnl: Optional[float] = Field(None, description="Realized profit/loss")
    pnl_pct: Optional[float] = Field(None, description="P&L as percentage")
    status: TradeStatus = Field(default=TradeStatus.OPEN, description="Trade status")
    opened_at: datetime = Field(default_factory=datetime.utcnow, description="Trade open time")
    closed_at: Optional[datetime] = Field(None, description="Trade close time")
    notes: Optional[str] = Field(None, description="Trade notes")

    @classmethod
    def from_mongo(cls, data: dict) -> "TradeDocument":
        """Create TradeDocument from MongoDB document."""
        if data is None:
            return None
        # Convert ObjectId to string
        if "_id" in data and isinstance(data["_id"], ObjectId):
            data["_id"] = str(data["_id"])
        return cls(**data)

    def to_mongo(self) -> dict:
        """Convert to MongoDB document format."""
        data = self.model_dump(by_alias=True, exclude_none=True)
        # Remove _id if None for insert operations
        if data.get("_id") is None:
            data.pop("_id", None)
        return data


class TradeUpdate(BaseModel):
    """Model for updating trade fields."""
    exit_price: Optional[float] = None
    pnl: Optional[float] = None
    pnl_pct: Optional[float] = None
    status: Optional[TradeStatus] = None
    closed_at: Optional[datetime] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    notes: Optional[str] = None


# =============================================================================
# Position Document
# =============================================================================

class PositionBase(BaseModel):
    """Base position fields."""
    user_id: str = Field(..., description="User identifier")
    pair: str = Field(..., description="Trading pair")
    direction: TradeDirection = Field(..., description="Position direction")
    entry_price: float = Field(..., gt=0, description="Average entry price")
    quantity: float = Field(..., gt=0, description="Position size")
    stop_loss: Optional[float] = Field(None, description="Stop loss price")
    take_profit: Optional[float] = Field(None, description="Take profit price")


class PositionCreate(PositionBase):
    """Model for creating a new position."""
    pass


class PositionDocument(PositionBase):
    """
    Position document as stored in MongoDB.

    Represents currently open positions with real-time P&L tracking.
    """
    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str, datetime: lambda v: v.isoformat()},
    )

    id: Optional[str] = Field(None, alias="_id", description="MongoDB document ID")
    current_price: Optional[float] = Field(None, description="Current market price")
    unrealized_pnl: Optional[float] = Field(None, description="Unrealized P&L")
    unrealized_pnl_pct: Optional[float] = Field(None, description="Unrealized P&L percentage")
    opened_at: datetime = Field(default_factory=datetime.utcnow, description="Position open time")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="Last update time")
    trade_id: Optional[str] = Field(None, description="Associated trade ID")

    @classmethod
    def from_mongo(cls, data: dict) -> "PositionDocument":
        """Create PositionDocument from MongoDB document."""
        if data is None:
            return None
        if "_id" in data and isinstance(data["_id"], ObjectId):
            data["_id"] = str(data["_id"])
        return cls(**data)

    def to_mongo(self) -> dict:
        """Convert to MongoDB document format."""
        data = self.model_dump(by_alias=True, exclude_none=True)
        if data.get("_id") is None:
            data.pop("_id", None)
        return data

    def calculate_pnl(self, current_price: float) -> tuple[float, float]:
        """Calculate unrealized P&L given current price."""
        if self.direction == TradeDirection.LONG:
            pnl = (current_price - self.entry_price) * self.quantity
        else:
            pnl = (self.entry_price - current_price) * self.quantity

        position_value = self.entry_price * self.quantity
        pnl_pct = (pnl / position_value) * 100 if position_value > 0 else 0

        return round(pnl, 2), round(pnl_pct, 2)


class PositionUpdate(BaseModel):
    """Model for updating position fields."""
    current_price: Optional[float] = None
    unrealized_pnl: Optional[float] = None
    unrealized_pnl_pct: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    updated_at: Optional[datetime] = None


# =============================================================================
# Account Document
# =============================================================================

class AccountBase(BaseModel):
    """Base account fields."""
    user_id: str = Field(..., description="User identifier")
    mode: AccountMode = Field(..., description="Account mode (paper/live)")


class AccountCreate(AccountBase):
    """Model for creating a new account."""
    initial_balance: float = Field(default=10000.0, gt=0, description="Initial balance")


class AccountDocument(AccountBase):
    """
    Account document as stored in MongoDB.

    Tracks user balance, equity, and account metrics.
    """
    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str, datetime: lambda v: v.isoformat()},
    )

    id: Optional[str] = Field(None, alias="_id", description="MongoDB document ID")
    balance: float = Field(default=10000.0, description="Current cash balance")
    initial_balance: float = Field(default=10000.0, description="Starting balance")
    equity: float = Field(default=10000.0, description="Total equity (balance + unrealized P&L)")
    margin_used: float = Field(default=0.0, description="Margin currently in use")
    unrealized_pnl: float = Field(default=0.0, description="Total unrealized P&L")
    realized_pnl: float = Field(default=0.0, description="Total realized P&L")
    total_trades: int = Field(default=0, description="Total number of trades")
    winning_trades: int = Field(default=0, description="Number of winning trades")
    losing_trades: int = Field(default=0, description="Number of losing trades")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Account creation time")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="Last update time")

    @classmethod
    def from_mongo(cls, data: dict) -> "AccountDocument":
        """Create AccountDocument from MongoDB document."""
        if data is None:
            return None
        if "_id" in data and isinstance(data["_id"], ObjectId):
            data["_id"] = str(data["_id"])
        return cls(**data)

    def to_mongo(self) -> dict:
        """Convert to MongoDB document format."""
        data = self.model_dump(by_alias=True, exclude_none=True)
        if data.get("_id") is None:
            data.pop("_id", None)
        return data

    @property
    def win_rate(self) -> float:
        """Calculate win rate percentage."""
        total = self.winning_trades + self.losing_trades
        if total == 0:
            return 0.0
        return round((self.winning_trades / total) * 100, 2)

    @property
    def total_pnl(self) -> float:
        """Calculate total P&L (realized + unrealized)."""
        return round(self.realized_pnl + self.unrealized_pnl, 2)

    @property
    def pnl_percentage(self) -> float:
        """Calculate total P&L as percentage of initial balance."""
        if self.initial_balance == 0:
            return 0.0
        return round((self.total_pnl / self.initial_balance) * 100, 2)


class AccountUpdate(BaseModel):
    """Model for updating account fields."""
    balance: Optional[float] = None
    equity: Optional[float] = None
    margin_used: Optional[float] = None
    unrealized_pnl: Optional[float] = None
    realized_pnl: Optional[float] = None
    total_trades: Optional[int] = None
    winning_trades: Optional[int] = None
    losing_trades: Optional[int] = None
    updated_at: Optional[datetime] = None


# =============================================================================
# Signal Document
# =============================================================================

class SignalBase(BaseModel):
    """Base signal fields."""
    pair: str = Field(..., description="Trading pair")
    direction: TradeDirection = Field(..., description="Signal direction")
    confidence: float = Field(..., ge=0, le=100, description="Confidence score (0-100)")
    entry_price: float = Field(..., gt=0, description="Recommended entry price")
    stop_loss: Optional[float] = Field(None, description="Recommended stop loss")
    take_profit: Optional[float] = Field(None, description="Recommended take profit")
    strategy: Optional[str] = Field(None, description="Strategy that generated the signal")


class SignalCreate(SignalBase):
    """Model for creating a new signal."""
    pass


class SignalDocument(SignalBase):
    """
    Signal document as stored in MongoDB.

    Represents trading signals generated by the ML/AI engine.
    """
    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str, datetime: lambda v: v.isoformat()},
    )

    id: Optional[str] = Field(None, alias="_id", description="MongoDB document ID")
    status: SignalStatus = Field(default=SignalStatus.ACTIVE, description="Signal status")
    timeframe: str = Field(default="1h", description="Analysis timeframe")
    key_factors: list[str] = Field(default_factory=list, description="Key factors for the signal")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Signal creation time")
    expires_at: Optional[datetime] = Field(None, description="Signal expiration time")
    executed_at: Optional[datetime] = Field(None, description="When signal was executed")
    trade_id: Optional[str] = Field(None, description="Associated trade ID if executed")

    @classmethod
    def from_mongo(cls, data: dict) -> "SignalDocument":
        """Create SignalDocument from MongoDB document."""
        if data is None:
            return None
        if "_id" in data and isinstance(data["_id"], ObjectId):
            data["_id"] = str(data["_id"])
        return cls(**data)

    def to_mongo(self) -> dict:
        """Convert to MongoDB document format."""
        data = self.model_dump(by_alias=True, exclude_none=True)
        if data.get("_id") is None:
            data.pop("_id", None)
        return data


class SignalUpdate(BaseModel):
    """Model for updating signal fields."""
    status: Optional[SignalStatus] = None
    executed_at: Optional[datetime] = None
    trade_id: Optional[str] = None


# =============================================================================
# Response Models
# =============================================================================

class TradeResponse(BaseModel):
    """API response model for trades."""
    id: str
    user_id: str
    pair: str
    direction: str
    entry_price: float
    exit_price: Optional[float] = None
    quantity: float
    pnl: Optional[float] = None
    pnl_pct: Optional[float] = None
    status: str
    opened_at: str
    closed_at: Optional[str] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    signal_id: Optional[str] = None


class PositionResponse(BaseModel):
    """API response model for positions."""
    id: str
    user_id: str
    pair: str
    direction: str
    entry_price: float
    current_price: Optional[float] = None
    quantity: float
    unrealized_pnl: Optional[float] = None
    unrealized_pnl_pct: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    opened_at: str


class AccountResponse(BaseModel):
    """API response model for accounts."""
    id: str
    user_id: str
    mode: str
    balance: float
    initial_balance: float
    equity: float
    margin_used: float
    unrealized_pnl: float
    realized_pnl: float
    total_pnl: float
    pnl_percentage: float
    total_trades: int
    win_rate: float
    created_at: str
    updated_at: str


# =============================================================================
# Settings Document
# =============================================================================

class SettingsDocument(BaseModel):
    """
    User settings document as stored in MongoDB.

    Stores broker credentials and trading preferences.
    """
    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str, datetime: lambda v: v.isoformat()},
    )

    id: Optional[str] = Field(None, alias="_id", description="MongoDB document ID")
    user_id: str = Field(default="default", description="User identifier")

    # OANDA Configuration
    oanda_account_id: Optional[str] = Field(None, description="OANDA account ID")
    oanda_access_token: Optional[str] = Field(None, description="OANDA API token")
    oanda_environment: str = Field(default="practice", description="practice or live")

    # Trading Mode
    trading_mode: str = Field(default="paper", description="paper or live")

    # Risk Management
    risk_per_trade: float = Field(default=0.02, description="Max risk per trade (0.02 = 2%)")
    max_daily_trades: int = Field(default=10, description="Max trades per day")
    max_daily_loss: float = Field(default=0.06, description="Max daily loss (0.06 = 6%)")

    # ML Settings
    ml_confidence_threshold: float = Field(default=0.70, description="Min confidence for auto-trade")

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    @classmethod
    def from_mongo(cls, data: dict) -> "SettingsDocument":
        """Create SettingsDocument from MongoDB document."""
        if data is None:
            return None
        if "_id" in data and isinstance(data["_id"], ObjectId):
            data["_id"] = str(data["_id"])
        return cls(**data)

    def to_mongo(self) -> dict:
        """Convert to MongoDB document format."""
        data = self.model_dump(by_alias=True, exclude_none=True)
        if data.get("_id") is None:
            data.pop("_id", None)
        return data


class SettingsUpdate(BaseModel):
    """Model for updating settings."""
    oanda_account_id: Optional[str] = None
    oanda_access_token: Optional[str] = None
    oanda_environment: Optional[str] = None
    trading_mode: Optional[str] = None
    risk_per_trade: Optional[float] = None
    max_daily_trades: Optional[int] = None
    max_daily_loss: Optional[float] = None
    ml_confidence_threshold: Optional[float] = None


class SettingsResponse(BaseModel):
    """API response model for settings (hides sensitive data)."""
    trading_mode: str
    oanda_configured: bool
    oanda_account_id: Optional[str] = None  # Partially masked
    oanda_environment: str
    risk_per_trade: float
    max_daily_trades: int
    max_daily_loss: float
    ml_confidence_threshold: float
