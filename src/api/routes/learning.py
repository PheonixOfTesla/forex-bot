from __future__ import annotations

"""
Learning API Routes

Provides endpoints for the learning/feedback system that tracks signal accuracy
and improves predictions over time.
"""

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from ...models.learning import (
    AccuracyResponse,
    IndicatorPerformanceResponse,
    InsightsResponse,
    PredictionOutcome,
    RecordOutcomeRequest,
)
from ...services.learning_engine import get_learning_engine

logger = logging.getLogger(__name__)
router = APIRouter()


# =============================================================================
# Learning Endpoints
# =============================================================================


@router.get("/learning/strategies")
async def get_strategy_leaderboard(
    strategy: Optional[str] = Query(
        default=None,
        description="Filter recent calls to a single strategy",
    ),
    pair: Optional[str] = Query(
        default=None,
        description="Filter recent calls to a single pair (e.g., EUR/USD)",
    ),
    min_trades: int = Query(
        default=1,
        ge=1,
        description="Minimum trades for a strategy to appear in the leaderboard",
    ),
    recent_limit: int = Query(
        default=20,
        ge=1,
        le=100,
        description="Number of recent calls to return",
    ),
):
    """
    Strategy leaderboard: follow and track calls against the most
    successful strategies.

    Returns every strategy ranked by measured win rate, plus the most
    recent tracked calls (optionally filtered by strategy or pair) so
    each new call can be compared against the strategy's record.
    """
    engine = get_learning_engine()

    leaderboard = engine.get_strategy_performance(min_trades=min_trades)
    recent_calls = engine.get_recent_calls(
        strategy=strategy, pair=pair, limit=recent_limit
    )

    return {
        "leaderboard": leaderboard,
        "top_strategy": leaderboard[0] if leaderboard else None,
        "recent_calls": recent_calls,
        "total_tracked_calls": engine.get_metrics().total_predictions,
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.get("/learning/accuracy", response_model=AccuracyResponse)
async def get_accuracy_stats(
    pair: Optional[str] = Query(
        default=None,
        description="Filter by trading pair",
    ),
    timeframe: Optional[str] = Query(
        default=None,
        description="Filter by timeframe (e.g., 1H, 4H, D)",
    ),
):
    """
    Get overall and per-pair accuracy statistics.

    Returns prediction accuracy breakdown by pair, timeframe, and direction.
    This data is built from recorded trade outcomes over time.

    Args:
        pair: Optional filter by trading pair
        timeframe: Optional filter by timeframe

    Returns:
        AccuracyResponse with accuracy statistics
    """
    logger.info(f"Fetching accuracy stats: pair={pair}, timeframe={timeframe}")

    engine = get_learning_engine()
    accuracy = engine.get_accuracy_stats()

    # Apply filters if specified
    if pair:
        normalized_pair = pair.upper().replace("-", "/")
        if normalized_pair in accuracy.by_pair:
            accuracy.by_pair = {normalized_pair: accuracy.by_pair[normalized_pair]}
        else:
            accuracy.by_pair = {}

    if timeframe:
        normalized_tf = timeframe.upper()
        if normalized_tf in accuracy.by_timeframe:
            accuracy.by_timeframe = {normalized_tf: accuracy.by_timeframe[normalized_tf]}
        else:
            accuracy.by_timeframe = {}

    return accuracy


@router.get("/learning/indicators", response_model=IndicatorPerformanceResponse)
async def get_indicator_performance(
    indicator: Optional[str] = Query(
        default=None,
        description="Filter by indicator name",
    ),
    min_signals: int = Query(
        default=3,
        ge=1,
        le=100,
        description="Minimum number of signals to include an indicator",
    ),
):
    """
    Get indicator performance statistics.

    Returns which indicators are performing best based on historical
    win rates and profit metrics. Also includes indicator combination
    analysis to identify synergies.

    Args:
        indicator: Optional filter by indicator name
        min_signals: Minimum signals required for inclusion

    Returns:
        IndicatorPerformanceResponse with indicator metrics
    """
    logger.info(f"Fetching indicator performance: indicator={indicator}")

    engine = get_learning_engine()
    performance = engine.get_indicator_performance()

    # Filter by minimum signals
    performance.indicators = [
        i for i in performance.indicators
        if i.total_signals >= min_signals
    ]

    # Filter by specific indicator if specified
    if indicator:
        normalized_indicator = indicator.lower()
        performance.indicators = [
            i for i in performance.indicators
            if normalized_indicator in i.indicator_name.lower()
        ]

    return performance


@router.get("/learning/insights", response_model=InsightsResponse)
async def get_learning_insights(
    category: Optional[str] = Query(
        default=None,
        description="Filter by category (performance/indicator/pair/strategy/risk)",
    ),
    priority: Optional[str] = Query(
        default=None,
        description="Filter by priority (high/medium/low)",
    ),
    limit: int = Query(
        default=10,
        ge=1,
        le=50,
        description="Maximum number of insights to return",
    ),
):
    """
    Get AI-generated insights about trading performance.

    Analyzes the learning data to produce actionable insights about:
    - Overall performance trends
    - Best/worst performing pairs
    - High-performance indicator combinations
    - Timeframe effectiveness
    - Recent performance trends

    Args:
        category: Filter by insight category
        priority: Filter by priority level
        limit: Maximum insights to return

    Returns:
        InsightsResponse with generated insights
    """
    logger.info(f"Generating insights: category={category}, priority={priority}")

    engine = get_learning_engine()
    insights = engine.generate_insights(limit=limit * 2)  # Get extra for filtering

    # Filter by category
    if category:
        insights.insights = [
            i for i in insights.insights
            if i.category.lower() == category.lower()
        ]

    # Filter by priority
    if priority:
        insights.insights = [
            i for i in insights.insights
            if i.priority.lower() == priority.lower()
        ]

    # Apply limit after filtering
    insights.insights = insights.insights[:limit]
    insights.total_insights = len(insights.insights)

    return insights


@router.post("/learning/record", response_model=PredictionOutcome)
async def record_trade_outcome(request: RecordOutcomeRequest):
    """
    Record a trade outcome when a paper trade closes.

    This is the key entry point for the learning system. Every time a paper
    trade completes, call this endpoint to record whether the prediction
    was correct. Over time, this builds a dataset of what works.

    Args:
        request: RecordOutcomeRequest with trade details

    Returns:
        The recorded PredictionOutcome

    Example:
        ```json
        {
            "signal_id": "sig_001",
            "pair": "EUR/USD",
            "direction": "buy",
            "confidence": 85.0,
            "entry_price": 1.0845,
            "exit_price": 1.0890,
            "entry_timestamp": "2024-01-15T10:30:00Z",
            "exit_timestamp": "2024-01-15T14:30:00Z",
            "indicators_used": ["rsi", "macd", "ema_crossover"],
            "indicator_values": {"rsi": 32.5, "macd": 0.0025},
            "strategy": "momentum_breakout",
            "timeframe": "1H",
            "market_conditions": "trending",
            "session": "london"
        }
        ```
    """
    logger.info(
        f"Recording trade outcome: signal={request.signal_id} "
        f"pair={request.pair} direction={request.direction}"
    )

    engine = get_learning_engine()

    try:
        outcome = engine.record_outcome(request)

        logger.info(
            f"Recorded outcome: {outcome.signal_id} -> {outcome.outcome.value} "
            f"({outcome.profit_pips:+.1f} pips)"
        )

        return outcome

    except Exception as e:
        logger.error(f"Failed to record outcome: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to record outcome: {str(e)}"
        )


@router.get("/learning/confidence-adjustment")
async def get_confidence_adjustment(
    pair: str = Query(..., description="Trading pair"),
    indicators: str = Query(
        ...,
        description="Comma-separated list of indicators used",
    ),
    timeframe: str = Query(
        default="1H",
        description="Analysis timeframe",
    ),
    original_confidence: float = Query(
        default=75.0,
        ge=0,
        le=100,
        description="Original confidence score to adjust",
    ),
):
    """
    Get confidence adjustment based on historical performance.

    This endpoint provides feedback to the signal generator. Pass in
    the pair, indicators, and timeframe, and receive an adjustment
    factor based on how well similar setups have performed historically.

    Args:
        pair: Trading pair
        indicators: Comma-separated indicator names
        timeframe: Analysis timeframe
        original_confidence: Original confidence to adjust

    Returns:
        Adjusted confidence and explanation
    """
    logger.info(
        f"Calculating confidence adjustment: pair={pair} "
        f"indicators={indicators} timeframe={timeframe}"
    )

    engine = get_learning_engine()

    # Parse indicators
    indicator_list = [i.strip() for i in indicators.split(",") if i.strip()]

    if not indicator_list:
        raise HTTPException(
            status_code=400,
            detail="At least one indicator must be specified"
        )

    # Get adjustment
    adjusted_confidence, explanation = engine.adjust_signal_confidence(
        original_confidence=original_confidence,
        pair=pair.upper().replace("-", "/"),
        indicators_used=indicator_list,
        timeframe=timeframe.upper(),
    )

    # Calculate the adjustment factor
    adjustment_factor = adjusted_confidence / original_confidence if original_confidence > 0 else 1.0

    return {
        "original_confidence": original_confidence,
        "adjusted_confidence": adjusted_confidence,
        "adjustment_factor": round(adjustment_factor, 3),
        "explanation": explanation,
        "pair": pair.upper().replace("-", "/"),
        "indicators": indicator_list,
        "timeframe": timeframe.upper(),
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.get("/learning/metrics")
async def get_learning_metrics():
    """
    Get comprehensive learning metrics.

    Returns the full learning metrics including all accuracy breakdowns,
    indicator weights, and setup performance data.
    """
    logger.info("Fetching comprehensive learning metrics")

    engine = get_learning_engine()
    metrics = engine.get_metrics()

    return {
        "total_predictions": metrics.total_predictions,
        "total_wins": metrics.total_wins,
        "total_losses": metrics.total_losses,
        "total_breakeven": metrics.total_breakeven,
        "overall_win_rate": metrics.overall_win_rate,
        "overall_profit_pips": round(metrics.overall_profit_pips, 1),
        "learning_started_at": metrics.learning_started_at.isoformat() if metrics.learning_started_at else None,
        "last_updated": metrics.last_updated.isoformat(),
        "pairs_tracked": len(metrics.accuracy_by_pair),
        "timeframes_tracked": len(metrics.accuracy_by_timeframe),
        "indicators_tracked": len(metrics.accuracy_by_indicator),
        "suggested_adjustments": metrics.suggested_confidence_adjustments,
    }


@router.get("/learning/best-setups")
async def get_best_setups(
    limit: int = Query(
        default=5,
        ge=1,
        le=20,
        description="Maximum number of setups to return",
    ),
    min_trades: int = Query(
        default=3,
        ge=1,
        le=50,
        description="Minimum trades required for a setup to be included",
    ),
):
    """
    Get the best performing trading setups.

    Returns indicator combinations and pair/timeframe combos that
    have historically performed well. Use this to identify your
    most reliable trading patterns.
    """
    logger.info(f"Fetching best setups: limit={limit}, min_trades={min_trades}")

    engine = get_learning_engine()
    performance = engine.get_indicator_performance()

    # Filter combinations by minimum trades
    best_combos = [
        c for c in performance.best_combinations
        if c.total_trades >= min_trades
    ]

    # Add pair performance
    accuracy = engine.get_accuracy_stats()
    best_pairs = sorted(
        [
            {"pair": k, **v}
            for k, v in accuracy.by_pair.items()
            if v.get("total", 0) >= min_trades
        ],
        key=lambda x: x.get("accuracy", 0),
        reverse=True,
    )

    return {
        "best_indicator_combinations": [
            {
                "indicators": c.indicators,
                "win_rate": c.win_rate,
                "total_trades": c.total_trades,
                "avg_profit_pips": c.avg_profit_pips,
                "best_pairs": c.best_pairs,
            }
            for c in best_combos[:limit]
        ],
        "best_pairs": best_pairs[:limit],
        "recommended_focus": (
            f"Focus on {best_combos[0].indicators if best_combos else 'building more data'} "
            f"setups on {best_pairs[0]['pair'] if best_pairs else 'any pair'}"
        ) if best_combos or best_pairs else "Need more data to provide recommendations",
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.delete("/learning/history")
async def clear_learning_history(
    confirm: bool = Query(
        ...,
        description="Must be true to confirm deletion",
    ),
):
    """
    Clear all learning history.

    WARNING: This deletes all recorded outcomes and learned patterns.
    Use with extreme caution. This action cannot be undone.

    Args:
        confirm: Must be true to confirm deletion
    """
    if not confirm:
        raise HTTPException(
            status_code=400,
            detail="Must set confirm=true to clear history"
        )

    logger.warning("Clearing all learning history")

    engine = get_learning_engine()
    engine.clear_history()

    return {
        "success": True,
        "message": "Learning history cleared",
        "timestamp": datetime.utcnow().isoformat(),
    }
