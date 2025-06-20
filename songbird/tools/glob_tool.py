# songbird/tools/glob_tool.py
"""
Glob tool for fast file pattern matching.
"""
import glob
import os
from pathlib import Path
from typing import Dict, Any, List, Optional
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

console = Console()


async def glob_pattern(
    pattern: str,
    directory: str = ".",
    recursive: bool = True,
    include_hidden: bool = False,
    max_results: int = 100
) -> Dict[str, Any]:
    """
    Find files using glob patterns with enhanced functionality.
    
    Args:
        pattern: Glob pattern to match (e.g., "**/*.py", "src/**/*.js", "*.md")
        directory: Directory to search in (default: current directory)
        recursive: Whether to search recursively (default: True)
        include_hidden: Whether to include hidden files/directories (default: False)
        max_results: Maximum number of results to return (default: 100)
        
    Returns:
        Dictionary with matching files and metadata
    """
    try:
        # Resolve directory path
        dir_path = Path(directory).resolve()
        if not dir_path.exists():
            return {
                "success": False,
                "error": f"Directory not found: {directory}",
                "matches": []
            }
        
        if not dir_path.is_dir():
            return {
                "success": False,
                "error": f"Path is not a directory: {directory}",
                "matches": []
            }
        
        # Prepare the search pattern
        if not os.path.isabs(pattern):
            # Relative pattern, combine with directory
            search_pattern = str(dir_path / pattern)
        else:
            search_pattern = pattern
        
        console.print(f"\n[bold cyan]Searching for pattern:[/bold cyan] {pattern}")
        console.print(f"[dim]Directory: {dir_path}[/dim]")
        console.print(f"[dim]Full pattern: {search_pattern}[/dim]\n")
        
        # Use glob to find matches
        matches = []
        
        if recursive and "**" not in pattern:
            # Add recursive pattern if not already present
            if pattern.startswith("/"):
                recursive_pattern = pattern
            else:
                recursive_pattern = f"**/{pattern}"
            search_pattern = str(dir_path / recursive_pattern)
        
        # Get matches using glob
        glob_matches = glob.glob(search_pattern, recursive=recursive)
        
        # Process matches
        for match_path in glob_matches:
            if len(matches) >= max_results:
                break
            
            match_file = Path(match_path)
            
            # Skip hidden files/directories unless requested
            if not include_hidden:
                if any(part.startswith('.') for part in match_file.parts):
                    continue
            
            # Skip if it's a directory (unless pattern specifically looks for directories)
            if match_file.is_dir() and not pattern.endswith('/'):
                continue
            
            # Get relative path from the search directory
            try:
                relative_path = match_file.relative_to(dir_path)
            except ValueError:
                # If we can't get relative path, use absolute
                relative_path = match_file
            
            # Get file info
            file_info = {
                "path": str(relative_path),
                "absolute_path": str(match_file),
                "name": match_file.name,
                "is_file": match_file.is_file(),
                "is_dir": match_file.is_dir(),
            }
            
            # Add file size and modification time for files
            if match_file.is_file():
                try:
                    stat = match_file.stat()
                    file_info.update({
                        "size": stat.st_size,
                        "size_human": _format_file_size(stat.st_size),
                        "modified": stat.st_mtime,
                        "modified_human": _format_modification_time(stat.st_mtime)
                    })
                except Exception:
                    file_info.update({
                        "size": 0,
                        "size_human": "unknown",
                        "modified": 0,
                        "modified_human": "unknown"
                    })
            
            matches.append(file_info)
        
        # Sort matches by path for consistent output
        matches.sort(key=lambda x: x["path"])
        
        # Display results
        _display_glob_results(matches, pattern, len(glob_matches) > max_results)
        
        return {
            "success": True,
            "pattern": pattern,
            "directory": str(dir_path),
            "matches": matches,
            "total_found": len(glob_matches),
            "total_returned": len(matches),
            "truncated": len(glob_matches) > max_results,
            "display_shown": True
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": f"Error in glob search: {e}",
            "matches": []
        }


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
    import datetime
    try:
        dt = datetime.datetime.fromtimestamp(timestamp)
        now = datetime.datetime.now()
        
        # If within last 24 hours, show time
        if (now - dt).days == 0:
            return dt.strftime("%H:%M")
        # If within last week, show day and time
        elif (now - dt).days < 7:
            return dt.strftime("%a %H:%M")
        # Otherwise show date
        else:
            return dt.strftime("%m/%d/%y")
    except Exception:
        return "unknown"


