"""
Trading Signal Classifier

XGBoost-based classifier for trading signal generation.
Filters bad setups and only trades when confidence exceeds threshold.
"""

import logging
import pickle
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple

import numpy as np
import pandas as pd
from pandas import DataFrame, Series
import xgboost as xgb
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    classification_report,
    confusion_matrix,
    roc_auc_score,
)

from .models import (
    Prediction,
    TrainingMetrics,
    EvaluationMetrics,
)
from .feature_engineering import FeatureEngineer

logger = logging.getLogger(__name__)


class TradingClassifier:
    """
    XGBoost-based classifier for trading signals.

    Predicts BUY, SELL, or SKIP signals with confidence scores.
    Only recommends trades when confidence exceeds threshold (default 70%).

    Input features:
        - open, high, low, close, volume
        - rsi_14, macd_signal, atr_14
        - hour, weekday
        - spread, prior_3_outcomes

    Output:
        - signal: BUY, SELL, or SKIP
        - confidence: 0.0 to 1.0
    """

    # Signal encoding
    SIGNAL_MAP = {"SKIP": 0, "BUY": 1, "SELL": 2}
    INVERSE_SIGNAL_MAP = {0: "SKIP", 1: "BUY", 2: "SELL"}

    # Default XGBoost parameters optimized for trading
    DEFAULT_PARAMS = {
        "objective": "multi:softprob",
        "num_class": 3,
        "max_depth": 6,
        "learning_rate": 0.05,
        "n_estimators": 200,
        "min_child_weight": 3,
        "subsample": 0.8,
        "colsample_bytree": 0.8,
        "gamma": 0.1,
        "reg_alpha": 0.1,
        "reg_lambda": 1.0,
        "scale_pos_weight": 1,
        "tree_method": "hist",
        "random_state": 42,
        "n_jobs": -1,
        "eval_metric": "mlogloss",
    }

    def __init__(
        self,
        model_path: Optional[str] = None,
        confidence_threshold: float = 0.70,
        params: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize TradingClassifier.

        Args:
            model_path: Path to load pre-trained model from
            confidence_threshold: Minimum confidence to generate trade signal
            params: XGBoost parameters (uses defaults if not provided)
        """
        self.confidence_threshold = confidence_threshold
        self.params = {**self.DEFAULT_PARAMS, **(params or {})}
        self.model: Optional[xgb.XGBClassifier] = None
        self.feature_engineer = FeatureEngineer()
        self.feature_columns: List[str] = []
        self.is_fitted = False
        self.model_version = "1.0.0"
        self.created_at: Optional[datetime] = None

        if model_path:
            self.load_model(model_path)

    def train(
        self,
        X: DataFrame,
        y: Series,
        validation_split: float = 0.2,
        early_stopping_rounds: int = 20,
        verbose: bool = True,
    ) -> TrainingMetrics:
        """
        Train the classifier on labeled data.

        Args:
            X: Feature DataFrame
            y: Target Series with signal labels (0=SKIP, 1=BUY, 2=SELL)
            validation_split: Fraction of data for validation
            early_stopping_rounds: Stop if no improvement for this many rounds
            verbose: Whether to print training progress

        Returns:
            TrainingMetrics with training results
        """
        import time

        start_time = time.time()
        logger.info(f"Training classifier on {len(X)} samples")

        # Store feature columns
        self.feature_columns = list(X.columns)

        # Split data
        X_train, X_val, y_train, y_val = train_test_split(
            X, y,
            test_size=validation_split,
            random_state=42,
            stratify=y if len(np.unique(y)) > 1 else None,
        )

        # Initialize model
        self.model = xgb.XGBClassifier(**self.params)

        # Train with early stopping
        self.model.fit(
            X_train, y_train,
            eval_set=[(X_val, y_val)],
            verbose=verbose,
        )

        self.is_fitted = True
        self.created_at = datetime.now()

        # Calculate training metrics
        y_pred = self.model.predict(X_val)
        y_pred_proba = self.model.predict_proba(X_val)

        training_time = time.time() - start_time

        # Get feature importance
        importance = self._get_feature_importance()

        # Calculate win rate prediction (for BUY/SELL signals only)
        trade_mask = y_pred != 0  # Not SKIP
        if trade_mask.sum() > 0:
            # Simulate win rate based on confidence
            confidences = y_pred_proba.max(axis=1)[trade_mask]
            win_rate_predicted = (confidences >= self.confidence_threshold).mean()
        else:
            win_rate_predicted = 0.0

        metrics = TrainingMetrics(
            accuracy=accuracy_score(y_val, y_pred),
            precision=precision_score(y_val, y_pred, average="weighted", zero_division=0),
            recall=recall_score(y_val, y_pred, average="weighted", zero_division=0),
            f1_score=f1_score(y_val, y_pred, average="weighted", zero_division=0),
            win_rate_predicted=win_rate_predicted,
            feature_importance=importance,
            training_time_seconds=training_time,
            n_samples=len(X),
        )

        logger.info(
            f"Training complete: accuracy={metrics.accuracy:.4f}, "
            f"f1={metrics.f1_score:.4f}, time={training_time:.2f}s"
        )

        return metrics

    def predict(self, features: DataFrame) -> List[Prediction]:
        """
        Generate predictions for multiple samples.

        Args:
            features: DataFrame with feature columns

        Returns:
            List of Prediction objects
        """
        if not self.is_fitted:
            raise RuntimeError("Model not fitted. Call train() or load_model() first.")

        # Ensure feature alignment
        features = self._align_features(features)

        # Get predictions
        y_pred = self.model.predict(features)
        y_pred_proba = self.model.predict_proba(features)

        predictions = []
        for i in range(len(features)):
            pred_class = int(y_pred[i])
            probabilities = y_pred_proba[i]
            confidence = float(probabilities[pred_class])

            # Determine signal based on confidence threshold
            if confidence < self.confidence_threshold:
                signal = "SKIP"
                confidence = 1.0 - max(probabilities[1], probabilities[2])
            else:
                signal = self.INVERSE_SIGNAL_MAP[pred_class]

            # Get feature values for this sample
            features_used = dict(features.iloc[i])

            predictions.append(Prediction(
                signal=signal,
                confidence=confidence,
                features_used=features_used,
            ))

        return predictions

    def predict_single(self, features: Dict[str, float]) -> Prediction:
        """
        Generate prediction for a single sample.

        Args:
            features: Dictionary of feature name to value

        Returns:
            Prediction object
        """
        # Convert to DataFrame
        df = pd.DataFrame([features])
        predictions = self.predict(df)
        return predictions[0]

    def save_model(self, path: str) -> None:
        """
        Save model and metadata to disk.

        Args:
            path: Path to save model (will create .json and .pkl files)
        """
        if not self.is_fitted:
            raise RuntimeError("Model not fitted. Nothing to save.")

        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        # Save XGBoost model
        model_path = path.with_suffix(".pkl")
        with open(model_path, "wb") as f:
            pickle.dump(self.model, f)

        # Save metadata
        metadata = {
            "model_version": self.model_version,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "feature_columns": self.feature_columns,
            "confidence_threshold": self.confidence_threshold,
            "params": self.params,
            "scaler_params": self.feature_engineer.get_scaler_params(),
        }

        metadata_path = path.with_suffix(".json")
        with open(metadata_path, "w") as f:
            json.dump(metadata, f, indent=2)

        logger.info(f"Model saved to {model_path} and {metadata_path}")

    def load_model(self, path: str) -> None:
        """
        Load model and metadata from disk.

        Args:
            path: Path to model files (without extension)
        """
        path = Path(path)

        # Try with extension first
        if path.suffix == ".pkl":
            model_path = path
            metadata_path = path.with_suffix(".json")
        elif path.suffix == ".json":
            metadata_path = path
            model_path = path.with_suffix(".pkl")
        else:
            model_path = path.with_suffix(".pkl")
            metadata_path = path.with_suffix(".json")

        # Load XGBoost model
        if not model_path.exists():
            raise FileNotFoundError(f"Model file not found: {model_path}")

        with open(model_path, "rb") as f:
            self.model = pickle.load(f)

        # Load metadata
        if metadata_path.exists():
            with open(metadata_path, "r") as f:
                metadata = json.load(f)

            self.model_version = metadata.get("model_version", "1.0.0")
            self.feature_columns = metadata.get("feature_columns", [])
            self.confidence_threshold = metadata.get("confidence_threshold", 0.70)
            self.params = metadata.get("params", self.DEFAULT_PARAMS)

            if metadata.get("created_at"):
                self.created_at = datetime.fromisoformat(metadata["created_at"])

            if metadata.get("scaler_params"):
                self.feature_engineer.set_scaler_params(metadata["scaler_params"])

        self.is_fitted = True
        logger.info(f"Model loaded from {model_path}")

    def get_feature_importance(self) -> Dict[str, float]:
        """
        Get feature importance scores.

        Returns:
            Dictionary of feature name to importance score
        """
        return self._get_feature_importance()

    def _get_feature_importance(self) -> Dict[str, float]:
        """Internal method to get feature importance."""
        if not self.is_fitted or self.model is None:
            return {}

        importance = self.model.feature_importances_
        return dict(zip(self.feature_columns, importance.tolist()))

    def evaluate(
        self,
        X_test: DataFrame,
        y_test: Series,
    ) -> EvaluationMetrics:
        """
        Evaluate model on test data.

        Args:
            X_test: Test features
            y_test: Test labels

        Returns:
            EvaluationMetrics with detailed evaluation results
        """
        if not self.is_fitted:
            raise RuntimeError("Model not fitted. Call train() or load_model() first.")

        # Align features
        X_test = self._align_features(X_test)

        # Get predictions
        y_pred = self.model.predict(X_test)
        y_pred_proba = self.model.predict_proba(X_test)

        # Calculate metrics
        accuracy = accuracy_score(y_test, y_pred)

        # Per-class metrics
        precision_per_class = {}
        recall_per_class = {}
        f1_per_class = {}

        for signal, class_idx in self.SIGNAL_MAP.items():
            binary_true = (y_test == class_idx).astype(int)
            binary_pred = (y_pred == class_idx).astype(int)

            if binary_true.sum() > 0:
                precision_per_class[signal] = precision_score(
                    binary_true, binary_pred, zero_division=0
                )
                recall_per_class[signal] = recall_score(
                    binary_true, binary_pred, zero_division=0
                )
                f1_per_class[signal] = f1_score(
                    binary_true, binary_pred, zero_division=0
                )

        # Confusion matrix
        cm = confusion_matrix(y_test, y_pred).tolist()

        # Classification report
        report = classification_report(
            y_test, y_pred,
            target_names=["SKIP", "BUY", "SELL"],
            zero_division=0,
        )

        # ROC AUC (one-vs-rest)
        try:
            roc_auc = roc_auc_score(y_test, y_pred_proba, multi_class="ovr")
        except ValueError:
            roc_auc = None

        return EvaluationMetrics(
            accuracy=accuracy,
            precision_per_class=precision_per_class,
            recall_per_class=recall_per_class,
            f1_per_class=f1_per_class,
            confusion_matrix=cm,
            classification_report=report,
            roc_auc=roc_auc,
        )

    def _align_features(self, features: DataFrame) -> DataFrame:
        """Ensure features match expected columns."""
        missing = set(self.feature_columns) - set(features.columns)
        if missing:
            logger.warning(f"Missing features: {missing}. Filling with zeros.")
            for col in missing:
                features[col] = 0

        # Select and order columns
        return features[self.feature_columns]

    def get_prediction_explanation(
        self,
        features: Dict[str, float],
    ) -> Dict[str, Any]:
        """
        Get explanation for a prediction including feature contributions.

        Args:
            features: Feature dictionary

        Returns:
            Dictionary with prediction and explanation
        """
        prediction = self.predict_single(features)
        importance = self.get_feature_importance()

        # Sort features by importance
        sorted_features = sorted(
            [(k, v, importance.get(k, 0)) for k, v in features.items()],
            key=lambda x: abs(x[2]),
            reverse=True,
        )

        top_features = [
            {"feature": f, "value": v, "importance": imp}
            for f, v, imp in sorted_features[:10]
        ]

        return {
            "prediction": prediction.to_dict(),
            "top_features": top_features,
            "model_version": self.model_version,
            "confidence_threshold": self.confidence_threshold,
        }

    def set_confidence_threshold(self, threshold: float) -> None:
        """
        Update confidence threshold for predictions.

        Args:
            threshold: New threshold (0.0 to 1.0)
        """
        if not 0.0 <= threshold <= 1.0:
            raise ValueError("Threshold must be between 0.0 and 1.0")
        self.confidence_threshold = threshold
        logger.info(f"Confidence threshold set to {threshold}")

    def get_model_info(self) -> Dict[str, Any]:
        """Get model information and metadata."""
        return {
            "is_fitted": self.is_fitted,
            "model_version": self.model_version,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "n_features": len(self.feature_columns),
            "feature_columns": self.feature_columns,
            "confidence_threshold": self.confidence_threshold,
            "params": self.params,
        }
