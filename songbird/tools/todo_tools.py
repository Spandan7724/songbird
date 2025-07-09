# TodoRead and TodoWrite tools for intelligent task management.

import json
from typing import Dict, Any, List, Optional
from rich.console import Console
from .todo_manager import TodoManager, display_todos_table
from .semantic_matcher import SemanticMatcher
from .semantic_config import get_semantic_config

console = Console()

# Module-level semantic matcher - initialized when first needed
_semantic_matcher: Optional[SemanticMatcher] = None

def _get_semantic_matcher(llm_provider=None) -> Optional[SemanticMatcher]:
    global _semantic_matcher
    if _semantic_matcher is None and llm_provider is not None:
        _semantic_matcher = SemanticMatcher(llm_provider)
    return _semantic_matcher


async def todo_read(
    session_id: Optional[str] = None,
    status: Optional[str] = None,
    show_completed: bool = False,
    llm_provider=None
) -> Dict[str, Any]:

    try:
        semantic_matcher = _get_semantic_matcher(llm_provider)
        todo_manager = TodoManager(session_id=session_id, semantic_matcher=semantic_matcher)
        
        if session_id:
            todos = todo_manager.get_todos(session_id=session_id)
        else:
            todos = todo_manager.get_current_session_todos()
        
        if status:
            todos = [t for t in todos if t.status == status]
        
        all_todos = todos.copy()
        
        if not show_completed:
            todos = [t for t in todos if t.status != "completed"]
        
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
        
        summary = {
            "total_tasks": len(all_todos),
            "pending": len([t for t in all_todos if t.status == "pending"]),
            "in_progress": len([t for t in all_todos if t.status == "in_progress"]),
            "completed": len([t for t in all_todos if t.status == "completed"])
        }
        
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
    session_id: Optional[str] = None,
    llm_provider=None
) -> Dict[str, Any]:

    try:
        # Initialize todo manager with semantic matcher
        semantic_matcher = _get_semantic_matcher(llm_provider)
        todo_manager = TodoManager(session_id=session_id, semantic_matcher=semantic_matcher)
        
        created_count = 0
        updated_count = 0
        completed_count = 0
        errors = []
        skipped_count = 0
        
        deduplicated_input = await _deduplicate_input_todos(todos, llm_provider)
        
        for todo_data in deduplicated_input:
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
                    semantic_matcher = _get_semantic_matcher(llm_provider)
                    if semantic_matcher:
                        try:
                            priority = await semantic_matcher.analyze_todo_priority(content)
                        except Exception:
                            priority = todo_manager.smart_prioritize(content)
                    else:
                        priority = todo_manager.smart_prioritize(content)
                
                if todo_id:
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
                        new_todo = await todo_manager.add_todo(content, priority)
                        if status != "pending":
                            todo_manager.update_todo(new_todo.id, status=status)
                        created_count += 1
                        
                        if status == "completed":
                            completed_count += 1
                else:
                    existing_todos = todo_manager.get_current_session_todos()
                    matching_todo = None
                    
                    normalized_content = _normalize_todo_content(content, semantic_matcher)
                    
                    for existing in existing_todos:
                        normalized_existing = _normalize_todo_content(existing.content, semantic_matcher)
                        if normalized_existing == normalized_content:
                            matching_todo = existing
                            break
                    
                    if not matching_todo:
                        best_match = None
                        best_similarity = 0.0
                        
                        for existing in existing_todos:
                            semantic_matcher = _get_semantic_matcher(llm_provider)
                            if semantic_matcher:
                                try:
                                    similarity = await semantic_matcher.calculate_semantic_similarity(content, existing.content)
                                except Exception:
                                    similarity = await _calculate_content_similarity(content, existing.content, semantic_matcher)
                            else:
                                similarity = await _calculate_content_similarity(content, existing.content, semantic_matcher)
                            
                            config = get_semantic_config()
                            if similarity > config.similarity_threshold and similarity > best_similarity:
                                best_match = existing
                                best_similarity = similarity
                        
                        matching_todo = best_match
                    
                    if matching_todo:
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
                        new_todo = await todo_manager.add_todo(content, priority)
                        if status != "pending":
                            todo_manager.update_todo(new_todo.id, status=status)
                        created_count += 1
                        
                        if status == "completed":
                            completed_count += 1
                        
            except Exception as e:
                errors.append(f"Error processing todo '{content}': {e}")
        
        current_todos = todo_manager.get_current_session_todos()
        
        display_todos = await _deduplicate_todos(current_todos, semantic_matcher)
        
        if display_todos:
            display_todos_table(display_todos, title="Updated Task List")
        
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
        
        # Report duplicates skipped
        input_skipped = len(todos) - len(deduplicated_input)
        if input_skipped > 0:
            message += f" ({input_skipped} duplicates skipped)"
        
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


