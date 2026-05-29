from __future__ import annotations

"""
Intelligence API Routes

Provides market intelligence data including sentiment, technical indicators,
AI insights, and pattern detection.
"""

import logging
import random
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Query

logger = logging.getLogger(__name__)
router = APIRouter()


# =============================================================================
# Mock Data Generation
# =============================================================================

_PAIRS = ["EUR/USD", "GBP/USD", "USD/JPY", "BTC/USD", "ETH/USD", "AUD/USD", "USD/CAD"]

# News headlines with sentiment
_NEWS_ITEMS = [
    {
        "headline": "Fed signals potential rate pause amid cooling inflation",
        "source": "Reuters",
        "sentiment": "bullish",
        "impact": "high",
        "pairs_affected": ["EUR/USD", "GBP/USD", "USD/JPY"],
    },
    {
        "headline": "ECB maintains hawkish stance on inflation concerns",
        "source": "Bloomberg",
        "sentiment": "bearish",
        "impact": "high",
        "pairs_affected": ["EUR/USD"],
    },
    {
        "headline": "Bitcoin ETF sees record inflows as institutional adoption grows",
        "source": "CoinDesk",
        "sentiment": "bullish",
        "impact": "high",
        "pairs_affected": ["BTC/USD", "ETH/USD"],
    },
    {
        "headline": "UK retail sales beat expectations, pound rallies",
        "source": "FT",
        "sentiment": "bullish",
        "impact": "medium",
        "pairs_affected": ["GBP/USD"],
    },
    {
        "headline": "China economic data disappoints, risk-off sentiment prevails",
        "source": "CNBC",
        "sentiment": "bearish",
        "impact": "medium",
        "pairs_affected": ["AUD/USD", "USD/JPY"],
    },
    {
        "headline": "Oil prices surge on supply concerns, CAD strengthens",
        "source": "Reuters",
        "sentiment": "bullish",
        "impact": "medium",
        "pairs_affected": ["USD/CAD"],
    },
    {
        "headline": "US jobs report stronger than expected",
        "source": "Bloomberg",
        "sentiment": "bullish",
        "impact": "high",
        "pairs_affected": ["EUR/USD", "GBP/USD", "USD/JPY"],
    },
    {
        "headline": "Ethereum network upgrade successfully completed",
        "source": "Decrypt",
        "sentiment": "bullish",
        "impact": "medium",
        "pairs_affected": ["ETH/USD"],
    },
    {
        "headline": "RBA holds rates, dovish forward guidance",
        "source": "AFR",
        "sentiment": "bearish",
        "impact": "high",
        "pairs_affected": ["AUD/USD"],
    },
    {
        "headline": "Geopolitical tensions ease, safe-haven demand drops",
        "source": "Reuters",
        "sentiment": "bearish",
        "impact": "medium",
        "pairs_affected": ["USD/JPY", "BTC/USD"],
    },
]

# Chart patterns
_PATTERNS = [
    {"name": "Head and Shoulders", "type": "reversal", "reliability": 75},
    {"name": "Double Top", "type": "reversal", "reliability": 72},
    {"name": "Double Bottom", "type": "reversal", "reliability": 71},
    {"name": "Rising Wedge", "type": "reversal", "reliability": 68},
    {"name": "Falling Wedge", "type": "continuation", "reliability": 67},
    {"name": "Bull Flag", "type": "continuation", "reliability": 70},
    {"name": "Bear Flag", "type": "continuation", "reliability": 69},
    {"name": "Ascending Triangle", "type": "continuation", "reliability": 73},
    {"name": "Descending Triangle", "type": "continuation", "reliability": 72},
    {"name": "Cup and Handle", "type": "continuation", "reliability": 74},
    {"name": "Inverse Head and Shoulders", "type": "reversal", "reliability": 74},
    {"name": "Triple Top", "type": "reversal", "reliability": 76},
]

# AI Insights templates
_INSIGHT_TEMPLATES = [
    {
        "title": "Momentum Shift Detected",
        "template": "Our models detect a significant momentum shift in {pair}. The {timeframe} timeframe shows {direction} pressure building with {confidence}% probability of continuation.",
        "category": "momentum",
    },
    {
        "title": "Correlation Breakdown Alert",
        "template": "Historical correlation between {pair1} and {pair2} has broken down. This divergence often precedes significant moves. Consider position adjustments.",
        "category": "correlation",
    },
    {
        "title": "Volatility Expansion Imminent",
        "template": "Bollinger Band compression on {pair} suggests volatility expansion is likely within the next {hours} hours. ATR is at {atr_percentile}th percentile.",
        "category": "volatility",
    },
    {
        "title": "Smart Money Flow Analysis",
        "template": "Institutional order flow analysis shows {direction} accumulation in {pair}. Large orders detected at {price_level} level with {volume} volume spike.",
        "category": "flow",
    },
    {
        "title": "Technical Confluence Zone",
        "template": "{pair} approaching key confluence zone at {price}. Multiple technical factors align: {factors}. High probability reaction expected.",
        "category": "technical",
    },
]


