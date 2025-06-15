"""Types for LLM interactions."""
from dataclasses import dataclass
from typing import Optional, List, Dict, Any


@dataclass
class ChatResponse:
    """Response from LLM chat completion."""
    content: str
    model: Optional[str] = None
    usage: Optional[dict] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None