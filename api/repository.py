"""
Repository Layer for Lightning Bot Database Operations

Provides async CRUD operations for trades, positions, and accounts.
"""
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any

from bson import ObjectId
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError, PyMongoError

from .database import (
    get_trades_collection,
    get_positions_collection,
    get_accounts_collection,
    get_signals_collection,
)
from .models import (
    TradeDocument,
    TradeCreate,
    TradeUpdate,
    TradeStatus,
    PositionDocument,
    PositionCreate,
    PositionUpdate,
    AccountDocument,
    AccountCreate,
    AccountUpdate,
    AccountMode,
    SignalDocument,
    SignalCreate,
    SignalUpdate,
    SignalStatus,
    TradeDirection,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Trade Repository
# =============================================================================

class TradeRepository:
    """Repository for trade operations."""

    @staticmethod
    async def create_trade(trade: TradeCreate) -> TradeDocument:
        """
        Create a new trade.

        Args:
            trade: Trade creation data

        Returns:
            Created TradeDocument with ID
        """
        collection = await get_trades_collection()

        trade_doc = TradeDocument(
            user_id=trade.user_id,
            pair=trade.pair,
            direction=trade.direction,
            entry_price=trade.entry_price,
            quantity=trade.quantity,
            stop_loss=trade.stop_loss,
            take_profit=trade.take_profit,
            signal_id=trade.signal_id,
            status=TradeStatus.OPEN,
            opened_at=datetime.utcnow(),
        )

        try:
            result = await collection.insert_one(trade_doc.to_mongo())
            trade_doc.id = str(result.inserted_id)
            logger.info(f"Created trade {trade_doc.id} for user {trade.user_id}")
            return trade_doc
        except PyMongoError as e:
            logger.error(f"Error creating trade: {e}")
            raise

    @staticmethod
    async def get_trade(trade_id: str) -> Optional[TradeDocument]:
        """
        Get a trade by ID.

        Args:
            trade_id: Trade document ID

        Returns:
            TradeDocument if found, None otherwise
        """
        collection = await get_trades_collection()

        try:
            doc = await collection.find_one({"_id": ObjectId(trade_id)})
            return TradeDocument.from_mongo(doc) if doc else None
        except Exception as e:
            logger.error(f"Error getting trade {trade_id}: {e}")
            return None

    @staticmethod
    async def get_trades(
        user_id: str,
        status: Optional[TradeStatus] = None,
        pair: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[TradeDocument]:
        """
        Get trades for a user with optional filters.

        Args:
            user_id: User identifier
            status: Optional status filter
            pair: Optional pair filter
            limit: Maximum results
            offset: Skip count for pagination

        Returns:
            List of TradeDocuments
        """
        collection = await get_trades_collection()

        query: Dict[str, Any] = {"user_id": user_id}
        if status:
            query["status"] = status.value
        if pair:
            query["pair"] = pair.upper()

        try:
            cursor = collection.find(query).sort("opened_at", -1).skip(offset).limit(limit)
            trades = []
            async for doc in cursor:
                trades.append(TradeDocument.from_mongo(doc))
            return trades
        except PyMongoError as e:
            logger.error(f"Error getting trades for user {user_id}: {e}")
            return []

    @staticmethod
    async def get_open_trades(user_id: str) -> List[TradeDocument]:
        """
        Get all open trades for a user.

        Args:
            user_id: User identifier

        Returns:
            List of open TradeDocuments
        """
        return await TradeRepository.get_trades(user_id, status=TradeStatus.OPEN)

    @staticmethod
    async def get_closed_trades(
        user_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> List[TradeDocument]:
        """
        Get closed trades for a user.

        Args:
            user_id: User identifier
            limit: Maximum results
            offset: Skip count

        Returns:
            List of closed TradeDocuments
        """
        return await TradeRepository.get_trades(
            user_id, status=TradeStatus.CLOSED, limit=limit, offset=offset
        )

    @staticmethod
    async def update_trade(trade_id: str, update: TradeUpdate) -> Optional[TradeDocument]:
        """
        Update a trade.

        Args:
            trade_id: Trade document ID
            update: Fields to update

        Returns:
            Updated TradeDocument if found
        """
        collection = await get_trades_collection()

        update_data = update.model_dump(exclude_none=True)
        if not update_data:
            return await TradeRepository.get_trade(trade_id)

        try:
            doc = await collection.find_one_and_update(
                {"_id": ObjectId(trade_id)},
                {"$set": update_data},
                return_document=ReturnDocument.AFTER,
            )
            if doc:
                logger.info(f"Updated trade {trade_id}")
                return TradeDocument.from_mongo(doc)
            return None
        except PyMongoError as e:
            logger.error(f"Error updating trade {trade_id}: {e}")
            raise

    @staticmethod
    async def close_trade(
        trade_id: str,
        exit_price: float,
        notes: Optional[str] = None,
    ) -> Optional[TradeDocument]:
        """
        Close an open trade.

        Calculates P&L and updates trade status to closed.

        Args:
            trade_id: Trade document ID
            exit_price: Exit price
            notes: Optional closing notes

        Returns:
            Closed TradeDocument if successful
        """
        collection = await get_trades_collection()

        # Get the current trade
        trade = await TradeRepository.get_trade(trade_id)
        if not trade:
            logger.warning(f"Trade not found: {trade_id}")
            return None

        if trade.status != TradeStatus.OPEN:
            logger.warning(f"Trade {trade_id} is not open, status: {trade.status}")
            return trade

        # Calculate P&L
        entry_value = trade.entry_price * trade.quantity
        exit_value = exit_price * trade.quantity

        if trade.direction == TradeDirection.LONG:
            pnl = exit_value - entry_value
        else:
            pnl = entry_value - exit_value

        pnl_pct = (pnl / entry_value) * 100 if entry_value > 0 else 0

        # Prepare update
        now = datetime.utcnow()
        update_data = {
            "exit_price": exit_price,
            "pnl": round(pnl, 2),
            "pnl_pct": round(pnl_pct, 2),
            "status": TradeStatus.CLOSED.value,
            "closed_at": now,
        }

        if notes:
            existing_notes = trade.notes or ""
            update_data["notes"] = f"{existing_notes}\n{notes}".strip()

        try:
            doc = await collection.find_one_and_update(
                {"_id": ObjectId(trade_id), "status": TradeStatus.OPEN.value},
                {"$set": update_data},
                return_document=ReturnDocument.AFTER,
            )
            if doc:
                logger.info(f"Closed trade {trade_id}, P&L: ${pnl:.2f} ({pnl_pct:.2f}%)")
                return TradeDocument.from_mongo(doc)
            return None
        except PyMongoError as e:
            logger.error(f"Error closing trade {trade_id}: {e}")
            raise

    @staticmethod
    async def get_trade_stats(user_id: str) -> Dict[str, Any]:
        """
        Get trading statistics for a user.

        Args:
            user_id: User identifier

        Returns:
            Dictionary with trade statistics
        """
        collection = await get_trades_collection()

        try:
            pipeline = [
                {"$match": {"user_id": user_id, "status": TradeStatus.CLOSED.value}},
                {
                    "$group": {
                        "_id": None,
                        "total_trades": {"$sum": 1},
                        "total_pnl": {"$sum": "$pnl"},
                        "wins": {"$sum": {"$cond": [{"$gt": ["$pnl", 0]}, 1, 0]}},
                        "losses": {"$sum": {"$cond": [{"$lt": ["$pnl", 0]}, 1, 0]}},
                        "avg_pnl": {"$avg": "$pnl"},
                        "max_win": {"$max": "$pnl"},
                        "max_loss": {"$min": "$pnl"},
                    }
                },
            ]

            cursor = collection.aggregate(pipeline)
            result = await cursor.to_list(length=1)

            if result:
                stats = result[0]
                total = stats.get("total_trades", 0)
                wins = stats.get("wins", 0)
                return {
                    "total_trades": total,
                    "total_pnl": round(stats.get("total_pnl", 0), 2),
                    "wins": wins,
                    "losses": stats.get("losses", 0),
                    "win_rate": round((wins / total) * 100, 2) if total > 0 else 0,
                    "avg_pnl": round(stats.get("avg_pnl", 0), 2),
                    "max_win": round(stats.get("max_win", 0), 2),
                    "max_loss": round(stats.get("max_loss", 0), 2),
                }

            return {
                "total_trades": 0,
                "total_pnl": 0,
                "wins": 0,
                "losses": 0,
                "win_rate": 0,
                "avg_pnl": 0,
                "max_win": 0,
                "max_loss": 0,
            }
        except PyMongoError as e:
            logger.error(f"Error getting trade stats for user {user_id}: {e}")
            raise


# =============================================================================
# Position Repository
# =============================================================================

class PositionRepository:
    """Repository for position operations."""

    @staticmethod
    async def create_position(position: PositionCreate) -> PositionDocument:
        """
        Create a new position.

        Args:
            position: Position creation data

        Returns:
            Created PositionDocument with ID
        """
        collection = await get_positions_collection()

        now = datetime.utcnow()
        position_doc = PositionDocument(
            user_id=position.user_id,
            pair=position.pair,
            direction=position.direction,
            entry_price=position.entry_price,
            quantity=position.quantity,
            stop_loss=position.stop_loss,
            take_profit=position.take_profit,
            current_price=position.entry_price,
            unrealized_pnl=0,
            unrealized_pnl_pct=0,
            opened_at=now,
            updated_at=now,
        )

        try:
            result = await collection.insert_one(position_doc.to_mongo())
            position_doc.id = str(result.inserted_id)
            logger.info(f"Created position {position_doc.id} for user {position.user_id}")
            return position_doc
        except PyMongoError as e:
            logger.error(f"Error creating position: {e}")
            raise

    @staticmethod
    async def get_position(position_id: str) -> Optional[PositionDocument]:
        """
        Get a position by ID.

        Args:
            position_id: Position document ID

        Returns:
            PositionDocument if found
        """
        collection = await get_positions_collection()

        try:
            doc = await collection.find_one({"_id": ObjectId(position_id)})
            return PositionDocument.from_mongo(doc) if doc else None
        except Exception as e:
            logger.error(f"Error getting position {position_id}: {e}")
            return None

    @staticmethod
    async def get_positions(
        user_id: str,
        pair: Optional[str] = None,
    ) -> List[PositionDocument]:
        """
        Get all positions for a user.

        Args:
            user_id: User identifier
            pair: Optional pair filter

        Returns:
            List of PositionDocuments
        """
        collection = await get_positions_collection()

        query: Dict[str, Any] = {"user_id": user_id}
        if pair:
            query["pair"] = pair.upper()

        try:
            cursor = collection.find(query).sort("opened_at", -1)
            positions = []
            async for doc in cursor:
                positions.append(PositionDocument.from_mongo(doc))
            return positions
        except PyMongoError as e:
            logger.error(f"Error getting positions for user {user_id}: {e}")
            return []

    @staticmethod
    async def update_position(
        position_id: str,
        update: PositionUpdate,
    ) -> Optional[PositionDocument]:
        """
        Update a position.

        Args:
            position_id: Position document ID
            update: Fields to update

        Returns:
            Updated PositionDocument if found
        """
        collection = await get_positions_collection()

        update_data = update.model_dump(exclude_none=True)
        update_data["updated_at"] = datetime.utcnow()

        try:
            doc = await collection.find_one_and_update(
                {"_id": ObjectId(position_id)},
                {"$set": update_data},
                return_document=ReturnDocument.AFTER,
            )
            if doc:
                logger.info(f"Updated position {position_id}")
                return PositionDocument.from_mongo(doc)
            return None
        except PyMongoError as e:
            logger.error(f"Error updating position {position_id}: {e}")
            raise

    @staticmethod
    async def update_position_price(
        position_id: str,
        current_price: float,
    ) -> Optional[PositionDocument]:
        """
        Update position with current market price and recalculate P&L.

        Args:
            position_id: Position document ID
            current_price: Current market price

        Returns:
            Updated PositionDocument
        """
        position = await PositionRepository.get_position(position_id)
        if not position:
            return None

        pnl, pnl_pct = position.calculate_pnl(current_price)

        update = PositionUpdate(
            current_price=current_price,
            unrealized_pnl=pnl,
            unrealized_pnl_pct=pnl_pct,
        )

        return await PositionRepository.update_position(position_id, update)

    @staticmethod
    async def delete_position(position_id: str) -> bool:
        """
        Delete a position.

        Args:
            position_id: Position document ID

        Returns:
            True if deleted, False otherwise
        """
        collection = await get_positions_collection()

        try:
            result = await collection.delete_one({"_id": ObjectId(position_id)})
            if result.deleted_count > 0:
                logger.info(f"Deleted position {position_id}")
                return True
            return False
        except PyMongoError as e:
            logger.error(f"Error deleting position {position_id}: {e}")
            raise

    @staticmethod
    async def delete_all_positions(user_id: str) -> int:
        """
        Delete all positions for a user.

        Args:
            user_id: User identifier

        Returns:
            Number of deleted positions
        """
        collection = await get_positions_collection()

        try:
            result = await collection.delete_many({"user_id": user_id})
            logger.info(f"Deleted {result.deleted_count} positions for user {user_id}")
            return result.deleted_count
        except PyMongoError as e:
            logger.error(f"Error deleting positions for user {user_id}: {e}")
            raise


# =============================================================================
# Account Repository
# =============================================================================

class AccountRepository:
    """Repository for account operations."""

    @staticmethod
    async def create_account(account: AccountCreate) -> AccountDocument:
        """
        Create a new account.

        Args:
            account: Account creation data

        Returns:
            Created AccountDocument
        """
        collection = await get_accounts_collection()

        now = datetime.utcnow()
        account_doc = AccountDocument(
            user_id=account.user_id,
            mode=account.mode,
            balance=account.initial_balance,
            initial_balance=account.initial_balance,
            equity=account.initial_balance,
            created_at=now,
            updated_at=now,
        )

        try:
            result = await collection.insert_one(account_doc.to_mongo())
            account_doc.id = str(result.inserted_id)
            logger.info(f"Created {account.mode.value} account for user {account.user_id}")
            return account_doc
        except DuplicateKeyError:
            logger.warning(f"Account already exists for user {account.user_id}, mode {account.mode}")
            # Return existing account
            existing = await AccountRepository.get_account(account.user_id, account.mode)
            if existing:
                return existing
            raise
        except PyMongoError as e:
            logger.error(f"Error creating account: {e}")
            raise

    @staticmethod
    async def get_account(
        user_id: str,
        mode: AccountMode = AccountMode.PAPER,
    ) -> Optional[AccountDocument]:
        """
        Get an account by user ID and mode.

        Args:
            user_id: User identifier
            mode: Account mode (paper/live)

        Returns:
            AccountDocument if found
        """
        collection = await get_accounts_collection()

        try:
            doc = await collection.find_one({"user_id": user_id, "mode": mode.value})
            return AccountDocument.from_mongo(doc) if doc else None
        except PyMongoError as e:
            logger.error(f"Error getting account for user {user_id}: {e}")
            return None

    @staticmethod
    async def get_or_create_account(
        user_id: str,
        mode: AccountMode = AccountMode.PAPER,
        initial_balance: float = 10000.0,
    ) -> AccountDocument:
        """
        Get existing account or create new one.

        Args:
            user_id: User identifier
            mode: Account mode
            initial_balance: Initial balance for new account

        Returns:
            AccountDocument
        """
        account = await AccountRepository.get_account(user_id, mode)
        if account:
            return account

        create_data = AccountCreate(
            user_id=user_id,
            mode=mode,
            initial_balance=initial_balance,
        )
        return await AccountRepository.create_account(create_data)

    @staticmethod
    async def update_account(
        user_id: str,
        mode: AccountMode,
        update: AccountUpdate,
    ) -> Optional[AccountDocument]:
        """
        Update an account.

        Args:
            user_id: User identifier
            mode: Account mode
            update: Fields to update

        Returns:
            Updated AccountDocument
        """
        collection = await get_accounts_collection()

        update_data = update.model_dump(exclude_none=True)
        update_data["updated_at"] = datetime.utcnow()

        try:
            doc = await collection.find_one_and_update(
                {"user_id": user_id, "mode": mode.value},
                {"$set": update_data},
                return_document=ReturnDocument.AFTER,
            )
            if doc:
                logger.info(f"Updated account for user {user_id}")
                return AccountDocument.from_mongo(doc)
            return None
        except PyMongoError as e:
            logger.error(f"Error updating account for user {user_id}: {e}")
            raise

    @staticmethod
    async def update_account_balance(
        user_id: str,
        mode: AccountMode,
        balance_change: float,
        is_realized_pnl: bool = False,
        trade_result: Optional[str] = None,  # "win", "loss", or None
    ) -> Optional[AccountDocument]:
        """
        Update account balance after a trade.

        Args:
            user_id: User identifier
            mode: Account mode
            balance_change: Amount to add/subtract from balance
            is_realized_pnl: Whether this is realized P&L (closed trade)
            trade_result: "win", "loss", or None

        Returns:
            Updated AccountDocument
        """
        collection = await get_accounts_collection()

        # Build update operations
        update_ops: Dict[str, Any] = {
            "$inc": {"balance": balance_change},
            "$set": {"updated_at": datetime.utcnow()},
        }

        if is_realized_pnl:
            update_ops["$inc"]["realized_pnl"] = balance_change
            update_ops["$inc"]["total_trades"] = 1

            if trade_result == "win":
                update_ops["$inc"]["winning_trades"] = 1
            elif trade_result == "loss":
                update_ops["$inc"]["losing_trades"] = 1

        try:
            doc = await collection.find_one_and_update(
                {"user_id": user_id, "mode": mode.value},
                update_ops,
                return_document=ReturnDocument.AFTER,
            )
            if doc:
                logger.info(f"Updated balance for user {user_id}: {balance_change:+.2f}")
                return AccountDocument.from_mongo(doc)
            return None
        except PyMongoError as e:
            logger.error(f"Error updating account balance for user {user_id}: {e}")
            raise

    @staticmethod
    async def update_equity(
        user_id: str,
        mode: AccountMode,
        unrealized_pnl: float,
    ) -> Optional[AccountDocument]:
        """
        Update account equity based on unrealized P&L.

        Args:
            user_id: User identifier
            mode: Account mode
            unrealized_pnl: Total unrealized P&L from open positions

        Returns:
            Updated AccountDocument
        """
        account = await AccountRepository.get_account(user_id, mode)
        if not account:
            return None

        equity = account.balance + unrealized_pnl

        update = AccountUpdate(
            equity=round(equity, 2),
            unrealized_pnl=round(unrealized_pnl, 2),
        )

        return await AccountRepository.update_account(user_id, mode, update)

    @staticmethod
    async def reset_account(
        user_id: str,
        mode: AccountMode,
        new_balance: float = 10000.0,
    ) -> Optional[AccountDocument]:
        """
        Reset an account to initial state.

        Args:
            user_id: User identifier
            mode: Account mode
            new_balance: New starting balance

        Returns:
            Reset AccountDocument
        """
        collection = await get_accounts_collection()

        now = datetime.utcnow()
        reset_data = {
            "balance": new_balance,
            "initial_balance": new_balance,
            "equity": new_balance,
            "margin_used": 0,
            "unrealized_pnl": 0,
            "realized_pnl": 0,
            "total_trades": 0,
            "winning_trades": 0,
            "losing_trades": 0,
            "updated_at": now,
        }

        try:
            doc = await collection.find_one_and_update(
                {"user_id": user_id, "mode": mode.value},
                {"$set": reset_data},
                return_document=ReturnDocument.AFTER,
            )
            if doc:
                logger.info(f"Reset {mode.value} account for user {user_id} to ${new_balance}")
                return AccountDocument.from_mongo(doc)
            return None
        except PyMongoError as e:
            logger.error(f"Error resetting account for user {user_id}: {e}")
            raise


# =============================================================================
# Signal Repository
# =============================================================================

class SignalRepository:
    """Repository for signal operations."""

    @staticmethod
    async def create_signal(signal: SignalCreate) -> SignalDocument:
        """
        Create a new signal.

        Args:
            signal: Signal creation data

        Returns:
            Created SignalDocument
        """
        collection = await get_signals_collection()

        signal_doc = SignalDocument(
            pair=signal.pair,
            direction=signal.direction,
            confidence=signal.confidence,
            entry_price=signal.entry_price,
            stop_loss=signal.stop_loss,
            take_profit=signal.take_profit,
            strategy=signal.strategy,
            status=SignalStatus.ACTIVE,
            created_at=datetime.utcnow(),
        )

        try:
            result = await collection.insert_one(signal_doc.to_mongo())
            signal_doc.id = str(result.inserted_id)
            logger.info(f"Created signal {signal_doc.id} for {signal.pair}")
            return signal_doc
        except PyMongoError as e:
            logger.error(f"Error creating signal: {e}")
            raise

    @staticmethod
    async def get_signal(signal_id: str) -> Optional[SignalDocument]:
        """
        Get a signal by ID.

        Args:
            signal_id: Signal document ID

        Returns:
            SignalDocument if found
        """
        collection = await get_signals_collection()

        try:
            doc = await collection.find_one({"_id": ObjectId(signal_id)})
            return SignalDocument.from_mongo(doc) if doc else None
        except Exception as e:
            logger.error(f"Error getting signal {signal_id}: {e}")
            return None

    @staticmethod
    async def get_signals(
        pair: Optional[str] = None,
        status: Optional[SignalStatus] = None,
        limit: int = 20,
    ) -> List[SignalDocument]:
        """
        Get signals with optional filters.

        Args:
            pair: Optional pair filter
            status: Optional status filter
            limit: Maximum results

        Returns:
            List of SignalDocuments
        """
        collection = await get_signals_collection()

        query: Dict[str, Any] = {}
        if pair:
            query["pair"] = pair.upper()
        if status:
            query["status"] = status.value

        try:
            cursor = collection.find(query).sort("created_at", -1).limit(limit)
            signals = []
            async for doc in cursor:
                signals.append(SignalDocument.from_mongo(doc))
            return signals
        except PyMongoError as e:
            logger.error(f"Error getting signals: {e}")
            return []

    @staticmethod
    async def get_active_signals(pair: Optional[str] = None) -> List[SignalDocument]:
        """
        Get active signals.

        Args:
            pair: Optional pair filter

        Returns:
            List of active SignalDocuments
        """
        return await SignalRepository.get_signals(pair=pair, status=SignalStatus.ACTIVE)

    @staticmethod
    async def update_signal(
        signal_id: str,
        update: SignalUpdate,
    ) -> Optional[SignalDocument]:
        """
        Update a signal.

        Args:
            signal_id: Signal document ID
            update: Fields to update

        Returns:
            Updated SignalDocument
        """
        collection = await get_signals_collection()

        update_data = update.model_dump(exclude_none=True)
        if not update_data:
            return await SignalRepository.get_signal(signal_id)

        try:
            doc = await collection.find_one_and_update(
                {"_id": ObjectId(signal_id)},
                {"$set": update_data},
                return_document=ReturnDocument.AFTER,
            )
            if doc:
                logger.info(f"Updated signal {signal_id}")
                return SignalDocument.from_mongo(doc)
            return None
        except PyMongoError as e:
            logger.error(f"Error updating signal {signal_id}: {e}")
            raise

    @staticmethod
    async def mark_signal_executed(
        signal_id: str,
        trade_id: str,
    ) -> Optional[SignalDocument]:
        """
        Mark a signal as executed.

        Args:
            signal_id: Signal document ID
            trade_id: Associated trade ID

        Returns:
            Updated SignalDocument
        """
        update = SignalUpdate(
            status=SignalStatus.EXECUTED,
            executed_at=datetime.utcnow(),
            trade_id=trade_id,
        )
        return await SignalRepository.update_signal(signal_id, update)

    @staticmethod
    async def expire_old_signals(hours: int = 24) -> int:
        """
        Expire signals older than specified hours.

        Args:
            hours: Age threshold in hours

        Returns:
            Number of expired signals
        """
        collection = await get_signals_collection()

        from datetime import timedelta
        cutoff = datetime.utcnow() - timedelta(hours=hours)

        try:
            result = await collection.update_many(
                {
                    "status": SignalStatus.ACTIVE.value,
                    "created_at": {"$lt": cutoff},
                },
                {"$set": {"status": SignalStatus.EXPIRED.value}},
            )
            if result.modified_count > 0:
                logger.info(f"Expired {result.modified_count} old signals")
            return result.modified_count
        except PyMongoError as e:
            logger.error(f"Error expiring signals: {e}")
            raise


# =============================================================================
# Settings Repository
# =============================================================================

class SettingsRepository:
    """Repository for user settings operations."""

    @staticmethod
    async def get_settings(user_id: str = "default"):
        """
        Get settings for a user.

        Args:
            user_id: User identifier

        Returns:
            Settings dict if found, None otherwise
        """
        from .database import get_db
        db = await get_db()

        try:
            doc = await db.settings.find_one({"user_id": user_id})
            return doc
        except Exception as e:
            logger.error(f"Error getting settings for user {user_id}: {e}")
            return None

    @staticmethod
    async def get_or_create_settings(user_id: str = "default"):
        """
        Get existing settings or create default.

        Args:
            user_id: User identifier

        Returns:
            Settings dict
        """
        from .database import get_db
        db = await get_db()

        settings = await SettingsRepository.get_settings(user_id)
        if settings:
            return settings

        # Create default settings
        now = datetime.utcnow()
        default_settings = {
            "_id": user_id,
            "user_id": user_id,
            "oanda_account_id": None,
            "oanda_access_token": None,
            "oanda_environment": "practice",
            "trading_mode": "paper",
            "risk_per_trade": 0.02,
            "max_daily_trades": 10,
            "max_daily_loss": 0.06,
            "ml_confidence_threshold": 0.70,
            "created_at": now,
            "updated_at": now,
        }

        try:
            await db.settings.insert_one(default_settings)
            logger.info(f"Created default settings for user {user_id}")
            return default_settings
        except Exception as e:
            logger.error(f"Error creating settings: {e}")
            # Return default even if insert failed
            return default_settings

    @staticmethod
    async def update_settings(user_id: str, updates: dict):
        """
        Update settings for a user.

        Args:
            user_id: User identifier
            updates: Dict of fields to update

        Returns:
            Updated settings dict
        """
        from .database import get_db
        db = await get_db()

        # Ensure settings exist
        await SettingsRepository.get_or_create_settings(user_id)

        # Add updated timestamp
        updates["updated_at"] = datetime.utcnow()

        try:
            await db.settings.update_one(
                {"user_id": user_id},
                {"$set": updates}
            )
            logger.info(f"Updated settings for user {user_id}")
            return await SettingsRepository.get_settings(user_id)
        except Exception as e:
            logger.error(f"Error updating settings: {e}")
            raise

    @staticmethod
    async def save_oanda_credentials(
        user_id: str,
        account_id: str,
        access_token: str,
        environment: str = "practice"
    ):
        """
        Save OANDA API credentials.

        Args:
            user_id: User identifier
            account_id: OANDA account ID
            access_token: OANDA API token
            environment: "practice" or "live"

        Returns:
            Updated settings dict
        """
        updates = {
            "oanda_account_id": account_id,
            "oanda_access_token": access_token,
            "oanda_environment": environment,
        }
        return await SettingsRepository.update_settings(user_id, updates)

    @staticmethod
    async def get_oanda_credentials(user_id: str = "default"):
        """
        Get OANDA credentials for a user.

        Args:
            user_id: User identifier

        Returns:
            Tuple of (account_id, access_token, environment) or (None, None, None)
        """
        settings = await SettingsRepository.get_settings(user_id)
        if not settings:
            return None, None, None

        return (
            settings.get("oanda_account_id"),
            settings.get("oanda_access_token"),
            settings.get("oanda_environment", "practice"),
        )


# =============================================================================
# Convenience Functions
# =============================================================================

# Settings functions
get_settings = SettingsRepository.get_settings
get_or_create_settings = SettingsRepository.get_or_create_settings
update_settings = SettingsRepository.update_settings
save_oanda_credentials = SettingsRepository.save_oanda_credentials
get_oanda_credentials = SettingsRepository.get_oanda_credentials

# Trade functions
create_trade = TradeRepository.create_trade
get_trade = TradeRepository.get_trade
get_trades = TradeRepository.get_trades
get_open_trades = TradeRepository.get_open_trades
get_closed_trades = TradeRepository.get_closed_trades
update_trade = TradeRepository.update_trade
close_trade = TradeRepository.close_trade
get_trade_stats = TradeRepository.get_trade_stats

# Position functions
create_position = PositionRepository.create_position
get_position = PositionRepository.get_position
get_positions = PositionRepository.get_positions
update_position = PositionRepository.update_position
update_position_price = PositionRepository.update_position_price
delete_position = PositionRepository.delete_position
delete_all_positions = PositionRepository.delete_all_positions

# Account functions
create_account = AccountRepository.create_account
get_account = AccountRepository.get_account
get_or_create_account = AccountRepository.get_or_create_account
update_account = AccountRepository.update_account
update_account_balance = AccountRepository.update_account_balance
update_equity = AccountRepository.update_equity
reset_account = AccountRepository.reset_account

# Signal functions
create_signal = SignalRepository.create_signal
get_signal = SignalRepository.get_signal
get_signals = SignalRepository.get_signals
get_active_signals = SignalRepository.get_active_signals
update_signal = SignalRepository.update_signal
mark_signal_executed = SignalRepository.mark_signal_executed
expire_old_signals = SignalRepository.expire_old_signals