def _generate_sentiment() -> dict:
    """Generate market sentiment data."""
    # Fear & Greed calculation (0-100, higher = more greed)
    base_value = 55  # Slightly greedy baseline
    variance = random.uniform(-20, 25)
    fear_greed = max(0, min(100, base_value + variance))

    if fear_greed < 20:
        sentiment_label = "Extreme Fear"
    elif fear_greed < 40:
        sentiment_label = "Fear"
    elif fear_greed < 60:
        sentiment_label = "Neutral"
    elif fear_greed < 80:
        sentiment_label = "Greed"
    else:
        sentiment_label = "Extreme Greed"

    # Generate pair-specific sentiment
    pair_sentiments = {}
    for pair in _PAIRS:
        bullish = random.uniform(30, 70)
        bearish = 100 - bullish - random.uniform(5, 15)
        neutral = 100 - bullish - bearish

        pair_sentiments[pair] = {
            "bullish": round(bullish, 1),
            "bearish": round(max(0, bearish), 1),
            "neutral": round(max(0, neutral), 1),
            "overall": "bullish" if bullish > 55 else "bearish" if bearish > 55 else "neutral",
        }

    # Social sentiment
    social_sentiment = {
        "twitter_mentions_24h": random.randint(15000, 45000),
        "sentiment_score": round(random.uniform(-0.5, 0.7), 2),  # -1 to 1
        "trending_topics": random.sample(
            ["Fed", "inflation", "crypto", "earnings", "rates", "oil", "gold", "recession"],
            k=4
        ),
    }

    return {
        "fear_greed_index": round(fear_greed, 1),
        "fear_greed_label": sentiment_label,
        "fear_greed_previous": round(fear_greed + random.uniform(-5, 5), 1),
        "market_mood": sentiment_label.lower().replace(" ", "_"),
        "pair_sentiments": pair_sentiments,
        "social_sentiment": social_sentiment,
        "updated_at": datetime.utcnow().isoformat(),
    }


def _generate_indicators(pair: str) -> dict:
    """Generate technical indicators for a pair."""
    # RSI
    rsi = random.uniform(25, 75)
    rsi_signal = "oversold" if rsi < 30 else "overbought" if rsi > 70 else "neutral"

    # MACD
    macd_value = random.uniform(-0.005, 0.005)
    macd_signal = random.uniform(-0.004, 0.004)
    macd_histogram = macd_value - macd_signal
    macd_trend = "bullish" if macd_histogram > 0 else "bearish"

    # Moving Averages
    ma_20 = random.uniform(0.98, 1.02)  # As ratio to current price
    ma_50 = random.uniform(0.96, 1.04)
    ma_200 = random.uniform(0.94, 1.06)

    # Price relative to MAs
    price_vs_ma20 = "above" if random.random() > 0.4 else "below"
    price_vs_ma50 = "above" if random.random() > 0.45 else "below"
    price_vs_ma200 = "above" if random.random() > 0.5 else "below"

    # Bollinger Bands
    bb_position = random.uniform(0, 1)  # 0 = lower band, 1 = upper band
    bb_width = random.uniform(0.02, 0.08)

    # ADX (trend strength)
    adx = random.uniform(15, 50)
    trend_strength = "strong" if adx > 25 else "weak"

    # Stochastic
    stoch_k = random.uniform(10, 90)
    stoch_d = stoch_k + random.uniform(-5, 5)

    return {
        "pair": pair,
        "rsi": {
            "value": round(rsi, 1),
            "signal": rsi_signal,
            "timeframe": "4H",
        },
        "macd": {
            "value": round(macd_value, 5),
            "signal_line": round(macd_signal, 5),
            "histogram": round(macd_histogram, 5),
            "trend": macd_trend,
        },
        "moving_averages": {
            "ma_20": {"period": 20, "position": price_vs_ma20},
            "ma_50": {"period": 50, "position": price_vs_ma50},
            "ma_200": {"period": 200, "position": price_vs_ma200},
            "trend": "bullish" if price_vs_ma20 == "above" and price_vs_ma50 == "above" else "bearish",
        },
        "bollinger_bands": {
            "position": round(bb_position, 2),
            "width": round(bb_width, 4),
            "squeeze": bb_width < 0.03,
        },
        "adx": {
            "value": round(adx, 1),
            "trend_strength": trend_strength,
        },
        "stochastic": {
            "k": round(stoch_k, 1),
            "d": round(stoch_d, 1),
            "signal": "oversold" if stoch_k < 20 else "overbought" if stoch_k > 80 else "neutral",
        },
        "overall_bias": "bullish" if rsi > 50 and macd_histogram > 0 else "bearish" if rsi < 50 and macd_histogram < 0 else "neutral",
        "updated_at": datetime.utcnow().isoformat(),
    }


