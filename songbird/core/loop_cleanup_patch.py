import asyncio
import atexit
import logging
import warnings

logger = logging.getLogger(__name__)

_original_del = None
_original_close = None
_cleanup_applied = False


def safe_event_loop_del(self):
    try:
        if not self.is_closed():
            warnings.warn(f"unclosed event loop {self!r}", ResourceWarning, source=self)
            if not self.is_running():
                self.close()
    except Exception:
        pass


def safe_event_loop_close(self):
    try:
        if _original_close:
            _original_close(self)
    except ValueError as e:
        if "Invalid file descriptor" in str(e):
            pass
        else:
            raise
    except Exception:
        logger.debug(f"Error closing event loop: {e}")


def apply_event_loop_cleanup_patch():
    global _original_del, _original_close, _cleanup_applied
    
    if _cleanup_applied:
        return
    
    try:
        # Store original methods
        _original_del = asyncio.BaseEventLoop.__del__
        _original_close = asyncio.BaseEventLoop.close
        
        # Apply patches
        asyncio.BaseEventLoop.__del__ = safe_event_loop_del
        asyncio.BaseEventLoop.close = safe_event_loop_close
        
        _cleanup_applied = True
        logger.debug("Applied event loop cleanup patches")
        
    except Exception as e:
        logger.debug(f"Failed to apply event loop cleanup patches: {e}")


def remove_event_loop_cleanup_patch():
    global _original_del, _original_close, _cleanup_applied
    
    if not _cleanup_applied:
        return
    
    try:
        # Restore original methods
        if _original_del:
            asyncio.BaseEventLoop.__del__ = _original_del
        if _original_close:
            asyncio.BaseEventLoop.close = _original_close
        
        _cleanup_applied = False
        logger.debug("Removed event loop cleanup patches")
        
    except Exception as e:
        logger.debug(f"Failed to remove event loop cleanup patches: {e}")


def suppress_event_loop_warnings():
    # Suppress ResourceWarnings about unclosed event loops
    warnings.filterwarnings("ignore", category=ResourceWarning, message=".*unclosed event loop.*")
    
    # Suppress ResourceWarnings about unclosed sockets (common during shutdown)
    warnings.filterwarnings("ignore", category=ResourceWarning, message=".*unclosed.*socket.*")
    
    # Suppress specific asyncio warnings
    warnings.filterwarnings("ignore", category=RuntimeWarning, module="asyncio")
    
    # Suppress LiteLLM async client cleanup warnings
    warnings.filterwarnings("ignore", category=RuntimeWarning, message=".*close_litellm_async_clients.*never awaited.*")
    warnings.filterwarnings("ignore", category=RuntimeWarning, module="litellm")


# Automatic application of patches
def auto_apply_patches():
    """
    Automatically apply patches when this module is imported.
    """
    apply_event_loop_cleanup_patch()
    suppress_event_loop_warnings()
    
    # Register cleanup for exit
    atexit.register(cleanup_on_exit)


def cleanup_on_exit():
    """
    Cleanup function called during exit.
    """
    try:
        # Close any remaining event loops safely
        import gc
        
        for obj in gc.get_objects():
            if isinstance(obj, asyncio.AbstractEventLoop) and not obj.is_closed():
                try:
                    if not obj.is_running():
                        obj.close()
                except Exception:
                    # Silently ignore errors during exit cleanup
                    pass
    except Exception:
        # Don't let cleanup errors prevent shutdown
        pass


# Apply patches automatically when imported
auto_apply_patches()