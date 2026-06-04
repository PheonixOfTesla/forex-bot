from __future__ import annotations

"""
Settings API Routes

Provides endpoints for managing trading bot settings.
"""

import logging
import os
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Path, Query
from pydantic import BaseModel

from ..schemas import (
    AssetSetting,
    AssetToggleRequest,
    NotificationSettings,
    RiskSettings,
    SettingsResponse,
    SettingsUpdate,
    TradingSettings,
)


# =============================================================================
# OANDA Settings Models
# =============================================================================


class OandaSettingsRequest(BaseModel):
    """Request to save OANDA API credentials."""
    oanda_account_id: Optional[str] = None
    oanda_access_token: Optional[str] = None
    oanda_environment: Optional[str] = None  # "practice" or "live"


class OandaSettingsResponse(BaseModel):
    """Response for OANDA settings."""
    oanda_configured: bool
    oanda_account_id: Optional[str] = None  # Masked
    oanda_environment: str = "practice"

logger = logging.getLogger(__name__)
router = APIRouter()


# =============================================================================
# Settings Store (Replace with actual database/config)
# =============================================================================


class SettingsStore:
    """In-memory settings store for development."""

    def __init__(self):
        self.risk = RiskSettings(
            risk_per_trade_pct=2.0,
            max_leverage=10,
            min_confidence_threshold=70.0,
            max_drawdown_pct=20.0,
            max_open_positions=5,
            daily_loss_limit_pct=5.0,
        )

        self.notifications = NotificationSettings(
            telegram_enabled=True,
            telegram_chat_id="123456789",
            notify_on_signal=True,
            notify_on_trade=True,
            notify_on_close=True,
            notify_on_error=True,
        )

        self.trading = TradingSettings(
            auto_execute=False,
            trading_hours_only=True,
            market_hours_start="08:00",
            market_hours_end="20:00",
            avoid_news_events=True,
            default_position_size_pct=1.0,
        )

        self.last_updated = datetime.utcnow()

        # OANDA settings - load from env or store in memory
        self.oanda_account_id = os.environ.get("OANDA_ACCOUNT_ID")
        self.oanda_access_token = os.environ.get("OANDA_ACCESS_TOKEN")
        self.oanda_environment = os.environ.get("OANDA_ENVIRONMENT", "practice")

        # Asset settings
        self.assets = {
            "EUR/USD": AssetSetting(
                asset="EUR/USD",
                enabled=True,
                max_position_size=50000,
                custom_risk_pct=None,
                strategies=["momentum_breakout", "mean_reversion", "trend_following"],
            ),
            "GBP/USD": AssetSetting(
                asset="GBP/USD",
                enabled=True,
                max_position_size=40000,
                custom_risk_pct=None,
                strategies=["momentum_breakout", "mean_reversion"],
            ),
            "USD/JPY": AssetSetting(
                asset="USD/JPY",
                enabled=True,
                max_position_size=500000,
                custom_risk_pct=None,
                strategies=["trend_following", "momentum_breakout"],
            ),
            "AUD/USD": AssetSetting(
                asset="AUD/USD",
                enabled=True,
                max_position_size=50000,
                custom_risk_pct=1.5,
                strategies=["mean_reversion"],
            ),
            "USD/CAD": AssetSetting(
                asset="USD/CAD",
                enabled=True,
                max_position_size=50000,
                custom_risk_pct=None,
                strategies=["trend_following"],
            ),
            "EUR/GBP": AssetSetting(
                asset="EUR/GBP",
                enabled=False,
                max_position_size=40000,
                custom_risk_pct=None,
                strategies=["mean_reversion"],
            ),
            "USD/CHF": AssetSetting(
                asset="USD/CHF",
                enabled=False,
                max_position_size=50000,
                custom_risk_pct=None,
                strategies=["trend_following"],
            ),
            "NZD/USD": AssetSetting(
                asset="NZD/USD",
                enabled=False,
                max_position_size=50000,
                custom_risk_pct=None,
                strategies=["momentum_breakout"],
            ),
        }


# Global settings store
_settings_store = SettingsStore()


# =============================================================================
# Settings Endpoints
# =============================================================================


@router.get("/settings", response_model=SettingsResponse)
async def get_settings() -> SettingsResponse:
    """
    Get all current settings.

    Returns:
        Complete settings including risk, notifications, and trading settings.
    """
    logger.info("Fetching settings")

    return SettingsResponse(
        risk=_settings_store.risk,
        notifications=_settings_store.notifications,
        trading=_settings_store.trading,
        last_updated=_settings_store.last_updated,
    )