def _generate_insights() -> List[dict]:
    """Generate AI insights."""
    insights = []
    num_insights = random.randint(3, 5)

    for _ in range(num_insights):
        template = random.choice(_INSIGHT_TEMPLATES)
        pair = random.choice(_PAIRS)

        # Fill in template
        insight_text = template["template"].format(
            pair=pair,
            pair1=pair,
            pair2=random.choice([p for p in _PAIRS if p != pair]),
            timeframe=random.choice(["1H", "4H", "daily"]),
            direction=random.choice(["bullish", "bearish"]),
            confidence=random.randint(65, 88),
            hours=random.choice([4, 8, 12, 24]),
            atr_percentile=random.randint(5, 25),
            price_level=f"key {random.choice(['support', 'resistance'])}",
            volume=random.choice(["2x", "3x", "significant"]),
            price=f"{random.uniform(1.0, 1.5):.4f}" if "USD" in pair else f"{random.randint(140, 160)}",
            factors=", ".join(random.sample(["MA confluence", "Fibonacci level", "previous S/R", "round number"], 2)),
        )

        insights.append({
            "id": f"insight_{random.randint(1000, 9999)}",
            "title": template["title"],
            "content": insight_text,
            "category": template["category"],
            "pairs_affected": [pair],
            "priority": random.choice(["high", "medium", "low"]),
            "generated_at": (datetime.utcnow() - timedelta(minutes=random.randint(5, 120))).isoformat(),
            "expires_at": (datetime.utcnow() + timedelta(hours=random.randint(2, 12))).isoformat(),
        })

    # Sort by priority
    priority_order = {"high": 0, "medium": 1, "low": 2}
    insights.sort(key=lambda x: priority_order.get(x["priority"], 1))

    return insights


def _generate_patterns() -> List[dict]:
    """Generate detected chart patterns."""
    patterns = []
    num_patterns = random.randint(3, 6)

    used_pairs = set()
    for _ in range(num_patterns):
        # Try to get unique pairs
        available_pairs = [p for p in _PAIRS if p not in used_pairs]
        if not available_pairs:
            available_pairs = _PAIRS
        pair = random.choice(available_pairs)
        used_pairs.add(pair)

        pattern = random.choice(_PATTERNS)

        # Calculate target based on pattern type
        if pattern["type"] == "reversal":
            direction = random.choice(["bullish", "bearish"])
        else:
            direction = "bullish" if random.random() > 0.5 else "bearish"

        completion = random.uniform(65, 95)

        patterns.append({
            "id": f"pattern_{random.randint(1000, 9999)}",
            "pair": pair,
            "pattern_name": pattern["name"],
            "pattern_type": pattern["type"],
            "direction": direction,
            "timeframe": random.choice(["1H", "4H", "daily"]),
            "completion_percentage": round(completion, 1),
            "reliability_score": pattern["reliability"] + random.randint(-5, 5),
            "detected_at": (datetime.utcnow() - timedelta(hours=random.randint(1, 24))).isoformat(),
            "expected_completion": (datetime.utcnow() + timedelta(hours=random.randint(4, 48))).isoformat(),
            "notes": f"Pattern is {round(completion)}% complete. {'Confirmation pending.' if completion < 80 else 'High confidence setup.'}",
        })

    # Sort by completion percentage descending
    patterns.sort(key=lambda x: x["completion_percentage"], reverse=True)

    return patterns


