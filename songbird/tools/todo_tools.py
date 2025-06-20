# songbird/tools/todo_tools.py
"""
TodoRead and TodoWrite tools for intelligent task management.
Provides Claude Code-like todo functionality for Songbird.
"""
import json
from typing import Dict, Any, List, Optional
from .todo_manager import TodoManager, display_todos_table


async def todo_read(
    session_id: Optional[str] = None,
    status: Optional[str] = None,
    show_completed: bool = False
) -> Dict[str, Any]:
    """
    Read and display the current session's todo list.
    
    Args:
        session_id: Optional session ID to filter todos (defaults to current session)
        status: Filter by status: 'pending', 'in_progress', 'completed'
        show_completed: Whether to include completed tasks (default: False)
        
    Returns:
        Dictionary with todo list information
    """
    try:
        # Initialize todo manager
        todo_manager = TodoManager(session_id=session_id)
        
        # Get todos for current session
        if session_id:
            todos = todo_manager.get_todos(session_id=session_id)
        else:
            todos = todo_manager.get_current_session_todos()
        
        # Apply status filter
        if status:
            todos = [t for t in todos if t.status == status]
        
        # Filter out completed unless requested
        if not show_completed:
            todos = [t for t in todos if t.status != "completed"]
        
        # Display the todos
        if todos:
            title = "Current Tasks"
            if status:
                title = f"Tasks ({status.title()})"
            if show_completed:
                title += " (including completed)"
            
            display_todos_table(todos, title=title)
        else:
            filter_desc = ""
            if status:
                filter_desc = f" with status '{status}'"
            if not show_completed:
                filter_desc += " (excluding completed)"
            
            print(f"\n📝 No tasks found{filter_desc}")
        
        # Prepare summary data
        summary = {
            "total_tasks": len(todos),
            "pending": len([t for t in todos if t.status == "pending"]),
            "in_progress": len([t for t in todos if t.status == "in_progress"]),
            "completed": len([t for t in todos if t.status == "completed"])
        }
        
        # Convert todos to simple format for LLM
        todo_list = []
        for todo in todos:
            todo_list.append({
                "id": todo.id,
                "content": todo.content,
                "status": todo.status,
                "priority": todo.priority,
                "created_at": todo.created_at.strftime("%Y-%m-%d %H:%M")
            })
        
        return {
            "success": True,
            "todos": todo_list,
            "summary": summary,
            "display_shown": True,
            "message": f"Found {len(todos)} tasks"
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": f"Error reading todos: {e}",
            "todos": []
        }


