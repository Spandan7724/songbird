# songbird/tools/todo_manager.py
"""
Todo management system for Songbird sessions.
Provides intelligent task tracking and management similar to Claude Code.
"""
import json
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

console = Console()


class TodoItem:
    """Represents a single todo item."""
    
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
        """Convert to dictionary for JSON serialization."""
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
        """Create from dictionary."""
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
        """Update item properties."""
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
        self.updated_at = datetime.now()


class TodoManager:
    """Manages todos for Songbird sessions."""
    
    def __init__(self, working_directory: str = ".", session_id: Optional[str] = None):
        self.working_directory = Path(working_directory).resolve()
        self.session_id = session_id
        self.storage_path = self._get_storage_path()
        self._todos: List[TodoItem] = []
        self._load_todos()
    
    def _get_storage_path(self) -> Path:
        """Get the storage path for todos."""
        # Find project root (git repo or current directory)
        project_root = self._find_project_root()
        
        # Create safe directory name
        project_path_str = str(project_root)
        safe_name = project_path_str.replace(os.sep, "-").replace(":", "")
        
        # Storage in user's home directory
        home = Path.home()
        storage_dir = home / ".songbird" / "projects" / safe_name
        storage_dir.mkdir(parents=True, exist_ok=True)
        
        return storage_dir / "todos.json"
    
    def _find_project_root(self) -> Path:
        """Find the VCS root (git) or use current directory."""
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
    
    def _load_todos(self):
        """Load todos from storage."""
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
        """Save todos to storage."""
        try:
            # Ensure directory exists
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(self.storage_path, 'w', encoding='utf-8') as f:
                json.dump([todo.to_dict() for todo in self._todos], f, indent=2)
        except Exception as e:
            console.print(f"[red]Error saving todos: {e}[/red]")
    
    def add_todo(self, content: str, priority: str = "medium") -> TodoItem:
        """Add a new todo item."""
        todo = TodoItem(
            content=content,
            priority=priority,
            session_id=self.session_id
        )
        self._todos.append(todo)
        self._save_todos()
        return todo
    
    def get_todos(self, status: Optional[str] = None, 
                  session_id: Optional[str] = None) -> List[TodoItem]:
        """Get todos with optional filtering."""
        filtered = self._todos
        
        if status:
            filtered = [t for t in filtered if t.status == status]
        
        if session_id:
            filtered = [t for t in filtered if t.session_id == session_id]
        
        return filtered
    
    def get_current_session_todos(self) -> List[TodoItem]:
        """Get todos for the current session."""
        if not self.session_id:
            # If no session ID, return all recent todos
            return self.get_todos()
        
        return self.get_todos(session_id=self.session_id)
    
    def update_todo(self, todo_id: str, **kwargs) -> bool:
        """Update a todo item."""
        for todo in self._todos:
            if todo.id == todo_id:
                todo.update(**kwargs)
                self._save_todos()
                return True
        return False
    
    def complete_todo(self, todo_id: str) -> bool:
        """Mark a todo as completed."""
        return self.update_todo(todo_id, status="completed")
    
    def delete_todo(self, todo_id: str) -> bool:
        """Delete a todo item."""
        for i, todo in enumerate(self._todos):
            if todo.id == todo_id:
                del self._todos[i]
                self._save_todos()
                return True
        return False
    
    def clear_completed(self):
        """Remove all completed todos."""
        self._todos = [t for t in self._todos if t.status != "completed"]
        self._save_todos()
    
    def get_todo_by_id(self, todo_id: str) -> Optional[TodoItem]:
        """Get a specific todo by ID."""
        for todo in self._todos:
            if todo.id == todo_id:
                return todo
        return None
    
    def smart_prioritize(self, content: str) -> str:
        """Intelligently determine priority based on content."""
        content_lower = content.lower()
        
        # High priority keywords
        high_priority_keywords = [
            "urgent", "critical", "important", "fix", "bug", "error", 
            "broken", "failing", "security", "deploy", "release"
        ]
        
        # Low priority keywords  
        low_priority_keywords = [
            "cleanup", "refactor", "documentation", "docs", "comment",
            "optimize", "improve", "enhance", "consider", "maybe"
        ]
        
        for keyword in high_priority_keywords:
            if keyword in content_lower:
                return "high"
        
        for keyword in low_priority_keywords:
            if keyword in content_lower:
                return "low"
        
        return "medium"
    
    def generate_smart_todos(self, user_message: str) -> List[str]:
        """Generate smart todo suggestions based on user message."""
        suggestions = []
        message_lower = user_message.lower()
        
        # Common patterns that suggest todos
        patterns = [
            ("need to", "Need to"),
            ("should", "Should"),
            ("must", "Must"),
            ("have to", "Have to"),
            ("todo", "TODO:"),
            ("fixme", "FIXME:"),
            ("implement", "Implement"),
            ("create", "Create"),
            ("add", "Add"),
            ("fix", "Fix"),
            ("update", "Update"),
            ("remove", "Remove"),
            ("delete", "Delete")
        ]
        
        for pattern, prefix in patterns:
            if pattern in message_lower:
                # Extract potential todo items
                sentences = user_message.split('.')
                for sentence in sentences:
                    if pattern in sentence.lower():
                        # Clean up the sentence
                        clean_sentence = sentence.strip()
                        if len(clean_sentence) > 10 and len(clean_sentence) < 100:
                            if not clean_sentence.startswith(prefix):
                                clean_sentence = f"{prefix} {clean_sentence.lower()}"
                            suggestions.append(clean_sentence)
        
        return suggestions[:3]  # Limit to 3 suggestions


