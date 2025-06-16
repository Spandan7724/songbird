# songbird/tools/file_search.py
"""
Enhanced file search functionality using ripgrep (rg) and native Python for comprehensive search capabilities.
"""
import asyncio
import json
import shutil
import re
import os
from pathlib import Path
from typing import List, Dict, Any, Optional, Union
from rich.console import Console
from rich.table import Table
from rich.syntax import Syntax
from rich.panel import Panel

console = Console()


async def file_search(
    pattern: str, 
    directory: str = ".",
    search_type: Optional[str] = "auto",
    file_pattern: Optional[str] = None,
    max_results: int = 50,
    context_lines: int = 2
) -> Dict[str, Any]:
    """
    Enhanced search for files, text patterns, functions, and classes.
    
    Args:
        pattern: What to search for (filename, text, function name, etc.)
        directory: Directory path to search in (default: current directory)
        search_type: Type of search - "auto", "filename", "text", "function", "class", "variable"
        file_pattern: Optional glob pattern to filter files (e.g., "*.py")
        max_results: Maximum number of results to return
        context_lines: Number of context lines to show around matches
        
    Returns:
        Dictionary with search results and metadata
    """
    dir_path = Path(directory).resolve()
    if not dir_path.exists() or not dir_path.is_dir():
        return {
            "success": False,
            "error": f"Directory not found: {directory}",
            "matches": []
        }
    
    # Auto-detect search type if not specified
    if search_type == "auto":
        search_type = _detect_search_type(pattern)
    
    # Display search intent
    console.print(f"\n[bold cyan]Searching for:[/bold cyan] {pattern}")
    console.print(f"[dim]Type: {search_type}, Directory: {dir_path}[/dim]\n")
    
    results = {
        "success": True,
        "search_type": search_type,
        "pattern": pattern,
        "directory": str(dir_path),
        "matches": []
    }
    
    try:
        if search_type == "filename":
            # Search for files by name
            results["matches"] = await _search_by_filename(pattern, dir_path, file_pattern, max_results)
        elif search_type in ["function", "class", "variable"]:
            # Search for code constructs
            results["matches"] = await _search_code_constructs(
                pattern, dir_path, search_type, file_pattern, max_results, context_lines
            )
        else:
            # General text search
            results["matches"] = await _search_text(
                pattern, dir_path, file_pattern, max_results, context_lines
            )
        
        # Display results summary
        _display_search_results(results)
        
        results["total_matches"] = len(results["matches"])
        results["truncated"] = len(results["matches"]) >= max_results
        
    except Exception as e:
        results["success"] = False
        results["error"] = str(e)
        console.print(f"[bold red]Search error:[/bold red] {e}")
    
    return results


def _detect_search_type(pattern: str) -> str:
    """Auto-detect the type of search based on the pattern."""
    # Check for function-like patterns
    if re.match(r'^(def|function|func)\s+\w+', pattern, re.IGNORECASE):
        return "function"
    elif re.match(r'^class\s+\w+', pattern, re.IGNORECASE):
        return "class"
    elif re.match(r'^\w+\.(py|js|java|cpp|c|go|rs|php|rb)$', pattern, re.IGNORECASE):
        return "filename"
    elif re.match(r'^[A-Za-z_]\w*$', pattern) and len(pattern) > 2:
        # Looks like an identifier - could be function/class/variable
        return "function"  # Default to function search
    else:
        return "text"


