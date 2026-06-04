"""
OANDA Broker Client

Lightweight async client for OANDA REST API using httpx.
"""
import os
from typing import Optional, Dict, Any, List
import httpx

# OANDA API endpoints
OANDA_PRACTICE_URL = "https://api-fxpractice.oanda.com"
OANDA_LIVE_URL = "https://api-fxtrade.oanda.com"


class OandaError(Exception):
    """OANDA API error."""
    def __init__(self, message: str, status_code: int = 0, response: Optional[Dict] = None):
        super().__init__(message)
        self.status_code = status_code
        self.response = response


class OandaClient:
    """
    Async OANDA REST API client.

    Environment variables:
    - OANDA_ACCOUNT_ID: Your OANDA account ID
    - OANDA_ACCESS_TOKEN: Your OANDA API token
    - OANDA_ENVIRONMENT: "practice" or "live"
    """

    def __init__(
        self,
        account_id: Optional[str] = None,
        access_token: Optional[str] = None,
        environment: Optional[str] = None,
    ):
        self.account_id = account_id or os.environ.get("OANDA_ACCOUNT_ID")
        self.access_token = access_token or os.environ.get("OANDA_ACCESS_TOKEN")
        self.environment = environment or os.environ.get("OANDA_ENVIRONMENT", "practice")

        if self.environment == "live":
            self.base_url = OANDA_LIVE_URL
        else:
            self.base_url = OANDA_PRACTICE_URL

        self._client: Optional[httpx.AsyncClient] = None

    def is_configured(self) -> bool:
        """Check if OANDA credentials are configured."""
        return bool(self.account_id and self.access_token)

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create httpx client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers={
                    "Authorization": f"Bearer {self.access_token}",
                    "Content-Type": "application/json",
                },
                timeout=30.0,
            )
        return self._client

    async def close(self):
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    def _normalize_pair(self, pair: str) -> str:
        """Convert pair format to OANDA format (EUR/USD -> EUR_USD)."""
        return pair.replace("/", "_").upper()

    async def _request(
        self,
        method: str,
        path: str,
        json: Optional[Dict] = None,
        params: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """Make an API request."""
        client = await self._get_client()

        try:
            response = await client.request(method, path, json=json, params=params)
            data = response.json() if response.content else {}

            if response.status_code >= 400:
                error_msg = data.get("errorMessage", str(data))
                raise OandaError(error_msg, response.status_code, data)

            return data
        except httpx.RequestError as e:
            raise OandaError(f"Request failed: {str(e)}")

    # =========================================================================
    # Account Endpoints
    # =========================================================================

    async def get_account(self) -> Dict[str, Any]:
        """
        Get account summary.

        Returns:
            Account details including balance, NAV, margin, etc.
        """
        path = f"/v3/accounts/{self.account_id}/summary"
        data = await self._request("GET", path)
        return data.get("account", {})

    async def get_account_balance(self) -> float:
        """Get current account balance."""
        account = await self.get_account()
        return float(account.get("balance", 0))

    async def get_account_nav(self) -> float:
        """Get current NAV (equity)."""
        account = await self.get_account()
        return float(account.get("NAV", 0))

    # =========================================================================
    # Position Endpoints
    # =========================================================================

    async def get_positions(self) -> List[Dict[str, Any]]:
        """
        Get all open positions.

        Returns:
            List of open positions with unrealized P&L.
        """
        path = f"/v3/accounts/{self.account_id}/openPositions"
        data = await self._request("GET", path)
        return data.get("positions", [])

    async def get_position(self, instrument: str) -> Optional[Dict[str, Any]]:
        """Get position for a specific instrument."""
        instrument = self._normalize_pair(instrument)
        path = f"/v3/accounts/{self.account_id}/positions/{instrument}"
        try:
            data = await self._request("GET", path)
            return data.get("position")
        except OandaError as e:
            if e.status_code == 404:
                return None
            raise

    async def close_position(
        self,
        instrument: str,
        long_units: Optional[str] = None,
        short_units: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Close a position.

        Args:
            instrument: Currency pair (e.g., "EUR_USD")
            long_units: Units to close ("ALL" or specific amount)
            short_units: Units to close ("ALL" or specific amount)

        Returns:
            Close position response with transaction details.
        """
        instrument = self._normalize_pair(instrument)
        path = f"/v3/accounts/{self.account_id}/positions/{instrument}/close"

        body = {}
        if long_units:
            body["longUnits"] = long_units
        if short_units:
            body["shortUnits"] = short_units

        return await self._request("PUT", path, json=body)

    # =========================================================================
    # Trade Endpoints
    # =========================================================================

    async def get_trades(self, state: str = "OPEN") -> List[Dict[str, Any]]:
        """
        Get trades.

        Args:
            state: "OPEN", "CLOSED", "ALL"

        Returns:
            List of trades.
        """
        path = f"/v3/accounts/{self.account_id}/trades"
        data = await self._request("GET", path, params={"state": state})
        return data.get("trades", [])

    async def get_trade(self, trade_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific trade."""
        path = f"/v3/accounts/{self.account_id}/trades/{trade_id}"
        try:
            data = await self._request("GET", path)
            return data.get("trade")
        except OandaError as e:
            if e.status_code == 404:
                return None
            raise

    async def close_trade(
        self,
        trade_id: str,
        units: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Close a specific trade.

        Args:
            trade_id: OANDA trade ID
            units: Units to close ("ALL" or specific amount), defaults to ALL

        Returns:
            Close trade response.
        """
        path = f"/v3/accounts/{self.account_id}/trades/{trade_id}/close"
        body = {"units": units or "ALL"}
        return await self._request("PUT", path, json=body)

    # =========================================================================
    # Order Endpoints
    # =========================================================================

    async def place_market_order(
        self,
        instrument: str,
        units: int,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Place a market order.

        Args:
            instrument: Currency pair (e.g., "EUR/USD" or "EUR_USD")
            units: Number of units (positive=buy/long, negative=sell/short)
            stop_loss: Optional stop loss price
            take_profit: Optional take profit price

        Returns:
            Order response with fill details.
        """
        instrument = self._normalize_pair(instrument)
        path = f"/v3/accounts/{self.account_id}/orders"

        order = {
            "type": "MARKET",
            "instrument": instrument,
            "units": str(units),
            "timeInForce": "FOK",  # Fill or Kill
            "positionFill": "DEFAULT",
        }

        if stop_loss:
            order["stopLossOnFill"] = {"price": f"{stop_loss:.5f}"}

        if take_profit:
            order["takeProfitOnFill"] = {"price": f"{take_profit:.5f}"}

        return await self._request("POST", path, json={"order": order})

    # =========================================================================
    # Pricing Endpoints
    # =========================================================================

    async def get_prices(self, instruments: List[str]) -> Dict[str, Dict[str, float]]:
        """
        Get current prices for instruments.

        Args:
            instruments: List of currency pairs

        Returns:
            Dict mapping instrument to {bid, ask, mid} prices.
        """
        normalized = [self._normalize_pair(i) for i in instruments]
        path = f"/v3/accounts/{self.account_id}/pricing"
        params = {"instruments": ",".join(normalized)}

        data = await self._request("GET", path, params=params)

        result = {}
        for price in data.get("prices", []):
            instrument = price["instrument"]
            bids = price.get("bids", [])
            asks = price.get("asks", [])

            bid = float(bids[0]["price"]) if bids else 0
            ask = float(asks[0]["price"]) if asks else 0
            mid = (bid + ask) / 2 if bid and ask else 0

            result[instrument] = {
                "bid": bid,
                "ask": ask,
                "mid": mid,
            }

        return result

    async def get_price(self, instrument: str) -> Optional[Dict[str, float]]:
        """Get current price for a single instrument."""
        prices = await self.get_prices([instrument])
        normalized = self._normalize_pair(instrument)
        return prices.get(normalized)


# Global client instance
_oanda_client: Optional[OandaClient] = None
_db_credentials_loaded: bool = False


def get_oanda_client() -> OandaClient:
    """Get the global OANDA client instance (uses env vars only)."""
    global _oanda_client
    if _oanda_client is None:
        _oanda_client = OandaClient()
    return _oanda_client


async def get_oanda_client_with_db(user_id: str = "default") -> OandaClient:
    """
    Get OANDA client with credentials from database.

    Falls back to environment variables if DB credentials not set.

    Args:
        user_id: User identifier to fetch credentials for

    Returns:
        Configured OandaClient instance
    """
    global _oanda_client, _db_credentials_loaded

    # Try to load from database
    try:
        from .repository import SettingsRepository
        account_id, access_token, environment = await SettingsRepository.get_oanda_credentials(user_id)

        if account_id and access_token:
            # Create new client with DB credentials
            _oanda_client = OandaClient(
                account_id=account_id,
                access_token=access_token,
                environment=environment or "practice"
            )
            _db_credentials_loaded = True
            return _oanda_client
    except Exception as e:
        # DB not available or error, fall back to env vars
        pass

    # Fall back to environment variables
    if _oanda_client is None:
        _oanda_client = OandaClient()

    return _oanda_client


def reset_oanda_client():
    """Reset the OANDA client (forces reload of credentials)."""
    global _oanda_client, _db_credentials_loaded
    if _oanda_client:
        # Note: Can't await close() in sync context, but client will be garbage collected
        _oanda_client = None
    _db_credentials_loaded = False
