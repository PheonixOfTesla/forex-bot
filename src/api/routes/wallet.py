from __future__ import annotations

"""
Wallet API Routes

Provides wallet management including balance, deposits, withdrawals, and transaction history.
"""

import logging
import uuid
from datetime import datetime, timedelta
from enum import Enum
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
router = APIRouter()


# =============================================================================
# Enums and Schemas
# =============================================================================


class TransactionType(str, Enum):
    """Transaction type."""
    DEPOSIT = "deposit"
    WITHDRAWAL = "withdrawal"
    TRADE_PNL = "trade_pnl"
    FEE = "fee"
    ADJUSTMENT = "adjustment"


class TransactionStatus(str, Enum):
    """Transaction status."""
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AccountMode(str, Enum):
    """Account mode."""
    PAPER = "paper"
    LIVE = "live"


class Transaction(BaseModel):
    """Transaction record."""
    id: str = Field(..., description="Transaction ID")
    type: TransactionType = Field(..., description="Transaction type")
    amount: float = Field(..., description="Transaction amount")
    balance_after: float = Field(..., description="Balance after transaction")
    status: TransactionStatus = Field(..., description="Transaction status")
    description: str = Field(..., description="Transaction description")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = Field(None, description="Completion timestamp")
    reference: Optional[str] = Field(None, description="External reference (broker, etc)")


class WalletResponse(BaseModel):
    """Wallet overview response."""
    mode: AccountMode = Field(..., description="Account mode (paper/live)")
    balance: float = Field(..., description="Current balance")
    paper_balance: float = Field(..., description="Paper trading balance")
    live_balance: float = Field(..., description="Live trading balance")
    available_balance: float = Field(..., description="Available for withdrawal")
    pending_deposits: float = Field(0, description="Pending deposit amount")
    pending_withdrawals: float = Field(0, description="Pending withdrawal amount")
    total_deposited: float = Field(..., description="Total deposited all time")
    total_withdrawn: float = Field(..., description="Total withdrawn all time")
    total_pnl: float = Field(..., description="Total realized P/L")
    recent_transactions: List[Transaction] = Field(default_factory=list)
    last_updated: datetime = Field(default_factory=datetime.utcnow)


class DepositRequest(BaseModel):
    """Deposit request."""
    amount: float = Field(..., gt=0, description="Deposit amount")
    payment_method: Optional[str] = Field(None, description="Payment method for live mode")


class DepositResponse(BaseModel):
    """Deposit response."""
    success: bool = Field(..., description="Whether deposit was successful")
    transaction_id: str = Field(..., description="Transaction ID")
    amount: float = Field(..., description="Deposit amount")
    new_balance: float = Field(..., description="New balance after deposit")
    status: TransactionStatus = Field(..., description="Transaction status")
    message: str = Field(..., description="Status message")
    broker_redirect_url: Optional[str] = Field(None, description="Broker deposit URL (live mode)")


class WithdrawRequest(BaseModel):
    """Withdrawal request."""
    amount: float = Field(..., gt=0, description="Withdrawal amount")
    destination: Optional[str] = Field(None, description="Withdrawal destination for live mode")


class WithdrawResponse(BaseModel):
    """Withdrawal response."""
    success: bool = Field(..., description="Whether withdrawal was initiated")
    transaction_id: str = Field(..., description="Transaction ID")
    amount: float = Field(..., description="Withdrawal amount")
    new_balance: float = Field(..., description="New balance after withdrawal")
    status: TransactionStatus = Field(..., description="Transaction status")
    message: str = Field(..., description="Status message")
    estimated_completion: Optional[str] = Field(None, description="Estimated completion time")
    broker_redirect_url: Optional[str] = Field(None, description="Broker withdrawal URL (live mode)")


class TransactionsResponse(BaseModel):
    """Transactions list response."""
    transactions: List[Transaction] = Field(..., description="List of transactions")
    total_count: int = Field(..., description="Total transaction count")
    page: int = Field(..., description="Current page")
    page_size: int = Field(..., description="Page size")