async def _search_by_filename(
    pattern: str, 
    directory: Path, 
    file_pattern: Optional[str],
    max_results: int
) -> List[Dict[str, Any]]:
    """Search for files by name pattern."""
    matches = []
    
    # Use glob pattern matching
    search_pattern = f"*{pattern}*" if "*" not in pattern else pattern
    
    for root, dirs, files in os.walk(directory):
        if len(matches) >= max_results:
            break
            
        # Skip hidden directories
        dirs[:] = [d for d in dirs if not d.startswith('.')]
        
        root_path = Path(root)
        for file in files:
            if len(matches) >= max_results:
                break
                
            # Apply file pattern filter if provided
            if file_pattern and not Path(file).match(file_pattern):
                continue
                
            # Check if filename matches pattern
            if Path(file).match(search_pattern.lower()) or Path(file).match(search_pattern):
                file_path = root_path / file
                relative_path = file_path.relative_to(directory)
                
                # Get file info
                stat = file_path.stat()
                matches.append({
                    "type": "file",
                    "file": str(relative_path),
                    "absolute_path": str(file_path),
                    "size": stat.st_size,
                    "modified": stat.st_mtime,
                    "line_number": None,
                    "match_text": file
                })
    
    return matches


async def _search_code_constructs(
    pattern: str,
    directory: Path,
    construct_type: str,
    file_pattern: Optional[str],
    max_results: int,
    context_lines: int
) -> List[Dict[str, Any]]:
    """Search for specific code constructs like functions, classes, or variables."""
    
    # Language-specific patterns for different constructs
    patterns_by_language = {
        "python": {
            "function": rf"^\s*(async\s+)?def\s+{re.escape(pattern)}\s*\(",
            "class": rf"^\s*class\s+{re.escape(pattern)}\s*[\(:]",
            "variable": rf"^\s*{re.escape(pattern)}\s*="
        },
        "javascript": {
            "function": rf"(function\s+{re.escape(pattern)}\s*\(|const\s+{re.escape(pattern)}\s*=\s*(\(|async))",
            "class": rf"class\s+{re.escape(pattern)}\s*[\{{]",
            "variable": rf"(const|let|var)\s+{re.escape(pattern)}\s*="
        },
        "java": {
            "function": rf"(public|private|protected)?\s*(static\s+)?\w+\s+{re.escape(pattern)}\s*\(",
            "class": rf"(public\s+)?class\s+{re.escape(pattern)}\s*[\{{]",
            "variable": rf"(public|private|protected)?\s*(static\s+)?\w+\s+{re.escape(pattern)}\s*="
        }
    }
    
    # Try ripgrep first if available
    rg_path = shutil.which("rg")
    if rg_path:
        return await _ripgrep_code_search(
            pattern, directory, construct_type, patterns_by_language, 
            file_pattern, max_results, context_lines
        )
    else:
        # Fallback to Python-based search
        return await _python_code_search(
            pattern, directory, construct_type, patterns_by_language,
            file_pattern, max_results, context_lines
        )