async def todo_write(
    todos: List[Dict[str, Any]],
    session_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Create, update, and manage todo items.
    
    Args:
        todos: List of todo items with structure:
               [{"id": "optional", "content": "task", "status": "pending/in_progress/completed", 
                 "priority": "high/medium/low"}]
        session_id: Optional session ID for the todos
        
    Returns:
        Dictionary with operation results
    """
    try:
        # Initialize todo manager
        todo_manager = TodoManager(session_id=session_id)
        
        created_count = 0
        updated_count = 0
        completed_count = 0
        errors = []
        
        for todo_data in todos:
            try:
                todo_id = todo_data.get("id")
                content = todo_data.get("content", "").strip()
                status = todo_data.get("status", "pending")
                priority = todo_data.get("priority", "medium")
                
                if not content:
                    errors.append("Todo content cannot be empty")
                    continue
                
                # Validate status and priority
                valid_statuses = ["pending", "in_progress", "completed"]
                valid_priorities = ["high", "medium", "low"]
                
                if status not in valid_statuses:
                    status = "pending"
                
                if priority not in valid_priorities:
                    # Smart prioritization
                    priority = todo_manager.smart_prioritize(content)
                
                if todo_id:
                    # Try to update existing todo by ID
                    existing_todo = todo_manager.get_todo_by_id(todo_id)
                    if existing_todo:
                        todo_manager.update_todo(
                            todo_id,
                            content=content,
                            status=status,
                            priority=priority
                        )
                        updated_count += 1
                        
                        if status == "completed" and existing_todo.status != "completed":
                            completed_count += 1
                    else:
                        # ID provided but todo not found, create new one
                        new_todo = todo_manager.add_todo(content, priority)
                        if status != "pending":
                            todo_manager.update_todo(new_todo.id, status=status)
                        created_count += 1
                        
                        if status == "completed":
                            completed_count += 1
                else:
                    # No ID provided - try to find existing todo by content match
                    existing_todos = todo_manager.get_current_session_todos()
                    matching_todo = None
                    
                    # Look for exact content match first
                    for existing in existing_todos:
                        if existing.content.strip().lower() == content.lower():
                            matching_todo = existing
                            break
                    
                    # If no exact match, look for fuzzy match (partial content)
                    if not matching_todo:
                        for existing in existing_todos:
                            # Check if content is a substring of existing todo (and vice versa)
                            existing_words = set(existing.content.lower().split())
                            new_words = set(content.lower().split())
                            
                            # If most words match, consider it the same todo
                            common_words = existing_words.intersection(new_words)
                            if len(common_words) >= min(len(existing_words), len(new_words)) * 0.7:
                                matching_todo = existing
                                break
                    
                    if matching_todo:
                        # Update existing todo
                        todo_manager.update_todo(
                            matching_todo.id,
                            content=content,
                            status=status,
                            priority=priority
                        )
                        updated_count += 1
                        
                        if status == "completed" and matching_todo.status != "completed":
                            completed_count += 1
                    else:
                        # Create new todo
                        new_todo = todo_manager.add_todo(content, priority)
                        if status != "pending":
                            todo_manager.update_todo(new_todo.id, status=status)
                        created_count += 1
                        
                        if status == "completed":
                            completed_count += 1
                        
            except Exception as e:
                errors.append(f"Error processing todo '{content}': {e}")
        
        # Get updated todo list for display
        current_todos = todo_manager.get_current_session_todos()
        
        # Filter out completed for display unless there are only completed tasks
        display_todos = [t for t in current_todos if t.status != "completed"]
        if not display_todos and current_todos:
            display_todos = current_todos  # Show completed if that's all we have
        
        # Display updated todos
        if display_todos:
            display_todos_table(display_todos, title="Updated Task List")
        
        # Prepare result summary
        operations = []
        if created_count > 0:
            operations.append(f"created {created_count}")
        if updated_count > 0:
            operations.append(f"updated {updated_count}")
        if completed_count > 0:
            operations.append(f"completed {completed_count}")
        
        if operations:
            message = f"Successfully {', '.join(operations)} task(s)"
        else:
            message = "No changes made to todos"
        
        if errors:
            message += f" ({len(errors)} errors occurred)"
        
        return {
            "success": True,
            "message": message,
            "created": created_count,
            "updated": updated_count,
            "completed": completed_count,
            "errors": errors,
            "total_todos": len(current_todos),
            "display_shown": len(display_todos) > 0
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": f"Error managing todos: {e}",
            "created": 0,
            "updated": 0,
            "completed": 0
        }


# Helper functions for smart todo management

def extract_todos_from_text(text: str) -> List[str]:
    """Extract potential todo items from text."""
    todo_manager = TodoManager()
    return todo_manager.generate_smart_todos(text)


def auto_complete_todos_from_message(message: str, session_id: Optional[str] = None) -> List[str]:
    """
    Automatically detect and complete todos based on user message.
    Returns list of completed todo IDs.
    """
    completed_ids = []
    
    try:
        todo_manager = TodoManager(session_id=session_id)
        active_todos = todo_manager.get_todos(status="in_progress")
        
        # Look for completion keywords
        completion_keywords = [
            "done", "finished", "completed", "fixed", "implemented", 
            "resolved", "merged", "deployed", "working"
        ]
        
        message_lower = message.lower()
        
        for todo in active_todos:
            # Check if todo content is mentioned in the message
            todo_words = todo.content.lower().split()
            
            # If multiple words from todo are mentioned along with completion keywords
            matching_words = sum(1 for word in todo_words if word in message_lower)
            has_completion_keyword = any(keyword in message_lower for keyword in completion_keywords)
            
            if matching_words >= 2 and has_completion_keyword:
                todo_manager.complete_todo(todo.id)
                completed_ids.append(todo.id)
        
    except Exception:
        pass  # Silently fail for auto-completion
    
    return completed_ids