"""Comprehensive aiohttp session manager to prevent unclosed session warnings."""

import asyncio
import logging
import aiohttp
import weakref
import gc
from typing import Optional, Set
import atexit

logger = logging.getLogger(__name__)


class AIOHTTPSessionManager:
    """
    Singleton aiohttp session manager that prevents unclosed session warnings.
    
    This manager creates and manages aiohttp.ClientSession instances that can be
    reused across different components, ensuring proper cleanup during shutdown.
    """
    
    _instance: Optional['AIOHTTPSessionManager'] = None
    _session: Optional[aiohttp.ClientSession] = None
    _lock = asyncio.Lock()
    _cleanup_registered = False
    _all_sessions: Set[weakref.ref] = set()
    
    def __new__(cls) -> 'AIOHTTPSessionManager':
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not hasattr(self, '_initialized'):
            self._initialized = True
            if not AIOHTTPSessionManager._cleanup_registered:
                atexit.register(self._cleanup_on_exit)
                AIOHTTPSessionManager._cleanup_registered = True
    
    async def get_session(self) -> aiohttp.ClientSession:
        async with AIOHTTPSessionManager._lock:
            if AIOHTTPSessionManager._session is None or AIOHTTPSessionManager._session.closed:
                logger.debug("Creating new aiohttp session")
                
                # Configure session with reasonable defaults
                timeout = aiohttp.ClientTimeout(
                    total=300,  # 5 minutes total timeout
                    connect=30,  # 30 seconds to connect
                    sock_read=60  # 60 seconds to read response
                )
                
                connector = aiohttp.TCPConnector(
                    limit=100,  # Total connection limit
                    limit_per_host=10,  # Per-host connection limit
                    ttl_dns_cache=300,  # DNS cache TTL
                    use_dns_cache=True,
                    keepalive_timeout=30,
                    enable_cleanup_closed=True  # Clean up closed connections
                )
                
                AIOHTTPSessionManager._session = aiohttp.ClientSession(
                    timeout=timeout,
                    connector=connector,
                    headers={
                        'User-Agent': 'Songbird-AI/1.0 (aiohttp Client)'
                    }
                )
                
                # Track this session for comprehensive cleanup
                session_ref = weakref.ref(AIOHTTPSessionManager._session, self._session_cleanup_callback)
                AIOHTTPSessionManager._all_sessions.add(session_ref)
                
                logger.debug(f"Created aiohttp session: {id(AIOHTTPSessionManager._session)}")
            
            return AIOHTTPSessionManager._session
    
    def _session_cleanup_callback(self, ref):
        AIOHTTPSessionManager._all_sessions.discard(ref)
    
    async def close_session(self) -> None:
        """
        Close the managed aiohttp session if it exists.
        """
        async with AIOHTTPSessionManager._lock:
            if AIOHTTPSessionManager._session and not AIOHTTPSessionManager._session.closed:
                logger.debug(f"Closing managed aiohttp session: {id(AIOHTTPSessionManager._session)}")
                
                session = AIOHTTPSessionManager._session
                AIOHTTPSessionManager._session = None
                
                # Use the official aiohttp cleanup pattern
                await session.close()
                
                # Wait for underlying SSL connections to close
                await asyncio.sleep(0.250)
                
                logger.debug("Managed aiohttp session closed successfully")
    
    async def close_all_sessions(self) -> None:
        """
        Close all aiohttp sessions we can find - comprehensive cleanup.
        """
        sessions_closed = 0
        
        # Close our managed session first
        await self.close_session()
        
        # Find and close any other aiohttp sessions using garbage collection
        try:
            for obj in gc.get_objects():
                if isinstance(obj, aiohttp.ClientSession) and not obj.closed:
                    try:
                        logger.debug(f"Found and closing orphaned aiohttp session: {id(obj)}")
                        await obj.close()
                        
                        # Also close the connector to prevent socket warnings
                        if hasattr(obj, 'connector') and obj.connector:
                            try:
                                await obj.connector.close()
                            except Exception as conn_error:
                                logger.debug(f"Error closing orphaned connector: {conn_error}")
                        
                        sessions_closed += 1
                        # Small delay between closures
                        await asyncio.sleep(0.05)
                    except Exception as e:
                        logger.debug(f"Error closing orphaned session {id(obj)}: {e}")
        except Exception as e:
            logger.debug(f"Error during comprehensive session cleanup: {e}")
        
        if sessions_closed > 0:
            logger.debug(f"Closed {sessions_closed} orphaned aiohttp sessions")
        
        # Clear our session tracking
        AIOHTTPSessionManager._all_sessions.clear()
        
        # Suppress socket ResourceWarnings during cleanup
        import warnings
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=ResourceWarning, message=".*unclosed.*socket.*")
            
            # Force garbage collection to trigger any remaining cleanup
            gc.collect()
            
            # Give time for all cleanup to complete
            await asyncio.sleep(0.2)
            
            # Force another garbage collection to ensure everything is cleaned up
            gc.collect()
    
    def _cleanup_on_exit(self) -> None:
        """
        Cleanup handler called during Python exit.
        
        During exit, avoid async operations and just clear references.
        """
        try:
            # During Python exit, don't run async operations
            # Just clear session references and suppress warnings
            import warnings
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", category=ResourceWarning)
                warnings.filterwarnings("ignore", category=RuntimeWarning)
                
                # Clear session references
                if AIOHTTPSessionManager._session:
                    AIOHTTPSessionManager._session = None
                
                AIOHTTPSessionManager._all_sessions.clear()
                logger.debug("aiohttp session references cleared during exit")
                
        except Exception:
            # Don't let cleanup errors prevent shutdown
            pass
    
    async def health_check(self) -> bool:
        """
        Check if the current session is healthy.
        
        Returns:
            bool: True if session exists and is not closed
        """
        async with AIOHTTPSessionManager._lock:
            return (AIOHTTPSessionManager._session is not None and 
                   not AIOHTTPSessionManager._session.closed)
    
    async def reset_session(self) -> None:
        await self.close_session()
        logger.debug("aiohttp session reset completed")
    
    async def configure_google_genai_session(self) -> None:
        """
        Configure Google GenAI SDK to use our managed aiohttp session.
        This should be called after we have a session available.
        """
        try:
            # Try to configure Google GenAI to use our session
            import google.generativeai as genai
            import os
            
            # Get our managed session
            session = await self.get_session()
            
            # Try different configuration approaches based on SDK version
            try:
                # Newer SDK approach with HttpOptions
                from google.genai import types
                
                http_options = types.HttpOptions(
                    async_client_args={
                        'session': session  # Pass our managed aiohttp session
                    }
                )
                
                # Configure GenAI with custom HTTP options
                genai.configure(
                    api_key=os.getenv("GEMINI_API_KEY"),
                    http_options=http_options
                )
                
                logger.debug(f"Configured Google GenAI to use managed aiohttp session: {id(session)}")
                
            except (ImportError, AttributeError):
                # Fallback for older SDK versions or different configuration methods
                logger.debug("Google GenAI SDK HttpOptions not available, trying alternative configuration")
                
                # Check if there's a direct session configuration method
                if hasattr(genai, '_http_client'):
                    genai._http_client = session
                    logger.debug("Configured Google GenAI SDK via _http_client attribute")
                else:
                    logger.debug("Google GenAI SDK doesn't support custom session configuration")
                
        except ImportError:
            # Google GenAI not installed, skip configuration
            logger.debug("Google GenAI SDK not available, skipping session configuration")
        except Exception as e:
            logger.debug(f"Error configuring Google GenAI session: {e}")
    
    def configure_google_genai_session_sync(self) -> None:
        """
        Synchronous wrapper to configure Google GenAI session.
        Schedules the async configuration for the next event loop iteration.
        """
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If loop is running, schedule as a task
                loop.create_task(self.configure_google_genai_session())
            else:
                # If no loop is running, run synchronously
                loop.run_until_complete(self.configure_google_genai_session())
        except RuntimeError:
            # No event loop available, will configure later when needed
            logger.debug("No event loop available for Google GenAI configuration, will configure on demand")


