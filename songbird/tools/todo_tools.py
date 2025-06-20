# songbird/tools/todo_tools.py
"""
TodoRead and TodoWrite tools for intelligent task management.
"""
import json
from typing import Dict, Any, List, Optional
from rich.console import Console
from .todo_manager import TodoManager, display_todos_table

console = Console()


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
        
        # Store all todos for summary calculation
        all_todos = todos.copy()
        
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
            
            console.print(f"\n[dim]No tasks found{filter_desc}[/dim]")
        
        # Prepare summary data using all todos, not just displayed ones
        summary = {
            "total_tasks": len(all_todos),
            "pending": len([t for t in all_todos if t.status == "pending"]),
            "in_progress": len([t for t in all_todos if t.status == "in_progress"]),
            "completed": len([t for t in all_todos if t.status == "completed"])
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
        
        # Always show all todos (including completed ones) after an update
        # This way users can see what was completed
        display_todos = current_todos
        
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


async def llm_auto_complete_todos(message: str, session_id: Optional[str] = None, llm_provider=None) -> List[str]:
    """
    Use LLM to intelligently detect which todos were completed based on user message.
    Returns list of completed todo IDs.
    """
    if not llm_provider:
        return []  # Fallback to no completion if no LLM available
    
    completed_ids = []
    
    try:
        todo_manager = TodoManager(session_id=session_id)
        # Check both pending and in_progress todos for completion
        active_todos = (
            todo_manager.get_todos(status="in_progress") + 
            todo_manager.get_todos(status="pending")
        )
        
        if not active_todos:
            return []
        
        # Create a structured prompt for the LLM
        todos_list = []
        for todo in active_todos:
            todos_list.append(f'"{todo.id}": "{todo.content}"')
        
        todos_json = "{\n  " + ",\n  ".join(todos_list) + "\n}"
        
        prompt = f"""Analyze this user message to determine which todos were completed:

User message: "{message}"

Current todos:
{todos_json}

Task: Identify which todo IDs were completed/finished based on the user's message.

Rules:
- Look for completion indicators: "finished", "completed", "done", "implemented", "fixed", "working", etc.
- Match todo content semantically (e.g., "JWT token system" matches "JWT tokens")  
- Only return IDs of todos that were clearly completed
- If no todos were completed, return empty array

Return ONLY a JSON array of completed todo IDs:
["id1", "id2"]"""

        try:
            # Use the LLM to analyze the message
            response = llm_provider.chat(prompt)
            response_text = response.content.strip()
            
            # Extract JSON from response (handle potential markdown formatting)
            import re
            json_match = re.search(r'\[.*?\]', response_text, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
                completed_todo_ids = json.loads(json_str)
                
                # Validate and complete the todos
                for todo_id in completed_todo_ids:
                    if todo_manager.complete_todo(todo_id):
                        completed_ids.append(todo_id)
            
        except Exception as e:
            # If LLM parsing fails, fall back to simple keyword detection
            console.print(f"[dim]LLM auto-completion failed, using fallback: {e}[/dim]")
            return await fallback_auto_complete_todos(message, session_id)
        
    except Exception:
        pass  # Silently fail for auto-completion
    
    return completed_ids


async def fallback_auto_complete_todos(message: str, session_id: Optional[str] = None) -> List[str]:
    """
    Fallback auto-completion using simple keyword matching.
    Used when LLM-based completion fails.
    """
    completed_ids = []
    
    try:
        todo_manager = TodoManager(session_id=session_id)
        active_todos = (
            todo_manager.get_todos(status="in_progress") + 
            todo_manager.get_todos(status="pending")
        )
        
        # Simple completion keywords
        completion_keywords = [
            "done", "finished", "completed", "fixed", "implemented", 
            "resolved", "working", "solved"
        ]
        
        message_lower = message.lower()
        has_completion_keyword = any(keyword in message_lower for keyword in completion_keywords)
        
        if has_completion_keyword:
            for todo in active_todos:
                todo_content_lower = todo.content.lower()
                # Simple direct substring match
                if todo_content_lower in message_lower:
                    todo_manager.complete_todo(todo.id)
                    completed_ids.append(todo.id)
        
    except Exception:
        pass
    
    return completed_ids


def auto_complete_todos_from_message(message: str, session_id: Optional[str] = None, llm_provider=None) -> List[str]:
    """
    Compatibility wrapper for the LLM-based auto-completion.
    Returns list of completed todo IDs.
    """
    import asyncio
    
    # Run the async LLM-based completion
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If we're already in an async context, create a task
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, llm_auto_complete_todos(message, session_id, llm_provider))
                return future.result()
        else:
            return asyncio.run(llm_auto_complete_todos(message, session_id, llm_provider))
    except Exception:
        # If async fails, use the fallback
        return asyncio.run(fallback_auto_complete_todos(message, session_id))