from __future__ import annotations

"""
Alembic migration setup helpers for forex trading database.
Provides utilities for managing database schema migrations.
"""

import os
from pathlib import Path
from typing import Optional

# Migration template for Alembic
ALEMBIC_INI_TEMPLATE = """
[alembic]
script_location = %(here)s/alembic
prepend_sys_path = .
version_path_separator = os

[post_write_hooks]

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console
qualname =

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
"""

ENV_PY_TEMPLATE = '''"""
Alembic environment configuration for forex-bot.
"""

import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# Import your models
from src.db.models import Base

# Alembic Config object
config = context.config

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Model metadata for autogenerate support
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """
    Run migrations in 'offline' mode.

    This configures the context with just a URL and not an Engine.
    By skipping the Engine creation we don't need a DBAPI available.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Run migrations with the given connection."""
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """
    Run migrations in 'online' mode with async engine.
    """
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
'''

SCRIPT_PY_MAKO_TEMPLATE = '''"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

# revision identifiers, used by Alembic.
revision: str = ${repr(up_revision)}
down_revision: Union[str, None] = ${repr(down_revision)}
branch_labels: Union[str, Sequence[str], None] = ${repr(branch_labels)}
depends_on: Union[str, Sequence[str], None] = ${repr(depends_on)}


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
'''


class MigrationSetup:
    """
    Helper class for setting up Alembic migrations.

    Usage:
        setup = MigrationSetup("/path/to/project")
        setup.initialize()

        # Then use alembic commands:
        # alembic revision --autogenerate -m "Initial migration"
        # alembic upgrade head
    """

    def __init__(self, project_root: str):
        """
        Initialize migration setup.

        Args:
            project_root: Root directory of the project
        """
        self.project_root = Path(project_root)
        self.alembic_dir = self.project_root / "alembic"
        self.versions_dir = self.alembic_dir / "versions"

    def initialize(self, database_url: Optional[str] = None) -> None:
        """
        Initialize Alembic migration structure.

        Args:
            database_url: Database URL to use in config
        """
        # Create directories
        self.alembic_dir.mkdir(exist_ok=True)
        self.versions_dir.mkdir(exist_ok=True)

        # Create alembic.ini
        alembic_ini = self.project_root / "alembic.ini"
        if not alembic_ini.exists():
            content = ALEMBIC_INI_TEMPLATE
            if database_url:
                content = content.replace(
                    "[alembic]",
                    f"[alembic]\nsqlalchemy.url = {database_url}"
                )
            alembic_ini.write_text(content)

        # Create env.py
        env_py = self.alembic_dir / "env.py"
        if not env_py.exists():
            env_py.write_text(ENV_PY_TEMPLATE)

        # Create script.py.mako
        script_mako = self.alembic_dir / "script.py.mako"
        if not script_mako.exists():
            script_mako.write_text(SCRIPT_PY_MAKO_TEMPLATE)

        # Create README
        readme = self.versions_dir / "README"
        if not readme.exists():
            readme.write_text("Generic single-database configuration.\n")

    def get_database_url_from_env(self, env_var: str = "DATABASE_URL") -> str:
        """
        Get database URL from environment variable.

        Args:
            env_var: Name of environment variable

        Returns:
            Database URL string

        Raises:
            ValueError: If environment variable not set
        """
        url = os.environ.get(env_var)
        if not url:
            raise ValueError(f"Environment variable {env_var} not set")

        # Convert postgres:// to postgresql+asyncpg://
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+asyncpg://", 1)
        elif url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)

        return url


