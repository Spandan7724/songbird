# songbird/tools/ls_tool.py
"""
LS tool for enhanced directory listing with Rich formatting.

"""
import os
import stat
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text

console = Console()


async def ls_directory(
    path: str = ".",
    show_hidden: bool = False,
    long_format: bool = False,
    sort_by: str = "name",
    reverse: bool = False,
    recursive: bool = False,
    max_depth: int = 3,
    file_type_filter: Optional[str] = None
) -> Dict[str, Any]:
    """
    List directory contents with enhanced formatting and options.
    
    Args:
        path: Directory path to list (default: current directory)
        show_hidden: Whether to show hidden files/directories (default: False)
        long_format: Whether to show detailed information (default: False)
        sort_by: Sort criteria: 'name', 'size', 'modified', 'type' (default: 'name')
        reverse: Whether to reverse sort order (default: False)
        recursive: Whether to list subdirectories recursively (default: False)
        max_depth: Maximum depth for recursive listing (default: 3)
        file_type_filter: Filter by file type: 'files', 'dirs', or None for both (default: None)
        
    Returns:
        Dictionary with directory listing and metadata
    """
    try:
        # Resolve directory path
        dir_path = Path(path).resolve()
        if not dir_path.exists():
            return {
                "success": False,
                "error": f"Directory not found: {path}",
                "entries": []
            }
        
        if not dir_path.is_dir():
            return {
                "success": False,
                "error": f"Path is not a directory: {path}",
                "entries": []
            }
        
        console.print(f"\n[bold cyan]Directory listing:[/bold cyan] {dir_path}")
        
        # Get directory entries
        if recursive:
            entries = await _get_recursive_entries(
                dir_path, show_hidden, max_depth, file_type_filter
            )
        else:
            entries = await _get_directory_entries(
                dir_path, show_hidden, file_type_filter
            )
        
        # Sort entries
        entries = _sort_entries(entries, sort_by, reverse)
        
        # Display results
        if long_format:
            _display_long_format(entries, dir_path, recursive)
        else:
            _display_short_format(entries, dir_path, recursive)
        
        # Prepare summary
        total_files = len([e for e in entries if e["is_file"]])
        total_dirs = len([e for e in entries if e["is_dir"]])
        
        return {
            "success": True,
            "path": str(dir_path),
            "entries": entries,
            "total_files": total_files,
            "total_directories": total_dirs,
            "total_entries": len(entries),
            "display_shown": True,
            "long_format": long_format,
            "recursive": recursive
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": f"Error listing directory: {e}",
            "entries": []
        }


async def _get_directory_entries(
    dir_path: Path,
    show_hidden: bool,
    file_type_filter: Optional[str]
) -> List[Dict[str, Any]]:
    """Get entries from a single directory."""
    entries = []
    
    try:
        for item in dir_path.iterdir():
            # Skip hidden files unless requested
            if not show_hidden and item.name.startswith('.'):
                continue
            
            # Apply file type filter
            if file_type_filter == "files" and not item.is_file():
                continue
            elif file_type_filter == "dirs" and not item.is_dir():
                continue
            
            entry = await _get_entry_info(item, dir_path)
            entries.append(entry)
            
    except PermissionError:
        # Handle permission denied gracefully
        pass
    
    return entries


async def _get_recursive_entries(
    dir_path: Path,
    show_hidden: bool,
    max_depth: int,
    file_type_filter: Optional[str],
    current_depth: int = 0
) -> List[Dict[str, Any]]:
    """Get entries recursively with depth limit."""
    entries = []
    
    if current_depth >= max_depth:
        return entries
    
    try:
        for item in dir_path.iterdir():
            # Skip hidden files unless requested
            if not show_hidden and item.name.startswith('.'):
                continue
            
            # Apply file type filter
            if file_type_filter == "files" and not item.is_file():
                continue
            elif file_type_filter == "dirs" and not item.is_dir():
                continue
            
            entry = await _get_entry_info(item, dir_path.parent if current_depth > 0 else dir_path)
            entry["depth"] = current_depth
            entries.append(entry)
            
            # Recurse into subdirectories
            if item.is_dir() and current_depth < max_depth - 1:
                subentries = await _get_recursive_entries(
                    item, show_hidden, max_depth, file_type_filter, current_depth + 1
                )
                entries.extend(subentries)
                
    except PermissionError:
        # Handle permission denied gracefully
        pass
    
    return entries


