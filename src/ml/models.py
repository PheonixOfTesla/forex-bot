"""
Data Models for ML Classifier Layer

Defines all dataclasses and type definitions used across the ML module.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Literal, Optional, Any
from enum import Enum


class SignalType(str, Enum):
    """Trading signal types."""
    BUY = "BUY"
    SELL = "SELL"
    SKIP = "SKIP"


@dataclass
class Prediction:
    """
    ML model prediction output.

    Attributes:
        signal: Trading signal (BUY, SELL, or SKIP)
        confidence: Confidence score between 0.0 and 1.0
        features_used: Dictionary of feature names to their values used in prediction
    """
    signal: Literal["BUY", "SELL", "SKIP"]
    confidence: float
    features_used: Dict[str, float] = field(default_factory=dict)

    def __post_init__(self):
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"Confidence must be between 0.0 and 1.0, got {self.confidence}")
        if self.signal not in ["BUY", "SELL", "SKIP"]:
            raise ValueError(f"Signal must be BUY, SELL, or SKIP, got {self.signal}")

    @property
    def is_tradeable(self) -> bool:
        """Returns True if signal is actionable (not SKIP) and confidence > 70%."""
        return self.signal != "SKIP" and self.confidence >= 0.70

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "signal": self.signal,
            "confidence": self.confidence,
            "features_used": self.features_used,
            "is_tradeable": self.is_tradeable,
        }


@dataclass
class TrainingMetrics:
    """
    Metrics from model training.

    Attributes:
        accuracy: Overall accuracy of the model
        precision: Precision score (true positives / predicted positives)
        recall: Recall score (true positives / actual positives)
        f1_score: Harmonic mean of precision and recall
        win_rate_predicted: Predicted win rate based on training data
        feature_importance: Dictionary of feature names to importance scores
        training_time_seconds: Time taken to train the model
        n_samples: Number of training samples used
    """
    accuracy: float
    precision: float
    recall: float
    f1_score: float
    win_rate_predicted: float
    feature_importance: Dict[str, float] = field(default_factory=dict)
    training_time_seconds: float = 0.0
    n_samples: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "accuracy": self.accuracy,
            "precision": self.precision,
            "recall": self.recall,
            "f1_score": self.f1_score,
            "win_rate_predicted": self.win_rate_predicted,
            "feature_importance": self.feature_importance,
            "training_time_seconds": self.training_time_seconds,
            "n_samples": self.n_samples,
        }


@dataclass
class EvaluationMetrics:
    """
    Metrics from model evaluation on test data.

    Attributes:
        accuracy: Overall accuracy
        precision_per_class: Precision for each signal class
        recall_per_class: Recall for each signal class
        f1_per_class: F1 score for each signal class
        confusion_matrix: Confusion matrix as nested list
        classification_report: Full classification report string
        roc_auc: ROC AUC score (for binary or one-vs-rest)
    """
    accuracy: float
    precision_per_class: Dict[str, float] = field(default_factory=dict)
    recall_per_class: Dict[str, float] = field(default_factory=dict)
    f1_per_class: Dict[str, float] = field(default_factory=dict)
    confusion_matrix: List[List[int]] = field(default_factory=list)
    classification_report: str = ""
    roc_auc: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "accuracy": self.accuracy,
            "precision_per_class": self.precision_per_class,
            "recall_per_class": self.recall_per_class,
            "f1_per_class": self.f1_per_class,
            "confusion_matrix": self.confusion_matrix,
            "roc_auc": self.roc_auc,
        }


@dataclass
class Trade:
    """
    Represents a single trade in backtesting.

    Attributes:
        entry_time: Time of trade entry
        exit_time: Time of trade exit
        symbol: Trading symbol (e.g., 'EURUSD')
        direction: Trade direction ('BUY' or 'SELL')
        entry_price: Price at entry
        exit_price: Price at exit
        lot_size: Position size in lots
        pnl: Profit/loss in account currency
        pnl_pips: Profit/loss in pips
        confidence: ML model confidence at entry
        features_at_entry: Features used for prediction at entry
    """
    entry_time: datetime
    exit_time: Optional[datetime]
    symbol: str
    direction: Literal["BUY", "SELL"]
    entry_price: float
    exit_price: Optional[float] = None
    lot_size: float = 0.01
    pnl: float = 0.0
    pnl_pips: float = 0.0
    confidence: float = 0.0
    features_at_entry: Dict[str, float] = field(default_factory=dict)
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    exit_reason: Optional[str] = None  # 'tp_hit', 'sl_hit', 'signal_exit', 'timeout'

    @property
    def is_winner(self) -> bool:
        """Returns True if trade was profitable."""
        return self.pnl > 0

    @property
    def duration_minutes(self) -> Optional[float]:
        """Returns trade duration in minutes."""
        if self.exit_time is None:
            return None
        return (self.exit_time - self.entry_time).total_seconds() / 60

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "entry_time": self.entry_time.isoformat() if self.entry_time else None,
            "exit_time": self.exit_time.isoformat() if self.exit_time else None,
            "symbol": self.symbol,
            "direction": self.direction,
            "entry_price": self.entry_price,
            "exit_price": self.exit_price,
            "lot_size": self.lot_size,
            "pnl": self.pnl,
            "pnl_pips": self.pnl_pips,
            "confidence": self.confidence,
            "is_winner": self.is_winner,
            "duration_minutes": self.duration_minutes,
            "exit_reason": self.exit_reason,
        }


@dataclass
class BacktestMetrics:
    """
    Performance metrics from a backtest run.

    Attributes:
        total_trades: Total number of trades executed
        winning_trades: Number of profitable trades
        losing_trades: Number of unprofitable trades
        win_rate: Percentage of winning trades
        total_pnl: Total profit/loss
        gross_profit: Sum of all winning trades
        gross_loss: Sum of all losing trades (negative)
        profit_factor: Gross profit / abs(gross loss)
        max_drawdown: Maximum drawdown percentage
        max_drawdown_duration_days: Duration of maximum drawdown
        sharpe_ratio: Risk-adjusted return metric
        sortino_ratio: Downside risk-adjusted return
        avg_trade_pnl: Average PnL per trade
        avg_winner: Average winning trade
        avg_loser: Average losing trade
        largest_winner: Largest single winning trade
        largest_loser: Largest single losing trade
        avg_trade_duration_minutes: Average trade duration
        trades_per_day: Average number of trades per day
    """
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0
    total_pnl: float = 0.0
    gross_profit: float = 0.0
    gross_loss: float = 0.0
    profit_factor: float = 0.0
    max_drawdown: float = 0.0
    max_drawdown_duration_days: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    avg_trade_pnl: float = 0.0
    avg_winner: float = 0.0
    avg_loser: float = 0.0
    largest_winner: float = 0.0
    largest_loser: float = 0.0
    avg_trade_duration_minutes: float = 0.0
    trades_per_day: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "win_rate": self.win_rate,
            "total_pnl": self.total_pnl,
            "gross_profit": self.gross_profit,
            "gross_loss": self.gross_loss,
            "profit_factor": self.profit_factor,
            "max_drawdown": self.max_drawdown,
            "max_drawdown_duration_days": self.max_drawdown_duration_days,
            "sharpe_ratio": self.sharpe_ratio,
            "sortino_ratio": self.sortino_ratio,
            "avg_trade_pnl": self.avg_trade_pnl,
            "avg_winner": self.avg_winner,
            "avg_loser": self.avg_loser,
            "largest_winner": self.largest_winner,
            "largest_loser": self.largest_loser,
            "avg_trade_duration_minutes": self.avg_trade_duration_minutes,
            "trades_per_day": self.trades_per_day,
        }


@dataclass
class BacktestResults:
    """
    Complete results from a backtest run.

    Attributes:
        total_trades: Total number of trades
        win_rate: Win rate percentage
        total_pnl: Total profit/loss
        max_drawdown: Maximum drawdown percentage
        sharpe_ratio: Sharpe ratio
        trades: List of all trades
        equity_curve: Equity values over time
        metrics: Detailed performance metrics
        start_date: Backtest start date
        end_date: Backtest end date
        initial_capital: Starting capital
        final_capital: Ending capital
    """
    total_trades: int
    win_rate: float
    total_pnl: float
    max_drawdown: float
    sharpe_ratio: float
    trades: List[Trade] = field(default_factory=list)
    equity_curve: List[float] = field(default_factory=list)
    metrics: Optional[BacktestMetrics] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    initial_capital: float = 25.0
    final_capital: float = 25.0
    timestamps: List[datetime] = field(default_factory=list)

    @property
    def return_pct(self) -> float:
        """Return percentage."""
        if self.initial_capital == 0:
            return 0.0
        return ((self.final_capital - self.initial_capital) / self.initial_capital) * 100

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "total_trades": self.total_trades,
            "win_rate": self.win_rate,
            "total_pnl": self.total_pnl,
            "max_drawdown": self.max_drawdown,
            "sharpe_ratio": self.sharpe_ratio,
            "return_pct": self.return_pct,
            "initial_capital": self.initial_capital,
            "final_capital": self.final_capital,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "metrics": self.metrics.to_dict() if self.metrics else None,
            "n_trades": len(self.trades),
        }


@dataclass
class CrossValidationResults:
    """
    Results from k-fold cross-validation.

    Attributes:
        n_folds: Number of folds used
        fold_metrics: List of metrics for each fold
        mean_accuracy: Mean accuracy across folds
        std_accuracy: Standard deviation of accuracy
        mean_f1: Mean F1 score across folds
        std_f1: Standard deviation of F1 score
        mean_win_rate: Mean predicted win rate
        all_predictions: All predictions from validation sets
    """
    n_folds: int
    fold_metrics: List[TrainingMetrics] = field(default_factory=list)
    mean_accuracy: float = 0.0
    std_accuracy: float = 0.0
    mean_f1: float = 0.0
    std_f1: float = 0.0
    mean_win_rate: float = 0.0
    all_predictions: List[Prediction] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "n_folds": self.n_folds,
            "mean_accuracy": self.mean_accuracy,
            "std_accuracy": self.std_accuracy,
            "mean_f1": self.mean_f1,
            "std_f1": self.std_f1,
            "mean_win_rate": self.mean_win_rate,
            "fold_metrics": [m.to_dict() for m in self.fold_metrics],
        }


@dataclass
class BestParams:
    """
    Best hyperparameters from tuning.

    Attributes:
        params: Dictionary of best parameters
        best_score: Best validation score achieved
        all_results: All parameter combinations and their scores
        search_method: Method used ('grid', 'random', 'bayesian')
        n_iterations: Number of iterations/combinations tried
    """
    params: Dict[str, Any] = field(default_factory=dict)
    best_score: float = 0.0
    all_results: List[Dict[str, Any]] = field(default_factory=list)
    search_method: str = "grid"
    n_iterations: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "params": self.params,
            "best_score": self.best_score,
            "search_method": self.search_method,
            "n_iterations": self.n_iterations,
        }


@dataclass
class TrainedModel:
    """
    Container for a trained model with metadata.

    Attributes:
        model: The trained model object
        feature_columns: List of feature column names
        metrics: Training metrics
        created_at: Timestamp of model creation
        model_version: Version string
        hyperparameters: Hyperparameters used
    """
    model: Any  # XGBoost model or similar
    feature_columns: List[str] = field(default_factory=list)
    metrics: Optional[TrainingMetrics] = None
    created_at: datetime = field(default_factory=datetime.now)
    model_version: str = "1.0.0"
    hyperparameters: Dict[str, Any] = field(default_factory=dict)
    scaler: Any = None  # Optional scaler for feature normalization

    def to_dict(self) -> Dict[str, Any]:
        """Convert metadata to dictionary (excludes model object)."""
        return {
            "feature_columns": self.feature_columns,
            "metrics": self.metrics.to_dict() if self.metrics else None,
            "created_at": self.created_at.isoformat(),
            "model_version": self.model_version,
            "hyperparameters": self.hyperparameters,
        }


@dataclass
class ComparisonReport:
    """
    Report comparing multiple strategies.

    Attributes:
        strategy_names: Names of strategies compared
        results: Backtest results for each strategy
        best_strategy: Name of best performing strategy
        ranking: Strategies ranked by performance
        comparison_metrics: Side-by-side metric comparison
    """
    strategy_names: List[str] = field(default_factory=list)
    results: Dict[str, BacktestResults] = field(default_factory=dict)
    best_strategy: str = ""
    ranking: List[str] = field(default_factory=list)
    comparison_metrics: Dict[str, Dict[str, float]] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "strategy_names": self.strategy_names,
            "best_strategy": self.best_strategy,
            "ranking": self.ranking,
            "comparison_metrics": self.comparison_metrics,
            "results": {k: v.to_dict() for k, v in self.results.items()},
        }
