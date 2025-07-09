# file search using ripgrep with Python fallback.

import asyncio
import json
import shutil
import os
from pathlib import Path
from typing import Dict, Any, Optional
from rich.console import Console
from rich.table import Table
import glob

console = Console()


async def file_search(
    pattern: str,
    directory: str = ".",
    file_type: Optional[str] = None,
    case_sensitive: bool = False,
    max_results: int = 50
) -> Dict[str, Any]:
    # Search for patterns in files using ripgrep (fast) or Python fallback.
    
    # Args:
    #     pattern: What to search for (text, regex, or filename/glob pattern)
    #     directory: Directory to search in
    #     file_type: File type filter (e.g., "py", "js", "md")
    #     case_sensitive: Whether search should be case sensitive
    #     max_results: Maximum results to return
        
    # Returns:
    #     Dictionary with search results

    dir_path = Path(directory).resolve()
    if not dir_path.exists():
        return {
            "success": False,
            "error": f"Directory not found: {directory}",
            "matches": []
        }

    console.print(f"\n[bold cyan]Searching for:[/bold cyan] {pattern}")
    console.print(f"[dim]Directory: {dir_path}[/dim]\n")

    is_glob_pattern = any(c in pattern for c in ['*', '?', '[', ']'])

    is_filename_search = (
        is_glob_pattern or
        (pattern.endswith(('.py', '.js', '.md', '.txt', '.json', '.yaml', '.yml'))
         and '/' not in pattern
         and '\\' not in pattern)
    )

    rg_path = shutil.which("rg")
    if rg_path:
        result = await _search_with_ripgrep(
            pattern, dir_path, file_type, case_sensitive, max_results, is_filename_search, is_glob_pattern
        )
    else:
        console.print(
            "[yellow]ripgrep not found, using Python search (slower)[/yellow]")
        result = await _search_with_python(
            pattern, dir_path, file_type, case_sensitive, max_results, is_filename_search, is_glob_pattern
        )

    _display_results(result)

    return result


async def _search_with_ripgrep(
    pattern: str,
    directory: Path,
    file_type: Optional[str],
    case_sensitive: bool,
    max_results: int,
    is_filename_search: bool,
    is_glob_pattern: bool
) -> Dict[str, Any]:
    # Use ripgrep for fast searching.

    matches = []

    try:
        if is_filename_search:
            cmd = [shutil.which("rg"), "--files", "--no-ignore", "--hidden"]

            if file_type:
                cmd.extend(["--type", file_type])
            elif is_glob_pattern:
                if pattern.startswith("*."):
                    cmd.extend(["--glob", pattern])
                else:
                    cmd.extend(["--glob", pattern])

            cmd.append(str(directory))

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await process.communicate()

            if stdout:
                for line in stdout.decode().strip().split('\n'):
                    if line:
                        file_path = Path(line)
                        if is_glob_pattern or file_path.name == pattern:
                            matches.append({
                                "type": "file",
                                "file": str(file_path.relative_to(directory)),
                                "line_number": None,
                                "match_text": file_path.name
                            })
        else:
            cmd = [
                shutil.which("rg"),
                "--json",
                "--no-ignore",
                "--hidden",
                "--max-count", str(max_results),
            ]

            if not case_sensitive:
                cmd.append("--ignore-case")

            if file_type:
                cmd.extend(["--type", file_type])

            cmd.extend([pattern, str(directory)])

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await process.communicate()

            if stdout:
                for line in stdout.decode().strip().split('\n'):
                    if line:
                        try:
                            data = json.loads(line)
                            if data.get('type') == 'match':
                                match_data = data['data']
                                matches.append({
                                    "type": "text",
                                    "file": str(Path(match_data['path']['text']).relative_to(directory)),
                                    "line_number": match_data['line_number'],
                                    "match_text": match_data['lines']['text'].strip()
                                })
                        except json.JSONDecodeError:
                            continue

        return {
            "success": True,
            "pattern": pattern,
            "search_type": "file" if is_filename_search else "text",
            "matches": matches[:max_results],
            "total_matches": len(matches),
            "truncated": len(matches) > max_results
        }

    except Exception as e:
        return {
            "success": False,
            "error": f"ripgrep error: {e}",
            "matches": []
        }