@router.put("/settings", response_model=SettingsResponse)
async def update_settings(settings: SettingsUpdate) -> SettingsResponse:
    """
    Update settings.

    Only the settings provided will be updated. Other settings remain unchanged.

    Args:
        settings: Settings to update (risk, notifications, and/or trading)

    Returns:
        Updated complete settings.
    """
    logger.info("Updating settings")

    if settings.risk:
        _settings_store.risk = settings.risk
        logger.info(f"Updated risk settings: {settings.risk}")

    if settings.notifications:
        _settings_store.notifications = settings.notifications
        logger.info(f"Updated notification settings: {settings.notifications}")

    if settings.trading:
        _settings_store.trading = settings.trading
        logger.info(f"Updated trading settings: {settings.trading}")

    _settings_store.last_updated = datetime.utcnow()

    return SettingsResponse(
        risk=_settings_store.risk,
        notifications=_settings_store.notifications,
        trading=_settings_store.trading,
        last_updated=_settings_store.last_updated,
    )


@router.get("/settings/risk", response_model=RiskSettings)
async def get_risk_settings() -> RiskSettings:
    """Get risk management settings."""
    return _settings_store.risk


@router.put("/settings/risk", response_model=RiskSettings)
async def update_risk_settings(risk: RiskSettings) -> RiskSettings:
    """Update risk management settings."""
    logger.info(f"Updating risk settings: {risk}")
    _settings_store.risk = risk
    _settings_store.last_updated = datetime.utcnow()
    return _settings_store.risk


@router.get("/settings/notifications", response_model=NotificationSettings)
async def get_notification_settings() -> NotificationSettings:
    """Get notification settings."""
    return _settings_store.notifications


@router.put("/settings/notifications", response_model=NotificationSettings)
async def update_notification_settings(
    notifications: NotificationSettings,
) -> NotificationSettings:
    """Update notification settings."""
    logger.info(f"Updating notification settings: {notifications}")
    _settings_store.notifications = notifications
    _settings_store.last_updated = datetime.utcnow()
    return _settings_store.notifications


@router.get("/settings/trading", response_model=TradingSettings)
async def get_trading_settings() -> TradingSettings:
    """Get trading behavior settings."""
    return _settings_store.trading


@router.put("/settings/trading", response_model=TradingSettings)
async def update_trading_settings(trading: TradingSettings) -> TradingSettings:
    """Update trading behavior settings."""
    logger.info(f"Updating trading settings: {trading}")
    _settings_store.trading = trading
    _settings_store.last_updated = datetime.utcnow()
    return _settings_store.trading


# =============================================================================
# Asset Settings Endpoints
# =============================================================================


@router.get("/settings/assets", response_model=List[AssetSetting])
async def get_asset_settings(
    enabled_only: bool = Query(
        default=False,
        description="Only return enabled assets",
    ),
) -> List[AssetSetting]:
    """
    Get settings for all trading assets.

    Args:
        enabled_only: If true, only return enabled assets

    Returns:
        List of asset trading settings.
    """
    logger.info(f"Fetching asset settings: enabled_only={enabled_only}")

    assets = list(_settings_store.assets.values())

    if enabled_only:
        assets = [a for a in assets if a.enabled]

    # Sort by asset name
    assets.sort(key=lambda a: a.asset)

    return assets


@router.get("/settings/assets/{asset}", response_model=AssetSetting)
async def get_asset_setting(
    asset: str = Path(..., description="Asset/pair name (e.g., EUR/USD)"),
) -> AssetSetting:
    """
    Get settings for a specific asset.

    Args:
        asset: Asset/pair name

    Returns:
        Asset trading settings.

    Raises:
        404: Asset not found
    """
    # Normalize asset name
    asset_key = asset.upper().replace("-", "/")

    setting = _settings_store.assets.get(asset_key)
    if not setting:
        raise HTTPException(
            status_code=404,
            detail=f"Asset not found: {asset}. Available: {list(_settings_store.assets.keys())}",
        )

    return setting


@router.put("/settings/assets/{asset}", response_model=AssetSetting)
async def update_asset_setting(
    asset: str = Path(..., description="Asset/pair name"),
    setting: AssetSetting = None,
) -> AssetSetting:
    """
    Update settings for a specific asset.

    Args:
        asset: Asset/pair name
        setting: New asset settings

    Returns:
        Updated asset settings.
    """
    asset_key = asset.upper().replace("-", "/")

    if asset_key not in _settings_store.assets:
        # Add new asset
        logger.info(f"Adding new asset setting: {asset_key}")

    _settings_store.assets[asset_key] = setting
    _settings_store.last_updated = datetime.utcnow()

    logger.info(f"Updated asset setting: {asset_key} = {setting}")

    return setting


