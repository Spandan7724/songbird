# songbird/tools/tree_tool.py
"""
Tree tool for displaying project structure in a clean tree format.
Optimized specifically for project overview and structure visualization.
"""
from pathlib import Path
from typing import Dict, Any, List, Optional, Set
from rich.console import Console

console = Console()

# Common directories and files to exclude by default
DEFAULT_EXCLUDES = {
    # Version control
    '.git', '.svn', '.hg', 
    # Dependencies
    'node_modules', '__pycache__', '.venv', 'venv', 'env',
    # Build artifacts
    'dist', 'build', '.next', '.nuxt', 'target',
    # IDE files
    '.vscode', '.idea', '.vs',
    # Temporary files
    '.tmp', 'tmp', '.cache', 'cache',
    # OS files
    '.DS_Store', 'Thumbs.db',
    # Python specific
    '*.egg-info', '.pytest_cache', '.mypy_cache',
    # JavaScript/Node specific
    '.npm', '.yarn', 'coverage',
    # Rust specific
    'target',
    # Go specific
    'vendor'
}


async def tree_display(
    path: str = ".",
    max_depth: int = 3,
    show_hidden: bool = False,
    show_sizes: bool = True,
    exclude_patterns: Optional[List[str]] = None,
    include_only: Optional[List[str]] = None,
    dirs_only: bool = False,
    files_only: bool = False
) -> Dict[str, Any]:
    """
    Display directory structure in a clean tree format optimized for project overview.
    
    Args:
        path: Directory path to display tree for (default: current directory)
        max_depth: Maximum depth to traverse (default: 3)
        show_hidden: Whether to show hidden files/directories (default: False)
        show_sizes: Whether to show file sizes (default: True)
        exclude_patterns: Additional patterns to exclude (default: None)
        include_only: Only include files/dirs matching these patterns (default: None)
        dirs_only: Show only directories (default: False)
        files_only: Show only files (default: False)
        
    Returns:
        Dictionary with tree structure and metadata
    """
    try:
        # Resolve directory path
        dir_path = Path(path).resolve()
        if not dir_path.exists():
            return {
                "success": False,
                "error": f"Directory not found: {path}",
                "tree_output": None,
                "total_items": 0,
                "file_count": 0,
                "dir_count": 0
            }
        
        if not dir_path.is_dir():
            return {
                "success": False,
                "error": f"Path is not a directory: {path}",
                "tree_output": None,
                "total_items": 0,
                "file_count": 0,
                "dir_count": 0
            }
        
        # Prepare exclusion patterns
        excludes = set(DEFAULT_EXCLUDES)
        if exclude_patterns:
            excludes.update(exclude_patterns)
        
        # Show tree header
        console.print(f"[bold cyan]Tree structure of:[/bold cyan] {dir_path}")
        if max_depth < 10:
            console.print(f"[dim]Max depth: {max_depth} | Hidden files: {'shown' if show_hidden else 'hidden'}[/dim]")
        console.print()
        
        # Build and display tree
        tree_data = await _build_tree_structure(
            dir_path, max_depth, show_hidden, excludes, 
            include_only, dirs_only, files_only
        )
        
        if not tree_data["entries"]:
            console.print("[dim]No items to display[/dim]")
            return {
                "success": True,
                "tree_output": "empty",
                "total_items": 0,
                "file_count": 0,
                "dir_count": 0
            }
        
        # Display the tree
        tree_output = _display_tree_structure(
            tree_data["entries"], show_sizes, str(dir_path)
        )
        
        # Show summary
        file_count = tree_data["file_count"]
        dir_count = tree_data["dir_count"]
        total_items = file_count + dir_count
        
        console.print()
        summary_parts = []
        if dir_count > 0:
            summary_parts.append(f"{dir_count} directories")
        if file_count > 0:
            summary_parts.append(f"{file_count} files")
        
        if summary_parts:
            console.print(f"[green]{', '.join(summary_parts)} displayed[/green]")
        
        return {
            "success": True,
            "tree_output": tree_output,
            "total_items": total_items,
            "file_count": file_count,
            "dir_count": dir_count,
            "max_depth": max_depth,
            "path": str(dir_path)
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": f"Error generating tree: {e}",
            "tree_output": None,
            "total_items": 0,
            "file_count": 0,
            "dir_count": 0
        }


