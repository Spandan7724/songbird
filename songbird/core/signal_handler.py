"""Signal handling for graceful shutdown of Songbird."""

import signal
import sys
import asyncio
from typing import Optional, Callable, Dict
from rich.console import Console


class GracefulShutdownHandler:
    """Handles graceful shutdown on SIGINT and SIGTERM signals."""
    
    def __init__(self, console: Optional[Console] = None):
        self.console = console or Console()
        self.shutdown_callbacks: Dict[str, Callable] = {}
        self.is_shutting_down = False
        self.original_handlers = {}
        
        # Track if we're in an async context
        self.async_context = False
        
        # Register default signal handlers
        self.setup_signal_handlers()
    
    def setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown."""
        # Store original handlers
        self.original_handlers[signal.SIGINT] = signal.signal(signal.SIGINT, self._signal_handler)
        self.original_handlers[signal.SIGTERM] = signal.signal(signal.SIGTERM, self._signal_handler)
        
        # On Windows, also handle SIGBREAK
        if sys.platform == "win32":
            try:
                self.original_handlers[signal.SIGBREAK] = signal.signal(signal.SIGBREAK, self._signal_handler)
            except AttributeError:
                # SIGBREAK might not be available
                pass
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        if self.is_shutting_down:
            # Force exit if we get another signal during shutdown
            self.console.print(f"\n[red]Force shutdown requested (signal {signum})[/red]")
            sys.exit(1)
        
        self.is_shutting_down = True
        
        signal_names = {
            signal.SIGINT: "SIGINT (Ctrl+C)",
            signal.SIGTERM: "SIGTERM",
        }
        
        if sys.platform == "win32":
            signal_names[signal.SIGBREAK] = "SIGBREAK (Ctrl+Break)"
        
        signal_name = signal_names.get(signum, f"signal {signum}")
        
        self.console.print(f"\n[yellow]Received {signal_name}. Shutting down gracefully...[/yellow]")
        
        # Check if we're in an async context
        try:
            loop = asyncio.get_running_loop()
            if loop and loop.is_running():
                # We're in an async context, schedule the shutdown
                loop.create_task(self._async_shutdown())
                return
        except RuntimeError:
            # No running event loop, proceed with sync shutdown
            pass
        
        # Synchronous shutdown
        self._sync_shutdown()
        sys.exit(0)
    
    async def _async_shutdown(self):
        try:
            # Execute async shutdown callbacks
            for name, callback in self.shutdown_callbacks.items():
                try:
                    self.console.print(f"[dim]Shutting down {name}...[/dim]")
                    if asyncio.iscoroutinefunction(callback):
                        await callback()
                    else:
                        callback()
                except Exception as e:
                    self.console.print(f"[red]Error during {name} shutdown: {e}[/red]")
            
            self.console.print("[green]Graceful shutdown completed[/green]")
            
        except Exception as e:
            self.console.print(f"[red]Error during async shutdown: {e}[/red]")
        finally:
            # Stop the event loop
            loop = asyncio.get_running_loop()
            loop.stop()
    
    def _sync_shutdown(self):
        """Perform synchronous shutdown tasks."""
        try:
            # Execute sync shutdown callbacks
            for name, callback in self.shutdown_callbacks.items():
                try:
                    self.console.print(f"[dim]Shutting down {name}...[/dim]")
                    if not asyncio.iscoroutinefunction(callback):
                        callback()
                    else:
                        self.console.print(f"[yellow]Skipping async callback {name} in sync shutdown[/yellow]")
                except Exception as e:
                    self.console.print(f"[red]Error during {name} shutdown: {e}[/red]")
            
            self.console.print("[green]Graceful shutdown completed[/green]")
            
        except Exception as e:
            self.console.print(f"[red]Error during sync shutdown: {e}[/red]")
    
    def register_shutdown_callback(self, name: str, callback: Callable):
        self.shutdown_callbacks[name] = callback
    
    def unregister_shutdown_callback(self, name: str):
        if name in self.shutdown_callbacks:
            del self.shutdown_callbacks[name]
    
    def enable_async_mode(self):
        self.async_context = True
    
    def restore_original_handlers(self):
        for signum, handler in self.original_handlers.items():
            signal.signal(signum, handler)
    
    def force_shutdown(self):
        self.console.print("[red]Force shutdown initiated[/red]")
        self.restore_original_handlers()
        sys.exit(1)


class SessionAwareShutdownHandler(GracefulShutdownHandler):

    def __init__(self, session_manager=None, console: Optional[Console] = None):
        super().__init__(console)
        self.session_manager = session_manager
        
        # Register session manager shutdown if provided
        if session_manager:
            self.register_session_manager(session_manager)
    
    def register_session_manager(self, session_manager):
        self.session_manager = session_manager
        
        # Register appropriate shutdown callback
        if hasattr(session_manager, 'shutdown'):
            self.register_shutdown_callback("session_manager", session_manager.shutdown)
        elif hasattr(session_manager, 'flush_all_sessions'):
            self.register_shutdown_callback("session_manager", session_manager.flush_all_sessions)
        elif hasattr(session_manager, '_flush_all_sessions_sync'):
            self.register_shutdown_callback("session_manager", session_manager._flush_all_sessions_sync)
    
    def register_conversation(self, conversation):
        if hasattr(conversation, 'cleanup'):
            self.register_shutdown_callback("conversation", conversation.cleanup)
    
    def register_ui_layer(self, ui_layer):
        if hasattr(ui_layer, 'cleanup'):
            self.register_shutdown_callback("ui_layer", ui_layer.cleanup)


# Global shutdown handler instance
_global_shutdown_handler: Optional[GracefulShutdownHandler] = None


def get_shutdown_handler() -> GracefulShutdownHandler:
    global _global_shutdown_handler
    if _global_shutdown_handler is None:
        _global_shutdown_handler = GracefulShutdownHandler()
    return _global_shutdown_handler


def setup_graceful_shutdown(
    session_manager=None,
    console: Optional[Console] = None,
    enable_async: bool = True
) -> SessionAwareShutdownHandler:
    handler = SessionAwareShutdownHandler(session_manager, console)
    
    if enable_async:
        handler.enable_async_mode()
    
    # Set as global handler
    global _global_shutdown_handler
    _global_shutdown_handler = handler
    
    return handler


def register_shutdown_callback(name: str, callback: Callable):
    handler = get_shutdown_handler()
    handler.register_shutdown_callback(name, callback)


def cleanup_shutdown_handler():
    global _global_shutdown_handler
    if _global_shutdown_handler:
        _global_shutdown_handler.restore_original_handlers()
        _global_shutdown_handler = None