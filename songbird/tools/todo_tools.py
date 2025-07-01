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
                    
                    # Normalize the new content for better matching
                    normalized_content = _normalize_todo_content(content)
                    
                    # Look for exact normalized match first
                    for existing in existing_todos:
                        normalized_existing = _normalize_todo_content(existing.content)
                        if normalized_existing == normalized_content:
                            matching_todo = existing
                            break
                    
                    # If no exact match, look for semantic similarity
                    if not matching_todo:
                        best_match = None
                        best_similarity = 0.0
                        
                        for existing in existing_todos:
                            similarity = _calculate_content_similarity(content, existing.content)
                            if similarity > 0.75 and similarity > best_similarity:  # Increased threshold
                                best_match = existing
                                best_similarity = similarity
                        
                        matching_todo = best_match
                    
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
        
        # Deduplicate todos to prevent double display
        display_todos = _deduplicate_todos(current_todos)
        
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
        
        # Use centralized prompt template
        from ..prompts import get_todo_completion_prompt_template
        prompt_template = get_todo_completion_prompt_template()
        prompt = prompt_template.format(message=message, todos_json=todos_json)

        try:
            # Use the LLM to analyze the message
            messages = [{"role": "user", "content": prompt}]
            response = await llm_provider.chat_with_messages(messages)
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


def _normalize_todo_content(content: str) -> str:
    """
    Normalize todo content for better matching.
    Removes common variations that don't change semantic meaning.
    """
    import re
    
    # Convert to lowercase and strip whitespace
    normalized = content.lower().strip()
    
    # Remove common prefixes/suffixes that don't matter for matching
    prefixes_to_remove = [
        'todo:', 'task:', 'step:', 'action:', 'next:', 'now:', 'please',
        'need to', 'should', 'must', 'will', 'going to', 'plan to'
    ]
    
    for prefix in prefixes_to_remove:
        if normalized.startswith(prefix):
            normalized = normalized[len(prefix):].strip()
    
    # Remove extra whitespace and punctuation that doesn't affect meaning
    normalized = re.sub(r'[^\w\s]', ' ', normalized)  # Replace punctuation with spaces
    normalized = re.sub(r'\s+', ' ', normalized)  # Collapse multiple spaces
    normalized = normalized.strip()
    
    return normalized


def _calculate_content_similarity(content1: str, content2: str) -> float:
    """
    Calculate semantic similarity between two todo contents.
    Returns a value between 0.0 and 1.0, where 1.0 is identical.
    """
    # Normalize both contents
    norm1 = _normalize_todo_content(content1)
    norm2 = _normalize_todo_content(content2)
    
    # If normalized versions are identical, return 1.0
    if norm1 == norm2:
        return 1.0
    
    # Split into words
    words1 = set(norm1.split())
    words2 = set(norm2.split())
    
    # If either is empty, no similarity
    if not words1 or not words2:
        return 0.0
    
    # Calculate Jaccard similarity (intersection over union)
    intersection = words1.intersection(words2)
    union = words1.union(words2)
    
    jaccard_similarity = len(intersection) / len(union)
    
    # Also check if one content is a substantial subset of the other
    subset_similarity = len(intersection) / min(len(words1), len(words2))
    
    # Return the higher of the two similarities, with a slight preference for Jaccard
    return max(jaccard_similarity, subset_similarity * 0.9)


def _deduplicate_todos(todos: List) -> List:
    """
    Remove duplicate todos based on content similarity.
    If duplicates exist, keep the one with the most recent status change.
    """
    if not todos:
        return todos
    
    # Group todos by normalized content
    content_groups = {}
    
    for todo in todos:
        normalized = _normalize_todo_content(todo.content)
        
        # Find if this content matches any existing group
        matched_group = None
        for existing_normalized in content_groups.keys():
            if _calculate_content_similarity(normalized, existing_normalized) > 0.85:
                matched_group = existing_normalized
                break
        
        if matched_group:
            content_groups[matched_group].append(todo)
        else:
            content_groups[normalized] = [todo]
    
    # For each group, keep only the best todo
    deduplicated = []
    for group_todos in content_groups.values():
        if len(group_todos) == 1:
            deduplicated.append(group_todos[0])
        else:
            # Multiple todos with similar content - keep the best one
            # Priority: completed > in_progress > pending
            # Secondary: most recent update
            status_priority = {"completed": 3, "in_progress": 2, "pending": 1}
            
            best_todo = max(group_todos, key=lambda t: (
                status_priority.get(t.status, 0),
                t.updated_at
            ))
            deduplicated.append(best_todo)
    
    return deduplicated


async def auto_complete_todos_from_message(message: str, session_id: Optional[str] = None, llm_provider=None) -> List[str]:
    """
    Async LLM-based auto-completion with fallback.
    Returns list of completed todo IDs.
    """
    # Try LLM-based completion first
    try:
        return await llm_auto_complete_todos(message, session_id, llm_provider)
    except Exception:
        # If LLM-based completion fails, use the simple fallback
        try:
            return await fallback_auto_complete_todos(message, session_id)
        except Exception:
            # If everything fails, return empty list
            return []