"""Message history manager for Songbird CLI input."""
from typing import List, Optional
from .optimized_manager import OptimizedSessionManager
from .models import Message


class MessageHistoryManager:
    
    def __init__(self, session_manager: OptimizedSessionManager):
        self.session_manager = session_manager
        self._history_cache: Optional[List[str]] = None
        self._current_index = -1
        self._original_input = ""
    
    def _load_project_user_messages(self) -> List[str]:
        """Load all user messages from current project sessions, sorted chronologically."""
        if self._history_cache is not None:
            return self._history_cache
        
        # Collect all user messages with their timestamps
        messages_with_time = []
        
        # Get all sessions for current project
        sessions_info = self.session_manager.list_sessions()
        
        for session_info in sessions_info:
            # Load full session with messages
            session = self.session_manager.load_session(session_info.id)
            if session and session.messages:
                # Extract user messages from this session with timestamps
                for i, message in enumerate(session.messages):
                    if isinstance(message, Message) and message.role == "user":
                        content = message.content.strip()
                        # Skip empty messages, command-only inputs, and very short messages
                        if (content and 
                            not content.startswith('/') and 
                            len(content) > 2):
                            # Use session creation time + message index for approximate timestamp
                            # This ensures messages are ordered correctly within and across sessions
                            timestamp = session.created_at.timestamp() + (i * 0.001)  # Add milliseconds for ordering
                            messages_with_time.append((timestamp, content))
        
        # Sort by timestamp (oldest first) and deduplicate
        messages_with_time.sort(key=lambda x: x[0])
        
        # Extract just the content, with basic deduplication
        user_messages = []
        seen_messages = set()
        for _, content in messages_with_time:
            # Simple deduplication - skip if we've seen this exact message recently
            if content not in seen_messages:
                user_messages.append(content)
                seen_messages.add(content)
                # Keep only recent messages in the seen set for rolling deduplication
                if len(seen_messages) > 50:
                    seen_messages.clear()
        
        # Reverse the list so that newest messages come first
        # This is what prompt-toolkit expects for proper up-arrow navigation
        user_messages.reverse()
        
        # Cache the results
        self._history_cache = user_messages
        return user_messages
    
    def start_navigation(self, current_input: str = "") -> str:
        self._original_input = current_input
        history = self._load_project_user_messages()
        
        if not history:
            self._current_index = -1
            return current_input
        
        # Start from the most recent message (now at index 0 since we reversed the list)
        self._current_index = 0
        return history[self._current_index]
    
    def navigate_up(self) -> Optional[str]:
        history = self._load_project_user_messages()
        
        if not history:
            return None
        
        # If we're not in navigation mode, start it
        if self._current_index == -1:
            self._current_index = 0  # Start from most recent (index 0)
            return history[self._current_index]
        
        # Move to older message (higher index since newest is at 0)
        if self._current_index < len(history) - 1:
            self._current_index += 1
            return history[self._current_index]
        
        # Already at oldest message
        return history[self._current_index] if self._current_index >= 0 else None
    
    def navigate_down(self) -> Optional[str]:
        """Navigate to next (newer) message in history, or back to original input."""
        history = self._load_project_user_messages()
        
        if not history or self._current_index == -1:
            return None
        
        # Move to newer message (lower index since newest is at 0)
        if self._current_index > 0:
            self._current_index -= 1
            return history[self._current_index]
        else:
            # Reached the newest message, go back to original input
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
        original = self._original_input
        self._current_index = -1
        self._original_input = ""
        return original
    
    def invalidate_cache(self):
        self._history_cache = None
    
    def get_history_count(self) -> int:
        history = self._load_project_user_messages()
        return len(history)
    
    def is_navigating(self) -> bool:
        return self._current_index != -1