async def _get_entry_info(item: Path, base_path: Path) -> Dict[str, Any]:
    """Get detailed information about a file or directory."""
    try:
        item_stat = item.stat()
        
        # Get relative path
        try:
            relative_path = item.relative_to(base_path)
        except ValueError:
            relative_path = item
        
        entry = {
            "name": item.name,
            "path": str(relative_path),
            "absolute_path": str(item),
            "is_file": item.is_file(),
            "is_dir": item.is_dir(),
            "is_symlink": item.is_symlink(),
            "size": item_stat.st_size if item.is_file() else 0,
            "size_human": _format_file_size(item_stat.st_size) if item.is_file() else "—",
            "modified": item_stat.st_mtime,
            "modified_human": _format_modification_time(item_stat.st_mtime),
            "permissions": _format_permissions(item_stat.st_mode),
            "owner": _get_owner_info(item_stat),
        }
        
        # Add file extension for files
        if item.is_file():
            entry["extension"] = item.suffix.lower()
        else:
            entry["extension"] = ""
        
        # Add symlink target if applicable
        if item.is_symlink():
            try:
                entry["symlink_target"] = str(item.readlink())
            except Exception:
                entry["symlink_target"] = "broken"
        
        return entry
        
    except Exception as e:
        # Return minimal info if stat fails
        return {
            "name": item.name,
            "path": str(item),
            "absolute_path": str(item),
            "is_file": False,
            "is_dir": False,
            "is_symlink": False,
            "size": 0,
            "size_human": "unknown",
            "modified": 0,
            "modified_human": "unknown",
            "permissions": "unknown",
            "owner": "unknown",
            "extension": "",
            "error": str(e)
        }


def _sort_entries(entries: List[Dict[str, Any]], sort_by: str, reverse: bool) -> List[Dict[str, Any]]:
    """Sort directory entries by specified criteria."""
    sort_key_map = {
        "name": lambda e: e["name"].lower(),
        "size": lambda e: e["size"],
        "modified": lambda e: e["modified"],
        "type": lambda e: (not e["is_dir"], e["name"].lower()),  # Directories first, then by name
    }
    
    sort_key = sort_key_map.get(sort_by, sort_key_map["name"])
    
    return sorted(entries, key=sort_key, reverse=reverse)


def _display_short_format(entries: List[Dict[str, Any]], dir_path: Path, recursive: bool):
    """Display directory entries in short format (grid layout)."""
    if not entries:
        console.print("[dim]Directory is empty[/dim]")
        return
    
    # Group by type for better organization
    directories = [e for e in entries if e["is_dir"]]
    files = [e for e in entries if e["is_file"]]
    symlinks = [e for e in entries if e["is_symlink"]]
    
    # Create table for better alignment
    table = Table(
        show_header=True,
        header_style="bold cyan",
        box=None,
        pad_edge=False
    )
    table.add_column("Type", width=6)
    table.add_column("Name", ratio=1)
    table.add_column("Size", justify="right", width=10)
    table.add_column("Modified", width=12)
    
    # Add directories first
    for entry in directories:
        name_display = entry["name"]
        if recursive and "depth" in entry:
            indent = "  " * entry["depth"]
            name_display = f"{indent}{name_display}"
        
        table.add_row(
            "📁 DIR",
            f"[bold blue]{name_display}[/bold blue]",
            "—",
            entry["modified_human"]
        )
    
    # Add files
    for entry in files:
        name_display = entry["name"]
        if recursive and "depth" in entry:
            indent = "  " * entry["depth"]
            name_display = f"{indent}{name_display}"
        
        # Color by file type
        file_color = _get_file_color(entry["extension"])
        
        table.add_row(
            "📄 FILE",
            f"[{file_color}]{name_display}[/{file_color}]",
            entry["size_human"],
            entry["modified_human"]
        )
    
    # Add symlinks
    for entry in symlinks:
        name_display = entry["name"]
        if recursive and "depth" in entry:
            indent = "  " * entry["depth"]
            name_display = f"{indent}{name_display}"
        
        target = entry.get("symlink_target", "unknown")
        
        table.add_row(
            "🔗 LINK",
            f"[cyan]{name_display}[/cyan] → [dim]{target}[/dim]",
            "—",
            entry["modified_human"]
        )
    
    # Display in a panel
    title = f"Contents of {dir_path.name or dir_path}"
    if recursive:
        title += " (recursive)"
    
    panel = Panel(table, title=title, border_style="blue", padding=(1, 2))
    console.print(panel)
    
    # Show summary
    summary_parts = []
    if directories:
        summary_parts.append(f"📁 {len(directories)} directories")
    if files:
        summary_parts.append(f"📄 {len(files)} files")
    if symlinks:
        summary_parts.append(f"🔗 {len(symlinks)} symlinks")
    
    if summary_parts:
        console.print(f"\n[bold]Summary:[/bold] {', '.join(summary_parts)}")


