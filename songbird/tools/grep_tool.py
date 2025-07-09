# grep tool for advanced content search with regex support.

import re
import asyncio
import shutil
import json
import os
from pathlib import Path
from typing import Dict, Any, Optional
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

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
    try:
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

    
    try:
        cmd = [shutil.which("rg"), "--json", "--no-heading"]
        
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
        
        if file_pattern:
            cmd.extend(["--glob", file_pattern])
        cmd.extend(["--max-count", str(max_results)])
        cmd.extend([pattern, str(directory)])
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
    # Python fallback for grep functionality
    
    import glob
    
    matches = []
    
    try:
        regex_flags = 0 if case_sensitive else re.IGNORECASE
        
        if regex:
            if whole_word:
                pattern = f"\\b{pattern}\\b"
            compiled_pattern = re.compile(pattern, regex_flags)
        else:
            escaped_pattern = re.escape(pattern)
            if whole_word:
                escaped_pattern = f"\\b{escaped_pattern}\\b"
            compiled_pattern = re.compile(escaped_pattern, regex_flags)
        
        files_to_search = []
        
        if file_pattern:
            search_pattern = str(directory / "**" / file_pattern)
            files_to_search = [Path(f) for f in glob.glob(search_pattern, recursive=True)]
        else:
            for root, dirs, files in os.walk(directory):
                # Skip hidden directories unless requested
                if not include_hidden:
                    dirs[:] = [d for d in dirs if not d.startswith('.')]
                
                for file in files:
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
                        
                        if context_lines > 0:
                            context_before = []
                            context_after = []
                            
                            for i in range(max(0, line_num - context_lines - 1), line_num - 1):
                                if i < len(lines):
                                    context_before.append({
                                        "line_number": i + 1,
                                        "text": lines[i].rstrip('\n'),
                                        "type": "context"
                                    })
                            
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
    matches = result.get("matches", [])
    
    if not matches:
        console.print("[yellow]No matches found[/yellow]")
        return
    
    pattern = result.get("pattern", "")
    
    files_with_matches = {}
    for match in matches:
        file_path = match["file"]
        if file_path not in files_with_matches:
            files_with_matches[file_path] = []
        files_with_matches[file_path].append(match)
    
    table = Table(
        title=f"Found {len(matches)} matches for '{pattern}' in {len(files_with_matches)} files"
    )
    table.add_column("File", style="cyan", width=30)
    table.add_column("Line", style="green", justify="right", width=6)
    table.add_column("Content", style="white", ratio=1)
    
    for file_path, file_matches in files_with_matches.items():
        for i, match in enumerate(file_matches):
            file_display = file_path if i == 0 else ""
            
            line_num = match.get("line_number", "")
            line_display = str(line_num) if line_num else "—"
            
            text = match["text"]
            highlighted_text = _highlight_pattern_in_text(text, pattern)
            
            table.add_row(
                f"[bold]{file_display}[/bold]" if file_display else "",
                line_display,
                highlighted_text
            )
            
            context_after = match.get("context_after", [])
            for context in context_after[:2]:
                table.add_row(
                    "",
                    f"[dim]{context.get('line_number', '')}[/dim]",
                    f"[dim]{context['text']}[/dim]"
                )
        
        if len(files_with_matches) > 1 and file_path != list(files_with_matches.keys())[-1]:
            table.add_row("", "", "[dim]...[/dim]")
    

    if result.get("truncated"):
        table.add_row(
            "[dim]...[/dim]",
            "[dim]...[/dim]",
            "[dim]More results available (increase max_results)[/dim]"
        )

    panel = Panel(table, border_style="white", padding=(1, 2))
    console.print(panel)
    

    console.print(f"\n[bold]Summary:[/bold] {len(matches)} matches across {len(files_with_matches)} files")

    if len(files_with_matches) > 1:
        file_summary = []
        for file_path, file_matches in list(files_with_matches.items())[:5]:
            count = len(file_matches)
            file_summary.append(f"{file_path}: {count}")
        
        if file_summary:
            console.print(f"[dim]Top files: {', '.join(file_summary)}[/dim]")


def _highlight_pattern_in_text(text: str, pattern: str) -> str:
    
    try:
        escaped_pattern = re.escape(pattern)
        highlighted = re.sub(
            f"({escaped_pattern})",
            r"[bold yellow on black]\1[/bold yellow on black]",
            text,
            flags=re.IGNORECASE
        )
        return highlighted
    except Exception:
        return text


async def grep_count(
    pattern: str,
    directory: str = ".",
    file_pattern: Optional[str] = None,
    case_sensitive: bool = False
) -> Dict[str, Any]:
    result = await grep_search(
        pattern=pattern,
        directory=directory,
        file_pattern=file_pattern,
        case_sensitive=case_sensitive,
        max_results=10000  
    )
    
    if result["success"]:
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

    # First, find all matches
    result = await grep_search(
        pattern=pattern,
        directory=directory,
        file_pattern=file_pattern,
        case_sensitive=case_sensitive,
        regex=regex,
        max_results=50  
    )
    
    if not result["success"]:
        return result
    
    # Show what replacements would look like
    preview_items = []
    for match in result["matches"]:
        original_text = match["text"]
    
        if regex:
            try:
                flags = 0 if case_sensitive else re.IGNORECASE
                new_text = re.sub(pattern, replacement, original_text, flags=flags)
            except Exception:
                new_text = original_text
        else:
            if case_sensitive:
                new_text = original_text.replace(pattern, replacement)
            else:
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