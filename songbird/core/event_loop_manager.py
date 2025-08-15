# songbird/core/event_loop_manager.py
"""Event loop lifecycle management to prevent cleanup errors during shutdown."""

import asyncio
import atexit
import logging
import threading
import weakref
from typing import Optional, Set

logger = logging.getLogger(__name__)


class EventLoopManager:
    """
    Manages asyncio event loop lifecycle to prevent cleanup errors during shutdown.
    This manager ensures that event loops are properly closed before Python interpreter
    """
    
    _instance: Optional['EventLoopManager'] = None
    _current_loop: Optional[asyncio.AbstractEventLoop] = None
    _cleanup_registered = False
    _tracked_loops: Set[weakref.ref] = set()
    _lock = threading.Lock()
    
    def __new__(cls) -> 'EventLoopManager':
        """Ensure singleton pattern."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """Initialize the event loop manager."""
        if not hasattr(self, '_initialized'):
            self._initialized = True
            if not EventLoopManager._cleanup_registered:
                atexit.register(self._cleanup_on_exit)
                EventLoopManager._cleanup_registered = True
    
    def register_loop(self, loop: Optional[asyncio.AbstractEventLoop] = None) -> None:
        """
        Register an event loop for cleanup tracking.
        """
        with EventLoopManager._lock:
            if loop is None:
                try:
                    loop = asyncio.get_running_loop()
                except RuntimeError:
                    try:
                        loop = asyncio.get_event_loop()
                    except RuntimeError:
                        return
            
            if loop:
                EventLoopManager._current_loop = loop
                
                def cleanup_callback(ref):
                    EventLoopManager._tracked_loops.discard(ref)
                
                loop_ref = weakref.ref(loop, cleanup_callback)
                EventLoopManager._tracked_loops.add(loop_ref)
                
                logger.debug(f"Registered event loop for cleanup: {id(loop)}")
    
    def close_loop_safely(self, loop: asyncio.AbstractEventLoop) -> None:
        """
        Safely close an event loop with proper error handling.
        """
        try:
            if loop and not loop.is_closed():
                logger.debug(f"Closing event loop: {id(loop)}")
                
                if hasattr(loop, 'all_tasks'):
                    pending_tasks = [task for task in asyncio.all_tasks(loop) if not task.done()]
                else:
                    pending_tasks = [task for task in asyncio.Task.all_tasks(loop) if not task.done()]
                
                if pending_tasks:
                    logger.debug(f"Cancelling {len(pending_tasks)} pending tasks")
                    for task in pending_tasks:
                        task.cancel()
                    
                    # Give tasks a moment to cancel
                    try:
                        loop.run_until_complete(asyncio.gather(*pending_tasks, return_exceptions=True))
                    except Exception as e:
                        logger.debug(f"Error waiting for task cancellation: {e}")
                
                # Close the loop
                loop.close()
                logger.debug(f"Event loop {id(loop)} closed successfully")
                
        except Exception as e:
            logger.debug(f"Error closing event loop {id(loop) if loop else 'None'}: {e}")
    
    def cleanup_all_loops(self) -> None:
        """
        Clean up all tracked event loops.
        """
        with EventLoopManager._lock:
            loops_closed = 0
            
            # Close the current loop first
            if EventLoopManager._current_loop:
                self.close_loop_safely(EventLoopManager._current_loop)
                loops_closed += 1
                EventLoopManager._current_loop = None
            
            # Close any other tracked loops
            for loop_ref in list(EventLoopManager._tracked_loops):
                loop = loop_ref()
                if loop:
                    self.close_loop_safely(loop)
                    loops_closed += 1
            
            EventLoopManager._tracked_loops.clear()
            
            if loops_closed > 0:
                logger.debug(f"Closed {loops_closed} event loops during cleanup")
    
    def _cleanup_on_exit(self) -> None:
        """
        Cleanup handler called during Python exit.
        
        This runs synchronously during exit and should clean up all event loops.
        """
        try:
            logger.debug("Event loop manager cleanup on exit")
            self.cleanup_all_loops()
        except Exception as e:
            # Don't let cleanup errors prevent shutdown
            logger.debug(f"Error during event loop cleanup: {e}")
    
    @classmethod
    def ensure_clean_shutdown(cls) -> None:
        """
        Ensure clean shutdown of the current event loop.
        Call this at the end of your main async function.
        """
        try:
            loop = asyncio.get_running_loop()
            manager = cls()
            manager.register_loop(loop)
        except RuntimeError:
            # No running loop, nothing to clean up
            pass


# Global instance for easy access
event_loop_manager = EventLoopManager()


def register_current_loop() -> None:
    """
    Convenience function to register the current event loop for cleanup.
    """
    event_loop_manager.register_loop()


def ensure_clean_shutdown() -> None:
    EventLoopManager.ensure_clean_shutdown()


def close_all_loops() -> None:
    event_loop_manager.cleanup_all_loops()


class ManagedEventLoop:
    """
    Context manager for safe event loop usage with automatic cleanup.
    """
    
    def __init__(self):
        self.loop = None
        self.manager = event_loop_manager
    
    async def __aenter__(self):
        """Enter the async context manager."""
        try:
            self.loop = asyncio.get_running_loop()
            self.manager.register_loop(self.loop)
        except RuntimeError:
            # No running loop
            pass
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit the async context manager with cleanup."""
        if self.loop:
            # Don't close the loop here, let the manager handle it during shutdown
            pass


def managed_async_main(func):
    """
    Decorator to ensure proper event loop cleanup for main async functions.
    
    Usage:
        @managed_async_main
        async def main():
            # Your async code here
            pass
        
        if __name__ == "__main__":
            asyncio.run(main())
    """
    async def wrapper(*args, **kwargs):
        async with ManagedEventLoop():
            return await func(*args, **kwargs)
    return wrapper