
import json
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
from rich.console import Console
from .semantic_matcher import SemanticMatcher

console = Console()


class TodoItem:
    # Represents a single todo item
    
    def __init__(self, content: str, priority: str = "medium", 
                 status: str = "pending", id: Optional[str] = None,
                 created_at: Optional[datetime] = None,
                 updated_at: Optional[datetime] = None,
                 session_id: Optional[str] = None):
        self.id = id or str(uuid.uuid4())
        self.content = content
        self.priority = priority  # high, medium, low
        self.status = status      # pending, in_progress, completed
        self.created_at = created_at or datetime.now()
        self.updated_at = updated_at or datetime.now()
        self.session_id = session_id
    
    def to_dict(self) -> Dict[str, Any]:
        # Convert to dictionary for JSON serialization
        return {
            "id": self.id,
            "content": self.content,
            "priority": self.priority,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "session_id": self.session_id
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TodoItem':
        # Create from dictionary
        return cls(
            id=data["id"],
            content=data["content"],
            priority=data.get("priority", "medium"),
            status=data.get("status", "pending"),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            session_id=data.get("session_id")
        )
    
    def update(self, **kwargs):
        # Update item properties
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
        self.updated_at = datetime.now()


class TodoManager:
    # Manages todos for Songbird sessions
    
    def __init__(self, working_directory: str = ".", session_id: Optional[str] = None, 
                 semantic_matcher: Optional[SemanticMatcher] = None):
        self.working_directory = Path(working_directory).resolve()
        self.session_id = session_id
        self.semantic_matcher = semantic_matcher
        self.storage_path = self._get_storage_path()
        self._todos: List[TodoItem] = []
        self._load_todos()
    
    def _get_storage_path(self) -> Path:
        # Storage in user's home directory
        home = Path.home()
        storage_dir = home / ".songbird" / "todos"
        storage_dir.mkdir(parents=True, exist_ok=True)
        
        # Use session-specific file if session_id is available
        if self.session_id:
            return storage_dir / f"{self.session_id}.json"
        else:
            # Fallback to legacy project-based storage for backward compatibility
            project_root = self._find_project_root()
            project_path_str = str(project_root)
            safe_name = project_path_str.replace(os.sep, "-").replace(":", "")
            legacy_storage_dir = home / ".songbird" / "projects" / safe_name
            legacy_storage_dir.mkdir(parents=True, exist_ok=True)
            return legacy_storage_dir / "todos.json"
    
    def _find_project_root(self) -> Path:
        # Find the VCS root (git) or use current directory
        try:
            import subprocess
            result = subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                cwd=self.working_directory,
                capture_output=True,
                text=True,
                check=True
            )
            return Path(result.stdout.strip()).resolve()
        except Exception:
            return self.working_directory
    
    def migrate_from_project_storage(self) -> bool:

        if not self.session_id:
            return False  # No session ID, can't migrate
        
        # Check if new storage already exists
        new_path = Path.home() / ".songbird" / "todos" / f"{self.session_id}.json"
        if new_path.exists():
            return False  # Already migrated
        
        # Look for legacy storage
        project_root = self._find_project_root()
        project_path_str = str(project_root)
        safe_name = project_path_str.replace(os.sep, "-").replace(":", "")
        legacy_dir = Path.home() / ".songbird" / "projects" / safe_name
        legacy_path = legacy_dir / f"todos-{self.session_id}.json"
        
        if not legacy_path.exists():
            return False  # No legacy file to migrate
        
        try:
            # Copy legacy file to new location
            new_path.parent.mkdir(parents=True, exist_ok=True)
            import shutil
            shutil.copy2(legacy_path, new_path)
            
            console.print(f"[green]✓ Migrated todos from legacy storage to {new_path}[/green]")
            return True
            
        except Exception as e:
            console.print(f"[yellow]Warning: Could not migrate todos: {e}[/yellow]")
            return False
    
    def _load_todos(self):
        if not self.storage_path.exists() and self.session_id:
            self.migrate_from_project_storage()
        
        if not self.storage_path.exists():
            self._todos = []
            return
        
        try:
            with open(self.storage_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self._todos = [TodoItem.from_dict(item) for item in data]
        except Exception as e:
            console.print(f"[yellow]Warning: Could not load todos: {e}[/yellow]")
            self._todos = []
    
    def _save_todos(self):
        try:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(self.storage_path, 'w', encoding='utf-8') as f:
                json.dump([todo.to_dict() for todo in self._todos], f, indent=2)
        except Exception as e:
            console.print(f"[red]Error saving todos: {e}[/red]")
    
    async def add_todo(self, content: str, priority: str = "medium", use_semantic_id: bool = True) -> TodoItem:

        if use_semantic_id:
            semantic_id = await self.generate_semantic_id(content)
        else:
            semantic_id = None
        
        todo = TodoItem(
            id=semantic_id,
            content=content,
            priority=priority,
            session_id=self.session_id
        )
        self._todos.append(todo)
        self._save_todos()
        return todo
    
    def get_todos(self, status: Optional[str] = None, 
                  session_id: Optional[str] = None) -> List[TodoItem]:

        filtered = self._todos
        
        if status:
            filtered = [t for t in filtered if t.status == status]
        
        if session_id:
            filtered = [t for t in filtered if t.session_id == session_id]
        
        return filtered
    
    def get_current_session_todos(self) -> List[TodoItem]:

        if not self.session_id:
            return self.get_todos()
        
        return self.get_todos(session_id=self.session_id)
    
    def update_todo(self, todo_id: str, **kwargs) -> bool:

        for todo in self._todos:
            if todo.id == todo_id:
                todo.update(**kwargs)
                self._save_todos()
                return True
        return False
    
    def complete_todo(self, todo_id: str) -> bool:
        return self.update_todo(todo_id, status="completed")
    
    def delete_todo(self, todo_id: str) -> bool:
        for i, todo in enumerate(self._todos):
            if todo.id == todo_id:
                del self._todos[i]
                self._save_todos()
                return True
        return False
    
    def clear_completed(self):
        self._todos = [t for t in self._todos if t.status != "completed"]
        self._save_todos()
    
    def get_todo_by_id(self, todo_id: str) -> Optional[TodoItem]:
        for todo in self._todos:
            if todo.id == todo_id:
                return todo
        return None
    
    async def smart_prioritize(self, content: str) -> str:
        """Smart priority detection using SemanticMatcher with fallback."""
        if self.semantic_matcher:
            try:
                return await self.semantic_matcher.analyze_todo_priority(content)
            except Exception:
                # Fall back to semantic matcher's fallback method
                return self.semantic_matcher._fallback_priority(content)
        else:
            # Create a temporary semantic matcher for fallback behavior only
            from .semantic_matcher import SemanticMatcher
            temp_matcher = SemanticMatcher(llm_provider=None)
            return temp_matcher._fallback_priority(content)
    
    async def generate_semantic_id(self, content: str) -> str:
        """Generate semantic ID using SemanticMatcher with fallback."""
        import re
        
        # Extract action using SemanticMatcher
        action = None
        if self.semantic_matcher:
            try:
                action = await self.semantic_matcher.extract_primary_action(content)
            except Exception:
                action = self.semantic_matcher._fallback_extract_action(content)
        else:
            # Create temporary semantic matcher for fallback behavior only
            from .semantic_matcher import SemanticMatcher
            temp_matcher = SemanticMatcher(llm_provider=None)
            action = temp_matcher._fallback_extract_action(content)
        
        # Fallback if no action found
        if not action:
            content_lower = content.lower()
            if any(word in content_lower for word in ['bug', 'error', 'issue', 'problem']):
                action = 'fix'
            elif any(word in content_lower for word in ['new', 'add']):
                action = 'add'
            elif any(word in content_lower for word in ['test', 'testing']):
                action = 'test'
            else:
                action = 'task'
        
        # Normalize content using SemanticMatcher
        normalized_content = content
        if self.semantic_matcher:
            try:
                normalized_content = await self.semantic_matcher.normalize_todo_content(content)
            except Exception:
                normalized_content = self.semantic_matcher._fallback_normalize_content(content)
        else:
            from .semantic_matcher import SemanticMatcher
            temp_matcher = SemanticMatcher(llm_provider=None)
            normalized_content = temp_matcher._fallback_normalize_content(content)
        
        # Extract meaningful words from normalized content
        clean_content = re.sub(r'[^\w\s-]', ' ', normalized_content.lower())
        words = clean_content.split()
        
        # Get stop words from semantic matcher
        stop_words = set()
        if self.semantic_matcher:
            stop_words = self.semantic_matcher._fallback_keywords['stop_words']
        else:
            from .semantic_matcher import SemanticMatcher
            temp_matcher = SemanticMatcher(llm_provider=None)
            stop_words = temp_matcher._fallback_keywords['stop_words']
        
        # Filter meaningful words
        meaningful_words = [
            word for word in words 
            if word not in stop_words and len(word) > 2 and word != action
        ]
        
        subject_words = meaningful_words[:3]
        
        # Build semantic ID
        if subject_words:
            semantic_id = f"{action}-{'-'.join(subject_words)}"
        else:
            fallback_words = [w for w in words[:3] if len(w) > 2]
            if fallback_words:
                semantic_id = '-'.join(fallback_words)
            else:
                semantic_id = f"{action}-task"
        
        # Clean and format ID
        semantic_id = re.sub(r'[^a-z0-9-]', '-', semantic_id)
        semantic_id = re.sub(r'-+', '-', semantic_id)
        semantic_id = semantic_id.strip('-')
        
        return self._ensure_unique_id(semantic_id)
    
    def _ensure_unique_id(self, preferred_id: str) -> str:
        existing_ids = {todo.id for todo in self._todos}
        
        if preferred_id not in existing_ids:
            return preferred_id
        
        for i in range(2, 100):
            candidate = f"{preferred_id}-{i}"
            if candidate not in existing_ids:
                return candidate
        
        import uuid
        return str(uuid.uuid4())
    
    async def generate_smart_todos(self, user_message: str) -> List[str]:
        """Generate smart todo suggestions using SemanticMatcher with pattern fallback."""
        suggestions = []
        
        # First, try to use LLM for smart todo generation if available
        if self.semantic_matcher and self.semantic_matcher.llm_provider:
            try:
                # Use LLM to extract actionable tasks from the message
                prompt = f"""
Extract actionable todo items from this user message:

Message: "{user_message}"

Look for:
- Explicit todo statements (need to, should, must, have to)
- Action items (implement, create, add, fix, update, etc.)
- Issues mentioned that need addressing
- Features or improvements suggested

Return 1-3 clear, actionable todo items. Respond with ONLY a JSON object:
{{
  "todos": ["actionable todo 1", "actionable todo 2", "actionable todo 3"],
  "reasoning": "brief explanation"
}}

If no clear todos are found, use "todos": []
"""
                messages = [{"role": "user", "content": prompt}]
                response = await self.semantic_matcher.llm_provider.chat_with_messages(messages)
                
                if response.content:
                    try:
                        import json
                        import re
                        json_match = re.search(r'\{.*?\}', response.content, re.DOTALL)
                        if json_match:
                            data = json.loads(json_match.group(0))
                            llm_todos = data.get('todos', [])
                            if isinstance(llm_todos, list) and llm_todos:
                                return llm_todos[:3]
                    except (json.JSONDecodeError, KeyError):
                        pass
            except Exception:
                pass  # Fall back to pattern matching
        
        # Fallback: Use pattern matching with consolidated patterns
        message_lower = user_message.lower()
        
        # Use consolidated action verbs from semantic matcher
        action_verbs = []
        if self.semantic_matcher:
            action_verbs = self.semantic_matcher._fallback_keywords['action_verbs']
        else:
            from .semantic_matcher import SemanticMatcher
            temp_matcher = SemanticMatcher(llm_provider=None)
            action_verbs = temp_matcher._fallback_keywords['action_verbs']
        
        # Check for patterns including action verbs
        patterns = [
            ("need to", "Need to"),
            ("should", "Should"),
            ("must", "Must"),
            ("have to", "Have to"),
            ("todo", "TODO:"),
            ("fixme", "FIXME:")
        ]
        
        # Add action verbs as patterns
        for verb in action_verbs[:10]:  # Limit to avoid too many patterns
            patterns.append((verb, verb.title()))
        
        for pattern, prefix in patterns:
            if pattern in message_lower:
                sentences = user_message.split('.')
                for sentence in sentences:
                    if pattern in sentence.lower():
                        clean_sentence = sentence.strip()
                        if len(clean_sentence) > 10 and len(clean_sentence) < 100:
                            if not clean_sentence.lower().startswith(prefix.lower()):
                                clean_sentence = f"{prefix} {clean_sentence.lower()}"
                            suggestions.append(clean_sentence)
        
        return suggestions[:3]


def display_todos_table(todos: List[TodoItem], title: str = "Current Tasks", show_summary: bool = True):
    if not todos:
        console.print("\n[dim]No tasks found[/dim]")
        return
    
    priority_order = {"high": 0, "medium": 1, "low": 2}
    status_order = {"in_progress": 0, "pending": 1, "completed": 2}
    
    sorted_todos = sorted(todos, key=lambda t: (
        status_order.get(t.status, 3),
        priority_order.get(t.priority, 3),
        t.created_at
    ))
    
    console.print(f"\n• {title}")
    
    for todo in sorted_todos:
        if todo.status == "completed":
            console.print(f"  [bold green]●[/bold green] [green strike]{todo.content}[/green strike]")
        elif todo.status == "in_progress":
            console.print(f"  [bold yellow]◐[/bold yellow] {todo.content}")
        else:
            console.print(f"  ◯ {todo.content}")
    
    if show_summary:
        completed = len([t for t in todos if t.status == "completed"])
        pending = len([t for t in todos if t.status == "pending"])
        in_progress = len([t for t in todos if t.status == "in_progress"])
        
        console.print(f"\n[dim]{completed} completed, {in_progress} in progress, {pending} pending[/dim]")