def create_initial_migration_script() -> str:
    """
    Generate a manual initial migration script.

    Returns:
        str: Python code for initial migration
    """
    return '''"""Initial migration - Create trading tables

Revision ID: 001_initial
Revises:
Create Date: 2024-01-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '001_initial'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create trades table
    op.create_table(
        'trades',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('timestamp', sa.DateTime(), nullable=False),
        sa.Column('asset', sa.String(20), nullable=False),
        sa.Column('strategy', sa.String(50), nullable=False),
        sa.Column('direction', sa.Enum('LONG', 'SHORT', name='tradedirection'), nullable=False),
        sa.Column('entry_price', sa.Float(), nullable=False),
        sa.Column('exit_price', sa.Float(), nullable=True),
        sa.Column('stop_loss', sa.Float(), nullable=True),
        sa.Column('take_profit', sa.Float(), nullable=True),
        sa.Column('quantity', sa.Float(), nullable=False),
        sa.Column('pnl', sa.Float(), nullable=True),
        sa.Column('pnl_percent', sa.Float(), nullable=True),
        sa.Column('confidence', sa.Float(), nullable=True),
        sa.Column('features_snapshot', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('market_conditions', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('session', sa.String(20), nullable=True),
        sa.Column('duration_minutes', sa.Integer(), nullable=True),
        sa.Column('was_stopped_out', sa.Boolean(), default=False),
        sa.Column('hit_target', sa.Boolean(), default=False),
        sa.Column('broker', sa.String(50), nullable=True),
        sa.Column('order_id', sa.String(100), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('order_id')
    )
    op.create_index('ix_trades_timestamp', 'trades', ['timestamp'])
    op.create_index('ix_trades_asset', 'trades', ['asset'])
    op.create_index('ix_trades_strategy', 'trades', ['strategy'])

    # Create positions table
    op.create_table(
        'positions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('asset', sa.String(20), nullable=False),
        sa.Column('direction', sa.Enum('LONG', 'SHORT', name='tradedirection', create_type=False), nullable=False),
        sa.Column('entry_price', sa.Float(), nullable=False),
        sa.Column('quantity', sa.Float(), nullable=False),
        sa.Column('current_price', sa.Float(), nullable=True),
        sa.Column('unrealized_pnl', sa.Float(), nullable=True),
        sa.Column('stop_loss', sa.Float(), nullable=True),
        sa.Column('take_profit', sa.Float(), nullable=True),
        sa.Column('opened_at', sa.DateTime(), nullable=False),
        sa.Column('broker', sa.String(50), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_positions_asset', 'positions', ['asset'])
    op.create_index('ix_positions_opened_at', 'positions', ['opened_at'])

    # Create daily_performance table
    op.create_table(
        'daily_performance',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('starting_balance', sa.Float(), nullable=False),
        sa.Column('ending_balance', sa.Float(), nullable=False),
        sa.Column('pnl', sa.Float(), nullable=False),
        sa.Column('pnl_percent', sa.Float(), nullable=False),
        sa.Column('trades_count', sa.Integer(), default=0),
        sa.Column('wins', sa.Integer(), default=0),
        sa.Column('losses', sa.Integer(), default=0),
        sa.Column('win_rate', sa.Float(), nullable=True),
        sa.Column('max_drawdown', sa.Float(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('date')
    )
    op.create_index('ix_daily_performance_date', 'daily_performance', ['date'])

    # Create strategy_performance table
    op.create_table(
        'strategy_performance',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('strategy_name', sa.String(50), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('trades_count', sa.Integer(), default=0),
        sa.Column('wins', sa.Integer(), default=0),
        sa.Column('losses', sa.Integer(), default=0),
        sa.Column('pnl', sa.Float(), default=0.0),
        sa.Column('avg_confidence', sa.Float(), nullable=True),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_strategy_performance_strategy_name', 'strategy_performance', ['strategy_name'])
    op.create_index('ix_strategy_performance_date', 'strategy_performance', ['date'])

    # Create failure_patterns table
    op.create_table(
        'failure_patterns',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('pattern_type', sa.String(50), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('detected_at', sa.DateTime(), nullable=False),
        sa.Column('frequency', sa.Integer(), default=1),
        sa.Column('affected_trades', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('suggested_action', sa.Text(), nullable=True),
        sa.Column('resolved', sa.Boolean(), default=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_failure_patterns_pattern_type', 'failure_patterns', ['pattern_type'])
    op.create_index('ix_failure_patterns_detected_at', 'failure_patterns', ['detected_at'])
    op.create_index('ix_failure_patterns_resolved', 'failure_patterns', ['resolved'])


def downgrade() -> None:
    op.drop_table('failure_patterns')
    op.drop_table('strategy_performance')
    op.drop_table('daily_performance')
    op.drop_table('positions')
    op.drop_table('trades')
    op.execute('DROP TYPE IF EXISTS tradedirection')
'''


async def run_migrations_programmatically(database_url: str) -> None:
    """
    Run migrations programmatically without Alembic CLI.

    This is useful for testing or embedded deployments.

    Args:
        database_url: Database connection URL
    """
    from sqlalchemy.ext.asyncio import create_async_engine
    from .models import Base

    engine = create_async_engine(database_url)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    await engine.dispose()
