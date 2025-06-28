# Updated songbird/memory/models.py with provider configuration

"""Data models for session memory."""
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Any, Optional
import uuid


@dataclass
class Message:
    """Represents a single message in the conversation."""
    role: str  # "user", "assistant", "system", "tool"
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    tool_calls: Optional[List[Dict[str, Any]]] = None
    tool_call_id: Optional[str] = None
    name: Optional[str] = None  # For tool messages

    def to_dict(self) -> Dict[str, Any]:
        """Convert message to dictionary for storage."""
        data = {
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp.isoformat()
        }
        if self.tool_calls:
            data["tool_calls"] = self.tool_calls
        if self.tool_call_id:
            data["tool_call_id"] = self.tool_call_id
        if self.name:
            data["name"] = self.name
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Message":
        """Create message from dictionary."""
        timestamp = datetime.fromisoformat(data["timestamp"])
        return cls(
            role=data["role"],
            content=data["content"],
            timestamp=timestamp,
            tool_calls=data.get("tool_calls"),
            tool_call_id=data.get("tool_call_id"),
            name=data.get("name")
        )


@dataclass
class Session:
    """Represents a chat session."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    messages: List[Message] = field(default_factory=list)
    summary: str = ""
    project_path: str = ""
    # Add provider configuration
    provider_config: Dict[str, Any] = field(default_factory=dict)
    schema_version: str = "1.0"  # Version for serialization compatibility

    def to_dict(self) -> Dict[str, Any]:
        """Convert session to dictionary for storage."""
        return {
            "id": self.id,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "messages": [msg.to_dict() for msg in self.messages],
            "summary": self.summary,
            "project_path": self.project_path,
            "provider_config": self.provider_config,  # Save provider config
            "schema_version": self.schema_version  # Include schema version
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Session":
        """Create session from dictionary."""
        return cls(
            id=data["id"],
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            messages=[Message.from_dict(msg)
                      for msg in data.get("messages", [])],
            summary=data.get("summary", ""),
            project_path=data.get("project_path", ""),
            # Load provider config
            provider_config=data.get("provider_config", {}),
            schema_version=data.get("schema_version", "1.0")  # Default to 1.0 for compatibility
        )

    def add_message(self, message: Message):
        """Add a message to the session."""
        self.messages.append(message)
        self.updated_at = datetime.now()

    def get_message_count(self) -> int:
        """Get the number of messages in the session."""
        return len(self.messages)

    def generate_summary(self, max_words: int = 10) -> str:
        """Generate a summary based on user messages."""
        # Get first few user messages
        user_messages = [
            msg for msg in self.messages if msg.role == "user"][:3]

        if not user_messages:
            return "Empty session"

        # Simple summary from first user message
        first_msg = user_messages[0].content
        words = first_msg.split()[:max_words]
        summary = " ".join(words)

        if len(first_msg.split()) > max_words:
            summary += "..."

        return summary

    def update_provider_config(self, provider: str, model: str, provider_type: str = "legacy"):
        """Update the provider configuration for this session."""
        self.provider_config = {
            "provider": provider,
            "model": model,
            "provider_type": provider_type,  # "legacy" or "litellm"
            "updated_at": datetime.now().isoformat()
        }
        self.updated_at = datetime.now()
    
    def update_litellm_config(self, provider: str, model: str, litellm_model: str, api_base: Optional[str] = None):
        """Update the provider configuration for LiteLLM usage."""
        self.provider_config = {
            "provider": provider,
            "model": model,
            "provider_type": "litellm",
            "litellm_model": litellm_model,  # The full LiteLLM model string like "openai/gpt-4o"
            "api_base": api_base,
            "updated_at": datetime.now().isoformat()
        }
        self.updated_at = datetime.now()
    
    def get_provider_type(self) -> str:
        """Get the provider type (legacy or litellm)."""
        return self.provider_config.get("provider_type", "legacy")
    
    def get_litellm_model(self) -> Optional[str]:
        """Get the LiteLLM model string if using LiteLLM."""
        if self.get_provider_type() == "litellm":
            return self.provider_config.get("litellm_model")
        return None
    
    def get_api_base(self) -> Optional[str]:
        """Get the API base URL if specified."""
        return self.provider_config.get("api_base")
    
    def is_litellm_session(self) -> bool:
        """Check if this session is using LiteLLM."""
        return self.get_provider_type() == "litellm"
