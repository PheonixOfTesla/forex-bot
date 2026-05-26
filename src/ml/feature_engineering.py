"""
Feature Engineering for ML Classifier

Handles feature preparation, transformation, and normalization for trading signals.
Supports lagged features, rolling statistics, and time-based features.
"""

import numpy as np
import pandas as pd
from pandas import DataFrame, Series
from typing import List, Optional, Tuple, Dict, Any
from sklearn.preprocessing import StandardScaler, RobustScaler
import logging

logger = logging.getLogger(__name__)


class FeatureEngineer:
    """
    Feature engineering pipeline for trading ML models.

    Transforms raw OHLCV data with indicators into ML-ready features.
    Handles lagged features, rolling statistics, time features, and normalization.
    """

    # Core feature columns expected from data
    CORE_FEATURES = [
        "open", "high", "low", "close", "volume",
        "rsi_14", "macd_signal", "atr_14"
    ]

    # Time-based features
    TIME_FEATURES = ["hour", "weekday", "is_session_overlap"]

    # Additional features
    EXTRA_FEATURES = ["spread", "prior_3_outcomes"]

    # All standard features for model input
    STANDARD_FEATURES = CORE_FEATURES + TIME_FEATURES + EXTRA_FEATURES

    def __init__(
        self,
        scaler_type: str = "robust",
        lag_periods: List[int] = None,
        rolling_windows: List[int] = None,
        include_lagged: bool = True,
        include_rolling: bool = True,
        include_time: bool = True,
    ):
        """
        Initialize FeatureEngineer.

        Args:
            scaler_type: Type of scaler ('standard', 'robust', or 'none')
            lag_periods: Periods for lagged features (default: [1, 2, 3])
            rolling_windows: Windows for rolling features (default: [5, 10, 20])
            include_lagged: Whether to add lagged features
            include_rolling: Whether to add rolling features
            include_time: Whether to add time-based features
        """
        self.scaler_type = scaler_type
        self.lag_periods = lag_periods or [1, 2, 3]
        self.rolling_windows = rolling_windows or [5, 10, 20]
        self.include_lagged = include_lagged
        self.include_rolling = include_rolling
        self.include_time = include_time

        self.scaler: Optional[StandardScaler | RobustScaler] = None
        self.feature_columns: List[str] = []
        self._fitted = False

    def prepare_features(
        self,
        df: DataFrame,
        include_target: bool = True,
        fit_scaler: bool = False,
    ) -> DataFrame:
        """
        Prepare features from raw data with indicators.

        Args:
            df: DataFrame with OHLCV data and indicators
            include_target: Whether to include target column if present
            fit_scaler: Whether to fit the scaler on this data

        Returns:
            DataFrame with engineered features ready for ML
        """
        logger.info(f"Preparing features from {len(df)} rows")
        df = df.copy()

        # Ensure datetime index
        if not isinstance(df.index, pd.DatetimeIndex):
            if "datetime" in df.columns:
                df.set_index("datetime", inplace=True)
            elif "timestamp" in df.columns:
                df.set_index("timestamp", inplace=True)
                df.index = pd.to_datetime(df.index)

        # Add time features
        if self.include_time:
            df = self.add_time_features(df)

        # Add lagged features for key columns
        if self.include_lagged:
            lag_columns = ["close", "rsi_14", "macd_signal", "volume"]
            lag_columns = [c for c in lag_columns if c in df.columns]
            df = self.add_lagged_features(df, lag_columns, self.lag_periods)

        # Add rolling features
        if self.include_rolling:
            rolling_columns = ["close", "volume", "atr_14"]
            rolling_columns = [c for c in rolling_columns if c in df.columns]
            df = self.add_rolling_features(df, rolling_columns, self.rolling_windows)

        # Add derived features
        df = self._add_derived_features(df)

        # Handle missing values
        df = self._handle_missing_values(df)

        # Determine feature columns (exclude target and non-feature columns)
        exclude_cols = ["target", "signal", "label", "returns", "forward_returns"]
        self.feature_columns = [
            col for col in df.columns
            if col not in exclude_cols and df[col].dtype in [np.float64, np.int64, np.float32, np.int32]
        ]

        # Normalize features
        if self.scaler_type != "none":
            df = self.normalize_features(df, fit=fit_scaler)

        # Select output columns
        output_cols = self.feature_columns.copy()
        if include_target and "target" in df.columns:
            output_cols.append("target")

        result = df[output_cols].copy()
        logger.info(f"Prepared {len(self.feature_columns)} features, {len(result)} rows")

        return result

    def add_lagged_features(
        self,
        df: DataFrame,
        columns: List[str],
        lags: List[int] = None,
    ) -> DataFrame:
        """
        Add lagged features for specified columns.

        Args:
            df: Input DataFrame
            columns: Columns to create lags for
            lags: Lag periods (default: [1, 2, 3])

        Returns:
            DataFrame with lagged features added
        """
        lags = lags or [1, 2, 3]
        df = df.copy()

        for col in columns:
            if col not in df.columns:
                logger.warning(f"Column {col} not found, skipping lagged features")
                continue

            for lag in lags:
                lag_col_name = f"{col}_lag_{lag}"
                df[lag_col_name] = df[col].shift(lag)

                # Also add lagged returns/changes
                if col in ["close", "volume"]:
                    pct_change_col = f"{col}_pct_change_lag_{lag}"
                    df[pct_change_col] = df[col].pct_change(lag)

        return df

    def add_rolling_features(
        self,
        df: DataFrame,
        columns: List[str],
        windows: List[int] = None,
    ) -> DataFrame:
        """
        Add rolling statistics for specified columns.

        Args:
            df: Input DataFrame
            columns: Columns to create rolling features for
            windows: Rolling window sizes (default: [5, 10, 20])

        Returns:
            DataFrame with rolling features added
        """
        windows = windows or [5, 10, 20]
        df = df.copy()

        for col in columns:
            if col not in df.columns:
                logger.warning(f"Column {col} not found, skipping rolling features")
                continue

            for window in windows:
                # Rolling mean
                df[f"{col}_rolling_mean_{window}"] = df[col].rolling(window=window).mean()

                # Rolling std
                df[f"{col}_rolling_std_{window}"] = df[col].rolling(window=window).std()

                # Rolling min/max
                df[f"{col}_rolling_min_{window}"] = df[col].rolling(window=window).min()
                df[f"{col}_rolling_max_{window}"] = df[col].rolling(window=window).max()

                # Rolling z-score (deviation from mean in std units)
                rolling_mean = df[f"{col}_rolling_mean_{window}"]
                rolling_std = df[f"{col}_rolling_std_{window}"]
                df[f"{col}_zscore_{window}"] = (df[col] - rolling_mean) / (rolling_std + 1e-8)

        return df

    def add_time_features(self, df: DataFrame) -> DataFrame:
        """
        Add time-based features from datetime index.

        Adds:
            - hour: Hour of day (0-23)
            - weekday: Day of week (0=Monday, 6=Sunday)
            - is_session_overlap: Whether in major session overlap

        Args:
            df: DataFrame with datetime index

        Returns:
            DataFrame with time features added
        """
        df = df.copy()

        if isinstance(df.index, pd.DatetimeIndex):
            df["hour"] = df.index.hour
            df["weekday"] = df.index.dayofweek
        else:
            logger.warning("No datetime index found, using zeros for time features")
            df["hour"] = 0
            df["weekday"] = 0

        # Session overlap detection (London-NY overlap: 13:00-17:00 UTC)
        # Asian-London overlap: 07:00-09:00 UTC
        df["is_session_overlap"] = (
            ((df["hour"] >= 13) & (df["hour"] < 17)) |  # London-NY
            ((df["hour"] >= 7) & (df["hour"] < 9))      # Asian-London
        ).astype(int)

        # Additional time features
        df["is_london_session"] = ((df["hour"] >= 7) & (df["hour"] < 16)).astype(int)
        df["is_ny_session"] = ((df["hour"] >= 13) & (df["hour"] < 22)).astype(int)
        df["is_asian_session"] = ((df["hour"] >= 23) | (df["hour"] < 9)).astype(int)

        # Cyclical encoding for hour (captures that 23:00 is close to 00:00)
        df["hour_sin"] = np.sin(2 * np.pi * df["hour"] / 24)
        df["hour_cos"] = np.cos(2 * np.pi * df["hour"] / 24)

        # Cyclical encoding for weekday
        df["weekday_sin"] = np.sin(2 * np.pi * df["weekday"] / 7)
        df["weekday_cos"] = np.cos(2 * np.pi * df["weekday"] / 7)

        return df

    def normalize_features(
        self,
        df: DataFrame,
        fit: bool = False,
    ) -> DataFrame:
        """
        Normalize feature columns using the configured scaler.

        Args:
            df: DataFrame with features
            fit: Whether to fit the scaler on this data

        Returns:
            DataFrame with normalized features
        """
        df = df.copy()

        # Columns to normalize (exclude categorical and binary)
        exclude_normalize = [
            "target", "signal", "label", "hour", "weekday",
            "is_session_overlap", "is_london_session", "is_ny_session", "is_asian_session"
        ]
        cols_to_normalize = [
            col for col in self.feature_columns
            if col not in exclude_normalize
        ]

        if not cols_to_normalize:
            return df

        if fit or self.scaler is None:
            if self.scaler_type == "robust":
                self.scaler = RobustScaler()
            else:
                self.scaler = StandardScaler()

            df[cols_to_normalize] = self.scaler.fit_transform(df[cols_to_normalize])
            self._fitted = True
            logger.info(f"Fitted scaler on {len(cols_to_normalize)} columns")
        else:
            df[cols_to_normalize] = self.scaler.transform(df[cols_to_normalize])

        return df

    def get_feature_columns(self) -> List[str]:
        """
        Get list of feature column names.

        Returns:
            List of feature column names used for model input
        """
        return self.feature_columns.copy()

    def _add_derived_features(self, df: DataFrame) -> DataFrame:
        """Add derived/calculated features."""
        df = df.copy()

        # Price-based features
        if all(col in df.columns for col in ["high", "low", "close"]):
            # True Range components
            df["high_low_range"] = df["high"] - df["low"]
            df["close_to_high"] = (df["high"] - df["close"]) / (df["high_low_range"] + 1e-8)
            df["close_to_low"] = (df["close"] - df["low"]) / (df["high_low_range"] + 1e-8)

        # Momentum features
        if "close" in df.columns:
            # Returns at different horizons
            df["returns_1"] = df["close"].pct_change(1)
            df["returns_5"] = df["close"].pct_change(5)
            df["returns_10"] = df["close"].pct_change(10)

            # Momentum indicator
            df["momentum_10"] = df["close"] / df["close"].shift(10) - 1

        # RSI-based features
        if "rsi_14" in df.columns:
            df["rsi_overbought"] = (df["rsi_14"] > 70).astype(int)
            df["rsi_oversold"] = (df["rsi_14"] < 30).astype(int)
            df["rsi_neutral"] = ((df["rsi_14"] >= 40) & (df["rsi_14"] <= 60)).astype(int)

        # Volatility features
        if "atr_14" in df.columns and "close" in df.columns:
            df["atr_pct"] = df["atr_14"] / df["close"]
            df["volatility_regime"] = pd.qcut(
                df["atr_pct"].rank(method="first"),
                q=3,
                labels=[0, 1, 2]
            ).astype(int)

        # Volume features
        if "volume" in df.columns:
            df["volume_sma_20"] = df["volume"].rolling(20).mean()
            df["volume_ratio"] = df["volume"] / (df["volume_sma_20"] + 1e-8)
            df["high_volume"] = (df["volume_ratio"] > 1.5).astype(int)

        # MACD features
        if "macd_signal" in df.columns:
            df["macd_positive"] = (df["macd_signal"] > 0).astype(int)
            df["macd_momentum"] = df["macd_signal"].diff()

        # Prior outcomes feature (simulated if not present)
        if "prior_3_outcomes" not in df.columns:
            # Calculate based on prior returns
            if "returns_1" in df.columns:
                df["prior_outcome_1"] = (df["returns_1"].shift(1) > 0).astype(int)
                df["prior_outcome_2"] = (df["returns_1"].shift(2) > 0).astype(int)
                df["prior_outcome_3"] = (df["returns_1"].shift(3) > 0).astype(int)
                df["prior_3_outcomes"] = (
                    df["prior_outcome_1"] + df["prior_outcome_2"] + df["prior_outcome_3"]
                ) / 3

        # Spread feature (simulated if not present)
        if "spread" not in df.columns:
            if "atr_14" in df.columns:
                # Estimate spread as fraction of ATR
                df["spread"] = df["atr_14"] * 0.01
            else:
                df["spread"] = 0.0001  # Default pip spread

        return df

    def _handle_missing_values(self, df: DataFrame) -> DataFrame:
        """Handle missing values in features."""
        df = df.copy()

        # Count missing before
        missing_before = df.isnull().sum().sum()

        # Forward fill then backward fill
        df = df.ffill().bfill()

        # Fill any remaining NaN with 0
        df = df.fillna(0)

        # Replace infinities
        df = df.replace([np.inf, -np.inf], 0)

        missing_after = df.isnull().sum().sum()
        logger.info(f"Handled missing values: {missing_before} -> {missing_after}")

        return df

    def inverse_transform(self, df: DataFrame) -> DataFrame:
        """
        Inverse transform normalized features back to original scale.

        Args:
            df: DataFrame with normalized features

        Returns:
            DataFrame with features in original scale
        """
        if self.scaler is None or not self._fitted:
            logger.warning("Scaler not fitted, returning original data")
            return df

        df = df.copy()
        exclude_normalize = [
            "target", "signal", "label", "hour", "weekday",
            "is_session_overlap", "is_london_session", "is_ny_session", "is_asian_session"
        ]
        cols_to_inverse = [
            col for col in self.feature_columns
            if col not in exclude_normalize and col in df.columns
        ]

        if cols_to_inverse:
            df[cols_to_inverse] = self.scaler.inverse_transform(df[cols_to_inverse])

        return df

    def get_scaler_params(self) -> Dict[str, Any]:
        """Get scaler parameters for serialization."""
        if self.scaler is None:
            return {}

        params = {
            "scaler_type": self.scaler_type,
            "feature_columns": self.feature_columns,
        }

        if hasattr(self.scaler, "mean_"):
            params["mean"] = self.scaler.mean_.tolist()
            params["scale"] = self.scaler.scale_.tolist()
        elif hasattr(self.scaler, "center_"):
            params["center"] = self.scaler.center_.tolist()
            params["scale"] = self.scaler.scale_.tolist()

        return params

    def set_scaler_params(self, params: Dict[str, Any]) -> None:
        """Restore scaler from saved parameters."""
        if not params:
            return

        self.scaler_type = params.get("scaler_type", "robust")
        self.feature_columns = params.get("feature_columns", [])

        if self.scaler_type == "robust":
            self.scaler = RobustScaler()
            if "center" in params:
                self.scaler.center_ = np.array(params["center"])
                self.scaler.scale_ = np.array(params["scale"])
                self._fitted = True
        else:
            self.scaler = StandardScaler()
            if "mean" in params:
                self.scaler.mean_ = np.array(params["mean"])
                self.scaler.scale_ = np.array(params["scale"])
                self.scaler.var_ = np.array(params["scale"]) ** 2
                self._fitted = True
