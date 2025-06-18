"""Message history manager for Songbird CLI input."""
from typing import List, Optional
from .manager import SessionManager
from .models import Message


class MessageHistoryManager:
    """Manages message history for CLI input navigation."""
    
    def __init__(self, session_manager: SessionManager):
        """Initialize with existing SessionManager for project awareness."""
        self.session_manager = session_manager
        self._history_cache: Optional[List[str]] = None
        self._current_index = -1
        self._original_input = ""
    
    def _load_project_user_messages(self) -> List[str]:
        """Load all user messages from current project sessions."""
        if self._history_cache is not None:
            return self._history_cache
        
        user_messages = []
        
        # Get all sessions for current project
        sessions_info = self.session_manager.list_sessions()
        
        # Load full sessions to get messages, sorted by creation time
        sessions_info.sort(key=lambda s: s.created_at)
        
        for session_info in sessions_info:
            # Load full session with messages
            session = self.session_manager.load_session(session_info.id)
            if session and session.messages:
                # Extract user messages from this session
                for message in session.messages:
                    if isinstance(message, Message) and message.role == "user":
                        content = message.content.strip()
                        # Skip empty messages, command-only inputs, and very short messages
                        if (content and 
                            not content.startswith('/') and 
                            len(content) > 2 and
                            content not in user_messages[-10:]):  # Basic deduplication
                            user_messages.append(content)
        
        # Cache the results
        self._history_cache = user_messages
        return user_messages
    
    def start_navigation(self, current_input: str = "") -> str:
        """Start history navigation, return first historical message or current input."""
        self._original_input = current_input
        history = self._load_project_user_messages()
        
        if not history:
            self._current_index = -1
            return current_input
        
        # Start from the most recent message
        self._current_index = len(history) - 1
        return history[self._current_index]
    
    def navigate_up(self) -> Optional[str]:
        """Navigate to previous (older) message in history."""
        history = self._load_project_user_messages()
        
        if not history:
            return None
        
        # If we're not in navigation mode, start it
        if self._current_index == -1:
            self._current_index = len(history) - 1
            return history[self._current_index]
        
        # Move to older message
        if self._current_index > 0:
            self._current_index -= 1
            return history[self._current_index]
        
        # Already at oldest message
        return history[self._current_index] if self._current_index >= 0 else None
    
    def navigate_down(self) -> Optional[str]:
        """Navigate to next (newer) message in history, or back to original input."""
        history = self._load_project_user_messages()
        
        if not history or self._current_index == -1:
            return None
        
        # Move to newer message
        if self._current_index < len(history) - 1:
            self._current_index += 1
            return history[self._current_index]
        else:
            # Reached the end, go back to original input
            self._current_index = -1
            return self._original_input
    
    def get_current_message(self) -> str:
        """Get currently selected message or original input."""
        if self._current_index == -1:
            return self._original_input
        
        history = self._load_project_user_messages()
        if history and 0 <= self._current_index < len(history):
            return history[self._current_index]
        
        return self._original_input
    
    def reset_navigation(self) -> str:
        """Reset navigation and return to original input."""
        original = self._original_input
        self._current_index = -1
        self._original_input = ""
        return original
    
    def invalidate_cache(self):
        """Invalidate the history cache to force reload on next access."""
        self._history_cache = None
    
    def get_history_count(self) -> int:
        """Get the number of messages in history."""
        history = self._load_project_user_messages()
        return len(history)
    
    def is_navigating(self) -> bool:
        """Check if currently in navigation mode."""
        return self._current_index != -1