async def _ripgrep_code_search(
    pattern: str,
    directory: Path,
    construct_type: str,
    patterns_by_language: Dict,
    file_pattern: Optional[str],
    max_results: int,
    context_lines: int
) -> List[Dict[str, Any]]:
    """Use ripgrep for fast code construct search."""
    matches = []
    
    # Build ripgrep command
    cmd = [
        shutil.which("rg"),
        "--json",
        "--case-sensitive",  # Code searches should be case-sensitive
        "--line-number",
        "--column",
        "--max-columns", "500",
        "--max-count", str(max_results),
    ]
    
    # Add context lines if requested
    if context_lines > 0:
        cmd.extend(["--context", str(context_lines)])
    
    # Add file type filters
    if file_pattern:
        cmd.extend(["--glob", file_pattern])
    
    # Try different language patterns
    for lang, patterns in patterns_by_language.items():
        if construct_type in patterns:
            regex_pattern = patterns[construct_type]
            
            # Run ripgrep with language-specific pattern
            search_cmd = cmd + [regex_pattern, str(directory)]
            
            try:
                process = await asyncio.create_subprocess_exec(
                    *search_cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                
                stdout, stderr = await process.communicate()
                
                if stdout:
                    for line in stdout.decode().strip().split('\n'):
                        if line and len(matches) < max_results:
                            try:
                                data = json.loads(line)
                                if data.get('type') == 'match':
                                    match_data = data['data']
                                    file_path = Path(match_data['path']['text'])
                                    
                                    matches.append({
                                        "type": construct_type,
                                        "file": str(file_path.relative_to(directory)),
                                        "absolute_path": str(file_path),
                                        "line_number": match_data['line_number'],
                                        "column": match_data.get('submatches', [{}])[0].get('start', 0) + 1,
                                        "match_text": match_data['lines']['text'].strip(),
                                        "language": lang,
                                        "context": _extract_context(data)
                                    })
                            except (json.JSONDecodeError, KeyError):
                                continue
            except Exception:
                continue
    
    return matches


async def _search_text(
    pattern: str,
    directory: Path,
    file_pattern: Optional[str],
    max_results: int,
    context_lines: int
) -> List[Dict[str, Any]]:
    """General text search using ripgrep or fallback."""
    rg_path = shutil.which("rg")
    
    if rg_path:
        # Use ripgrep for fast search
        cmd = [
            rg_path,
            "--json",
            "--ignore-case",
            "--line-number",
            "--column",
            "--max-columns", "500",
            "--max-count", str(max_results),
        ]
        
        if context_lines > 0:
            cmd.extend(["--context", str(context_lines)])
        
        if file_pattern:
            cmd.extend(["--glob", file_pattern])
        
        cmd.extend([pattern, str(directory)])
        
        try:
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
                                file_path = Path(match_data['path']['text'])
                                
                                matches.append({
                                    "type": "text",
                                    "file": str(file_path.relative_to(directory)),
                                    "absolute_path": str(file_path),
                                    "line_number": match_data['line_number'],
                                    "column": match_data.get('submatches', [{}])[0].get('start', 0) + 1,
                                    "match_text": match_data['lines']['text'].strip(),
                                    "context": _extract_context(data)
                                })
                        except (json.JSONDecodeError, KeyError):
                            continue
            
            return matches[:max_results]
            
        except Exception as e:
            # Fallback to Python search
            console.print(f"[yellow]Ripgrep failed, using Python search: {e}[/yellow]")
    
    # Python-based fallback search
    return await _python_text_search(pattern, directory, file_pattern, max_results, context_lines)


async def _python_text_search(
    pattern: str,
    directory: Path,
    file_pattern: Optional[str],
    max_results: int,
    context_lines: int
) -> List[Dict[str, Any]]:
    """Python-based text search fallback."""
    matches = []
    pattern_re = re.compile(pattern, re.IGNORECASE)
    
    for root, dirs, files in os.walk(directory):
        if len(matches) >= max_results:
            break
            
        # Skip hidden directories
        dirs[:] = [d for d in dirs if not d.startswith('.')]
        
        root_path = Path(root)
        for file in files:
            if len(matches) >= max_results:
                break
                
            # Apply file pattern filter
            if file_pattern and not Path(file).match(file_pattern):
                continue
                
            file_path = root_path / file
            
            # Skip binary files
            if _is_binary_file(file_path):
                continue
                
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    lines = f.readlines()
                    
                for i, line in enumerate(lines):
                    if len(matches) >= max_results:
                        break
                        
                    if pattern_re.search(line):
                        # Extract context
                        start = max(0, i - context_lines)
                        end = min(len(lines), i + context_lines + 1)
                        context = lines[start:end]
                        
                        matches.append({
                            "type": "text",
                            "file": str(file_path.relative_to(directory)),
                            "absolute_path": str(file_path),
                            "line_number": i + 1,
                            "column": pattern_re.search(line).start() + 1,
                            "match_text": line.strip(),
                            "context": context if context_lines > 0 else None
                        })
            except Exception:
                continue
    
    return matches


async def _python_code_search(
    pattern: str,
    directory: Path,
    construct_type: str,
    patterns_by_language: Dict,
    file_pattern: Optional[str],
    max_results: int,
    context_lines: int
) -> List[Dict[str, Any]]:
    """Python-based code construct search fallback."""
    matches = []
    
    # Map file extensions to languages
    ext_to_lang = {
        '.py': 'python',
        '.js': 'javascript',
        '.jsx': 'javascript',
        '.ts': 'javascript',
        '.tsx': 'javascript',
        '.java': 'java',
    }
    
    for root, dirs, files in os.walk(directory):
        if len(matches) >= max_results:
            break
            
        dirs[:] = [d for d in dirs if not d.startswith('.')]
        root_path = Path(root)
        
        for file in files:
            if len(matches) >= max_results:
                break
                
            file_path = root_path / file
            ext = file_path.suffix.lower()
            
            # Determine language
            lang = ext_to_lang.get(ext)
            if not lang or (file_pattern and not file_path.match(file_pattern)):
                continue
                
            # Get pattern for this language and construct type
            if lang in patterns_by_language and construct_type in patterns_by_language[lang]:
                regex_pattern = patterns_by_language[lang][construct_type]
                pattern_re = re.compile(regex_pattern, re.MULTILINE)
                
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                        
                    for match in pattern_re.finditer(content):
                        if len(matches) >= max_results:
                            break
                            
                        # Find line number
                        line_start = content.rfind('\n', 0, match.start()) + 1
                        line_number = content[:match.start()].count('\n') + 1
                        
                        # Extract the matched line
                        line_end = content.find('\n', match.start())
                        if line_end == -1:
                            line_end = len(content)
                        match_line = content[line_start:line_end]
                        
                        matches.append({
                            "type": construct_type,
                            "file": str(file_path.relative_to(directory)),
                            "absolute_path": str(file_path),
                            "line_number": line_number,
                            "column": match.start() - line_start + 1,
                            "match_text": match_line.strip(),
                            "language": lang,
                            "context": None  # TODO: Add context extraction
                        })
                except Exception:
                    continue
    
    return matches


def _extract_context(ripgrep_data: Dict) -> Optional[List[str]]:
    """Extract context lines from ripgrep JSON output."""
    # TODO: Implement context extraction from ripgrep JSON
    return None


def _is_binary_file(file_path: Path) -> bool:
    """Check if a file is likely binary."""
    binary_extensions = {
        '.pyc', '.pyo', '.so', '.dll', '.exe', '.bin', '.dat',
        '.db', '.sqlite', '.jpg', '.jpeg', '.png', '.gif', '.bmp',
        '.ico', '.svg', '.mp3', '.mp4', '.avi', '.mov', '.pdf',
        '.doc', '.docx', '.xls', '.xlsx', '.zip', '.tar', '.gz',
        '.rar', '.7z', '.jar', '.war', '.ear', '.class'
    }
    
    return file_path.suffix.lower() in binary_extensions


def _display_search_results(results: Dict[str, Any]):
    """Display search results in a formatted table."""
    matches = results.get("matches", [])
    
    if not matches:
        console.print("[yellow]No matches found.[/yellow]")
        return
    
    # Create a table for results
    table = Table(title=f"Search Results ({len(matches)} matches)", show_lines=True)
    table.add_column("File", style="cyan", no_wrap=True)
    table.add_column("Line", style="green", justify="right")
    table.add_column("Match", style="white")
    
    # Group by file for better display
    current_file = None
    for match in matches[:20]:  # Show first 20 results
        file_name = match["file"]
        line_num = match.get("line_number", "-")
        match_text = match["match_text"]
        
        # Truncate long lines
        if len(match_text) > 80:
            match_text = match_text[:77] + "..."
        
        # Only show filename once per group
        if file_name != current_file:
            table.add_row(file_name, str(line_num), match_text)
            current_file = file_name
        else:
            table.add_row("", str(line_num), match_text)
    
    if len(matches) > 20:
        table.add_row("...", "...", f"[dim]({len(matches) - 20} more matches)[/dim]")
    
    console.print(table)
    
    # Show summary by file
    if len(matches) > 5:
        file_counts = {}
        for match in matches:
            file_counts[match["file"]] = file_counts.get(match["file"], 0) + 1
        
        console.print("\n[bold]Matches by file:[/bold]")
        for file, count in sorted(file_counts.items(), key=lambda x: x[1], reverse=True)[:10]:
            console.print(f"  {file}: {count} matches")