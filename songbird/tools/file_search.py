# songbird/tools/file_search.py
"""
Simple file search that prefers ripgrep but falls back to pure Python.

Supports three modes automatically detected from the `pattern` argument:

1. Exact-filename search          (e.g. "config.py")
2. Glob search with *,?,[ ]       (e.g. "*.py", "*test*.js")
3. Text / regex search            (default)

When `file_type` is given, it narrows results to that extension / language.
"""
from __future__ import annotations

import asyncio
import json
import os
import shutil
from pathlib import Path
from fnmatch import fnmatch
from typing import Any, Dict, List, Optional

from rich.console import Console
from rich.table import Table

console = Console()


# --------------------------------------------------------------------------- #
#  Public entry-point used by Songbird tool executor
# --------------------------------------------------------------------------- #
async def file_search(
    pattern: str,
    directory: str = ".",
    file_type: Optional[str] = None,
    case_sensitive: bool = False,
    max_results: int = 50,
) -> Dict[str, Any]:
    dir_path = Path(directory).resolve()
    if not dir_path.exists():
        return {"success": False, "error": f"Directory not found: {directory}", "matches": []}

    # Debug banner
    console.print(f"\n[bold cyan]Searching for:[/bold cyan] {pattern}")
    console.print(f"[dim]Directory: {dir_path}[/dim]\n")

    # --- mode detection ---------------------------------------------------- #
    has_glob_chars = any(c in pattern for c in "*?[]")
    is_filename_search = (
        not has_glob_chars
        and "/" not in pattern
        and pattern.endswith(tuple(".py .js .ts .jsx .tsx .md .txt .json .yaml .yml".split()))
    )
    is_glob_search = has_glob_chars  # simple alias

    rg_path = shutil.which("rg")
    if rg_path:
        result = await _search_with_ripgrep(
            pattern,
            dir_path,
            file_type,
            case_sensitive,
            max_results,
            is_filename_search,
            is_glob_search,
        )
    else:
        console.print(
            "[yellow]ripgrep not found, using Python search (slower)[/yellow]")
        result = await _search_with_python(
            pattern,
            dir_path,
            file_type,
            case_sensitive,
            max_results,
            is_filename_search,
            is_glob_search,
        )

    _display_results(result)
    return result


# --------------------------------------------------------------------------- #
#  ripgrep path
# --------------------------------------------------------------------------- #
async def _search_with_ripgrep(
    pattern: str,
    directory: Path,
    file_type: Optional[str],
    case_sensitive: bool,
    max_results: int,
    is_filename_search: bool,
    is_glob_search: bool,
) -> Dict[str, Any]:
    matches: List[Dict[str, Any]] = []

    try:
        # ------------------------------------------------------------------ #
        # A) glob search  (*.py, *foo*.md, etc.)
        # ------------------------------------------------------------------ #
        if is_glob_search:
            cmd = [shutil.which("rg"), "--files", "-g", pattern]
            if file_type:
                cmd.insert(3, "--type")
                cmd.insert(4, file_type)  # after --files
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=str(directory),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()
            for line in stdout.decode().splitlines():
                if not line:
                    continue
                rel_path = line.strip()  # already relative because of cwd
                matches.append(
                    {"type": "file", "file": rel_path, "line_number": None, "match_text": Path(line).name}
                )

        # ------------------------------------------------------------------ #
        # B) exact-filename search  (config.py)
        # ------------------------------------------------------------------ #
        elif is_filename_search:
            cmd = [shutil.which("rg"), "--files"]
            if file_type:
                cmd.extend(["--type", file_type])
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=str(directory),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()
            for line in stdout.decode().splitlines():
                if Path(line).name == pattern:
                    matches.append(
                        {"type": "file", "file": line.strip(), "line_number": None, "match_text": Path(line).name}
                    )

        # ------------------------------------------------------------------ #
        # C) text / regex search
        # ------------------------------------------------------------------ #
        else:
            cmd = [shutil.which("rg"), "--json",
                   "--max-count", str(max_results)]
            if not case_sensitive:
                cmd.append("--ignore-case")
            if file_type:
                cmd.extend(["--type", file_type])
            cmd.extend([pattern, str(directory)])
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()
            for line in stdout.decode().splitlines():
                try:
                    data = json.loads(line)
                    if data.get("type") == "match":
                        md = data["data"]
                        matches.append(
                            {
                                "type": "text",
                                "file": str(Path(md["path"]["text"]).relative_to(directory)),
                                "line_number": md["line_number"],
                                "match_text": md["lines"]["text"].strip(),
                            }
                        )
                except json.JSONDecodeError:
                    continue

        return {
            "success": True,
            "pattern": pattern,
            "matches": matches[:max_results],
            "total_matches": len(matches),
            "truncated": len(matches) > max_results,
        }

    except Exception as e:
        return {"success": False, "error": f"ripgrep error: {e}", "matches": []}


