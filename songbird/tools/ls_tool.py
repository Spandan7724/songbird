# songbird/tools/ls_tool.py
"""
LS tool for directory listing with minimal formatting.
"""
import os
from pathlib import Path
from typing import Dict, Any, List, Optional
from rich.console import Console

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
    List directory contents with minimal formatting.
    
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
                "entries": [],
                "file_count": 0,
                "dir_count": 0,
                "total_count": 0
            }
        
        if not dir_path.is_dir():
            return {
                "success": False,
                "error": f"Path is not a directory: {path}",
                "entries": [],
                "file_count": 0,
                "dir_count": 0,
                "total_count": 0
            }
        
        console.print(f"[dim]{dir_path}[/dim]")
        
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
        
        # Count files and directories
        file_count = len([e for e in entries if e["is_file"]])
        dir_count = len([e for e in entries if e["is_dir"]])
        
        # Display results - pass recursive flag
        _display_minimal_format(entries, long_format, file_count, dir_count, recursive)
        
        return {
            "success": True,
            "path": str(dir_path),
            "entries": entries,
            "file_count": file_count,
            "dir_count": dir_count,
            "total_count": len(entries),
            "total_entries": len(entries)  # For compatibility
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": f"Error listing directory: {e}",
            "entries": [],
            "file_count": 0,
            "dir_count": 0,
            "total_count": 0
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
            
            # Apply file type filter at collection time for efficiency
            is_dir = item.is_dir()
            is_file = item.is_file()
            
            if file_type_filter == "files" and not is_file:
                # Still need to recurse into directories to find files
                if is_dir and current_depth < max_depth - 1:
                    subentries = await _get_recursive_entries(
                        item, show_hidden, max_depth, file_type_filter, current_depth + 1
                    )
                    entries.extend(subentries)
                continue
            elif file_type_filter == "dirs" and not is_dir:
                continue
            
            entry = await _get_entry_info(item, dir_path.parent if current_depth > 0 else dir_path)
            entry["depth"] = current_depth
            entries.append(entry)
            
            # Recurse into subdirectories
            if is_dir and current_depth < max_depth - 1:
                subentries = await _get_recursive_entries(
                    item, show_hidden, max_depth, file_type_filter, current_depth + 1
                )
                entries.extend(subentries)
                
    except PermissionError:
        # Handle permission denied gracefully
        pass
    
    return entries


async def _get_entry_info(item: Path, base_path: Path) -> Dict[str, Any]:
    """Get basic information about a file or directory."""
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
            "modified": item_stat.st_mtime,
        }
        
        # Add file extension for files
        if item.is_file():
            entry["extension"] = item.suffix.lower()
        else:
            entry["extension"] = ""
        
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
            "modified": 0,
            "extension": "",
            "error": str(e)
        }


def _sort_entries(entries: List[Dict[str, Any]], sort_by: str, reverse: bool) -> List[Dict[str, Any]]:
    """Sort directory entries by specified criteria."""
    sort_key_map = {
        "name": lambda e: e["name"].lower(),
        "size": lambda e: e["size"],
        "modified": lambda e: e["modified"],
        "type": lambda e: (not e["is_dir"], e["name"].lower()),  # Directories first
    }
    
    sort_key = sort_key_map.get(sort_by, sort_key_map["name"])
    
    return sorted(entries, key=sort_key, reverse=reverse)


def _display_tree_format(entries: List[Dict[str, Any]], show_files: bool = True):
    """Display directory entries in tree format like 'tree' command."""
    if not entries:
        console.print("[dim]empty[/dim]")
        return
    
    # Build tree structure
    tree = {}
    root_entries = []
    
    for entry in entries:
        path_parts = entry["path"].split(os.sep)
        
        if len(path_parts) == 1:
            # Root level entry
            root_entries.append(entry)
        else:
            # Nested entry - build tree structure
            current = tree
            for i, part in enumerate(path_parts[:-1]):
                if part not in current:
                    current[part] = {"_children": {}, "_is_dir": True}
                current = current[part]["_children"]
            
            # Add the final item
            final_name = path_parts[-1]
            current[final_name] = {
                "_entry": entry,
                "_children": {},
                "_is_dir": entry["is_dir"]
            }
    
    # Display root entries first
    root_entries.sort(key=lambda e: (not e["is_dir"], e["name"].lower()))
    
    for i, entry in enumerate(root_entries):
        is_last = (i == len(root_entries) - 1)
        _print_tree_entry(entry, "", is_last, show_files)
        
        # If it's a directory, show its contents from tree
        if entry["is_dir"] and entry["name"] in tree:
            _print_tree_recursive(tree[entry["name"]]["_children"], "", is_last, show_files)
    
    # Handle any remaining tree entries not in root
    remaining_roots = set(tree.keys()) - set(e["name"] for e in root_entries)
    for root_name in sorted(remaining_roots):
        console.print(f"[blue]{root_name}/[/blue]")
        _print_tree_recursive(tree[root_name]["_children"], "", True, show_files)


