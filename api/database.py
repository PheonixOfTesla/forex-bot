"""
MongoDB Database Connection for Lightning Bot API

Async MongoDB integration using Motor driver, optimized for Vercel serverless.
"""
import os
import logging
from typing import Optional
from contextlib import asynccontextmanager

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo import IndexModel, ASCENDING, DESCENDING
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError

logger = logging.getLogger(__name__)

# Global client instance for connection pooling in serverless
_client: Optional[AsyncIOMotorClient] = None
_db: Optional[AsyncIOMotorDatabase] = None


def get_mongodb_uri() -> str:
    """Get MongoDB URI from environment variable."""
    uri = os.environ.get("MONGODB_URI")
    if not uri:
        raise ValueError("MONGODB_URI environment variable is not set")
    return uri


def get_database_name() -> str:
    """Get database name from environment or use default."""
    return os.environ.get("MONGODB_DATABASE", "lightning_trading")


async def get_client() -> AsyncIOMotorClient:
    """
    Get or create MongoDB client with connection pooling.

    Uses a singleton pattern optimized for serverless environments:
    - Reuses connections across warm invocations
    - Configures appropriate pool sizes for serverless
    """
    global _client

    if _client is None:
        uri = get_mongodb_uri()
        _client = AsyncIOMotorClient(
            uri,
            # Serverless-optimized settings
            maxPoolSize=10,  # Limit pool size for serverless
            minPoolSize=1,   # Keep at least 1 connection warm
            maxIdleTimeMS=45000,  # Close idle connections after 45s
            serverSelectionTimeoutMS=5000,  # 5s timeout for server selection
            connectTimeoutMS=10000,  # 10s connection timeout
            socketTimeoutMS=30000,  # 30s socket timeout
            retryWrites=True,
            retryReads=True,
            # Write concern for production reliability
            w="majority",
        )
        logger.info("MongoDB client created with connection pooling")

    return _client


async def get_db() -> AsyncIOMotorDatabase:
    """
    Get the database instance.

    Returns:
        AsyncIOMotorDatabase: The MongoDB database instance
    """
    global _db

    if _db is None:
        client = await get_client()
        db_name = get_database_name()
        _db = client[db_name]
        logger.info(f"Connected to database: {db_name}")

    return _db


async def init_db() -> None:
    """
    Initialize database with required indexes.

    Creates indexes for:
    - trades: user_id, pair, status, opened_at, signal_id
    - positions: user_id, pair, opened_at
    - accounts: user_id (unique), mode
    - signals: pair, status, created_at

    Should be called on application startup.
    """
    db = await get_db()

    # Trades collection indexes
    trades_indexes = [
        IndexModel([("user_id", ASCENDING)]),
        IndexModel([("user_id", ASCENDING), ("status", ASCENDING)]),
        IndexModel([("pair", ASCENDING)]),
        IndexModel([("opened_at", DESCENDING)]),
        IndexModel([("closed_at", DESCENDING)]),
        IndexModel([("signal_id", ASCENDING)]),
        IndexModel([("user_id", ASCENDING), ("opened_at", DESCENDING)]),
    ]

    # Positions collection indexes
    positions_indexes = [
        IndexModel([("user_id", ASCENDING)]),
        IndexModel([("user_id", ASCENDING), ("pair", ASCENDING)]),
        IndexModel([("opened_at", DESCENDING)]),
    ]

    # Accounts collection indexes
    accounts_indexes = [
        IndexModel([("user_id", ASCENDING)], unique=True),
        IndexModel([("user_id", ASCENDING), ("mode", ASCENDING)], unique=True),
    ]

    # Signals collection indexes
    signals_indexes = [
        IndexModel([("pair", ASCENDING)]),
        IndexModel([("status", ASCENDING)]),
        IndexModel([("created_at", DESCENDING)]),
        IndexModel([("pair", ASCENDING), ("status", ASCENDING)]),
    ]

    try:
        # Create indexes (idempotent operation)
        await db.trades.create_indexes(trades_indexes)
        logger.info("Created indexes for 'trades' collection")

        await db.positions.create_indexes(positions_indexes)
        logger.info("Created indexes for 'positions' collection")

        await db.accounts.create_indexes(accounts_indexes)
        logger.info("Created indexes for 'accounts' collection")

        await db.signals.create_indexes(signals_indexes)
        logger.info("Created indexes for 'signals' collection")

        logger.info("Database initialization complete")

    except Exception as e:
        logger.error(f"Error creating indexes: {e}")
        raise


async def close_db() -> None:
    """
    Close the database connection.

    Should be called on application shutdown.
    """
    global _client, _db

    if _client is not None:
        _client.close()
        _client = None
        _db = None
        logger.info("MongoDB connection closed")


async def check_connection() -> bool:
    """
    Check if the database connection is healthy.

    Returns:
        bool: True if connection is healthy, False otherwise
    """
    try:
        client = await get_client()
        # Ping the database to verify connection
        await client.admin.command("ping")
        return True
    except (ConnectionFailure, ServerSelectionTimeoutError) as e:
        logger.error(f"Database connection check failed: {e}")
        return False


@asynccontextmanager
async def get_db_session():
    """
    Context manager for database sessions.

    Provides a clean way to work with database transactions.
    Note: MongoDB doesn't support transactions in standalone mode,
    but this pattern is useful for future replica set deployments.

    Usage:
        async with get_db_session() as db:
            await db.trades.insert_one(document)
    """
    db = await get_db()
    try:
        yield db
    except Exception as e:
        logger.error(f"Database session error: {e}")
        raise


# Collection accessors for convenience
async def get_trades_collection():
    """Get the trades collection."""
    db = await get_db()
    return db.trades


async def get_positions_collection():
    """Get the positions collection."""
    db = await get_db()
    return db.positions


async def get_accounts_collection():
    """Get the accounts collection."""
    db = await get_db()
    return db.accounts


async def get_signals_collection():
    """Get the signals collection."""
    db = await get_db()
    return db.signals
