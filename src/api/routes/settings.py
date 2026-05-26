"""
Settings API Routes

Provides endpoints for managing trading bot settings.
"""

import logging
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Path, Query

from ..schemas import (
    AssetSetting,
    AssetToggleRequest,
    NotificationSettings,
    RiskSettings,
    SettingsResponse,
    SettingsUpdate,
    TradingSettings,
)

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
