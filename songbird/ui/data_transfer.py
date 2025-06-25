# songbird/ui/data_transfer.py
"""Data transfer objects for clean UI layer communication."""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from enum import Enum


class MessageType(Enum):
    """Types of UI messages."""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL_RESULT = "tool_result"
    ERROR = "error"


class UIChoiceType(Enum):
    """Types of UI choices."""
    SINGLE_SELECT = "single_select"
    MULTI_SELECT = "multi_select"
    CONFIRM = "confirm"
    TEXT_INPUT = "text_input"


@dataclass
class UIMessage:
    """Message to be displayed by the UI layer."""
    content: str
    message_type: MessageType
    metadata: Optional[Dict[str, Any]] = None
    
    @classmethod
    def user(cls, content: str, **metadata) -> 'UIMessage':
        return cls(content, MessageType.USER, metadata)
    
    @classmethod
    def assistant(cls, content: str, **metadata) -> 'UIMessage':
        return cls(content, MessageType.ASSISTANT, metadata)
    
    @classmethod
    def system(cls, content: str, **metadata) -> 'UIMessage':
        return cls(content, MessageType.SYSTEM, metadata)
    
    @classmethod
    def tool_result(cls, content: str, **metadata) -> 'UIMessage':
        return cls(content, MessageType.TOOL_RESULT, metadata)
    
    @classmethod
    def error(cls, content: str, **metadata) -> 'UIMessage':
        return cls(content, MessageType.ERROR, metadata)


@dataclass
class UIResponse:
    """Response from user interaction."""
    content: str
    response_type: str = "text"
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class UIChoice:
    """Choice prompt configuration."""
    prompt: str
    options: List[str]
    choice_type: UIChoiceType = UIChoiceType.SINGLE_SELECT
    default_index: int = 0
    allow_cancel: bool = True
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class AgentOutput:
    """Output from agent core to UI layer."""
    message: Optional[UIMessage] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None
    needs_user_input: bool = False
    choice_prompt: Optional[UIChoice] = None
    is_complete: bool = False
    error: Optional[str] = None
    
    @classmethod
    def message_only(cls, message: UIMessage) -> 'AgentOutput':
        return cls(message=message)
    
    @classmethod
    def tool_calls(cls, tool_calls: List[Dict[str, Any]]) -> 'AgentOutput':
        return cls(tool_calls=tool_calls)
    
    @classmethod
    def user_input_needed(cls, choice_prompt: Optional[UIChoice] = None) -> 'AgentOutput':
        return cls(needs_user_input=True, choice_prompt=choice_prompt)
    
    @classmethod
    def completion(cls, final_message: Optional[UIMessage] = None) -> 'AgentOutput':
        return cls(message=final_message, is_complete=True)
    
    @classmethod
    def error_response(cls, error_message: str) -> 'AgentOutput':
        return cls(error=error_message)


@dataclass
class ToolOutput:
    """Output from tool execution."""
    success: bool
    result: Dict[str, Any] 
    display_message: Optional[UIMessage] = None
    error: Optional[str] = None
    
    @classmethod
    def success_result(cls, result: Dict[str, Any], display_message: Optional[UIMessage] = None) -> 'ToolOutput':
        return cls(success=True, result=result, display_message=display_message)
    
    @classmethod
    def error_result(cls, error_message: str, result: Optional[Dict[str, Any]] = None) -> 'ToolOutput':
        return cls(success=False, result=result or {}, error=error_message)