async def extract_todos_from_text(text: str, llm_provider=None) -> List[str]:
    semantic_matcher = _get_semantic_matcher(llm_provider)
    todo_manager = TodoManager(semantic_matcher=semantic_matcher)
    return await todo_manager.generate_smart_todos(text)


async def llm_auto_complete_todos(message: str, session_id: Optional[str] = None, llm_provider=None) -> List[str]:
    config = get_semantic_config()
    if not config.enable_auto_todo_completion:
        return []
    
    if not llm_provider:
        return []
    
    completed_ids = []
    
    try:
        semantic_matcher = _get_semantic_matcher(llm_provider)
        todo_manager = TodoManager(session_id=session_id, semantic_matcher=semantic_matcher)
        active_todos = (
            todo_manager.get_todos(status="in_progress") + 
            todo_manager.get_todos(status="pending")
        )
        
        if not active_todos:
            return []
        
        todos_list = []
        for todo in active_todos:
            todos_list.append(f'"{todo.id}": "{todo.content}"')
        
        todos_json = "{\n  " + ",\n  ".join(todos_list) + "\n}"
        
        prompt = f"""
User message: "{message}"

Active todos:
{todos_json}

Determine which todos are indicated as completed by this user message. Focus on:

EXPLICIT COMPLETION STATEMENTS:
- "I finished X", "X is done", "X is complete"
- "The X is working", "X works now" 
- "I implemented X", "I fixed X", "I built X"
- "X is ready", "X has been completed"

IMPLICIT COMPLETION INDICATORS:
- Results/demonstrations: "The BFS algorithm outputs the correct traversal"
- Working systems: "The authentication system now validates tokens properly"
- Problem resolutions: "The login bug no longer occurs"

WHAT NOT TO MARK AS COMPLETE:
- Questions about todos ("How do I implement X?")
- Requests for help ("Can you help with X?")  
- Planning statements ("I need to work on X")
- Partial progress ("I'm working on X")

Be inclusive but accurate - if work seems genuinely done based on the message, mark it complete.

Return a JSON array of completed todo IDs, e.g.: ["todo-id-1", "todo-id-2"]
If no todos are completed, return: []
"""

        try:
            messages = [{"role": "user", "content": prompt}]
            response = await llm_provider.chat_with_messages(messages)
            response_text = response.content.strip()
            
            import re
            json_match = re.search(r'\[.*?\]', response_text, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
                completed_todo_ids = json.loads(json_str)
                
                for todo_id in completed_todo_ids:
                    if todo_manager.complete_todo(todo_id):
                        completed_ids.append(todo_id)
            
        except Exception as e:
            console.print(f"[dim]LLM auto-completion failed, using fallback: {e}[/dim]")
            return await fallback_auto_complete_todos(message, session_id)
        
    except Exception:
        pass
    
    return completed_ids


async def fallback_auto_complete_todos(message: str, session_id: Optional[str] = None, llm_provider=None) -> List[str]:
    completed_ids = []
    
    try:
        semantic_matcher = _get_semantic_matcher(llm_provider)
        todo_manager = TodoManager(session_id=session_id, semantic_matcher=semantic_matcher)
        active_todos = (
            todo_manager.get_todos(status="in_progress") + 
            todo_manager.get_todos(status="pending")
        )
        
        # Use SemanticMatcher for completion detection with fallback
        if semantic_matcher:
            try:
                todo_contents = [todo.content for todo in active_todos]
                completed_contents = await semantic_matcher.detect_completion_signals(message, todo_contents)
                
                # Match completed contents back to todo IDs
                for completed_content in completed_contents:
                    for todo in active_todos:
                        if todo.content == completed_content:
                            todo_manager.complete_todo(todo.id)
                            completed_ids.append(todo.id)
                            break
            except Exception:
                # Fall back to semantic matcher's fallback method
                todo_contents = [todo.content for todo in active_todos]
                completed_contents = semantic_matcher._fallback_detect_completion(message, todo_contents)
                for completed_content in completed_contents:
                    for todo in active_todos:
                        if todo.content == completed_content:
                            todo_manager.complete_todo(todo.id)
                            completed_ids.append(todo.id)
                            break
        else:
            # Use semantic matcher fallback method directly
            temp_matcher = SemanticMatcher(llm_provider=None)
            todo_contents = [todo.content for todo in active_todos]
            completed_contents = temp_matcher._fallback_detect_completion(message, todo_contents)
            for completed_content in completed_contents:
                for todo in active_todos:
                    if todo.content == completed_content:
                        todo_manager.complete_todo(todo.id)
                        completed_ids.append(todo.id)
                        break
        
    except Exception:
        pass
    
    return completed_ids


def _normalize_todo_content(content: str, semantic_matcher: Optional[SemanticMatcher] = None) -> str:
    """Normalize todo content using SemanticMatcher with fallback."""
    if semantic_matcher:
        return semantic_matcher._fallback_normalize_content(content)
    else:
        # Use temporary semantic matcher for fallback behavior only
        temp_matcher = SemanticMatcher(llm_provider=None)
        return temp_matcher._fallback_normalize_content(content)


async def _calculate_content_similarity(content1: str, content2: str, semantic_matcher: Optional[SemanticMatcher] = None) -> float:
    """Calculate content similarity using SemanticMatcher with fallback to heuristics."""
    if semantic_matcher:
        try:
            return await semantic_matcher.calculate_semantic_similarity(content1, content2)
        except Exception:
            # Fall back to semantic matcher's fallback method
            return semantic_matcher._fallback_similarity(content1, content2)
    else:
        # Use temporary semantic matcher for fallback behavior only
        temp_matcher = SemanticMatcher(llm_provider=None)
        return temp_matcher._fallback_similarity(content1, content2)


# Hardcoded concept and action similarity functions removed - 
# now handled by SemanticMatcher centrally


async def _deduplicate_input_todos(input_todos: List[Dict[str, Any]], llm_provider=None) -> List[Dict[str, Any]]:

    if not input_todos:
        return input_todos
    
    unique_todos = []
    seen_contents = []
    
    for todo in input_todos:
        content = todo.get("content", "").strip()
        if not content:
            continue
            
        # Check if this content is similar to any already seen
        is_duplicate = False
        for seen_content in seen_contents:
            # Use LLM-based semantic matching if available
            semantic_matcher = _get_semantic_matcher(llm_provider)
            if semantic_matcher:
                try:
                    similarity = await semantic_matcher.calculate_semantic_similarity(content, seen_content)
                except Exception:
                    similarity = await _calculate_content_similarity(content, seen_content, semantic_matcher)
            else:
                similarity = await _calculate_content_similarity(content, seen_content, semantic_matcher)
            
            config = get_semantic_config()
            if similarity > config.input_dedup_threshold:
                is_duplicate = True
                break
        
        if not is_duplicate:
            unique_todos.append(todo)
            seen_contents.append(content)
    
    return unique_todos


async def _deduplicate_todos(todos: List, semantic_matcher: Optional[SemanticMatcher] = None) -> List:

    if not todos:
        return todos
    
    # Group todos by normalized content
    content_groups = {}
    
    for todo in todos:
        normalized = _normalize_todo_content(todo.content, semantic_matcher)
        
        # Find if this content matches any existing group
        matched_group = None
        for existing_normalized in content_groups.keys():
            if await _calculate_content_similarity(normalized, existing_normalized, semantic_matcher) > 0.85:
                matched_group = existing_normalized
                break
        
        if matched_group:
            content_groups[matched_group].append(todo)
        else:
            content_groups[normalized] = [todo]
    
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
    try:
        return await llm_auto_complete_todos(message, session_id, llm_provider)
    except Exception:
        try:
            return await fallback_auto_complete_todos(message, session_id)
        except Exception:
            return []


async def analyze_tool_completion(
    tool_name: str,
    tool_args: Dict[str, Any], 
    active_todos: List[Any],
    llm_provider=None
) -> List[str]:

    if not active_todos or not llm_provider:
        return []
    
    from .semantic_config import get_semantic_config
    config = get_semantic_config()
    if not config.enable_auto_todo_completion:
        return []

    action_description = _describe_tool_action(tool_name, tool_args)
    

    todos_list = []
    for todo in active_todos:
        todos_list.append(f'"{todo.id}": "{todo.content}"')
    
    prompt = f"""
Action performed: {action_description}

Active todos:
{{{', '.join(todos_list)}}}

Which todos were completed by this action? Consider:
- Creating a file with implementation completes implementation todos
- Running code successfully completes testing/verification todos  
- A single action can complete multiple related todos
- File edits complete modification/fix todos
- Shell commands that produce expected results complete execution todos

Be inclusive - if the action accomplishes what a todo describes, mark it complete.

Return only the JSON array of completed todo IDs, e.g.: ["todo-id-1", "todo-id-2"]
If no todos are completed, return: []
"""
    
    try:
        messages = [{"role": "user", "content": prompt}]
        response = await llm_provider.chat_with_messages(messages)
        
        # Parse response
        import json
        import re
        json_match = re.search(r'\[.*?\]', response.content, re.DOTALL)
        if json_match:
            completed_ids = json.loads(json_match.group(0))
            
            # Validate that returned IDs exist in active todos
            valid_ids = []
            active_todo_ids = {todo.id for todo in active_todos}
            for todo_id in completed_ids:
                if todo_id in active_todo_ids:
                    valid_ids.append(todo_id)
            
            return valid_ids
    except Exception:
        pass
    
    return []


def _describe_tool_action(tool_name: str, tool_args: Dict[str, Any]) -> str:
    """Create a human-readable description of what a tool did."""
    if tool_name == 'file_create':
        path = tool_args.get('file_path', 'unknown')
        content_preview = tool_args.get('content', '')[:200]
        
        # Analyze content for more context
        content_info = ""
        if content_preview:
            content_lower = content_preview.lower()
            if 'def ' in content_lower or 'class ' in content_lower:
                content_info = " with Python code"
            elif 'function' in content_lower:
                content_info = " with JavaScript/function code"
            elif any(algo in content_lower for algo in ['bfs', 'dfs', 'sort', 'search', 'algorithm']):
                content_info = " implementing an algorithm"
            elif 'import' in content_lower:
                content_info = " with imports and implementation"
            else:
                content_info = " with code implementation"
        
        return f"Created file '{path}'{content_info}. Content preview: {content_preview}..."
    
    elif tool_name == 'file_edit':
        path = tool_args.get('file_path', 'unknown')
        return f"Edited file '{path}'"
    
    elif tool_name == 'shell_exec':
        cmd = tool_args.get('command', 'unknown')
        return f"Executed command: {cmd}"
    
    elif tool_name == 'file_search':
        pattern = tool_args.get('pattern', 'unknown')
        return f"Searched for files matching pattern: {pattern}"
    
    elif tool_name == 'grep':
        pattern = tool_args.get('pattern', 'unknown')
        return f"Searched file contents for: {pattern}"
    
    else:
        return f"Performed {tool_name} action with args: {tool_args}"