@router.post("/settings/assets/{asset}/toggle", response_model=AssetSetting)
async def toggle_asset(
    asset: str = Path(..., description="Asset/pair name"),
    request: AssetToggleRequest = None,
) -> AssetSetting:
    """
    Toggle trading for an asset on or off.

    Args:
        asset: Asset/pair name
        request: Toggle request with enabled status

    Returns:
        Updated asset settings.

    Raises:
        404: Asset not found
    """
    asset_key = asset.upper().replace("-", "/")

    setting = _settings_store.assets.get(asset_key)
    if not setting:
        raise HTTPException(
            status_code=404,
            detail=f"Asset not found: {asset}",
        )

    # Toggle
    setting.enabled = request.enabled if request else not setting.enabled
    _settings_store.last_updated = datetime.utcnow()

    action = "enabled" if setting.enabled else "disabled"
    logger.info(f"Asset {asset_key} {action}")

    return setting


@router.delete("/settings/assets/{asset}")
async def delete_asset_setting(
    asset: str = Path(..., description="Asset/pair name"),
):
    """
    Remove an asset from trading settings.

    Args:
        asset: Asset/pair name

    Raises:
        404: Asset not found
    """
    asset_key = asset.upper().replace("-", "/")

    if asset_key not in _settings_store.assets:
        raise HTTPException(
            status_code=404,
            detail=f"Asset not found: {asset}",
        )

    del _settings_store.assets[asset_key]
    _settings_store.last_updated = datetime.utcnow()

    logger.info(f"Deleted asset setting: {asset_key}")

    return {"success": True, "message": f"Asset {asset_key} removed"}


# =============================================================================
# Settings Validation & Reset
# =============================================================================


