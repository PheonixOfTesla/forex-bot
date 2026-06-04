from __future__ import annotations

"""
Lightning Bot API Module

FastAPI-based REST API for the automated trading bot.
Imports are lazy to avoid circular import issues.
"""

__all__ = ["app", "create_app"]


def __getattr__(name):
    """Lazy import to avoid circular imports."""
    if name == "app":
        from .main import app
        return app
    if name == "create_app":
        from .main import create_app
        return create_app
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
