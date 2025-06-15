"""Types for LLM interactions."""
from dataclasses import dataclass
from typing import Optional


@dataclass
class ChatResponse:
    """Response from LLM chat completion."""
    content: str
    model: Optional[str] = None
    usage: Optional[dict] = None