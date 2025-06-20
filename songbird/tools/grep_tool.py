# songbird/tools/grep_tool.py
"""
Grep tool for advanced content search with regex support.
"""
import re
import asyncio
import subprocess
import shutil
import json
import os
from pathlib import Path
from typing import Dict, Any, List, Optional, Pattern
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.syntax import Syntax

console = Console()


async def grep_search(
    pattern: str,
    directory: str = ".",
    file_pattern: Optional[str] = None,
    case_sensitive: bool = False,
    whole_word: bool = False,
    regex: bool = False,
    context_lines: int = 0,
    max_results: int = 100,
    include_line_numbers: bool = True,
    include_hidden: bool = False
) -> Dict[str, Any]:
    """
    Search for patterns in file contents with advanced options.
    
    Args:
        pattern: Text pattern or regex to search for
        directory: Directory to search in (default: current directory)
        file_pattern: Glob pattern to filter files (e.g., "*.py", "*.{js,ts}")
        case_sensitive: Whether search is case sensitive (default: False)
        whole_word: Whether to match whole words only (default: False)
        regex: Whether pattern is a regular expression (default: False)
        context_lines: Number of context lines to show around matches (default: 0)
        max_results: Maximum number of results to return (default: 100)
        include_line_numbers: Whether to include line numbers (default: True)
        include_hidden: Whether to search hidden files (default: False)
        
    Returns:
        Dictionary with search results and metadata
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
        
        console.print(f"\n[bold cyan]Searching for:[/bold cyan] {pattern}")
        console.print(f"[dim]Directory: {dir_path}[/dim]")
        if file_pattern:
            console.print(f"[dim]File pattern: {file_pattern}[/dim]")
        console.print()
        
        # Try ripgrep first for better performance
        rg_path = shutil.which("rg")
        if rg_path:
            result = await _grep_with_ripgrep(
                pattern, dir_path, file_pattern, case_sensitive, whole_word,
                regex, context_lines, max_results, include_line_numbers, include_hidden
            )
        else:
            console.print("[yellow]ripgrep not found, using Python search (slower)[/yellow]")
            result = await _grep_with_python(
                pattern, dir_path, file_pattern, case_sensitive, whole_word,
                regex, context_lines, max_results, include_line_numbers, include_hidden
            )
        
        # Display results
        if result["success"]:
            _display_grep_results(result)
        
        return result
        
    except Exception as e:
        return {
            "success": False,
            "error": f"Error in grep search: {e}",
            "matches": []
        }


async def _grep_with_ripgrep(
    pattern: str, directory: Path, file_pattern: Optional[str],
    case_sensitive: bool, whole_word: bool, regex: bool,
    context_lines: int, max_results: int, include_line_numbers: bool,
    include_hidden: bool
) -> Dict[str, Any]:
    """Use ripgrep for fast searching."""
    
    try:
        # Build ripgrep command
        cmd = [shutil.which("rg"), "--json", "--no-heading"]
        
        # Search options
        if not case_sensitive:
            cmd.append("--ignore-case")
        
        if whole_word:
            cmd.append("--word-regexp")
        
        if not regex:
            cmd.append("--fixed-strings")
        
        if include_hidden:
            cmd.append("--hidden")
        
        if context_lines > 0:
            cmd.extend(["--before-context", str(context_lines)])
            cmd.extend(["--after-context", str(context_lines)])
        
        if include_line_numbers:
            cmd.append("--line-number")
        
        # File pattern filtering
        if file_pattern:
            cmd.extend(["--glob", file_pattern])
        
        # Limit results
        cmd.extend(["--max-count", str(max_results)])
        
        # Add pattern and directory
        cmd.extend([pattern, str(directory)])
        
        # Execute command
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        
        matches = []
        if stdout:
            for line in stdout.decode().strip().split('\n'):
                if line:
                    try:
                        data = json.loads(line)
                        if data.get('type') == 'match':
                            match_data = data['data']
                            
                            # Parse line content and context
                            lines_data = match_data.get('lines', {})
                            text = lines_data.get('text', '').rstrip('\n')
                            
                            match = {
                                "file": str(Path(match_data['path']['text']).relative_to(directory)),
                                "line_number": match_data.get('line_number'),
                                "text": text,
                                "type": "match"
                            }
                            
                            # Add context if available
                            if 'submatches' in match_data:
                                match["submatches"] = match_data['submatches']
                            
                            matches.append(match)
                            
                    except json.JSONDecodeError:
                        continue
        
        return {
            "success": True,
            "pattern": pattern,
            "search_type": "ripgrep",
            "matches": matches,
            "total_matches": len(matches),
            "truncated": len(matches) >= max_results
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": f"ripgrep error: {e}",
            "matches": []
        }


async def _grep_with_python(
    pattern: str, directory: Path, file_pattern: Optional[str],
    case_sensitive: bool, whole_word: bool, regex: bool,
    context_lines: int, max_results: int, include_line_numbers: bool,
    include_hidden: bool
) -> Dict[str, Any]:
    """Python fallback for grep functionality."""
    
    import glob
    import fnmatch
    
    matches = []
    
    try:
        # Compile regex pattern
        regex_flags = 0 if case_sensitive else re.IGNORECASE
        
        if regex:
            if whole_word:
                pattern = f"\\b{pattern}\\b"
            compiled_pattern = re.compile(pattern, regex_flags)
        else:
            # Escape special regex characters for literal search
            escaped_pattern = re.escape(pattern)
            if whole_word:
                escaped_pattern = f"\\b{escaped_pattern}\\b"
            compiled_pattern = re.compile(escaped_pattern, regex_flags)
        
        # Find files to search
        files_to_search = []
        
        if file_pattern:
            # Use glob pattern
            search_pattern = str(directory / "**" / file_pattern)
            files_to_search = [Path(f) for f in glob.glob(search_pattern, recursive=True)]
        else:
            # Search all files
            for root, dirs, files in os.walk(directory):
                # Skip hidden directories unless requested
                if not include_hidden:
                    dirs[:] = [d for d in dirs if not d.startswith('.')]
                
                for file in files:
                    # Skip hidden files unless requested
                    if not include_hidden and file.startswith('.'):
                        continue
                    
                    file_path = Path(root) / file
                    if file_path.is_file():
                        files_to_search.append(file_path)
        
        # Search each file
        for file_path in files_to_search:
            if len(matches) >= max_results:
                break
            
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    lines = f.readlines()
                
                for line_num, line in enumerate(lines, 1):
                    if len(matches) >= max_results:
                        break
                    
                    if compiled_pattern.search(line):
                        # Found a match
                        relative_path = file_path.relative_to(directory)
                        
                        match = {
                            "file": str(relative_path),
                            "line_number": line_num if include_line_numbers else None,
                            "text": line.rstrip('\n'),
                            "type": "match"
                        }
                        
                        # Add context lines if requested
                        if context_lines > 0:
                            context_before = []
                            context_after = []
                            
                            # Before context
                            for i in range(max(0, line_num - context_lines - 1), line_num - 1):
                                if i < len(lines):
                                    context_before.append({
                                        "line_number": i + 1,
                                        "text": lines[i].rstrip('\n'),
                                        "type": "context"
                                    })
                            
                            # After context
                            for i in range(line_num, min(len(lines), line_num + context_lines)):
                                if i < len(lines):
                                    context_after.append({
                                        "line_number": i + 1,
                                        "text": lines[i].rstrip('\n'),
                                        "type": "context"
                                    })
                            
                            match["context_before"] = context_before
                            match["context_after"] = context_after
                        
                        matches.append(match)
                        
            except Exception:
                # Skip files that can't be read
                continue
        
        return {
            "success": True,
            "pattern": pattern,
            "search_type": "python",
            "matches": matches,
            "total_matches": len(matches),
            "truncated": len(matches) >= max_results
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": f"Python grep error: {e}",
            "matches": []
        }


def _display_grep_results(result: Dict[str, Any]):
    """Display grep results in a formatted table."""
    matches = result.get("matches", [])
    
    if not matches:
        console.print("[yellow]No matches found[/yellow]")
        return
    
    pattern = result.get("pattern", "")
    
    # Group matches by file
    files_with_matches = {}
    for match in matches:
        file_path = match["file"]
        if file_path not in files_with_matches:
            files_with_matches[file_path] = []
        files_with_matches[file_path].append(match)
    
    # Create table
    table = Table(
        title=f"Found {len(matches)} matches for '{pattern}' in {len(files_with_matches)} files"
    )
    table.add_column("File", style="cyan", width=30)
    table.add_column("Line", style="green", justify="right", width=6)
    table.add_column("Content", style="white", ratio=1)
    
    # Add matches to table
    for file_path, file_matches in files_with_matches.items():
        for i, match in enumerate(file_matches):
            # Only show filename on first match for each file
            file_display = file_path if i == 0 else ""
            
            line_num = match.get("line_number", "")
            line_display = str(line_num) if line_num else "—"
            
            # Highlight pattern in text
            text = match["text"]
            highlighted_text = _highlight_pattern_in_text(text, pattern)
            
            table.add_row(
                f"[bold]{file_display}[/bold]" if file_display else "",
                line_display,
                highlighted_text
            )
            
            # Add context lines if available
            context_after = match.get("context_after", [])
            for context in context_after[:2]:  # Limit context display
                table.add_row(
                    "",
                    f"[dim]{context.get('line_number', '')}[/dim]",
                    f"[dim]{context['text']}[/dim]"
                )
        
        # Add separator between files if there are multiple files
        if len(files_with_matches) > 1 and file_path != list(files_with_matches.keys())[-1]:
            table.add_row("", "", "[dim]...[/dim]")
    
    # Show truncation warning if needed
    if result.get("truncated"):
        table.add_row(
            "[dim]...[/dim]",
            "[dim]...[/dim]",
            "[dim]More results available (increase max_results)[/dim]"
        )
    
    # Display in a panel
    panel = Panel(table, border_style="green", padding=(1, 2))
    console.print(panel)
    
    # Show summary
    console.print(f"\n[bold]Summary:[/bold] {len(matches)} matches across {len(files_with_matches)} files")
    
    # Show file breakdown if multiple files
    if len(files_with_matches) > 1:
        file_summary = []
        for file_path, file_matches in list(files_with_matches.items())[:5]:
            count = len(file_matches)
            file_summary.append(f"{file_path}: {count}")
        
        if file_summary:
            console.print(f"[dim]Top files: {', '.join(file_summary)}[/dim]")


def _highlight_pattern_in_text(text: str, pattern: str) -> str:
    """Highlight search pattern in text with color."""
    # Simple case-insensitive highlighting
    # In a real implementation, you'd want to handle regex patterns properly
    
    try:
        # Create a case-insensitive search
        escaped_pattern = re.escape(pattern)
        highlighted = re.sub(
            f"({escaped_pattern})",
            r"[bold yellow on black]\1[/bold yellow on black]",
            text,
            flags=re.IGNORECASE
        )
        return highlighted
    except Exception:
        # If highlighting fails, return original text
        return text


# Additional grep utilities

async def grep_count(
    pattern: str,
    directory: str = ".",
    file_pattern: Optional[str] = None,
    case_sensitive: bool = False
) -> Dict[str, Any]:
    """
    Count matches without returning content.
    
    Args:
        pattern: Pattern to search for
        directory: Directory to search in
        file_pattern: File pattern filter
        case_sensitive: Whether search is case sensitive
        
    Returns:
        Dictionary with count information
    """
    result = await grep_search(
        pattern=pattern,
        directory=directory,
        file_pattern=file_pattern,
        case_sensitive=case_sensitive,
        max_results=10000  # High limit for counting
    )
    
    if result["success"]:
        # Group by file for count summary
        file_counts = {}
        for match in result["matches"]:
            file_path = match["file"]
            file_counts[file_path] = file_counts.get(file_path, 0) + 1
        
        total_matches = sum(file_counts.values())
        
        return {
            "success": True,
            "pattern": pattern,
            "total_matches": total_matches,
            "files_with_matches": len(file_counts),
            "file_counts": file_counts
        }
    else:
        return result


async def grep_replace_preview(
    pattern: str,
    replacement: str,
    directory: str = ".",
    file_pattern: Optional[str] = None,
    case_sensitive: bool = False,
    regex: bool = False
) -> Dict[str, Any]:
    """
    Preview what a grep replace operation would do.
    
    Args:
        pattern: Pattern to search for
        replacement: Replacement text
        directory: Directory to search in
        file_pattern: File pattern filter
        case_sensitive: Whether search is case sensitive
        regex: Whether pattern is regex
        
    Returns:
        Dictionary with preview information
    """
    # First, find all matches
    result = await grep_search(
        pattern=pattern,
        directory=directory,
        file_pattern=file_pattern,
        case_sensitive=case_sensitive,
        regex=regex,
        max_results=50  # Limit for preview
    )
    
    if not result["success"]:
        return result
    
    # Show what replacements would look like
    preview_items = []
    for match in result["matches"]:
        original_text = match["text"]
        
        # Perform replacement (simplified - in practice you'd handle regex properly)
        if regex:
            try:
                flags = 0 if case_sensitive else re.IGNORECASE
                new_text = re.sub(pattern, replacement, original_text, flags=flags)
            except Exception:
                new_text = original_text  # Keep original on error
        else:
            if case_sensitive:
                new_text = original_text.replace(pattern, replacement)
            else:
                # Case-insensitive replacement
                import re
                new_text = re.sub(re.escape(pattern), replacement, original_text, flags=re.IGNORECASE)
        
        if new_text != original_text:
            preview_items.append({
                "file": match["file"],
                "line_number": match.get("line_number"),
                "original": original_text,
                "replacement": new_text
            })
    
    return {
        "success": True,
        "pattern": pattern,
        "replacement": replacement,
        "preview_items": preview_items,
        "files_affected": len(set(item["file"] for item in preview_items)),
        "total_replacements": len(preview_items)
    }