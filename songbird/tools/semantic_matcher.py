# songbird/tools/semantic_matcher.py
"""
LLM-based semantic similarity matching for todos.
Replaces hardcoded concept groups with intelligent analysis.
"""

import json
import re
from typing import Optional, List, Dict, Any
from ..llm.providers import BaseProvider
from .semantic_config import get_semantic_config


class SemanticMatcher:
    """
    LLM-powered semantic similarity matcher for todo content.
    Provides intelligent duplicate detection and content similarity analysis.
    """
    
    def __init__(self, llm_provider: Optional[BaseProvider] = None):
        self.llm_provider = llm_provider
        self._cache = {}
        self.config = get_semantic_config()
        
        # Consolidated hardcoded fallback data (replaces scattered lists across codebase)
        self._fallback_keywords = self._get_consolidated_fallback_keywords()
    
    def _get_consolidated_fallback_keywords(self) -> Dict[str, Any]:
        """Get all consolidated hardcoded keywords for fallback behavior."""
        return {
            'priority': {
                'high': ['urgent', 'critical', 'important', 'fix', 'bug', 'error', 'broken', 
                        'failing', 'security', 'deploy', 'release'],
                'low': ['cleanup', 'refactor', 'documentation', 'docs', 'comment', 'optimize', 
                       'improve', 'enhance', 'consider', 'maybe']
            },
            'action_verbs': [
                'implement', 'create', 'add', 'build', 'develop', 'write',
                'fix', 'debug', 'resolve', 'solve', 'repair',
                'update', 'modify', 'change', 'edit', 'refactor',
                'test', 'validate', 'verify', 'check',
                'remove', 'delete', 'clean', 'cleanup',
                'analyze', 'research', 'investigate', 'explore',
                'design', 'plan', 'configure', 'setup'
            ],
            'stop_words': {
                'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
                'of', 'with', 'by', 'from', 'up', 'about', 'into', 'through', 'during',
                'before', 'after', 'above', 'below', 'between', 'this', 'that', 'these',
                'those', 'i', 'me', 'my', 'myself', 'we', 'our', 'ours', 'ourselves'
            },
            'prefixes_to_remove': [
                'todo:', 'task:', 'step:', 'action:', 'next:', 'now:', 'please',
                'need to', 'should', 'must', 'will', 'going to', 'plan to'
            ],
            'completion_keywords': [
                'done', 'finished', 'completed', 'fixed', 'implemented', 
                'resolved', 'working', 'solved'
            ],
            'concept_groups': {
                'analysis': {'analyze', 'examine', 'review', 'investigate', 'study', 'inspect', 'assess', 'evaluate'},
                'implementation': {'implement', 'create', 'build', 'develop', 'code', 'write', 'add', 'construct'},
                'modification': {'refactor', 'update', 'modify', 'change', 'edit', 'improve', 'enhance', 'optimize'},
                'testing': {'test', 'validate', 'verify', 'check', 'ensure', 'confirm', 'qa'},
                'documentation': {'document', 'docs', 'documentation', 'comment', 'readme', 'wiki'},
                'debugging': {'fix', 'debug', 'resolve', 'solve', 'repair', 'troubleshoot', 'handle', 'address'},
                'structure': {'structure', 'architecture', 'design', 'layout', 'organization', 'framework'},
                'performance': {'performance', 'optimize', 'speed', 'efficiency', 'bottleneck', 'latency'},
                'codebase': {'codebase', 'code', 'project', 'application', 'system', 'repo', 'repository'},
                'maintenance': {'maintain', 'maintainability', 'cleanup', 'clean', 'organize', 'manage'}
            },
            'action_groups': {
                'create': {'create', 'add', 'build', 'implement', 'develop', 'write', 'establish'},
                'modify': {'update', 'modify', 'change', 'edit', 'refactor', 'improve', 'enhance'},
                'analyze': {'analyze', 'examine', 'review', 'investigate', 'study', 'assess'},
                'fix': {'fix', 'debug', 'resolve', 'solve', 'repair', 'address', 'handle'},
                'test': {'test', 'validate', 'verify', 'check', 'ensure'},
                'remove': {'remove', 'delete', 'clean', 'cleanup', 'clear'}
            }
        }
    
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
        # Check if LLM priority analysis is enabled
        if not self.config.enable_llm_priority or not self.llm_provider:
            return self._fallback_priority(content)
        
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
            
        except Exception as e:
            # Check if fallback is enabled
            if self.config.fallback_to_heuristics:
                return self._fallback_priority(content)
            else:
                raise e
        
        return self._fallback_priority(content)
    
    async def normalize_todo_content(self, content: str) -> str:
        """
        Normalize todo content by removing prefixes and cleaning text using LLM analysis.
        
        Args:
            content: Todo content to normalize
            
        Returns:
            Normalized content string
        """
        if self.config.enable_llm_normalization and self.llm_provider:
            prompt = self._build_normalization_prompt(content)
            
            try:
                messages = [{"role": "user", "content": prompt}]
                response = await self.llm_provider.chat_with_messages(messages)
                
                if response.content:
                    normalized = self._parse_normalization_response(response.content)
                    if normalized:
                        return normalized
                        
            except Exception:
                if self.config.fallback_to_heuristics:
                    return self._fallback_normalize_content(content)
                else:
                    raise
        
        return self._fallback_normalize_content(content)
    
    async def extract_primary_action(self, content: str) -> Optional[str]:
        """
        Extract the primary action verb from todo content using LLM analysis.
        
        Args:
            content: Todo content to analyze
            
        Returns:
            Primary action verb or None if not found
        """
        if self.config.enable_llm_action_extraction and self.llm_provider:
            prompt = self._build_action_extraction_prompt(content)
            
            try:
                messages = [{"role": "user", "content": prompt}]
                response = await self.llm_provider.chat_with_messages(messages)
                
                if response.content:
                    action = self._parse_action_response(response.content)
                    if action:
                        return action
                        
            except Exception:
                if self.config.fallback_to_heuristics:
                    return self._fallback_extract_action(content)
                else:
                    raise
        
        return self._fallback_extract_action(content)
    
    async def detect_completion_signals(self, message: str, todos: List[str]) -> List[str]:
        """
        Detect which todos are indicated as completed in a message using LLM analysis.
        
        Args:
            message: User message to analyze
            todos: List of active todo contents
            
        Returns:
            List of todo contents that appear to be completed
        """
        if not todos:
            return []
            
        if self.config.enable_llm_completion_detection and self.llm_provider:
            prompt = self._build_completion_detection_prompt(message, todos)
            
            try:
                messages = [{"role": "user", "content": prompt}]
                response = await self.llm_provider.chat_with_messages(messages)
                
                if response.content:
                    completed = self._parse_completion_response(response.content)
                    if completed:
                        return completed
                        
            except Exception:
                if self.config.fallback_to_heuristics:
                    return self._fallback_detect_completion(message, todos)
                else:
                    raise
        
        return self._fallback_detect_completion(message, todos)
    
    async def categorize_todo_concept(self, content: str) -> str:
        """
        Categorize todo content into concept groups using LLM analysis.
        
        Args:
            content: Todo content to categorize
            
        Returns:
            Category name (e.g., 'implementation', 'testing', 'debugging')
        """
        if self.config.enable_llm_categorization and self.llm_provider:
            prompt = self._build_categorization_prompt(content)
            
            try:
                messages = [{"role": "user", "content": prompt}]
                response = await self.llm_provider.chat_with_messages(messages)
                
                if response.content:
                    category = self._parse_categorization_response(response.content)
                    if category:
                        return category
                        
            except Exception:
                if self.config.fallback_to_heuristics:
                    return self._fallback_categorize_concept(content)
                else:
                    raise
        
        return self._fallback_categorize_concept(content)
    
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
    
    def _build_normalization_prompt(self, content: str) -> str:
        """Build the content normalization prompt for the LLM."""
        return f"""
Normalize this todo/task content by cleaning and standardizing it:

Original: "{content}"

Tasks:
1. Remove common prefixes like "todo:", "task:", "need to", "should", etc.
2. Convert to a clear, concise action statement
3. Remove unnecessary words while preserving meaning
4. Maintain the core action and objective

Respond with ONLY a JSON object in this exact format:
{{
  "normalized": "cleaned content",
  "action": "primary action verb",
  "reasoning": "brief explanation of changes"
}}

Examples:
- "TODO: Need to implement user login system" → "Implement user login system"
- "Should refactor the database code" → "Refactor database code"
- "We need to fix the login bug" → "Fix login bug"
"""
    
    def _build_action_extraction_prompt(self, content: str) -> str:
        """Build the action extraction prompt for the LLM."""
        return f"""
Extract the primary action verb from this todo/task:

Task: "{content}"

Identify the main action that this task involves. Focus on verbs like:
- implement, create, add, build, develop, write
- fix, debug, resolve, solve, repair
- update, modify, change, edit, refactor
- test, validate, verify, check
- remove, delete, clean, cleanup
- analyze, research, investigate, explore

Respond with ONLY a JSON object in this exact format:
{{
  "action": "primary action verb",
  "confidence": 0.0-1.0,
  "reasoning": "brief explanation"
}}

If no clear action is found, use "action": null
"""
    
    def _build_completion_detection_prompt(self, message: str, todos: List[str]) -> str:
        """Build the completion detection prompt for the LLM."""
        todos_list = "\n".join([f"- {todo}" for todo in todos])
        
        return f"""
Analyze this user message to determine which active todos appear to be completed:

User Message: "{message}"

Active Todos:
{todos_list}

Look for completion indicators like:
- "done", "finished", "completed", "fixed", "implemented", "resolved"
- Past tense descriptions of the work
- Statements about successful completion
- References to having solved or addressed the task

Respond with ONLY a JSON object in this exact format:
{{
  "completed_todos": ["todo content 1", "todo content 2"],
  "reasoning": "brief explanation of completion signals detected"
}}

If no todos appear completed, use "completed_todos": []
"""
    
    def _build_categorization_prompt(self, content: str) -> str:
        """Build the categorization prompt for the LLM."""
        return f"""
Categorize this todo/task into one of these concept groups:

Task: "{content}"

Categories:
- analysis: analyze, examine, review, investigate, study, assess
- implementation: implement, create, build, develop, code, write, add
- modification: refactor, update, modify, change, edit, improve, enhance
- testing: test, validate, verify, check, ensure, confirm
- documentation: document, docs, comment, readme, wiki
- debugging: fix, debug, resolve, solve, repair, troubleshoot
- structure: architecture, design, layout, organization, framework
- performance: optimize, speed, efficiency, bottleneck, latency
- codebase: code management, project organization, repository
- maintenance: maintain, cleanup, organize, manage

Respond with ONLY a JSON object in this exact format:
{{
  "category": "category_name",
  "confidence": 0.0-1.0,
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
    
    def _parse_normalization_response(self, response_content: str) -> Optional[str]:
        """Parse the LLM normalization response."""
        try:
            json_match = re.search(r'\{.*?\}', response_content, re.DOTALL)
            if not json_match:
                return None
            
            json_str = json_match.group(0)
            data = json.loads(json_str)
            
            normalized = data.get('normalized')
            if isinstance(normalized, str) and normalized.strip():
                return normalized.strip()
            
        except (json.JSONDecodeError, KeyError, ValueError, TypeError):
            pass
        
        return None
    
    def _parse_action_response(self, response_content: str) -> Optional[str]:
        """Parse the LLM action extraction response."""
        try:
            json_match = re.search(r'\{.*?\}', response_content, re.DOTALL)
            if not json_match:
                return None
            
            json_str = json_match.group(0)
            data = json.loads(json_str)
            
            action = data.get('action')
            if isinstance(action, str) and action.strip():
                return action.strip().lower()
            
        except (json.JSONDecodeError, KeyError, ValueError, TypeError):
            pass
        
        return None
    
    def _parse_completion_response(self, response_content: str) -> List[str]:
        """Parse the LLM completion detection response."""
        try:
            json_match = re.search(r'\{.*?\}', response_content, re.DOTALL)
            if not json_match:
                return []
            
            json_str = json_match.group(0)
            data = json.loads(json_str)
            
            completed = data.get('completed_todos', [])
            if isinstance(completed, list):
                return [todo for todo in completed if isinstance(todo, str)]
            
        except (json.JSONDecodeError, KeyError, ValueError, TypeError):
            pass
        
        return []
    
    def _parse_categorization_response(self, response_content: str) -> Optional[str]:
        """Parse the LLM categorization response."""
        try:
            json_match = re.search(r'\{.*?\}', response_content, re.DOTALL)
            if not json_match:
                return None
            
            json_str = json_match.group(0)
            data = json.loads(json_str)
            
            category = data.get('category')
            valid_categories = {
                'analysis', 'implementation', 'modification', 'testing', 
                'documentation', 'debugging', 'structure', 'performance', 
                'codebase', 'maintenance'
            }
            
            if isinstance(category, str) and category.lower() in valid_categories:
                return category.lower()
            
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
        """Simple fallback priority determination using consolidated keywords."""
        content_lower = content.lower()
        
        # Use consolidated high priority keywords
        if any(keyword in content_lower for keyword in self._fallback_keywords['priority']['high']):
            return 'high'
        
        # Use consolidated low priority keywords
        if any(keyword in content_lower for keyword in self._fallback_keywords['priority']['low']):
            return 'low'
        
        return 'medium'
    
    def _fallback_normalize_content(self, content: str) -> str:
        """Fallback content normalization using consolidated keywords."""
        import re
        
        # Convert to lowercase and strip
        normalized = content.lower().strip()
        
        # Remove common prefixes using consolidated list
        for prefix in self._fallback_keywords['prefixes_to_remove']:
            if normalized.startswith(prefix):
                normalized = normalized[len(prefix):].strip()
        
        # Clean up punctuation and whitespace
        normalized = re.sub(r'[^\w\s]', ' ', normalized)
        normalized = re.sub(r'\s+', ' ', normalized)
        
        return normalized.strip()
    
    def _fallback_extract_action(self, content: str) -> Optional[str]:
        """Fallback action extraction using consolidated action verbs."""
        content_lower = content.lower()
        words = content_lower.split()
        
        # Find first action verb in the consolidated list
        for word in words:
            # Remove punctuation from word
            clean_word = re.sub(r'[^\w]', '', word)
            if clean_word in self._fallback_keywords['action_verbs']:
                return clean_word
        
        return None
    
    def _fallback_detect_completion(self, message: str, todos: List[str]) -> List[str]:
        """Fallback completion detection using consolidated completion keywords."""
        message_lower = message.lower()
        completed = []
        
        # Check if message contains completion keywords
        has_completion_signal = any(
            keyword in message_lower 
            for keyword in self._fallback_keywords['completion_keywords']
        )
        
        if has_completion_signal:
            # Simple matching: if message mentions todo words and has completion signal
            for todo in todos:
                todo_words = set(todo.lower().split())
                message_words = set(message_lower.split())
                
                # If todo words overlap significantly with message, consider it completed
                if len(todo_words.intersection(message_words)) >= 2:
                    completed.append(todo)
        
        return completed
    
    def _fallback_categorize_concept(self, content: str) -> str:
        """Fallback concept categorization using consolidated concept groups."""
        content_lower = content.lower()
        words = set(content_lower.split())
        
        # Score each category based on word matches
        category_scores = {}
        for category, keywords in self._fallback_keywords['concept_groups'].items():
            score = len(words.intersection(keywords))
            if score > 0:
                category_scores[category] = score
        
        # Return category with highest score, default to 'implementation'
        if category_scores:
            return max(category_scores.items(), key=lambda x: x[1])[0]
        else:
            return 'implementation'  # Default category
    
    def _normalize_content(self, content: str) -> str:
        """Legacy method for backward compatibility - delegates to fallback."""
        return self._fallback_normalize_content(content)
    
    def clear_cache(self):
        """Clear the similarity cache."""
        self._cache.clear()
    
    def get_cache_stats(self) -> dict:
        """Get cache statistics."""
        return {
            "cache_size": len(self._cache),
            "sample_keys": list(self._cache.keys())[:3]
        }