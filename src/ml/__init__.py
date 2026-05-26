"""
ML Classifier Layer for Forex Trading Bot

This module provides machine learning capabilities for trade signal classification,
feature engineering, training pipelines, and backtesting.

Components:
- classifier: XGBoost-based trading signal classifier
- feature_engineering: Feature preparation and transformation
- training: Training pipeline with cross-validation and hyperparameter tuning
- backtester: Strategy backtesting with performance metrics
- models: Data models and type definitions

Models:
- XGBoost Classifier: Primary model for trade direction prediction
- TensorFlow LSTM (optional): Deep learning for sequence modeling

Features:
- Model training and validation
- Feature importance analysis
- Confidence score generation (trades only when confidence > 70%)
- Model persistence and loading
- Periodic retraining pipeline
- Comprehensive backtesting

Input features:
- open, high, low, close, volume
- rsi_14, macd_signal, atr_14
- hour, weekday, spread, prior_3_outcomes

Output:
- signal: BUY | SELL | SKIP
- confidence: 0.0-1.0
"""

from .models import (
    Prediction,
    TrainingMetrics,
    EvaluationMetrics,
    BacktestResults,
    BacktestMetrics,
    Trade,
    CrossValidationResults,
    BestParams,
    TrainedModel,
    ComparisonReport,
    SignalType,
)
from .classifier import TradingClassifier
from .feature_engineering import FeatureEngineer
from .training import TrainingPipeline
from .backtester import Backtester, BaseStrategy, MLStrategy

__all__ = [
    # Models
    "Prediction",
    "TrainingMetrics",
    "EvaluationMetrics",
    "BacktestResults",
    "BacktestMetrics",
    "Trade",
    "CrossValidationResults",
    "BestParams",
    "TrainedModel",
    "ComparisonReport",
    "SignalType",
    # Classes
    "TradingClassifier",
    "FeatureEngineer",
    "TrainingPipeline",
    "Backtester",
    "BaseStrategy",
    "MLStrategy",
]