async def _build_tree_structure(
    root_path: Path,
    max_depth: int,
    show_hidden: bool,
    excludes: Set[str],
    include_only: Optional[List[str]],
    dirs_only: bool,
    files_only: bool,
    current_depth: int = 0
) -> Dict[str, Any]:
    """Build tree structure recursively."""
    
    entries = []
    file_count = 0
    dir_count = 0
    
    if current_depth >= max_depth:
        return {"entries": entries, "file_count": file_count, "dir_count": dir_count}
    
    try:
        # Get directory contents
        items = []
        for item in root_path.iterdir():
            # Skip hidden files unless requested
            if not show_hidden and item.name.startswith('.'):
                continue
            
            # Check exclusion patterns
            if _should_exclude(item.name, excludes):
                continue
            
            # Apply include filter
            if include_only and not any(pattern in item.name for pattern in include_only):
                continue
            
            # Apply type filters - but still need to process directories for recursion
            if dirs_only and not item.is_dir():
                continue
                
            items.append(item)
        
        # Sort items: directories first, then files, both alphabetically
        items.sort(key=lambda x: (not x.is_dir(), x.name.lower()))
        
        for item in items:
            # Determine if we should include this item in the display
            should_include = True
            if files_only and item.is_dir():
                should_include = False
            elif dirs_only and item.is_file():
                should_include = False
            
            if should_include:
                entry = {
                    "name": item.name,
                    "path": str(item.relative_to(root_path)),
                    "is_dir": item.is_dir(),
                    "is_file": item.is_file(),
                    "depth": current_depth,
                    "size": 0
                }
                
                # Get file size for files
                if item.is_file():
                    try:
                        entry["size"] = item.stat().st_size
                        file_count += 1
                    except Exception:
                        entry["size"] = 0
                else:
                    dir_count += 1
                
                entries.append(entry)
            
            # Always recurse into subdirectories to find nested files/dirs
            if item.is_dir() and current_depth < max_depth - 1:
                sub_tree = await _build_tree_structure(
                    item, max_depth, show_hidden, excludes,
                    include_only, dirs_only, files_only, current_depth + 1
                )
                entries.extend(sub_tree["entries"])
                file_count += sub_tree["file_count"]
                dir_count += sub_tree["dir_count"]
    
    except PermissionError:
        # Skip directories we can't read
        pass
    
    return {"entries": entries, "file_count": file_count, "dir_count": dir_count}


def _should_exclude(name: str, excludes: Set[str]) -> bool:
    """Check if a name should be excluded based on patterns."""
    # Exact match
    if name in excludes:
        return True
    
    # Pattern matching for wildcards
    for pattern in excludes:
        if '*' in pattern:
            import fnmatch
            if fnmatch.fnmatch(name, pattern):
                return True
    
    return False


