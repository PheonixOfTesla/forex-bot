"""
Training Pipeline for ML Classifier

Handles data loading, label creation, cross-validation, and hyperparameter tuning.
"""

import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any, Union

import numpy as np
import pandas as pd
from pandas import DataFrame, Series
from sklearn.model_selection import (
    TimeSeriesSplit,
    StratifiedKFold,
    ParameterGrid,
    RandomizedSearchCV,
)
import xgboost as xgb

from .models import (
    TrainingMetrics,
    CrossValidationResults,
    BestParams,
    TrainedModel,
)
from .classifier import TradingClassifier
from .feature_engineering import FeatureEngineer

logger = logging.getLogger(__name__)


class TrainingPipeline:
    """
    Training pipeline for trading signal classifier.

    Handles:
    - Loading historical data
    - Creating target labels from forward returns
    - Train/validation/test splits
    - Cross-validation
    - Hyperparameter tuning
    """

    # Default thresholds for label creation
    DEFAULT_THRESHOLDS = {
        "buy_threshold": 0.001,    # 10 pips for major pairs
        "sell_threshold": -0.001,  # -10 pips
        "forward_period": 10,      # 10 bars forward
    }

    # Default hyperparameter grid
    DEFAULT_PARAM_GRID = {
        "max_depth": [4, 6, 8],
        "learning_rate": [0.01, 0.05, 0.1],
        "n_estimators": [100, 200, 300],
        "min_child_weight": [1, 3, 5],
        "subsample": [0.7, 0.8, 0.9],
        "colsample_bytree": [0.7, 0.8, 0.9],
        "gamma": [0, 0.1, 0.2],
    }

    def __init__(
        self,
        data_path: str,
        buy_threshold: float = None,
        sell_threshold: float = None,
        forward_period: int = None,
    ):
        """
        Initialize TrainingPipeline.

        Args:
            data_path: Path to historical data directory
            buy_threshold: Return threshold for BUY signal
            sell_threshold: Return threshold for SELL signal
            forward_period: Number of bars forward to calculate returns
        """
        self.data_path = Path(data_path)
        self.buy_threshold = buy_threshold or self.DEFAULT_THRESHOLDS["buy_threshold"]
        self.sell_threshold = sell_threshold or self.DEFAULT_THRESHOLDS["sell_threshold"]
        self.forward_period = forward_period or self.DEFAULT_THRESHOLDS["forward_period"]

        self.feature_engineer = FeatureEngineer()
        self.classifier = TradingClassifier()

    def load_historical_data(
        self,
        symbols: List[str],
        years: int = 5,
        timeframe: str = "H1",
    ) -> DataFrame:
        """
        Load historical data for specified symbols.

        Args:
            symbols: List of currency pair symbols
            years: Number of years of data to load
            timeframe: Timeframe (M1, M5, M15, H1, H4, D1)

        Returns:
            Combined DataFrame with all symbols
        """
        logger.info(f"Loading {years} years of data for {symbols}")

        all_data = []
        end_date = datetime.now()
        start_date = end_date - timedelta(days=years * 365)

        for symbol in symbols:
            # Try different file patterns
            patterns = [
                f"{symbol}_{timeframe}_*.csv",
                f"{symbol.lower()}_{timeframe.lower()}_*.csv",
                f"{symbol}_{timeframe}.csv",
                f"{symbol}.csv",
            ]

            df = None
            for pattern in patterns:
                files = list(self.data_path.glob(pattern))
                if files:
                    df = self._load_data_files(files, start_date, end_date)
                    break

            if df is None or df.empty:
                logger.warning(f"No data found for {symbol}, generating synthetic data")
                df = self._generate_synthetic_data(symbol, start_date, end_date, timeframe)

            df["symbol"] = symbol
            all_data.append(df)

        if not all_data:
            raise ValueError("No data loaded for any symbol")

        combined = pd.concat(all_data, ignore_index=True)
        logger.info(f"Loaded {len(combined)} total rows")

        return combined

    def _load_data_files(
        self,
        files: List[Path],
        start_date: datetime,
        end_date: datetime,
    ) -> DataFrame:
        """Load and combine data from multiple files."""
        dfs = []
        for file in files:
            try:
                df = pd.read_csv(file)

                # Standardize column names
                df.columns = df.columns.str.lower().str.strip()

                # Parse datetime
                if "datetime" in df.columns:
                    df["datetime"] = pd.to_datetime(df["datetime"])
                elif "date" in df.columns and "time" in df.columns:
                    df["datetime"] = pd.to_datetime(df["date"] + " " + df["time"])
                elif "timestamp" in df.columns:
                    df["datetime"] = pd.to_datetime(df["timestamp"])

                # Filter by date range
                if "datetime" in df.columns:
                    df = df[(df["datetime"] >= start_date) & (df["datetime"] <= end_date)]

                dfs.append(df)
            except Exception as e:
                logger.error(f"Error loading {file}: {e}")

        if not dfs:
            return pd.DataFrame()

        return pd.concat(dfs, ignore_index=True)

    def _generate_synthetic_data(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
        timeframe: str,
    ) -> DataFrame:
        """Generate synthetic OHLCV data for testing."""
        logger.info(f"Generating synthetic data for {symbol}")

        # Determine frequency
        freq_map = {
            "M1": "1min", "M5": "5min", "M15": "15min",
            "H1": "1h", "H4": "4h", "D1": "1D",
        }
        freq = freq_map.get(timeframe, "1h")

        # Generate datetime index
        dates = pd.date_range(start=start_date, end=end_date, freq=freq)

        # Base price
        base_price = 1.1000 if "EUR" in symbol else 1.3000

        # Generate random walk
        np.random.seed(hash(symbol) % (2**32))
        n = len(dates)
        returns = np.random.normal(0, 0.0005, n)
        close = base_price * np.exp(np.cumsum(returns))

        # Generate OHLCV
        volatility = np.abs(np.random.normal(0.001, 0.0003, n))
        high = close * (1 + volatility)
        low = close * (1 - volatility)
        open_price = np.roll(close, 1)
        open_price[0] = base_price
        volume = np.random.exponential(1000, n)

        # Add technical indicators
        df = pd.DataFrame({
            "datetime": dates,
            "open": open_price,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
        })

        df = self._add_indicators(df)

        return df

    def _add_indicators(self, df: DataFrame) -> DataFrame:
        """Add technical indicators to data."""
        df = df.copy()

        # RSI
        delta = df["close"].diff()
        gain = delta.where(delta > 0, 0).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / (loss + 1e-10)
        df["rsi_14"] = 100 - (100 / (1 + rs))

        # MACD
        ema12 = df["close"].ewm(span=12).mean()
        ema26 = df["close"].ewm(span=26).mean()
        macd = ema12 - ema26
        df["macd_signal"] = macd.ewm(span=9).mean()

        # ATR
        high_low = df["high"] - df["low"]
        high_close = (df["high"] - df["close"].shift()).abs()
        low_close = (df["low"] - df["close"].shift()).abs()
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        df["atr_14"] = tr.rolling(14).mean()

        # Spread (simulated)
        df["spread"] = df["atr_14"] * 0.01

        return df

    def create_labels(
        self,
        df: DataFrame,
        forward_returns_period: int = None,
    ) -> Series:
        """
        Create target labels from forward returns.

        Args:
            df: DataFrame with close prices
            forward_returns_period: Bars forward to calculate returns

        Returns:
            Series with labels (0=SKIP, 1=BUY, 2=SELL)
        """
        period = forward_returns_period or self.forward_period
        logger.info(f"Creating labels with {period}-period forward returns")

        # Calculate forward returns
        forward_returns = df["close"].shift(-period) / df["close"] - 1

        # Create labels
        labels = pd.Series(index=df.index, data=0)  # Default SKIP
        labels[forward_returns > self.buy_threshold] = 1   # BUY
        labels[forward_returns < self.sell_threshold] = 2  # SELL

        # Log distribution
        distribution = labels.value_counts()
        logger.info(f"Label distribution: SKIP={distribution.get(0, 0)}, "
                    f"BUY={distribution.get(1, 0)}, SELL={distribution.get(2, 0)}")

        return labels

    def split_data(
        self,
        df: DataFrame,
        train_ratio: float = 0.7,
        val_ratio: float = 0.15,
    ) -> Tuple[DataFrame, DataFrame, DataFrame]:
        """
        Split data into train/validation/test sets.

        Uses time-based split to prevent look-ahead bias.

        Args:
            df: Full dataset
            train_ratio: Fraction for training
            val_ratio: Fraction for validation

        Returns:
            Tuple of (train_df, val_df, test_df)
        """
        n = len(df)
        train_end = int(n * train_ratio)
        val_end = int(n * (train_ratio + val_ratio))

        train_df = df.iloc[:train_end]
        val_df = df.iloc[train_end:val_end]
        test_df = df.iloc[val_end:]

        logger.info(f"Split: train={len(train_df)}, val={len(val_df)}, test={len(test_df)}")

        return train_df, val_df, test_df

    def run_training(
        self,
        symbols: List[str] = None,
        years: int = 5,
        validation_split: float = 0.2,
    ) -> TrainedModel:
        """
        Run full training pipeline.

        Args:
            symbols: Symbols to train on (default: major pairs)
            years: Years of historical data
            validation_split: Validation set fraction

        Returns:
            TrainedModel with trained classifier and metadata
        """
        symbols = symbols or ["EURUSD", "GBPUSD", "USDJPY"]
        logger.info(f"Starting training pipeline for {symbols}")

        # Load data
        raw_data = self.load_historical_data(symbols, years)

        # Prepare features
        featured_data = self.feature_engineer.prepare_features(
            raw_data,
            include_target=False,
            fit_scaler=True,
        )

        # Create labels
        labels = self.create_labels(raw_data)

        # Align data and labels
        valid_idx = labels.notna() & ~labels.isna()
        X = featured_data.loc[valid_idx]
        y = labels.loc[valid_idx]

        # Drop rows with NaN features
        valid_features = ~X.isna().any(axis=1)
        X = X.loc[valid_features]
        y = y.loc[valid_features]

        # Train classifier
        metrics = self.classifier.train(
            X, y,
            validation_split=validation_split,
        )

        return TrainedModel(
            model=self.classifier.model,
            feature_columns=self.classifier.feature_columns,
            metrics=metrics,
            created_at=datetime.now(),
            hyperparameters=self.classifier.params,
            scaler=self.feature_engineer.scaler,
        )

    def cross_validate(
        self,
        X: DataFrame,
        y: Series,
        n_folds: int = 5,
        use_time_series_split: bool = True,
    ) -> CrossValidationResults:
        """
        Perform cross-validation.

        Args:
            X: Feature DataFrame
            y: Target Series
            n_folds: Number of folds
            use_time_series_split: Use TimeSeriesSplit for temporal data

        Returns:
            CrossValidationResults with fold metrics
        """
        logger.info(f"Running {n_folds}-fold cross-validation")

        if use_time_series_split:
            cv = TimeSeriesSplit(n_splits=n_folds)
        else:
            cv = StratifiedKFold(n_splits=n_folds, shuffle=True, random_state=42)

        fold_metrics = []

        for fold, (train_idx, val_idx) in enumerate(cv.split(X, y)):
            X_train, X_val = X.iloc[train_idx], X.iloc[val_idx]
            y_train, y_val = y.iloc[train_idx], y.iloc[val_idx]

            # Train fold model
            fold_classifier = TradingClassifier()
            metrics = fold_classifier.train(
                X_train, y_train,
                validation_split=0.0,
                verbose=False,
            )

            # Evaluate on validation set
            predictions = fold_classifier.predict(X_val)
            y_pred = [TradingClassifier.SIGNAL_MAP[p.signal] for p in predictions]

            from sklearn.metrics import accuracy_score, f1_score as sk_f1

            fold_accuracy = accuracy_score(y_val, y_pred)
            fold_f1 = sk_f1(y_val, y_pred, average="weighted", zero_division=0)

            fold_metrics.append(TrainingMetrics(
                accuracy=fold_accuracy,
                precision=metrics.precision,
                recall=metrics.recall,
                f1_score=fold_f1,
                win_rate_predicted=metrics.win_rate_predicted,
                feature_importance=metrics.feature_importance,
            ))

            logger.info(f"Fold {fold + 1}: accuracy={fold_accuracy:.4f}, f1={fold_f1:.4f}")

        # Calculate aggregate metrics
        accuracies = [m.accuracy for m in fold_metrics]
        f1_scores = [m.f1_score for m in fold_metrics]
        win_rates = [m.win_rate_predicted for m in fold_metrics]

        return CrossValidationResults(
            n_folds=n_folds,
            fold_metrics=fold_metrics,
            mean_accuracy=np.mean(accuracies),
            std_accuracy=np.std(accuracies),
            mean_f1=np.mean(f1_scores),
            std_f1=np.std(f1_scores),
            mean_win_rate=np.mean(win_rates),
        )

    def hyperparameter_tune(
        self,
        X: DataFrame,
        y: Series,
        param_grid: Dict[str, List[Any]] = None,
        n_iter: int = 20,
        method: str = "random",
        cv_folds: int = 3,
    ) -> BestParams:
        """
        Tune hyperparameters using grid or random search.

        Args:
            X: Feature DataFrame
            y: Target Series
            param_grid: Parameter grid to search
            n_iter: Number of iterations for random search
            method: Search method ('grid' or 'random')
            cv_folds: Number of CV folds

        Returns:
            BestParams with optimal hyperparameters
        """
        param_grid = param_grid or self.DEFAULT_PARAM_GRID
        logger.info(f"Starting hyperparameter tuning with {method} search")

        # Base parameters
        base_params = {
            "objective": "multi:softprob",
            "num_class": 3,
            "tree_method": "hist",
            "random_state": 42,
            "n_jobs": -1,
            "eval_metric": "mlogloss",
        }

        # Create base model
        model = xgb.XGBClassifier(**base_params)

        # Time series split for CV
        cv = TimeSeriesSplit(n_splits=cv_folds)

        if method == "random":
            search = RandomizedSearchCV(
                model,
                param_distributions=param_grid,
                n_iter=n_iter,
                scoring="f1_weighted",
                cv=cv,
                verbose=1,
                random_state=42,
                n_jobs=-1,
            )
        else:
            # Grid search
            from sklearn.model_selection import GridSearchCV
            search = GridSearchCV(
                model,
                param_grid=param_grid,
                scoring="f1_weighted",
                cv=cv,
                verbose=1,
                n_jobs=-1,
            )

        # Run search
        search.fit(X, y)

        # Collect all results
        all_results = []
        for i in range(len(search.cv_results_["params"])):
            all_results.append({
                "params": search.cv_results_["params"][i],
                "mean_score": search.cv_results_["mean_test_score"][i],
                "std_score": search.cv_results_["std_test_score"][i],
            })

        # Sort by score
        all_results.sort(key=lambda x: x["mean_score"], reverse=True)

        best_params = BestParams(
            params=search.best_params_,
            best_score=search.best_score_,
            all_results=all_results[:10],  # Top 10 results
            search_method=method,
            n_iterations=n_iter if method == "random" else len(list(ParameterGrid(param_grid))),
        )

        logger.info(f"Best params: {best_params.params}, score: {best_params.best_score:.4f}")

        return best_params

    def save_pipeline(self, path: str) -> None:
        """Save the full pipeline including model and feature engineer."""
        import pickle

        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        pipeline_data = {
            "classifier": self.classifier,
            "feature_engineer": self.feature_engineer,
            "buy_threshold": self.buy_threshold,
            "sell_threshold": self.sell_threshold,
            "forward_period": self.forward_period,
        }

        with open(path, "wb") as f:
            pickle.dump(pipeline_data, f)

        logger.info(f"Pipeline saved to {path}")

    @classmethod
    def load_pipeline(cls, path: str) -> "TrainingPipeline":
        """Load a saved pipeline."""
        import pickle

        with open(path, "rb") as f:
            pipeline_data = pickle.load(f)

        # Create new instance
        instance = cls.__new__(cls)
        instance.data_path = Path(".")
        instance.classifier = pipeline_data["classifier"]
        instance.feature_engineer = pipeline_data["feature_engineer"]
        instance.buy_threshold = pipeline_data["buy_threshold"]
        instance.sell_threshold = pipeline_data["sell_threshold"]
        instance.forward_period = pipeline_data["forward_period"]

        logger.info(f"Pipeline loaded from {path}")

        return instance