async def _search_with_python(
    pattern: str,
    directory: Path,
    file_type: Optional[str],
    case_sensitive: bool,
    max_results: int,
    is_filename_search: bool,
    is_glob_pattern: bool
) -> Dict[str, Any]:
    # Simple Python fallback for when ripgrep isn't available.

    matches = []

    extensions = None
    if file_type:
        ext_map = {
            "py": [".py"],
            "js": [".js", ".jsx", ".ts", ".tsx"],
            "md": [".md", ".markdown"],
            "txt": [".txt"],
            "json": [".json"],
            "yaml": [".yaml", ".yml"],
        }
        extensions = ext_map.get(file_type, [f".{file_type}"])

    try:
        if is_filename_search and is_glob_pattern:
            pattern_path = directory / pattern
            for file_path in glob.glob(str(pattern_path), recursive=True):
                if len(matches) >= max_results:
                    break

                file_path = Path(file_path)
                if file_path.is_file():
                    matches.append({
                        "type": "file",
                        "file": str(file_path.relative_to(directory)),
                        "line_number": None,
                        "match_text": file_path.name
                    })
        else:
            for root, dirs, files in os.walk(directory):
                dirs[:] = [d for d in dirs if not d.startswith('.')]

                for file in files:
                    if len(matches) >= max_results:
                        break

                    file_path = Path(root) / file

                    if extensions and not any(file.endswith(ext) for ext in extensions):
                        continue

                    if is_filename_search:
                        if file == pattern:
                            matches.append({
                                "type": "file",
                                "file": str(file_path.relative_to(directory)),
                                "line_number": None,
                                "match_text": file
                            })
                    else:
                        try:
                            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                                for line_num, line in enumerate(f, 1):
                                    if len(matches) >= max_results:
                                        break

                                    if case_sensitive:
                                        found = pattern in line
                                    else:
                                        found = pattern.lower() in line.lower()

                                    if found:
                                        matches.append({
                                            "type": "text",
                                            "file": str(file_path.relative_to(directory)),
                                            "line_number": line_num,
                                            "match_text": line.strip()
                                        })
                        except Exception:
                            continue

        return {
            "success": True,
            "pattern": pattern,
            "search_type": "file" if is_filename_search else "text",
            "matches": matches,
            "total_matches": len(matches),
            "truncated": False
        }

    except Exception as e:
        return {
            "success": False,
            "error": f"Search error: {e}",
            "matches": []
        }


def _display_results(result: Dict[str, Any]):
    # Display search results in a nice table.

    if not result.get("success"):
        console.print(f"[red]Search failed: {result.get('error')}[/red]")
        return

    matches = result.get("matches", [])
    if not matches:
        console.print("[yellow]No matches found[/yellow]")
        return

    table = Table(
        title=f"Found {len(matches)} matches for '{result['pattern']}'")
    table.add_column("File", style="cyan")
    table.add_column("Line", style="green", justify="right")
    table.add_column("Match", style="white")

    for match in matches[:20]:
        line_num = str(match.get("line_number", "")
                       ) if match.get("line_number") else "—"
        match_text = match["match_text"]

        if len(match_text) > 80:
            match_text = match_text[:77] + "..."

        table.add_row(
            match["file"],
            line_num,
            match_text
        )

    if len(matches) > 20:
        table.add_row(
            "...", "...", f"[dim]{len(matches) - 20} more matches[/dim]")

    console.print(table)

    if len(matches) > 5:
        files = {}
        for match in matches:
            files[match["file"]] = files.get(match["file"], 0) + 1

        console.print(f"\n[bold]Files with matches:[/bold] {len(files)}")
        for file, count in list(files.items())[:5]:
            console.print(
                f"  {file}: {count} match{'es' if count > 1 else ''}")
