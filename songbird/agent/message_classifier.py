# songbird/agent/message_classifier.py
"""
LLM-based message classification to replace hardcoded word lists.
Provides intelligent intent analysis for todo system decisions.
"""

import json
import re
from typing import Dict, Any, Optional
from dataclasses import dataclass
from ..llm.providers import BaseProvider


@dataclass
class MessageIntent:
    """Structured representation of message intent analysis."""
    is_question: bool
    is_implementation_request: bool
    is_passive_request: bool
    is_todo_meta_query: bool
    complexity_level: str  # "low", "medium", "high"
    estimated_todos_needed: int
    should_auto_create_todos: bool
    confidence: float  # 0.0 to 1.0


class MessageClassifier:
    """
    LLM-powered message classification to replace hardcoded word lists.
    Analyzes user messages to determine intent, complexity, and actionability.
    """
    
    def __init__(self, llm_provider: BaseProvider):
        self.llm_provider = llm_provider
        self._cache: Dict[str, MessageIntent] = {}
    
    async def classify_message(self, message: str, context: Optional[Dict[str, Any]] = None) -> MessageIntent:
        """
        Classify a user message to determine intent and todo creation appropriateness.
        """
        cache_key = self._get_cache_key(message, context)
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        
        context_info = self._build_context_info(context)
        
        
        prompt = self._build_classification_prompt(message, context_info)
        
        try:
            messages = [{"role": "user", "content": prompt}]
            response = await self.llm_provider.chat_with_messages(messages)
            
            if response.content:
                intent = self._parse_classification_response(response.content)
                if intent:
                    self._cache[cache_key] = intent
                    return intent
            
        except Exception:
            return self._fallback_classification(message)
        
        return self._fallback_classification(message)
    
    def _get_cache_key(self, message: str, context: Optional[Dict[str, Any]]) -> str:
        """Generate cache key for message classification."""
        words = message.lower().split()[:5]
        key_parts = [str(len(message)), *words]
        
        if context:
            if context.get('existing_todos_count'):
                key_parts.append(f"todos:{context['existing_todos_count']}")
            if context.get('recent_auto_creation'):
                key_parts.append("recent_auto")
        
        return "_".join(key_parts)
    
    def _build_context_info(self, context: Optional[Dict[str, Any]]) -> str:
        """Build context information string for the LLM prompt."""
        if not context:
            return ""
        
        context_parts = []
        
        if context.get('existing_todos_count'):
            context_parts.append(f"Session has {context['existing_todos_count']} existing todos")
        
        if context.get('recent_auto_creation'):
            context_parts.append("Recently auto-created todos in this session")
        
        if context.get('conversation_length'):
            context_parts.append(f"Conversation has {context['conversation_length']} messages")
        
        if context_parts:
            return f"\n\nContext: {', '.join(context_parts)}"
        return ""
    
    def _build_classification_prompt(self, message: str, context_info: str) -> str:
        """Build the classification prompt for the LLM."""
        return f"""
Analyze this user message and classify its intent for a coding assistant with todo management:

Message: "{message}"{context_info}

Classify the message and respond with ONLY a JSON object in this exact format:
{{
  "is_question": boolean,
  "is_implementation_request": boolean,
  "is_passive_request": boolean,
  "is_todo_meta_query": boolean,
  "complexity_level": "low|medium|high",
  "estimated_todos_needed": number,
  "should_auto_create_todos": boolean,
  "confidence": number
}}

Guidelines:
- is_question: True if asking for information/explanation (vs. requesting action)
- is_implementation_request: True if asking to build/create/implement something
- is_passive_request: True if asking to show/display/explain existing code
- is_todo_meta_query: True if asking about the todo system itself
- complexity_level: "low" (1-2 steps), "medium" (3-6 steps), "high" (7+ steps)
- estimated_todos_needed: Realistic number of todos this task would require (0-20)
- should_auto_create_todos: True if this message warrants automatic todo creation
- confidence: How confident you are in this classification (0.0-1.0)

Examples:
- "What does this function do?" → is_question=true, should_auto_create_todos=false
- "Implement user authentication" → is_implementation_request=true, complexity_level="high", estimated_todos_needed=8
- "Show me the login code" → is_passive_request=true, should_auto_create_todos=false
- "Fix this bug" → complexity_level="low", estimated_todos_needed=2
"""
    
    def _parse_classification_response(self, response_content: str) -> Optional[MessageIntent]:
        """Parse the LLM response into a MessageIntent object."""
        try:
            json_match = re.search(r'\{.*?\}', response_content, re.DOTALL)
            if not json_match:
                return None
            
            json_str = json_match.group(0)
            data = json.loads(json_str)
            
            required_fields = [
                'is_question', 'is_implementation_request', 'is_passive_request',
                'is_todo_meta_query', 'complexity_level', 'estimated_todos_needed',
                'should_auto_create_todos', 'confidence'
            ]
            
            if not all(field in data for field in required_fields):
                return None
            
            if data['complexity_level'] not in ['low', 'medium', 'high']:
                return None
            
            # Create MessageIntent object
            return MessageIntent(
                is_question=bool(data['is_question']),
                is_implementation_request=bool(data['is_implementation_request']),
                is_passive_request=bool(data['is_passive_request']),
                is_todo_meta_query=bool(data['is_todo_meta_query']),
                complexity_level=str(data['complexity_level']),
                estimated_todos_needed=max(0, min(20, int(data['estimated_todos_needed']))),
                should_auto_create_todos=bool(data['should_auto_create_todos']),
                confidence=max(0.0, min(1.0, float(data['confidence'])))
            )
            
        except (json.JSONDecodeError, KeyError, ValueError, TypeError):
            return None
    
    def _fallback_classification(self, message: str) -> MessageIntent:
        """
        Simple fallback classification when LLM is unavailable.
        Uses basic heuristics as a safety net.
        """
        message_lower = message.lower().strip()
        word_count = len(message.split())
        
        # Simple question detection
        is_question = '?' in message or any(
            message_lower.startswith(word) for word in ['what', 'how', 'why', 'when', 'where', 'which', 'who', 'can you tell', 'can you show']
        )
        
        # Simple implementation request detection
        implementation_keywords = ['implement', 'create', 'build', 'add', 'develop', 'write', 'make']
        is_implementation_request = any(keyword in message_lower for keyword in implementation_keywords)
        
        # Simple passive request detection
        passive_keywords = ['show', 'display', 'list', 'tell me', 'explain', 'what is']
        is_passive_request = any(keyword in message_lower for keyword in passive_keywords)
        
        # Simple todo meta query detection
        is_todo_meta_query = any(keyword in message_lower for keyword in ['todo', 'task list', 'tasks'])
        
        # Simple complexity estimation
        if word_count < 5:
            complexity_level = "low"
            estimated_todos = 0
        elif word_count < 15:
            complexity_level = "medium" if is_implementation_request else "low"
            estimated_todos = 3 if is_implementation_request else 1
        else:
            complexity_level = "high" if is_implementation_request else "medium"
            estimated_todos = 6 if is_implementation_request else 2
        
        # Simple auto-creation decision
        should_auto_create = (
            is_implementation_request and 
            not is_question and 
            not is_passive_request and 
            not is_todo_meta_query and
            word_count >= 5
        )
        
        return MessageIntent(
            is_question=is_question,
            is_implementation_request=is_implementation_request,
            is_passive_request=is_passive_request,
            is_todo_meta_query=is_todo_meta_query,
            complexity_level=complexity_level,
            estimated_todos_needed=estimated_todos,
            should_auto_create_todos=should_auto_create,
            confidence=0.6  # Lower confidence for fallback
        )
    
    def clear_cache(self):
        self._cache.clear()
    
    def get_cache_stats(self) -> Dict[str, int]:
        return {
            "cache_size": len(self._cache),
            "cache_entries": list(self._cache.keys())[:5]
        }