# =============================================================================
# In-Memory State (Replace with database in production)
# =============================================================================


class WalletState:
    """In-memory wallet state for development."""

    def __init__(self):
        self.mode: AccountMode = AccountMode.PAPER
        self.paper_balance: float = 10000.00
        self.live_balance: float = 0.00
        self.total_deposited: float = 10000.00
        self.total_withdrawn: float = 0.00
        self.total_pnl: float = 485.32
        self.transactions: List[Transaction] = self._generate_initial_transactions()

    def _generate_initial_transactions(self) -> List[Transaction]:
        """Generate some initial transactions for demo."""
        now = datetime.utcnow()
        return [
            Transaction(
                id="txn_001",
                type=TransactionType.DEPOSIT,
                amount=10000.00,
                balance_after=10000.00,
                status=TransactionStatus.COMPLETED,
                description="Initial paper deposit",
                created_at=now - timedelta(days=30),
                completed_at=now - timedelta(days=30),
            ),
            Transaction(
                id="txn_002",
                type=TransactionType.TRADE_PNL,
                amount=127.45,
                balance_after=10127.45,
                status=TransactionStatus.COMPLETED,
                description="EUR/USD LONG +127.45",
                created_at=now - timedelta(days=7),
                completed_at=now - timedelta(days=7),
            ),
            Transaction(
                id="txn_003",
                type=TransactionType.TRADE_PNL,
                amount=-42.13,
                balance_after=10085.32,
                status=TransactionStatus.COMPLETED,
                description="GBP/USD SHORT -42.13",
                created_at=now - timedelta(days=5),
                completed_at=now - timedelta(days=5),
            ),
            Transaction(
                id="txn_004",
                type=TransactionType.TRADE_PNL,
                amount=200.00,
                balance_after=10285.32,
                status=TransactionStatus.COMPLETED,
                description="USD/JPY LONG +200.00",
                created_at=now - timedelta(days=3),
                completed_at=now - timedelta(days=3),
            ),
            Transaction(
                id="txn_005",
                type=TransactionType.TRADE_PNL,
                amount=200.00,
                balance_after=10485.32,
                status=TransactionStatus.COMPLETED,
                description="EUR/GBP SHORT +200.00",
                created_at=now - timedelta(days=1),
                completed_at=now - timedelta(days=1),
            ),
        ]

    @property
    def current_balance(self) -> float:
        """Get current balance based on mode."""
        return self.paper_balance if self.mode == AccountMode.PAPER else self.live_balance

    @property
    def available_balance(self) -> float:
        """Get available balance (excluding pending withdrawals)."""
        pending = sum(
            t.amount for t in self.transactions
            if t.type == TransactionType.WITHDRAWAL and t.status == TransactionStatus.PENDING
        )
        return max(0, self.current_balance - pending)

    @property
    def pending_deposits(self) -> float:
        """Get total pending deposits."""
        return sum(
            t.amount for t in self.transactions
            if t.type == TransactionType.DEPOSIT and t.status == TransactionStatus.PENDING
        )

    @property
    def pending_withdrawals(self) -> float:
        """Get total pending withdrawals."""
        return sum(
            t.amount for t in self.transactions
            if t.type == TransactionType.WITHDRAWAL and t.status == TransactionStatus.PENDING
        )


# Global wallet state
_wallet = WalletState()


# =============================================================================
# Wallet Endpoints
# =============================================================================