@router.post("/settings/validate")
async def validate_settings():
    """
    Validate current settings configuration.

    Checks for common issues and inconsistencies.
    """
    issues = []
    warnings = []

    # Risk settings validation
    if _settings_store.risk.risk_per_trade_pct > 5.0:
        warnings.append("Risk per trade is high (>5%). Consider reducing.")

    if _settings_store.risk.max_leverage > 20:
        warnings.append("High leverage (>20x) increases risk significantly.")

    if _settings_store.risk.min_confidence_threshold < 60:
        warnings.append("Low confidence threshold may lead to more losing trades.")

    # Trading settings validation
    if _settings_store.trading.auto_execute and not _settings_store.notifications.telegram_enabled:
        warnings.append("Auto-execute is ON but notifications are OFF. Consider enabling alerts.")

    # Asset settings validation
    enabled_assets = [a for a in _settings_store.assets.values() if a.enabled]
    if len(enabled_assets) == 0:
        issues.append("No assets are enabled for trading.")
    elif len(enabled_assets) > _settings_store.risk.max_open_positions:
        warnings.append(
            f"More assets enabled ({len(enabled_assets)}) than max positions "
            f"({_settings_store.risk.max_open_positions})."
        )

    return {
        "valid": len(issues) == 0,
        "issues": issues,
        "warnings": warnings,
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.post("/settings/reset")
async def reset_settings(
    confirm: bool = Query(
        default=False,
        description="Confirm reset to defaults",
    ),
):
    """
    Reset all settings to defaults.

    Args:
        confirm: Must be True to confirm reset

    Returns:
        Reset confirmation or error.
    """
    if not confirm:
        raise HTTPException(
            status_code=400,
            detail="Add ?confirm=true to confirm settings reset",
        )

    logger.warning("Resetting all settings to defaults")

    global _settings_store
    _settings_store = SettingsStore()

    return {
        "success": True,
        "message": "All settings reset to defaults",
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.get("/settings/export")
async def export_settings():
    """
    Export all settings as JSON.

    Returns:
        Complete settings export for backup.
    """
    return {
        "version": "1.0",
        "exported_at": datetime.utcnow().isoformat(),
        "risk": _settings_store.risk.model_dump(),
        "notifications": _settings_store.notifications.model_dump(),
        "trading": _settings_store.trading.model_dump(),
        "assets": {k: v.model_dump() for k, v in _settings_store.assets.items()},
    }


# =============================================================================
# OANDA Configuration Endpoints
# =============================================================================


async def get_oanda_from_db():
    """Get OANDA credentials from MongoDB."""
    try:
        from ..database import get_db
        db = await get_db()
        if db is None:
            return None, None, "practice"

        settings = await db.settings.find_one({"_id": "oanda_credentials"})
        if settings:
            return (
                settings.get("account_id"),
                settings.get("access_token"),
                settings.get("environment", "practice"),
            )
    except Exception as e:
        logger.warning(f"Could not load OANDA from DB: {e}")

    return None, None, "practice"


async def save_oanda_to_db(account_id: str, access_token: str, environment: str):
    """Save OANDA credentials to MongoDB."""
    try:
        from ..database import get_db
        db = await get_db()
        if db is None:
            return False

        await db.settings.update_one(
            {"_id": "oanda_credentials"},
            {"$set": {
                "account_id": account_id,
                "access_token": access_token,
                "environment": environment,
                "updated_at": datetime.utcnow(),
            }},
            upsert=True,
        )
        return True
    except Exception as e:
        logger.error(f"Could not save OANDA to DB: {e}")
        return False


@router.get("/settings/oanda")
async def get_oanda_settings():
    """Get OANDA configuration status (credentials masked)."""
    # Try DB first, then fall back to memory/env
    db_account, db_token, db_env = await get_oanda_from_db()

    account_id = db_account or _settings_store.oanda_account_id
    access_token = db_token or _settings_store.oanda_access_token
    environment = db_env or _settings_store.oanda_environment

    configured = bool(account_id and access_token)

    # Mask account ID for security
    masked_id = None
    if account_id:
        masked_id = f"{account_id[:8]}...{account_id[-4:]}" if len(account_id) > 12 else account_id

    return {
        "oanda_configured": configured,
        "oanda_account_id": masked_id,
        "oanda_environment": environment,
        "persisted": bool(db_account),
    }


@router.post("/settings/oanda")
async def save_oanda_settings(request: OandaSettingsRequest):
    """
    Save OANDA API credentials to MongoDB for persistence.
    """
    account_id = request.oanda_account_id or _settings_store.oanda_account_id
    access_token = request.oanda_access_token or _settings_store.oanda_access_token
    environment = request.oanda_environment or _settings_store.oanda_environment or "practice"

    # Update in-memory store
    if request.oanda_account_id:
        _settings_store.oanda_account_id = request.oanda_account_id
    if request.oanda_access_token:
        _settings_store.oanda_access_token = request.oanda_access_token
    if request.oanda_environment:
        _settings_store.oanda_environment = request.oanda_environment

    _settings_store.last_updated = datetime.utcnow()

    # Save to MongoDB for persistence
    persisted = False
    if account_id and access_token:
        persisted = await save_oanda_to_db(account_id, access_token, environment)

    # Test connection
    oanda_status = None
    if account_id and access_token:
        try:
            from ..broker import OandaClient
            client = OandaClient(
                account_id=account_id,
                access_token=access_token,
                environment=environment,
            )
            account = await client.get_account()
            oanda_status = {
                "connected": True,
                "balance": float(account.get("balance", 0)),
                "currency": account.get("currency", "USD"),
            }
            await client.close()
        except Exception as e:
            oanda_status = {
                "connected": False,
                "error": str(e),
            }

    logger.info(f"OANDA settings saved. Persisted: {persisted}, Status: {oanda_status}")

    return {
        "success": True,
        "message": "OANDA settings saved" + (" to database" if persisted else " (in memory only)"),
        "persisted": persisted,
        "oanda_status": oanda_status,
    }


@router.post("/settings/oanda/test")
async def test_oanda_connection():
    """Test OANDA connection with current credentials."""
    # Try DB first, then memory/env
    db_account, db_token, db_env = await get_oanda_from_db()

    account_id = db_account or _settings_store.oanda_account_id
    access_token = db_token or _settings_store.oanda_access_token
    environment = db_env or _settings_store.oanda_environment

    if not account_id or not access_token:
        return {
            "success": False,
            "error": "OANDA credentials not configured",
        }

    try:
        from ..broker import OandaClient
        client = OandaClient(
            account_id=account_id,
            access_token=access_token,
            environment=environment,
        )

        account = await client.get_account()
        await client.close()

        return {
            "success": True,
            "account": {
                "id": account.get("id"),
                "balance": float(account.get("balance", 0)),
                "currency": account.get("currency", "USD"),
                "nav": float(account.get("NAV", 0)),
                "unrealized_pnl": float(account.get("unrealizedPL", 0)),
                "open_trades": int(account.get("openTradeCount", 0)),
            }
        }
    except Exception as e:
        logger.error(f"OANDA connection test failed: {e}")
        return {
            "success": False,
            "error": str(e),
        }
