"""
Vercel Serverless Function Entry Point

This module imports and exposes the full FastAPI application
from src/api/main.py for Vercel deployment.
"""

# Import the full FastAPI app with all routes
from src.api.main import app

# Vercel expects the app variable to be available
__all__ = ["app"]