@router.get("/wallet", response_model=WalletResponse)
async def get_wallet() -> WalletResponse:
    """
    Get wallet overview.

    Returns current balance, paper/live balance, transaction history summary,
    and other wallet information.
    """
    logger.info("Fetching wallet data")

    # Get recent transactions (last 10)
    recent = sorted(_wallet.transactions, key=lambda t: t.created_at, reverse=True)[:10]

    return WalletResponse(
        mode=_wallet.mode,
        balance=_wallet.current_balance,
        paper_balance=_wallet.paper_balance,
        live_balance=_wallet.live_balance,
        available_balance=_wallet.available_balance,
        pending_deposits=_wallet.pending_deposits,
        pending_withdrawals=_wallet.pending_withdrawals,
        total_deposited=_wallet.total_deposited,
        total_withdrawn=_wallet.total_withdrawn,
        total_pnl=_wallet.total_pnl,
        recent_transactions=recent,
        last_updated=datetime.utcnow(),
    )


@router.post("/wallet/deposit", response_model=DepositResponse)
async def deposit(request: DepositRequest) -> DepositResponse:
    """
    Deposit funds to wallet.

    For paper mode: Instantly adds to paper balance.
    For live mode: Returns broker redirect URL (placeholder).
    """
    logger.info(f"Processing deposit: {request.amount}")

    transaction_id = f"txn_{uuid.uuid4().hex[:8]}"

    if _wallet.mode == AccountMode.PAPER:
        # Paper mode: instant deposit
        _wallet.paper_balance += request.amount
        _wallet.total_deposited += request.amount

        transaction = Transaction(
            id=transaction_id,
            type=TransactionType.DEPOSIT,
            amount=request.amount,
            balance_after=_wallet.paper_balance,
            status=TransactionStatus.COMPLETED,
            description=f"Paper deposit +${request.amount:.2f}",
            created_at=datetime.utcnow(),
            completed_at=datetime.utcnow(),
        )
        _wallet.transactions.append(transaction)

        return DepositResponse(
            success=True,
            transaction_id=transaction_id,
            amount=request.amount,
            new_balance=_wallet.paper_balance,
            status=TransactionStatus.COMPLETED,
            message=f"Successfully deposited ${request.amount:.2f} to paper account",
        )
    else:
        # Live mode: redirect to broker
        transaction = Transaction(
            id=transaction_id,
            type=TransactionType.DEPOSIT,
            amount=request.amount,
            balance_after=_wallet.live_balance,  # Doesn't change until confirmed
            status=TransactionStatus.PENDING,
            description=f"Live deposit +${request.amount:.2f} (pending)",
            created_at=datetime.utcnow(),
        )
        _wallet.transactions.append(transaction)

        return DepositResponse(
            success=True,
            transaction_id=transaction_id,
            amount=request.amount,
            new_balance=_wallet.live_balance,
            status=TransactionStatus.PENDING,
            message="Redirecting to broker for deposit",
            broker_redirect_url="https://broker.example.com/deposit",  # Placeholder
        )


@router.post("/wallet/withdraw", response_model=WithdrawResponse)
async def withdraw(request: WithdrawRequest) -> WithdrawResponse:
    """
    Withdraw funds from wallet.

    For paper mode: Instantly deducts from paper balance.
    For live mode: Returns broker redirect URL (placeholder).
    """
    logger.info(f"Processing withdrawal: {request.amount}")

    # Check available balance
    if request.amount > _wallet.available_balance:
        raise HTTPException(
            status_code=400,
            detail=f"Insufficient balance. Available: ${_wallet.available_balance:.2f}"
        )

    transaction_id = f"txn_{uuid.uuid4().hex[:8]}"

    if _wallet.mode == AccountMode.PAPER:
        # Paper mode: instant withdrawal
        _wallet.paper_balance -= request.amount
        _wallet.total_withdrawn += request.amount

        transaction = Transaction(
            id=transaction_id,
            type=TransactionType.WITHDRAWAL,
            amount=-request.amount,
            balance_after=_wallet.paper_balance,
            status=TransactionStatus.COMPLETED,
            description=f"Paper withdrawal -${request.amount:.2f}",
            created_at=datetime.utcnow(),
            completed_at=datetime.utcnow(),
        )
        _wallet.transactions.append(transaction)

        return WithdrawResponse(
            success=True,
            transaction_id=transaction_id,
            amount=request.amount,
            new_balance=_wallet.paper_balance,
            status=TransactionStatus.COMPLETED,
            message=f"Successfully withdrew ${request.amount:.2f} from paper account",
        )
    else:
        # Live mode: redirect to broker
        transaction = Transaction(
            id=transaction_id,
            type=TransactionType.WITHDRAWAL,
            amount=-request.amount,
            balance_after=_wallet.live_balance,  # Doesn't change until processed
            status=TransactionStatus.PENDING,
            description=f"Live withdrawal -${request.amount:.2f} (pending)",
            created_at=datetime.utcnow(),
        )
        _wallet.transactions.append(transaction)

        return WithdrawResponse(
            success=True,
            transaction_id=transaction_id,
            amount=request.amount,
            new_balance=_wallet.live_balance,
            status=TransactionStatus.PENDING,
            message="Withdrawal initiated. Processing time: 1-3 business days",
            estimated_completion="1-3 business days",
            broker_redirect_url="https://broker.example.com/withdraw",  # Placeholder
        )