def _display_glob_results(matches: List[Dict[str, Any]], pattern: str, truncated: bool):
    """Display glob results in a formatted table."""
    if not matches:
        console.print("[yellow]No matches found[/yellow]")
        return
    
    # Create table
    table = Table(
        title=f"Found {len(matches)} matches for pattern '{pattern}'"
    )
    table.add_column("Type", style="bold", width=6)
    table.add_column("Name", style="cyan", ratio=1)
    table.add_column("Size", style="green", justify="right", width=8)
    table.add_column("Modified", style="dim", width=10)
    table.add_column("Path", style="white", ratio=1)
    
    # Add rows
    for match in matches:
        # Type indicator
        if match["is_dir"]:
            type_indicator = "📁 DIR"
            type_style = "bold blue"
            size_display = "—"
            modified_display = "—"
        else:
            type_indicator = "📄 FILE"
            type_style = "white"
            size_display = match.get("size_human", "—")
            modified_display = match.get("modified_human", "—")
        
        # Directory path (parent directory)
        full_path = Path(match["path"])
        if len(full_path.parts) > 1:
            dir_path = str(full_path.parent)
        else:
            dir_path = "."
        
        table.add_row(
            f"[{type_style}]{type_indicator}[/{type_style}]",
            f"[bold]{match['name']}[/bold]",
            size_display,
            modified_display,
            f"[dim]{dir_path}[/dim]"
        )
    
    # Show truncation warning if needed
    if truncated:
        table.add_row(
            "[dim]...[/dim]",
            "[dim]More results available[/dim]",
            "[dim]...[/dim]",
            "[dim]...[/dim]",
            "[dim]Increase max_results to see more[/dim]"
        )
    
    # Display in a panel
    panel = Panel(table, border_style="cyan", padding=(1, 2))
    console.print(panel)
    
    # Show file type summary
    if len(matches) > 5:
        files = [m for m in matches if m["is_file"]]
        dirs = [m for m in matches if m["is_dir"]]
        
        summary_parts = []
        if files:
            summary_parts.append(f"📄 {len(files)} files")
        if dirs:
            summary_parts.append(f"📁 {len(dirs)} directories")
        
        if summary_parts:
            console.print(f"\n[bold]Summary:[/bold] {', '.join(summary_parts)}")
        
        # Show file extension breakdown for files
        if files:
            extensions = {}
            for file_match in files:
                ext = Path(file_match["name"]).suffix.lower()
                if not ext:
                    ext = "(no extension)"
                extensions[ext] = extensions.get(ext, 0) + 1
            
            if len(extensions) > 1:
                ext_summary = []
                for ext, count in sorted(extensions.items(), key=lambda x: x[1], reverse=True)[:5]:
                    ext_summary.append(f"{ext}: {count}")
                console.print(f"[dim]Extensions: {', '.join(ext_summary)}[/dim]")


# Additional helper functions for advanced glob operations

async def glob_exclude(
    pattern: str,
    exclude_patterns: List[str],
    directory: str = ".",
    recursive: bool = True
) -> Dict[str, Any]:
    """
    Glob with exclude patterns.
    
    Args:
        pattern: Main glob pattern to match
        exclude_patterns: List of patterns to exclude
        directory: Directory to search in
        recursive: Whether to search recursively
        
    Returns:
        Dictionary with filtered results
    """
    # Get initial matches
    result = await glob_pattern(pattern, directory, recursive)
    
    if not result["success"]:
        return result
    
    # Filter out excluded patterns
    filtered_matches = []
    for match in result["matches"]:
        match_path = match["path"]
        
        # Check if match should be excluded
        should_exclude = False
        for exclude_pattern in exclude_patterns:
            if glob.fnmatch.fnmatch(match_path, exclude_pattern):
                should_exclude = True
                break
        
        if not should_exclude:
            filtered_matches.append(match)
    
    # Update result
    result["matches"] = filtered_matches
    result["total_returned"] = len(filtered_matches)
    result["excluded_patterns"] = exclude_patterns
    
    return result


async def glob_multiple(
    patterns: List[str],
    directory: str = ".",
    recursive: bool = True
) -> Dict[str, Any]:
    """
    Search multiple glob patterns at once.
    
    Args:
        patterns: List of glob patterns to search
        directory: Directory to search in
        recursive: Whether to search recursively
        
    Returns:
        Dictionary with combined results
    """
    all_matches = []
    seen_paths = set()
    
    for pattern in patterns:
        result = await glob_pattern(pattern, directory, recursive)
        
        if result["success"]:
            for match in result["matches"]:
                path = match["path"]
                if path not in seen_paths:
                    seen_paths.add(path)
                    all_matches.append(match)
    
    # Sort combined results
    all_matches.sort(key=lambda x: x["path"])
    
    return {
        "success": True,
        "patterns": patterns,
        "directory": directory,
        "matches": all_matches,
        "total_returned": len(all_matches),
        "display_shown": True
    }