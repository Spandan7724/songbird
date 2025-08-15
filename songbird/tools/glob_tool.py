# Glob tool for fast file pattern matching with minimal output.

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
    
    # Find files using glob patterns with enhanced functionality.
    
    # Args:
    #     pattern: Glob pattern to match (e.g., "**/*.py", "src/**/*.js", "*.md")
    #     directory: Directory to search in (default: current directory)
    #     recursive: Whether to search recursively (default: True)
    #     include_hidden: Whether to include hidden files/directories (default: False)
    #     max_results: Maximum number of results to return (default: 100)
        
    # Returns:
    #     Dictionary with matching files and metadata
    
    try:
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
        
        if not os.path.isabs(pattern):
            search_pattern = str(dir_path / pattern)
        else:
            search_pattern = pattern
        console.print(f"[dim]Searching: {pattern} in {dir_path}[/dim]")
        
        matches = []
        
        if recursive and "**" not in pattern:
            if pattern.startswith("/"):
                recursive_pattern = pattern
            else:
                recursive_pattern = f"**/{pattern}"
            search_pattern = str(dir_path / recursive_pattern)
        
        glob_matches = glob.glob(search_pattern, recursive=recursive)
        
        for match_path in glob_matches:
            if len(matches) >= max_results:
                break
            
            match_file = Path(match_path)
            
            if not include_hidden:
                if any(part.startswith('.') for part in match_file.parts):
                    continue
            
            if match_file.is_dir() and not pattern.endswith('/'):
                continue
            
            try:
                relative_path = match_file.relative_to(dir_path)
            except ValueError:
                relative_path = match_file
            
            file_info = {
                "path": str(relative_path),
                "absolute_path": str(match_file),
                "name": match_file.name,
                "is_file": match_file.is_file(),
                "is_dir": match_file.is_dir(),
            }
            
            if match_file.is_file():
                try:
                    stat = match_file.stat()
                    file_info["size"] = stat.st_size
                except Exception:
                    file_info["size"] = 0
            
            matches.append(file_info)
        
        matches.sort(key=lambda x: x["path"])
        
        file_count = len([m for m in matches if m["is_file"]])
        dir_count = len([m for m in matches if m["is_dir"]])
        
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
            "count": len(matches),
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
    if not matches:
        console.print("[yellow]No matches found[/yellow]")
        return
    
    summary_parts = []
    if file_count > 0:
        summary_parts.append(f"{file_count} files")
    if dir_count > 0:
        summary_parts.append(f"{dir_count} directories")
    
    console.print(f"\n[green]Found {' and '.join(summary_parts)} matching '{pattern}'[/green]")
    
    console.print()
    for i, match in enumerate(matches[:20]):
        type_char = "D" if match["is_dir"] else "F"
        size_str = ""
        if match["is_file"] and "size" in match:
            size_str = f" {_format_size(match['size'])}"
        
        style = "blue" if match["is_dir"] else "white"
        console.print(f"  [{type_char}] [{style}]{match['path']}[/{style}]{size_str}")
    
    if len(matches) > 20:
        console.print(f"  ... and {len(matches) - 20} more")
    
    if total_found > len(matches):
        console.print(f"\n[dim]Note: Results limited to {len(matches)} of {total_found} total matches[/dim]")


def _format_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes}B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f}KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f}MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.1f}GB"


async def glob_exclude(
    pattern: str,
    exclude_patterns: List[str],
    directory: str = ".",
    recursive: bool = True
) -> Dict[str, Any]:

    result = await glob_pattern(pattern, directory, recursive)
    
    if not result["success"]:
        return result
    
    filtered_matches = []
    for match in result["matches"]:
        match_path = match["path"]
        
        should_exclude = False
        for exclude_pattern in exclude_patterns:
            if glob.fnmatch.fnmatch(match_path, exclude_pattern):
                should_exclude = True
                break
        
        if not should_exclude:
            filtered_matches.append(match)
    
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
    
    all_matches.sort(key=lambda x: x["path"])
    
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