def _display_tree_structure(
    entries: List[Dict[str, Any]], 
    show_sizes: bool,
    root_path: str
) -> str:
    """Display tree structure with proper Unicode connectors."""
    
    if not entries:
        return "empty"
    
    # Group entries by their full paths to build proper tree structure
    tree_lines = []
    path_stack = []  # Track which paths are being displayed
    
    # Build tree display
    for i, entry in enumerate(entries):
        depth = entry["depth"]
        name = entry["name"]
        is_dir = entry["is_dir"]
        size = entry.get("size", 0)
        
        # Determine if this is the last item at this depth level
        is_last_at_depth = _is_last_at_depth(entries, i, depth)
        
        # Build the prefix (tree connectors)
        prefix = _build_tree_prefix(depth, is_last_at_depth, path_stack)
        
        # Format the name with styling
        if is_dir:
            display_name = f"[spring_green1]{name}/[/spring_green1]"
        else:
            display_name = name
            # Add file size if requested and available
            if show_sizes and size > 0:
                display_name += f" [dim]({_format_size(size)})[/dim]"
        
        # Create the tree line
        tree_line = f"{prefix}{display_name}"
        tree_lines.append(tree_line)
        console.print(tree_line)
        
        # Update path stack for next iteration
        _update_path_stack(path_stack, depth, is_last_at_depth)
    
    return "\n".join([line.replace("[blue]", "").replace("[/blue]", "").replace("[dim]", "").replace("[/dim]", "") for line in tree_lines])


def _is_last_at_depth(entries: List[Dict[str, Any]], current_index: int, depth: int) -> bool:
    """Determine if current entry is the last one at its depth level."""
    
    # Look ahead to see if there are more entries at the same or shallower depth
    for i in range(current_index + 1, len(entries)):
        next_entry = entries[i]
        next_depth = next_entry["depth"]
        
        if next_depth < depth:
            # We've moved to a shallower level, so this was the last at this depth
            return True
        elif next_depth == depth:
            # There's another entry at the same depth, so this is not the last
            return False
    
    # No more entries at the same or shallower depth, so this is the last
    return True


def _build_tree_prefix(depth: int, is_last: bool, path_stack: List[bool]) -> str:
    """Build the tree prefix with proper Unicode connectors."""
    
    if depth == 0:
        return ""
    
    prefix = ""
    
    # Build prefix based on parent levels
    for level in range(depth - 1):
        if level < len(path_stack) and not path_stack[level]:
            prefix += "│   "  # Vertical line for non-last items
        else:
            prefix += "    "  # Empty space for last items
    
    # Add connector for current level
    if is_last:
        prefix += "└── "  # Last item connector
    else:
        prefix += "├── "  # Middle item connector
    
    return prefix


def _update_path_stack(path_stack: List[bool], depth: int, is_last: bool):
    """Update the path stack to track which levels are at their last item."""
    
    # Ensure path_stack has enough elements
    while len(path_stack) <= depth:
        path_stack.append(False)
    
    # Update the current depth
    if depth < len(path_stack):
        path_stack[depth] = is_last
    
    # Trim path_stack to current depth + 1
    path_stack[depth + 1:] = []


def _format_size(size_bytes: int) -> str:
    """Format file size in human-readable format."""
    if size_bytes < 1024:
        return f"{size_bytes}B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f}KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f}MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.1f}GB"


# Utility functions for enhanced tree operations

async def tree_project_overview(path: str = ".") -> Dict[str, Any]:
    """
    Display a clean project overview focusing on main structure.
    
    Args:
        path: Project root path
        
    Returns:
        Dictionary with project tree overview
    """
    return await tree_display(
        path=path,
        max_depth=2,
        show_hidden=False,
        show_sizes=False,
        dirs_only=False,
        files_only=False
    )


async def tree_files_only(path: str = ".", max_depth: int = 3) -> Dict[str, Any]:
    """
    Display only files in tree format.
    
    Args:
        path: Directory path
        max_depth: Maximum depth to traverse
        
    Returns:
        Dictionary with files-only tree
    """
    return await tree_display(
        path=path,
        max_depth=max_depth,
        files_only=True,
        show_sizes=True
    )


async def tree_dirs_only(path: str = ".", max_depth: int = 5) -> Dict[str, Any]:
    """
    Display only directories in tree format.
    
    Args:
        path: Directory path
        max_depth: Maximum depth to traverse
        
    Returns:
        Dictionary with directories-only tree
    """
    return await tree_display(
        path=path,
        max_depth=max_depth,
        dirs_only=True,
        show_sizes=False
    )