# --------------------------------------------------------------------------- #
#  Pure-Python fallback
# --------------------------------------------------------------------------- #
async def _search_with_python(
    pattern: str,
    directory: Path,
    file_type: Optional[str],
    case_sensitive: bool,
    max_results: int,
    is_filename_search: bool,
    is_glob_search: bool,
) -> Dict[str, Any]:
    matches: List[Dict[str, Any]] = []

    # Map of file_type to extensions
    ext_map = {
        "py": [".py"],
        "js": [".js", ".jsx", ".ts", ".tsx"],
        "md": [".md", ".markdown"],
        "txt": [".txt"],
        "json": [".json"],
        "yaml": [".yaml", ".yml"],
    }
    extensions = ext_map.get(
        file_type, [f".{file_type}"]) if file_type else None

    try:
        for root, dirs, files in os.walk(directory):
            dirs[:] = [d for d in dirs if not d.startswith(".")]  # skip hidden

            for name in files:
                if len(matches) >= max_results:
                    break
                path = Path(root) / name

                # file-type filter
                if extensions and not any(name.endswith(ext) for ext in extensions):
                    continue

                rel = str(path.relative_to(directory))

                # glob path match
                if is_glob_search and fnmatch(rel, pattern):
                    matches.append({"type": "file", "file": rel,
                                   "line_number": None, "match_text": name})
                    continue

                # exact filename
                if is_filename_search and name == pattern:
                    matches.append({"type": "file", "file": rel,
                                   "line_number": None, "match_text": name})
                    continue

                # text search
                if not (is_filename_search or is_glob_search):
                    try:
                        with open(path, "r", encoding="utf-8", errors="ignore") as f:
                            for ln, line in enumerate(f, 1):
                                if len(matches) >= max_results:
                                    break
                                hay = line if case_sensitive else line.lower()
                                needle = pattern if case_sensitive else pattern.lower()
                                if needle in hay:
                                    matches.append(
                                        {"type": "text", "file": rel,
                                            "line_number": ln, "match_text": line.strip()}
                                    )
                    except Exception:
                        continue

        return {
            "success": True,
            "pattern": pattern,
            "matches": matches,
            "total_matches": len(matches),
            "truncated": len(matches) > max_results,
        }

    except Exception as e:
        return {"success": False, "error": f"Search error: {e}", "matches": []}


# --------------------------------------------------------------------------- #
#  Nicely render results
# --------------------------------------------------------------------------- #
def _display_results(res: Dict[str, Any]) -> None:
    if not res.get("success"):
        console.print(f"[red]Search failed: {res.get('error')}[/red]")
        return

    matches = res.get("matches", [])
    if not matches:
        console.print("[yellow]No matches found[/yellow]")
        return

    table = Table(title=f"Found {len(matches)} matches for '{res['pattern']}'")
    table.add_column("File", style="cyan")
    table.add_column("Line", style="green", justify="right")
    table.add_column("Match", style="white")

    for m in matches[:20]:
        ln = str(m.get("line_number", "")) if m.get("line_number") else "—"
        txt = m["match_text"]
        if len(txt) > 80:
            txt = txt[:77] + "..."
        table.add_row(m["file"], ln, txt)

    if len(matches) > 20:
        table.add_row("...", "...", f"[dim]{len(matches) - 20} more[/dim]")

    # Optional file summary
    if len(matches) > 5:
        cnt = {}
        for m in matches:
            cnt[m["file"]] = cnt.get(m["file"], 0) + 1
        console.print(f"\n[bold]{len(cnt)} files[/bold] contained matches")
        for f, n in list(cnt.items())[:5]:
            console.print(f"  {f}: {n} match{'es' if n > 1 else ''}")
