# songbird/tools/file_operations.py
"""
File operations tools for reading and editing files with diff previews.
"""
import difflib
import os
from pathlib import Path
from typing import Dict, Any, List, Optional
from rich.console import Console
from rich.syntax import Syntax
from rich.panel import Panel
from rich.text import Text


console = Console()


async def file_read(file_path: str, lines: Optional[int] = None, start_line: Optional[int] = None) -> Dict[str, Any]:
    """
    Read file contents for LLM analysis.
    
    Args:
        file_path: Path to file to read
        lines: Number of lines to read (None = all)
        start_line: Starting line number (1-indexed, None = start from beginning)
        
    Returns:
        Dictionary with file contents and metadata
    """
    try:
        path = Path(file_path)
        
        if not path.exists():
            return {
                "success": False,
                "error": f"File not found: {file_path}"
            }
            
        if not path.is_file():
            return {
                "success": False,
                "error": f"Path is not a file: {file_path}"
            }
        
        # Check if file is too large (> 1MB)
        if path.stat().st_size > 1024 * 1024:
            return {
                "success": False,
                "error": f"File too large (>1MB): {file_path}"
            }
        
        with open(path, 'r', encoding='utf-8') as f:
            all_lines = f.readlines()
        
        # Handle line range selection
        if start_line is not None:
            start_idx = max(0, start_line - 1)  # Convert to 0-indexed
            if lines is not None:
                selected_lines = all_lines[start_idx:start_idx + lines]
            else:
                selected_lines = all_lines[start_idx:]
        else:
            if lines is not None:
                selected_lines = all_lines[:lines]
            else:
                selected_lines = all_lines
        
        content = ''.join(selected_lines)
        
        return {
            "success": True,
            "file_path": str(path),
            "content": content,
            "total_lines": len(all_lines),
            "lines_returned": len(selected_lines),
            "encoding": "utf-8"
        }
        
    except UnicodeDecodeError:
        return {
            "success": False,
            "error": f"Cannot read file (binary or encoding issue): {file_path}"
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Error reading file: {e}"
        }


async def file_edit(file_path: str, new_content: str, create_backup: bool = True) -> Dict[str, Any]:
    """
    Edit file with diff preview and confirmation.
    
    Args:
        file_path: Path to file to edit
        new_content: New file content
        create_backup: Whether to create .bak backup
        
    Returns:
        Dictionary with operation result and diff preview
    """
    try:
        path = Path(file_path)
        
        # Read existing content if file exists
        old_content = ""
        if path.exists():
            if not path.is_file():
                return {
                    "success": False,
                    "error": f"Path exists but is not a file: {file_path}"
                }
            
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    old_content = f.read()
            except UnicodeDecodeError:
                return {
                    "success": False,
                    "error": f"Cannot edit binary file: {file_path}"
                }
        
        # Generate diff
        old_lines = old_content.splitlines(keepends=True)
        new_lines = new_content.splitlines(keepends=True)
        
        diff_lines = list(difflib.unified_diff(
            old_lines, 
            new_lines,
            fromfile=f"a/{path.name}",
            tofile=f"b/{path.name}",
            lineterm=""
        ))
        
        # Create diff preview
        diff_preview = _format_diff_preview(diff_lines)
        
        return {
            "success": True,
            "file_path": str(path),
            "diff_preview": diff_preview,
            "changes_made": len(diff_lines) > 0,
            "old_content": old_content,
            "new_content": new_content,
            "requires_confirmation": True
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": f"Error preparing file edit: {e}"
        }


async def apply_file_edit(file_path: str, new_content: str, create_backup: bool = True) -> Dict[str, Any]:
    """
    Actually apply the file edit after confirmation.
    
    Args:
        file_path: Path to file to edit
        new_content: New file content
        create_backup: Whether to create .bak backup
        
    Returns:
        Dictionary with operation result
    """
    try:
        path = Path(file_path)
        file_existed = path.exists()
        
        # Create backup if requested and file exists
        if create_backup and file_existed:
            backup_path = path.with_suffix(path.suffix + '.bak')
            backup_path.write_text(path.read_text(encoding='utf-8'), encoding='utf-8')
        
        # Ensure parent directory exists
        path.parent.mkdir(parents=True, exist_ok=True)
        
        # Write new content
        with open(path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        
        return {
            "success": True,
            "file_path": str(path),
            "message": f"File {'updated' if file_existed else 'created'} successfully",
            "backup_created": create_backup and file_existed
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": f"Error applying file edit: {e}"
        }


def _format_diff_preview(diff_lines: List[str]) -> str:
    """Format diff lines with color coding for terminal display."""
    if not diff_lines:
        return "No changes detected."
    
    # Create Rich Text object for colored diff
    diff_text = Text()
    
    for line in diff_lines:
        if line.startswith('+++') or line.startswith('---'):
            diff_text.append(line + '\n', style="bold blue")
        elif line.startswith('@@'):
            diff_text.append(line + '\n', style="bold cyan")
        elif line.startswith('+'):
            diff_text.append(line + '\n', style="bold green")
        elif line.startswith('-'):
            diff_text.append(line + '\n', style="bold red")
        else:
            diff_text.append(line + '\n', style="dim")
    
    # Use console to render to string
    with console.capture() as capture:
        console.print(diff_text, end="")
    
    return capture.get()


def display_diff_preview(diff_preview: str, file_path: str):
    """Display a formatted diff preview with Rich."""
    panel = Panel(
        diff_preview,
        title=f"📝 Proposed changes to {file_path}",
        title_align="left",
        border_style="blue"
    )
    console.print(panel)