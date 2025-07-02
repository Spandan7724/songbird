# songbird/tools/glob_tool.py
"""
Glob tool for fast file pattern matching with minimal output.
"""
import glob
import os
from pathlib import Path
from typing import Dict, Any, List
from rich.console import Console

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
                "matches": [],
                "count": 0,
                "file_count": 0,
                "dir_count": 0
            }
        
        if not dir_path.is_dir():
            return {
                "success": False,
                "error": f"Path is not a directory: {directory}",
                "matches": [],
                "count": 0,
                "file_count": 0,
                "dir_count": 0
            }
        
        # Prepare the search pattern
        if not os.path.isabs(pattern):
            # Relative pattern, combine with directory
            search_pattern = str(dir_path / pattern)
        else:
            search_pattern = pattern
        
        # Minimal output
        console.print(f"[dim]Searching: {pattern} in {dir_path}[/dim]")
        
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
            
            # Add file size for files
            if match_file.is_file():
                try:
                    stat = match_file.stat()
                    file_info["size"] = stat.st_size
                except Exception:
                    file_info["size"] = 0
            
            matches.append(file_info)
        
        # Sort matches by path for consistent output
        matches.sort(key=lambda x: x["path"])
        
        # Count files and directories
        file_count = len([m for m in matches if m["is_file"]])
        dir_count = len([m for m in matches if m["is_dir"]])
        
        # Display minimal results
        _display_minimal_results(matches, pattern, len(glob_matches), file_count, dir_count)
        
        return {
            "success": True,
            "pattern": pattern,
            "directory": str(dir_path),
            "matches": matches,
            "total_found": len(glob_matches),
            "total_returned": len(matches),
            "file_count": file_count,
            "dir_count": dir_count,
            "count": len(matches),  # Total count for easy access
            "truncated": len(glob_matches) > max_results
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": f"Error in glob search: {e}",
            "matches": [],
            "count": 0,
            "file_count": 0,
            "dir_count": 0
        }


def _display_minimal_results(matches: List[Dict[str, Any]], pattern: str, total_found: int, file_count: int, dir_count: int):
    """Display glob results in minimal format."""
    if not matches:
        console.print("[yellow]No matches found[/yellow]")
        return
    
    # Show count summary
    summary_parts = []
    if file_count > 0:
        summary_parts.append(f"{file_count} files")
    if dir_count > 0:
        summary_parts.append(f"{dir_count} directories")
    
    console.print(f"\n[green]Found {' and '.join(summary_parts)} matching '{pattern}'[/green]")
    
    # Simple list format
    console.print()
    for i, match in enumerate(matches[:20]):  # Limit display to 20 items
        # Simple type indicator
        type_char = "D" if match["is_dir"] else "F"
        size_str = ""
        if match["is_file"] and "size" in match:
            size_str = f" {_format_size(match['size'])}"
        
        # Clean path display
        style = "blue" if match["is_dir"] else "white"
        console.print(f"  [{type_char}] [{style}]{match['path']}[/{style}]{size_str}")
    
    if len(matches) > 20:
        console.print(f"  ... and {len(matches) - 20} more")
    
    if total_found > len(matches):
        console.print(f"\n[dim]Note: Results limited to {len(matches)} of {total_found} total matches[/dim]")


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
    result["file_count"] = len([m for m in filtered_matches if m["is_file"]])
    result["dir_count"] = len([m for m in filtered_matches if m["is_dir"]])
    result["count"] = len(filtered_matches)
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
    
    # Count files and directories
    file_count = len([m for m in all_matches if m["is_file"]])
    dir_count = len([m for m in all_matches if m["is_dir"]])
    
    return {
        "success": True,
        "patterns": patterns,
        "directory": directory,
        "matches": all_matches,
        "total_returned": len(all_matches),
        "file_count": file_count,
        "dir_count": dir_count,
        "count": len(all_matches)
    }