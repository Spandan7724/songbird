# songbird/llm/http_session_manager.py
"""HTTP session manager for proper httpx session lifecycle management."""

import asyncio
import logging
import httpx
from typing import Optional
import atexit

logger = logging.getLogger(__name__)


class HTTPSessionManager:
    """
    Singleton HTTP session manager that ensures proper cleanup of httpx sessions.
    
    This manager creates a single httpx.AsyncClient that can be reused across
    all LiteLLM calls, preventing resource leaks and unclosed session warnings.
    """
    
    _instance: Optional['HTTPSessionManager'] = None
    _session: Optional[httpx.AsyncClient] = None
    _lock = asyncio.Lock()
    _cleanup_registered = False
    
    def __new__(cls) -> 'HTTPSessionManager':
        """Ensure singleton pattern."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """Initialize the session manager."""
        if not hasattr(self, '_initialized'):
            self._initialized = True
            # Register cleanup handler only once
            if not HTTPSessionManager._cleanup_registered:
                atexit.register(self._cleanup_on_exit)
                HTTPSessionManager._cleanup_registered = True
    
    async def get_session(self) -> httpx.AsyncClient:
        """
        Get or create the singleton HTTP session.
        
        Returns:
            httpx.AsyncClient: Configured HTTP session
        """
        async with HTTPSessionManager._lock:
            if HTTPSessionManager._session is None or HTTPSessionManager._session.is_closed:
                logger.debug("Creating new HTTP session")
                
                # Configure session with reasonable defaults
                timeout = httpx.Timeout(
                    timeout=300.0,  # 5 minutes total timeout
                    connect=30.0,   # 30 seconds to connect
                    read=60.0       # 60 seconds to read response
                )
                
                limits = httpx.Limits(
                    max_connections=100,        # Total connection limit
                    max_keepalive_connections=20,  # Keepalive connections
                    keepalive_expiry=30.0       # Keepalive timeout
                )
                
                HTTPSessionManager._session = httpx.AsyncClient(
                    timeout=timeout,
                    limits=limits,
                    headers={
                        'User-Agent': 'Songbird-AI/1.0 (LiteLLM HTTP Client)'
                    }
                )
                
                logger.debug(f"Created HTTP session: {id(HTTPSessionManager._session)}")
            
            return HTTPSessionManager._session
    
    async def close_session(self) -> None:
        """
        Close the HTTP session if it exists.
        """
        async with HTTPSessionManager._lock:
            if HTTPSessionManager._session and not HTTPSessionManager._session.is_closed:
                logger.debug(f"Closing HTTP session: {id(HTTPSessionManager._session)}")
                await HTTPSessionManager._session.aclose()
                
                # Give time for connections to close properly
                await asyncio.sleep(0.1)
                
                HTTPSessionManager._session = None
                logger.debug("HTTP session closed successfully")
    
    def _cleanup_on_exit(self) -> None:
        """
        Cleanup handler called during Python exit.
        
        This runs synchronously during exit, so we need to handle async cleanup.
        """
        try:
            # Try to get the current event loop
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If loop is running, schedule cleanup as a task
                loop.create_task(self.close_session())
            else:
                # If no loop is running, run cleanup synchronously
                loop.run_until_complete(self.close_session())
        except RuntimeError:
            # No event loop available, try to create one
            try:
                asyncio.run(self.close_session())
            except Exception as e:
                # Final fallback - at least log the issue
                logger.debug(f"Could not close HTTP session during exit: {e}")
    
    async def health_check(self) -> bool:
        """
        Check if the current session is healthy.
        
        Returns:
            bool: True if session exists and is not closed
        """
        async with HTTPSessionManager._lock:
            return (HTTPSessionManager._session is not None and 
                   not HTTPSessionManager._session.is_closed)
    
    async def reset_session(self) -> None:
        """
        Force reset the session (close current and create new on next get).
        """
        await self.close_session()
        logger.debug("HTTP session reset completed")


# Global instance for easy access
session_manager = HTTPSessionManager()


async def get_managed_session() -> httpx.AsyncClient:
    """
    Convenience function to get the managed HTTP session.
    
    Returns:
        httpx.AsyncClient: The singleton managed session
    """
    return await session_manager.get_session()


async def close_managed_session() -> None:
    """
    Convenience function to close the managed HTTP session.
    """
    await session_manager.close_session()