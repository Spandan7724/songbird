# songbird/tools/file_operations.py
"""
File operations tools for reading and editing files with diff previews.
"""
import difflib
from pathlib import Path
from typing import Dict, Any, List, Optional
from rich.console import Console
from rich.syntax import Syntax
from rich.panel import Panel


console = Console()

# Session-level tracking of read files
_session_read_files = set()

def mark_file_as_read(file_path: str):
    """Mark a file as read in the current session."""
    _session_read_files.add(str(Path(file_path).resolve()))

def was_file_read_in_session(file_path: str) -> bool:
    """Check if a file was read in the current session."""
    return str(Path(file_path).resolve()) in _session_read_files

def clear_session_read_tracking():
    """Clear the session read tracking (for new sessions)."""
    _session_read_files.clear()


def _get_lexer_from_filename(filename: str) -> str:
    """Get appropriate lexer based on file extension."""
    ext = Path(filename).suffix.lower()
    lexer_map = {
        '.py': 'python',
        '.js': 'javascript',
        '.ts': 'typescript',
        '.jsx': 'jsx',
        '.tsx': 'tsx',
        '.java': 'java',
        '.c': 'c',
        '.cpp': 'cpp',
        '.cs': 'csharp',
        '.go': 'go',
        '.rs': 'rust',
        '.php': 'php',
        '.rb': 'ruby',
        '.swift': 'swift',
        '.kt': 'kotlin',
        '.scala': 'scala',
        '.r': 'r',
        '.m': 'matlab',
        '.sql': 'sql',
        '.sh': 'bash',
        '.ps1': 'powershell',
        '.yaml': 'yaml',
        '.yml': 'yaml',
        '.json': 'json',
        '.xml': 'xml',
        '.html': 'html',
        '.css': 'css',
        '.scss': 'scss',
        '.sass': 'sass',
        '.less': 'less',
        '.md': 'markdown',
        '.rst': 'rst',
        '.tex': 'latex',
        '.vim': 'vim',
        '.lua': 'lua',
        '.dart': 'dart',
        '.elm': 'elm',
        '.clj': 'clojure',
        '.ex': 'elixir',
        '.erl': 'erlang',
        '.fs': 'fsharp',
        '.hs': 'haskell',
        '.jl': 'julia',
        '.nim': 'nim',
        '.ml': 'ocaml',
        '.pl': 'perl',
        '.raku': 'perl6',
        '.purs': 'purescript',
        '.rkt': 'racket',
        '.re': 'reason',
        '.v': 'verilog',
        '.vhd': 'vhdl',
        '.zig': 'zig',
        '.toml': 'toml',
        '.ini': 'ini',
        '.cfg': 'ini',
        '.conf': 'apache',
        '.bat': 'batch',
        '.dockerfile': 'docker',
        '.makefile': 'makefile',
        '.cmake': 'cmake',
        '.gradle': 'groovy',
        '.proto': 'protobuf',
        '.diff': 'diff',
        '.patch': 'diff',
    }
    return lexer_map.get(ext, 'text')


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
        
        # Mark file as read in current session
        mark_file_as_read(file_path)
        
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


async def file_edit(file_path: str, new_content: str, create_backup: bool = False) -> Dict[str, Any]:
    """
    Edit file with diff preview and confirmation.
    Automatically reads the file first if it hasn't been read in this session.
    
    Args:
        file_path: Path to file to edit
        new_content: New file content
        create_backup: Whether to create .bak backup
        
    Returns:
        Dictionary with operation result and diff preview
    """
    try:
        path = Path(file_path)
        
        # Check if file exists and hasn't been read in this session
        if path.exists() and not was_file_read_in_session(file_path):
            console.print(f"[dim]Reading file before editing: {file_path}[/dim]")
            read_result = await file_read(file_path)
            if not read_result.get("success"):
                return {
                    "success": False,
                    "error": f"Could not read file before editing: {read_result.get('error', 'Unknown error')}"
                }
            console.print(f"[dim]File content loaded ({read_result.get('lines_returned', 0)} lines)[/dim]")
        
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