def display_todos_table(todos: List[TodoItem], title: str = "Current Tasks"):
    """Display todos in a formatted table."""
    if not todos:
        console.print(f"\n[dim]No tasks found[/dim]")
        return
    
    # Create table
    table = Table(title=title, title_style="bold cyan")
    table.add_column("Priority", style="bold", width=8)
    table.add_column("Status", style="bold", width=12)
    table.add_column("Task", style="white", ratio=1)
    table.add_column("Created", style="dim", width=10)
    
    # Sort by priority and status
    priority_order = {"high": 0, "medium": 1, "low": 2}
    status_order = {"in_progress": 0, "pending": 1, "completed": 2}
    
    sorted_todos = sorted(todos, key=lambda t: (
        status_order.get(t.status, 3),
        priority_order.get(t.priority, 3),
        t.created_at
    ))
    
    # Add rows
    for todo in sorted_todos:
        # Priority styling
        if todo.priority == "high":
            priority_style = "bold red"
            priority_text = "🔴 HIGH"
        elif todo.priority == "medium":
            priority_style = "bold yellow"
            priority_text = "🟡 MED"
        else:
            priority_style = "bold green"
            priority_text = "🟢 LOW"
        
        # Status styling
        if todo.status == "completed":
            status_style = "bold green"
            status_text = "✅ Done"
            task_style = "dim"
        elif todo.status == "in_progress":
            status_style = "bold blue"
            status_text = "🔄 Active"
            task_style = "bold white"
        else:
            status_style = "white"
            status_text = "⏳ Pending"
            task_style = "white"
        
        # Format created date
        created_str = todo.created_at.strftime("%m/%d")
        
        table.add_row(
            f"[{priority_style}]{priority_text}[/{priority_style}]",
            f"[{status_style}]{status_text}[/{status_style}]",
            f"[{task_style}]{todo.content}[/{task_style}]",
            f"[dim]{created_str}[/dim]"
        )
    
    # Display in a panel
    panel = Panel(table, border_style="blue", padding=(1, 2))
    console.print(panel)
    
    # Show summary
    total = len(todos)
    completed = len([t for t in todos if t.status == "completed"])
    in_progress = len([t for t in todos if t.status == "in_progress"])
    pending = len([t for t in todos if t.status == "pending"])
    
    summary = f"[dim]Total: {total} | ✅ {completed} | 🔄 {in_progress} | ⏳ {pending}[/dim]"
    console.print(f"\n{summary}")