@router.get("/wallet/transactions", response_model=TransactionsResponse)
async def get_transactions(
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=20, ge=1, le=100, description="Items per page"),
    type: Optional[TransactionType] = Query(default=None, description="Filter by type"),
) -> TransactionsResponse:
    """
    Get transaction history with pagination.

    Args:
        page: Page number (1-indexed)
        page_size: Number of items per page (max 100)
        type: Optional filter by transaction type
    """
    logger.info(f"Fetching transactions: page={page}, size={page_size}, type={type}")

    # Filter transactions
    filtered = _wallet.transactions
    if type:
        filtered = [t for t in filtered if t.type == type]

    # Sort by date (newest first)
    sorted_txns = sorted(filtered, key=lambda t: t.created_at, reverse=True)

    # Paginate
    total_count = len(sorted_txns)
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    page_txns = sorted_txns[start_idx:end_idx]

    return TransactionsResponse(
        transactions=page_txns,
        total_count=total_count,
        page=page,
        page_size=page_size,
    )


@router.post("/wallet/mode")
async def set_mode(mode: AccountMode) -> dict:
    """
    Switch between paper and live trading mode.

    Args:
        mode: Account mode to switch to
    """
    logger.info(f"Switching wallet mode to: {mode}")

    old_mode = _wallet.mode
    _wallet.mode = mode

    return {
        "success": True,
        "previous_mode": old_mode,
        "current_mode": mode,
        "balance": _wallet.current_balance,
        "message": f"Switched to {mode.value} trading mode",
    }


@router.get("/wallet/balance-history")
async def get_balance_history(
    days: int = Query(default=30, ge=1, le=365, description="Number of days")
) -> List[dict]:
    """
    Get wallet balance history for charting.

    Args:
        days: Number of days of history
    """
    logger.info(f"Fetching balance history for {days} days")

    history = []
    now = datetime.utcnow()

    # Generate history based on transactions
    # Start with initial balance and replay transactions
    base_balance = 10000.00

    for i in range(days, -1, -1):
        date = now - timedelta(days=i)

        # Sum all completed transactions up to this date
        balance = base_balance
        for txn in _wallet.transactions:
            if txn.completed_at and txn.completed_at <= date:
                if txn.type == TransactionType.DEPOSIT:
                    balance += txn.amount
                elif txn.type == TransactionType.WITHDRAWAL:
                    balance += txn.amount  # Already negative
                elif txn.type == TransactionType.TRADE_PNL:
                    balance += txn.amount

        # Add some variance for visualization
        variance = (hash(str(date.date())) % 100 - 50) / 20

        history.append({
            "timestamp": date.isoformat(),
            "balance": round(balance + variance, 2),
        })

    return history