async def file_create(file_path: str, content: str) -> Dict[str, Any]:
    """
    Create a new file with the specified content.
    
    Args:
        file_path: Path to the new file to create
        content: Content to write to the file
        
    Returns:
        Dictionary with operation result
    """
    import asyncio
    
    try:
        path = Path(file_path)
        
        # Check if file already exists
        if path.exists():
            return {
                "success": False,
                "error": f"File already exists: {file_path}. Use file_edit to modify existing files."
            }
        
        # Print creation message immediately
        console.print(f"\n[bold green]Creating new file:[/bold green] {path}")
        
        # Small delay to ensure message is visible before file preview
        await asyncio.sleep(0.05)
        
        # Show preview of what will be created
        syntax = Syntax(
            content,
            lexer=_get_lexer_from_filename(str(path)),
            theme="github-dark",
            line_numbers=True,
            word_wrap=False
        )
        panel = Panel(
            syntax,
            title=f"New file: {path.name}",
            title_align="left",
            border_style="green",
            expand=True
        )
        console.print(panel)
        
        # Ensure parent directory exists
        path.parent.mkdir(parents=True, exist_ok=True)
        
        # Write content to new file
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        return {
            "success": True,
            "file_path": str(path),
            "message": f"Created new file: {path.name}",
            "lines_written": len(content.splitlines()),
            "content_preview_shown": True
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": f"Error creating file: {e}"
        }


async def apply_file_edit(file_path: str, new_content: str) -> Dict[str, Any]:
    """
    Actually apply the file edit after confirmation.
    
    Args:
        file_path: Path to file to edit
        new_content: New file content
        
    Returns:
        Dictionary with operation result
    """
    try:
        path = Path(file_path)
        file_existed = path.exists()
        
        # Ensure parent directory exists
        path.parent.mkdir(parents=True, exist_ok=True)
        
        # Write new content
        with open(path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        
        return {
            "success": True,
            "file_path": str(path),
            "message": f"File {'updated' if file_existed else 'created'} successfully"
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
    
    # Simple string formatting for better compatibility
    formatted_lines = []
    for line in diff_lines:
        formatted_lines.append(line)
    
    return '\n'.join(formatted_lines)


def display_diff_preview(diff_preview: str, file_path: str):
    """Display a formatted diff preview with Rich."""
    # Add spacing to prevent cutoff from status messages
    console.print()
    
    # Use Rich's Syntax for better diff display
    syntax = Syntax(
        diff_preview, 
        "diff", 
        theme="github-dark", 
        line_numbers=False,
        word_wrap=False,
        background_color="default"
    )
    panel = Panel(
        syntax,
        title=f"Proposed changes to {file_path}",
        title_align="left",
        border_style="blue",
        expand=True,
        width=None  # Let it auto-size to content
    )
    console.print(panel)
    
    
## CUSTOM DIFF PREVIEW FUNCTIONALITY
# Uncomment this function if you want to use the custom diff preview display    
# def display_diff_preview(diff_preview: str, file_path: str):
#     """Display a formatted diff preview with Rich."""
#     # Process diff lines to apply custom colors
#     lines = diff_preview.split('\n')
#     formatted_text = Text()
    
#     for line in lines:
#         if line.startswith('---'):
#             # File header (old file)
#             formatted_text.append(line + '\n', style="bold blue")
#         elif line.startswith('+++'):
#             # File header (new file)
#             formatted_text.append(line + '\n', style="bold blue")
#         elif line.startswith('@@'):
#             # Hunk header
#             formatted_text.append(line + '\n', style="bold cyan")
#         elif line.startswith('-'):
#             # Removed lines - you can change this color!
#             formatted_text.append(line + '\n', style="bold red")
#         elif line.startswith('+'):
#             # Added lines
#             formatted_text.append(line + '\n', style="bold green")
#         else:
#             # Context lines (unchanged)
#             formatted_text.append(line + '\n', style="dim white")
    
#     panel = Panel(
#         formatted_text,
#         title=f"Proposed changes to {file_path}",
#         title_align="left",
#         border_style="blue",
#         expand=True,
#         width=None  # Let it auto-size to content
#     )
#     console.print(panel)        