# songbird/core/__init__.py
"""Core infrastructure components for Songbird."""

from .signal_handler import (
    GracefulShutdownHandler,
    SessionAwareShutdownHandler,
    get_shutdown_handler,
    setup_graceful_shutdown,
    register_shutdown_callback,
    cleanup_shutdown_handler
)

__all__ = [
    "GracefulShutdownHandler",
    "SessionAwareShutdownHandler",
    "get_shutdown_handler",
    "setup_graceful_shutdown",
    "register_shutdown_callback",
    "cleanup_shutdown_handler"
]