def _display_long_format(entries: List[Dict[str, Any]], dir_path: Path, recursive: bool):
    """Display directory entries in long format (detailed list)."""
    if not entries:
        console.print("[dim]Directory is empty[/dim]")
        return
    
    # Create detailed table
    table = Table(
        show_header=True,
        header_style="bold cyan"
    )
    table.add_column("Permissions", width=12)
    table.add_column("Owner", width=10)
    table.add_column("Size", justify="right", width=10)
    table.add_column("Modified", width=16)
    table.add_column("Name", ratio=1)
    
    for entry in entries:
        name_display = entry["name"]
        if recursive and "depth" in entry:
            indent = "  " * entry["depth"]
            name_display = f"{indent}{name_display}"
        
        # Style name by type
        if entry["is_dir"]:
            name_display = f"📁 [bold blue]{name_display}[/bold blue]"
        elif entry["is_symlink"]:
            target = entry.get("symlink_target", "unknown")
            name_display = f"🔗 [cyan]{name_display}[/cyan] → [dim]{target}[/dim]"
        else:
            file_color = _get_file_color(entry["extension"])
            name_display = f"📄 [{file_color}]{name_display}[/{file_color}]"
        
        table.add_row(
            entry["permissions"],
            entry["owner"],
            entry["size_human"],
            entry["modified_human"],
            name_display
        )
    
    # Display in a panel
    title = f"Detailed listing of {dir_path.name or dir_path}"
    if recursive:
        title += " (recursive)"
    
    panel = Panel(table, title=title, border_style="blue", padding=(1, 2))
    console.print(panel)


def _format_file_size(size_bytes: int) -> str:
    """Format file size in human-readable format."""
    if size_bytes == 0:
        return "0 B"
    
    size_names = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    size = float(size_bytes)
    
    while size >= 1024.0 and i < len(size_names) - 1:
        size /= 1024.0
        i += 1
    
    if i == 0:
        return f"{int(size)} {size_names[i]}"
    else:
        return f"{size:.1f} {size_names[i]}"


def _format_modification_time(timestamp: float) -> str:
    """Format modification time in human-readable format."""
    try:
        dt = datetime.fromtimestamp(timestamp)
        now = datetime.now()
        
        # If within last 24 hours, show time
        if (now - dt).days == 0:
            return dt.strftime("%H:%M:%S")
        # If within last week, show day and time
        elif (now - dt).days < 7:
            return dt.strftime("%a %H:%M")
        # If within last year, show month/day time
        elif (now - dt).days < 365:
            return dt.strftime("%m/%d %H:%M")
        # Otherwise show full date
        else:
            return dt.strftime("%m/%d/%Y")
    except Exception:
        return "unknown"


def _format_permissions(mode: int) -> str:
    """Format file permissions in human-readable format."""
    try:
        # Convert to rwx format
        perms = stat.filemode(mode)
        return perms
    except Exception:
        return "unknown"


