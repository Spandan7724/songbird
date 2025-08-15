import asyncio
import logging
import httpx
from typing import Optional

logger = logging.getLogger(__name__)


class HTTPSessionManager:
    """
    Singleton HTTP session manager that ensures proper cleanup of httpx sessions.
    """
    
    _instance: Optional['HTTPSessionManager'] = None
    _session: Optional[httpx.AsyncClient] = None
    _lock = asyncio.Lock()
    _cleanup_registered = False
    
    def __new__(cls) -> 'HTTPSessionManager':
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not hasattr(self, '_initialized'):
            self._initialized = True
            HTTPSessionManager._cleanup_registered = True
    
    async def get_session(self) -> httpx.AsyncClient:
        """
        Get or create the singleton HTTP session.
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
        
        This runs synchronously during exit, so we need to handle async cleanup carefully.
        """
        try:
            # During exit, we should avoid async operations that might fail
            # Instead, just mark the session as None and let garbage collection handle it
            if HTTPSessionManager._session and not HTTPSessionManager._session.is_closed:
                try:
                    # Try a synchronous close if possible
                    import warnings
                    with warnings.catch_warnings():
                        warnings.filterwarnings("ignore", category=RuntimeWarning)
                        # Don't try to run async code during exit - just clear the reference
                        HTTPSessionManager._session = None
                        logger.debug("HTTP session reference cleared during exit")
                except Exception as e:
                    logger.debug(f"Error during exit cleanup: {e}")
        except Exception:
            # Don't let cleanup errors prevent shutdown
            pass
    
    async def health_check(self) -> bool:
        async with HTTPSessionManager._lock:
            return (HTTPSessionManager._session is not None and 
                   not HTTPSessionManager._session.is_closed)
    
    async def reset_session(self) -> None:
        await self.close_session()
        logger.debug("HTTP session reset completed")


# Global instance for easy access
session_manager = HTTPSessionManager()


async def get_managed_session() -> httpx.AsyncClient:
    return await session_manager.get_session()


async def close_managed_session() -> None:
    await session_manager.close_session()