# Global instance for easy access
aiohttp_session_manager = AIOHTTPSessionManager()


async def get_managed_aiohttp_session() -> aiohttp.ClientSession:
    return await aiohttp_session_manager.get_session()


async def close_managed_aiohttp_session() -> None:
    await aiohttp_session_manager.close_all_sessions()


def configure_google_genai_aiohttp() -> None:
    aiohttp_session_manager.configure_google_genai_session_sync()


# Monkey patch detection and warning
def detect_aiohttp_session_creation():
    original_init = aiohttp.ClientSession.__init__
    
    def patched_init(self, *args, **kwargs):
        logger.debug(f"New aiohttp.ClientSession created: {id(self)} from {get_caller_info()}")
        return original_init(self, *args, **kwargs)
    
    aiohttp.ClientSession.__init__ = patched_init


def get_caller_info() -> str:
    import inspect
    try:
        frame = inspect.currentframe()
        # Go up the stack to find the caller
        for _ in range(3):  # Skip this function, patched_init, and __init__
            frame = frame.f_back
            if frame is None:
                break
        
        if frame:
            filename = frame.f_code.co_filename
            lineno = frame.f_lineno
            function = frame.f_code.co_name
            return f"{filename}:{lineno} in {function}"
        else:
            return "unknown"
    except Exception:
        return "unknown"


# Optional: Enable session creation detection for debugging
# Uncomment the line below to track all aiohttp session creation
# detect_aiohttp_session_creation()