def _print_tree_entry(entry: Dict[str, Any], prefix: str, is_last: bool, show_files: bool):
    """Print a single tree entry with proper formatting."""
    if not show_files and entry["is_file"]:
        return
    
    # Determine the connector
    connector = "└── " if is_last else "├── "
    
    # Format the name
    if entry["is_dir"]:
        name = f"[blue]{entry['name']}[/blue]"
    else:
        name = entry["name"]
        # Add size for files
        if entry.get("size", 0) > 0:
            name += f" [dim]({_format_size(entry['size'])})[/dim]"
    
    console.print(f"{prefix}{connector}{name}")


def _print_tree_recursive(tree_dict: Dict, prefix: str, parent_is_last: bool, show_files: bool, depth: int = 0):
    """Recursively print tree structure."""
    if depth > 10:  # Prevent infinite recursion
        return
    
    # Sort entries: directories first, then files
    items = list(tree_dict.items())
    items.sort(key=lambda x: (not x[1].get("_is_dir", False), x[0].lower()))
    
    for i, (name, node) in enumerate(items):
        is_last = (i == len(items) - 1)
        
        # Skip files if not showing them
        if not show_files and not node.get("_is_dir", False):
            continue
        
        # Determine the new prefix
        if parent_is_last:
            new_prefix = prefix + "    "
        else:
            new_prefix = prefix + "│   "
        
        # Print the entry
        connector = "└── " if is_last else "├── "
        
        if "_entry" in node:
            entry = node["_entry"]
            if entry["is_dir"]:
                console.print(f"{prefix}{connector}[blue]{name}/[/blue]")
            else:
                size_str = f" [dim]({_format_size(entry['size'])})[/dim]" if entry.get("size", 0) > 0 else ""
                console.print(f"{prefix}{connector}{name}{size_str}")
        else:
            # Directory without explicit entry
            console.print(f"{prefix}{connector}[blue]{name}/[/blue]")
        
        # Recurse into subdirectories
        if node.get("_children") and node.get("_is_dir", False):
            _print_tree_recursive(node["_children"], new_prefix, is_last, show_files, depth + 1)


def _display_minimal_format(entries: List[Dict[str, Any]], long_format: bool, file_count: int, dir_count: int, recursive: bool = False):
    if not entries:
        console.print("[dim]empty[/dim]")
        return
    
    # Display count summary
    summary_parts = []
    if dir_count > 0:
        summary_parts.append(f"{dir_count} dirs")
    if file_count > 0:
        summary_parts.append(f"{file_count} files")
    
    if summary_parts:
        console.print(f"[sky_blue2]{', '.join(summary_parts)}[/sky_blue2]")
    
    console.print()
    
    # Use tree format for recursive listings
    if recursive:
        _display_tree_format(entries, show_files=True)
    else:
        # Simple list display for non-recursive
        display_count = 0
        for entry in entries:
            if display_count >= 50:  # Limit display
                remaining = len(entries) - 50
                console.print(f"  ... and {remaining} more")
                break
                
            if entry["is_dir"]:
                type_char = "D"
                style = "sky_blue2"
            elif entry["is_symlink"]:
                type_char = "L"
                style = "cyan"
            else:
                type_char = "F"
                style = "white"
            
            name = entry["name"]
            
            # Add size for files in long format
            if long_format and entry["is_file"]:
                size_str = _format_size(entry["size"])
                console.print(f"  [{type_char}] [{style}]{name}[/{style}] {size_str}")
            else:
                console.print(f"  [{type_char}] [{style}]{name}[/{style}]")
            
            display_count += 1


def _format_size(size_bytes: int) -> str:
    """Simple size formatting."""
    if size_bytes < 1024:
        return f"{size_bytes}B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f}KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f}MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.1f}GB"


# Additional LS utilities


async def ls_size_summary(path: str = ".", show_hidden: bool = False) -> Dict[str, Any]:
    result = await ls_directory(
        path=path,
        show_hidden=show_hidden,
        long_format=True
    )
    
    if result["success"]:
        files = [e for e in result["entries"] if e["is_file"]]
        total_size = sum(e["size"] for e in files)
        
        # Show size breakdown
        console.print(f"[dim]Size analysis of {path}[/dim]\n")
        console.print(f"Files: {len(files)}")
        console.print(f"Total: {_format_size(total_size)}")
        
        # Show largest files
        if files:
            largest = sorted(files, key=lambda x: x["size"], reverse=True)[:5]
            console.print("\n[dim]Largest files:[/dim]")
            for file in largest:
                console.print(f"  {_format_size(file['size']):>8}  {file['name']}")
        
        result["total_size"] = total_size
        result["total_size_human"] = _format_size(total_size)
    
    return result