# songbird/tools/semantic_matcher.py
"""
LLM-based semantic similarity matching for todos.
Replaces hardcoded concept groups with intelligent analysis.
"""

import json
import re
from typing import Optional
from ..llm.providers import BaseProvider
from .semantic_config import get_semantic_config


class SemanticMatcher:
    """
    LLM-powered semantic similarity matcher for todo content.
    Provides intelligent duplicate detection and content similarity analysis.
    """
    
    def __init__(self, llm_provider: BaseProvider):
        self.llm_provider = llm_provider
        self._cache = {}
        self.config = get_semantic_config()
    
    async def calculate_semantic_similarity(self, content1: str, content2: str) -> float:
        """
        Calculate semantic similarity between two todo contents using LLM analysis.
        
        Args:
            content1: First todo content
            content2: Second todo content
            
        Returns:
            Similarity score between 0.0 and 1.0
        """
        # Quick exact match check
        if content1.strip().lower() == content2.strip().lower():
            return 1.0
        
        # Check cache if enabled
        cache_key = self._get_cache_key(content1, content2)
        if self.config.cache_llm_results and cache_key in self._cache:
            return self._cache[cache_key]
        
        # Use LLM-based similarity if enabled
        if self.config.enable_llm_similarity:
            # Build similarity analysis prompt
            prompt = self._build_similarity_prompt(content1, content2)
            
            try:
                # Get LLM analysis
                messages = [{"role": "user", "content": prompt}]
                response = await self.llm_provider.chat_with_messages(messages)
                
                if response.content:
                    similarity = self._parse_similarity_response(response.content)
                    if similarity is not None:
                        # Cache the result if enabled
                        if self.config.cache_llm_results:
                            self._cache[cache_key] = similarity
                        return similarity
                
            except Exception:
                # Fall back to simple heuristics if enabled
                if self.config.fallback_to_heuristics:
                    return self._fallback_similarity(content1, content2)
                else:
                    raise
        
        # Default fallback
        return self._fallback_similarity(content1, content2)
    
    async def analyze_todo_priority(self, content: str, context: Optional[str] = None) -> str:
        """
        Analyze todo content and suggest appropriate priority using LLM.
        
        Args:
            content: Todo content to analyze
            context: Optional context about the project or task
            
        Returns:
            Priority level: "high", "medium", or "low"
        """
        # Build priority analysis prompt
        prompt = self._build_priority_prompt(content, context)
        
        try:
            # Get LLM analysis
            messages = [{"role": "user", "content": prompt}]
            response = await self.llm_provider.chat_with_messages(messages)
            
            if response.content:
                priority = self._parse_priority_response(response.content)
                if priority:
                    return priority
            
        except Exception:
            # Fall back to simple heuristics
            return self._fallback_priority(content)
        
        return self._fallback_priority(content)
    
    def _get_cache_key(self, content1: str, content2: str) -> str:
        """Generate cache key for similarity comparison."""
        # Normalize and sort to ensure consistent caching
        norm1 = content1.strip().lower()
        norm2 = content2.strip().lower()
        if norm1 > norm2:
            norm1, norm2 = norm2, norm1
        return f"{hash(norm1)}_{hash(norm2)}"
    
    def _build_similarity_prompt(self, content1: str, content2: str) -> str:
        """Build the similarity analysis prompt for the LLM."""
        return f"""
Analyze the semantic similarity between these two todo/task descriptions:

Todo 1: "{content1}"
Todo 2: "{content2}"

Consider these factors:
- Are they essentially the same task with different wording?
- Do they have the same action/verb (implement, analyze, fix, etc.)?
- Do they target the same or very similar components/features?
- Would completing one make the other redundant?
- Are they different aspects of the same larger task?

Respond with ONLY a JSON object in this exact format:
{{
  "similarity_score": number,
  "reasoning": "brief explanation",
  "are_duplicates": boolean
}}

Where:
- similarity_score: 0.0 (completely different) to 1.0 (essentially identical)
- reasoning: Brief explanation of your assessment
- are_duplicates: True if these should be considered duplicates

Examples:
- "Implement user login" vs "Add user authentication" → similarity_score: 0.9, are_duplicates: true
- "Fix login bug" vs "Optimize database queries" → similarity_score: 0.1, are_duplicates: false
- "Analyze code structure" vs "Review codebase architecture" → similarity_score: 0.8, are_duplicates: true
"""
    
    def _build_priority_prompt(self, content: str, context: Optional[str] = None) -> str:
        """Build the priority analysis prompt for the LLM."""
        context_info = f"\n\nContext: {context}" if context else ""
        
        return f"""
Analyze this todo/task and suggest an appropriate priority level:

Task: "{content}"{context_info}

Consider these factors:
- Urgency: How time-sensitive is this task?
- Impact: How much does this affect the project's success?
- Dependencies: Do other tasks depend on this being completed?
- Complexity: How much effort is required?
- Risk: What happens if this is delayed?

Common high priority indicators: critical bugs, security issues, blocking other work, urgent deadlines, core functionality
Common medium priority indicators: features, improvements, refactoring, non-blocking bugs
Common low priority indicators: documentation, cleanup, nice-to-have features, optimizations

Respond with ONLY a JSON object in this exact format:
{{
  "priority": "high|medium|low",
  "reasoning": "brief explanation"
}}
"""
    
    def _parse_similarity_response(self, response_content: str) -> Optional[float]:
        """Parse the LLM similarity response."""
        try:
            # Extract JSON from response
            json_match = re.search(r'\{.*?\}', response_content, re.DOTALL)
            if not json_match:
                return None
            
            json_str = json_match.group(0)
            data = json.loads(json_str)
            
            similarity_score = data.get('similarity_score')
            if isinstance(similarity_score, (int, float)):
                return max(0.0, min(1.0, float(similarity_score)))
            
        except (json.JSONDecodeError, KeyError, ValueError, TypeError):
            pass
        
        return None
    
    def _parse_priority_response(self, response_content: str) -> Optional[str]:
        """Parse the LLM priority response."""
        try:
            # Extract JSON from response
            json_match = re.search(r'\{.*?\}', response_content, re.DOTALL)
            if not json_match:
                return None
            
            json_str = json_match.group(0)
            data = json.loads(json_str)
            
            priority = data.get('priority')
            if priority in ['high', 'medium', 'low']:
                return priority
            
        except (json.JSONDecodeError, KeyError, ValueError, TypeError):
            pass
        
        return None
    
    def _fallback_similarity(self, content1: str, content2: str) -> float:
        """Simple fallback similarity calculation."""
        # Normalize content
        norm1 = self._normalize_content(content1)
        norm2 = self._normalize_content(content2)
        
        if norm1 == norm2:
            return 1.0
        
        # Split into words
        words1 = set(norm1.split())
        words2 = set(norm2.split())
        
        if not words1 or not words2:
            return 0.0
        
        # Calculate Jaccard similarity
        intersection = words1.intersection(words2)
        union = words1.union(words2)
        
        return len(intersection) / len(union) if union else 0.0
    
    def _fallback_priority(self, content: str) -> str:
        """Simple fallback priority determination."""
        content_lower = content.lower()
        
        # High priority keywords
        high_keywords = ['urgent', 'critical', 'fix', 'bug', 'error', 'security', 'broken', 'failing']
        if any(keyword in content_lower for keyword in high_keywords):
            return 'high'
        
        # Low priority keywords
        low_keywords = ['cleanup', 'documentation', 'docs', 'comment', 'optimize', 'refactor']
        if any(keyword in content_lower for keyword in low_keywords):
            return 'low'
        
        return 'medium'
    
    def _normalize_content(self, content: str) -> str:
        """Normalize content for comparison."""
        import re
        
        # Convert to lowercase and strip
        normalized = content.lower().strip()
        
        # Remove common prefixes
        prefixes = ['todo:', 'task:', 'need to', 'should', 'must']
        for prefix in prefixes:
            if normalized.startswith(prefix):
                normalized = normalized[len(prefix):].strip()
        
        # Clean up punctuation and whitespace
        normalized = re.sub(r'[^\w\s]', ' ', normalized)
        normalized = re.sub(r'\s+', ' ', normalized)
        
        return normalized.strip()
    
    def clear_cache(self):
        """Clear the similarity cache."""
        self._cache.clear()
    
    def get_cache_stats(self) -> dict:
        """Get cache statistics."""
        return {
            "cache_size": len(self._cache),
            "sample_keys": list(self._cache.keys())[:3]
        }