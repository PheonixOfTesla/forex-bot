"""
Database connection management for async SQLAlchemy with PostgreSQL.
Provides connection pooling, session management, and table operations.
"""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from .models import Base

logger = logging.getLogger(__name__)


class Database:
    """
    Async database connection manager.

    Handles connection pooling, session creation, and schema management
    for PostgreSQL using asyncpg driver.

    Usage:
        db = Database("postgresql+asyncpg://user:pass@localhost/forex")
        await db.connect()
        async with db.get_session() as session:
            # Use session
        await db.disconnect()
    """

    def __init__(
        self,
        database_url: str,
        echo: bool = False,
        pool_size: int = 5,
        max_overflow: int = 10,
        pool_timeout: int = 30,
    ):
        """
        Initialize database connection configuration.

        Args:
            database_url: PostgreSQL connection string
                         (e.g., postgresql+asyncpg://user:pass@localhost/dbname)
            echo: If True, log all SQL statements
            pool_size: Number of connections to keep in the pool
            max_overflow: Max connections that can be created beyond pool_size
            pool_timeout: Seconds to wait for a connection from the pool
        """
        self.database_url = database_url
        self.echo = echo
        self.pool_size = pool_size
        self.max_overflow = max_overflow
        self.pool_timeout = pool_timeout

        self._engine: Optional[AsyncEngine] = None
        self._session_factory: Optional[async_sessionmaker[AsyncSession]] = None

    async def connect(self) -> None:
        """
        Establish database connection and create session factory.

        Creates an async engine with connection pooling optimized for
        trading workloads.
        """
        logger.info(f"Connecting to database...")

        # Create async engine with connection pooling
        self._engine = create_async_engine(
            self.database_url,
            echo=self.echo,
            pool_size=self.pool_size,
            max_overflow=self.max_overflow,
            pool_timeout=self.pool_timeout,
            pool_pre_ping=True,  # Verify connections before use
        )

        # Create session factory
        self._session_factory = async_sessionmaker(
            bind=self._engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False,
        )

        logger.info("Database connection established")

    async def disconnect(self) -> None:
        """
        Close database connection and dispose of connection pool.
        """
        if self._engine:
            logger.info("Disconnecting from database...")
            await self._engine.dispose()
            self._engine = None
            self._session_factory = None
            logger.info("Database disconnected")

    @asynccontextmanager
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """
        Get an async database session.

        Usage:
            async with db.get_session() as session:
                # Use session for queries
                result = await session.execute(select(Trade))

        Yields:
            AsyncSession: Database session with automatic cleanup

        Raises:
            RuntimeError: If database is not connected
        """
        if not self._session_factory:
            raise RuntimeError(
                "Database not connected. Call connect() first."
            )

        session = self._session_factory()
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

    async def get_session_no_context(self) -> AsyncSession:
        """
        Get a raw session without context manager.
        Caller is responsible for commit/rollback/close.

        Returns:
            AsyncSession: Database session

        Raises:
            RuntimeError: If database is not connected
        """
        if not self._session_factory:
            raise RuntimeError(
                "Database not connected. Call connect() first."
            )
        return self._session_factory()

    async def create_tables(self) -> None:
        """
        Create all database tables defined in models.

        Uses SQLAlchemy metadata to create tables if they don't exist.
        Safe to call multiple times.
        """
        if not self._engine:
            raise RuntimeError(
                "Database not connected. Call connect() first."
            )

        logger.info("Creating database tables...")
        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables created")

    async def drop_tables(self) -> None:
        """
        Drop all database tables.

        WARNING: This will delete all data. Use with caution.
        """
        if not self._engine:
            raise RuntimeError(
                "Database not connected. Call connect() first."
            )

        logger.warning("Dropping all database tables...")
        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        logger.warning("All database tables dropped")

    @property
    def engine(self) -> Optional[AsyncEngine]:
        """Get the underlying async engine."""
        return self._engine

    @property
    def is_connected(self) -> bool:
        """Check if database is connected."""
        return self._engine is not None


class DatabasePool:
    """
    Singleton database pool for application-wide access.

    Usage:
        # Initialize once at startup
        await DatabasePool.initialize("postgresql+asyncpg://...")

        # Use anywhere in the application
        async with DatabasePool.get_session() as session:
            # Use session

        # Cleanup at shutdown
        await DatabasePool.shutdown()
    """

    _instance: Optional[Database] = None

    @classmethod
    async def initialize(cls, database_url: str, **kwargs) -> None:
        """Initialize the global database pool."""
        if cls._instance is not None:
            await cls._instance.disconnect()

        cls._instance = Database(database_url, **kwargs)
        await cls._instance.connect()

    @classmethod
    @asynccontextmanager
    async def get_session(cls) -> AsyncGenerator[AsyncSession, None]:
        """Get a session from the global pool."""
        if cls._instance is None:
            raise RuntimeError(
                "DatabasePool not initialized. Call initialize() first."
            )
        async with cls._instance.get_session() as session:
            yield session

    @classmethod
    async def shutdown(cls) -> None:
        """Shutdown the global database pool."""
        if cls._instance:
            await cls._instance.disconnect()
            cls._instance = None

    @classmethod
    def get_database(cls) -> Database:
        """Get the underlying Database instance."""
        if cls._instance is None:
            raise RuntimeError(
                "DatabasePool not initialized. Call initialize() first."
            )
        return cls._instance