def _generate_correlation_matrix() -> dict:
    """Generate correlation matrix for pairs."""
    # Generate realistic correlations
    correlations = {}

    for i, pair1 in enumerate(_PAIRS):
        correlations[pair1] = {}
        for j, pair2 in enumerate(_PAIRS):
            if pair1 == pair2:
                correlations[pair1][pair2] = 1.0
            elif pair2 in correlations and pair1 in correlations[pair2]:
                correlations[pair1][pair2] = correlations[pair2][pair1]
            else:
                # Generate realistic correlations
                if ("USD" in pair1 and "USD" in pair2) or ("BTC" in pair1 and "ETH" in pair2):
                    base_corr = random.uniform(0.5, 0.85)
                elif "EUR" in pair1 and "GBP" in pair2:
                    base_corr = random.uniform(0.6, 0.8)
                else:
                    base_corr = random.uniform(-0.3, 0.5)

                # Add some noise
                corr = base_corr + random.uniform(-0.1, 0.1)
                correlations[pair1][pair2] = round(max(-1, min(1, corr)), 2)

    return correlations


# =============================================================================
# Intelligence Endpoints
# =============================================================================


@router.get("/intelligence/sentiment")
async def get_market_sentiment(
    pair: Optional[str] = Query(
        default=None,
        description="Filter sentiment for specific pair",
    ),
):
    """
    Get market sentiment analysis.

    Returns Fear/Greed index, pair-specific sentiment, and social metrics.
    """
    logger.info(f"Fetching market sentiment: pair={pair}")

    sentiment = _generate_sentiment()

    if pair:
        normalized_pair = pair.upper().replace("-", "/")
        if normalized_pair in sentiment["pair_sentiments"]:
            sentiment["pair_sentiments"] = {
                normalized_pair: sentiment["pair_sentiments"][normalized_pair]
            }

    return sentiment


@router.get("/intelligence/indicators")
async def get_technical_indicators(
    pair: Optional[str] = Query(
        default=None,
        description="Filter by trading pair (returns all if not specified)",
    ),
):
    """
    Get technical indicators summary.

    Returns RSI, MACD, Moving Averages, Bollinger Bands, ADX, and Stochastic
    for one or all pairs.
    """
    logger.info(f"Fetching technical indicators: pair={pair}")

    if pair:
        normalized_pair = pair.upper().replace("-", "/")
        return _generate_indicators(normalized_pair)

    # Return all pairs
    indicators = []
    for p in _PAIRS:
        indicators.append(_generate_indicators(p))

    return {
        "indicators": indicators,
        "updated_at": datetime.utcnow().isoformat(),
    }


@router.get("/intelligence/insights")
async def get_ai_insights(
    category: Optional[str] = Query(
        default=None,
        description="Filter by category (momentum, correlation, volatility, flow, technical)",
    ),
    limit: int = Query(
        default=10,
        ge=1,
        le=50,
        description="Maximum number of insights to return",
    ),
):
    """
    Get AI-generated market insights.

    Returns natural language analysis of market conditions and opportunities.
    """
    logger.info(f"Fetching AI insights: category={category}")

    insights = _generate_insights()

    if category:
        insights = [i for i in insights if i["category"] == category.lower()]

    return {
        "insights": insights[:limit],
        "total": len(insights),
        "generated_at": datetime.utcnow().isoformat(),
    }


@router.get("/intelligence/patterns")
async def get_detected_patterns(
    pair: Optional[str] = Query(
        default=None,
        description="Filter by trading pair",
    ),
    pattern_type: Optional[str] = Query(
        default=None,
        description="Filter by pattern type (reversal, continuation)",
    ),
):
    """
    Get detected chart patterns.

    Returns active patterns with completion status and reliability scores.
    """
    logger.info(f"Fetching patterns: pair={pair}, type={pattern_type}")

    patterns = _generate_patterns()

    if pair:
        normalized_pair = pair.upper().replace("-", "/")
        patterns = [p for p in patterns if p["pair"] == normalized_pair]

    if pattern_type:
        patterns = [p for p in patterns if p["pattern_type"] == pattern_type.lower()]

    return {
        "patterns": patterns,
        "total": len(patterns),
        "updated_at": datetime.utcnow().isoformat(),
    }


@router.get("/intelligence/correlations")
async def get_correlations():
    """
    Get correlation matrix for trading pairs.

    Returns pairwise correlations useful for portfolio analysis.
    """
    logger.info("Fetching correlation matrix")

    return {
        "pairs": _PAIRS,
        "matrix": _generate_correlation_matrix(),
        "period_days": 30,
        "updated_at": datetime.utcnow().isoformat(),
    }