def _get_owner_info(item_stat) -> str:
    """Get file owner information."""
    try:
        import pwd
        owner = pwd.getpwuid(item_stat.st_uid).pw_name
        return owner
    except (ImportError, KeyError, OSError):
        # Windows or owner not found
        try:
            return str(item_stat.st_uid)
        except Exception:
            return "unknown"


def _get_file_color(extension: str) -> str:
    """Get color for file based on extension."""
    color_map = {
        # Programming languages
        ".py": "green",
        ".js": "yellow",
        ".ts": "blue",
        ".jsx": "yellow",
        ".tsx": "blue",
        ".java": "red",
        ".c": "blue",
        ".cpp": "blue",
        ".cs": "purple",
        ".go": "cyan",
        ".rs": "orange",
        ".php": "purple",
        ".rb": "red",
        ".swift": "orange",
        
        # Web
        ".html": "orange",
        ".css": "blue",
        ".scss": "pink",
        ".less": "blue",
        
        # Data
        ".json": "yellow",
        ".xml": "orange",
        ".yaml": "green",
        ".yml": "green",
        ".csv": "green",
        ".sql": "blue",
        
        # Documentation
        ".md": "blue",
        ".rst": "blue",
        ".txt": "white",
        
        # Images
        ".png": "magenta",
        ".jpg": "magenta",
        ".jpeg": "magenta",
        ".gif": "magenta",
        ".svg": "cyan",
        
        # Archives
        ".zip": "red",
        ".tar": "red",
        ".gz": "red",
        ".rar": "red",
        
        # Config
        ".conf": "cyan",
        ".ini": "cyan",
        ".toml": "cyan",
        ".env": "yellow",
    }
    
    return color_map.get(extension.lower(), "white")


# Additional LS utilities

async def ls_tree(path: str = ".", max_depth: int = 3) -> Dict[str, Any]:
    """
    Display directory tree structure.
    
    Args:
        path: Directory path to show tree for
        max_depth: Maximum depth to traverse
        
    Returns:
        Dictionary with tree structure
    """
    result = await ls_directory(
        path=path,
        recursive=True,
        max_depth=max_depth,
        file_type_filter="dirs"  # Only show directories for tree
    )
    
    if result["success"]:
        console.print(f"\n[bold]Directory tree for {path}:[/bold]")
        _display_tree_structure(result["entries"])
    
    return result


def _display_tree_structure(entries: List[Dict[str, Any]]):
    """Display entries as a tree structure."""
    # Group by depth and sort
    by_depth = {}
    for entry in entries:
        depth = entry.get("depth", 0)
        if depth not in by_depth:
            by_depth[depth] = []
        by_depth[depth].append(entry)
    
    # Display tree
    for depth in sorted(by_depth.keys()):
        for entry in by_depth[depth]:
            indent = "│   " * depth
            if depth > 0:
                indent = indent[:-4] + "├── "
            
            console.print(f"{indent}📁 [bold blue]{entry['name']}[/bold blue]")


async def ls_size_summary(path: str = ".", show_hidden: bool = False) -> Dict[str, Any]:
    """
    Show directory size summary.
    
    Args:
        path: Directory path to analyze
        show_hidden: Whether to include hidden files
        
    Returns:
        Dictionary with size analysis
    """
    result = await ls_directory(
        path=path,
        show_hidden=show_hidden,
        long_format=True
    )
    
    if result["success"]:
        files = [e for e in result["entries"] if e["is_file"]]
        total_size = sum(e["size"] for e in files)
        
        # Show size breakdown
        console.print(f"\n[bold]Size summary for {path}:[/bold]")
        console.print(f"Total files: {len(files)}")
        console.print(f"Total size: {_format_file_size(total_size)}")
        
        # Show largest files
        if files:
            largest = sorted(files, key=lambda x: x["size"], reverse=True)[:5]
            console.print("\n[bold]Largest files:[/bold]")
            for file in largest:
                console.print(f"  {file['size_human']:>8} {file['name']}")
        
        result["total_size"] = total_size
        result["total_size_human"] = _format_file_size(total_size)
    
    return result