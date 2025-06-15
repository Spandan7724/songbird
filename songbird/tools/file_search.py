# songbird/tools/file_search.py
"""
File search functionality using ripgrep (rg) for fast text search.
"""
import asyncio
import json
import shutil
from pathlib import Path
from typing import List, Dict, Any


async def file_search(pattern: str, directory: str) -> List[Dict[str, Any]]:
    """
    Search for text pattern in files using ripgrep.
    
    Args:
        pattern: Text pattern to search for
        directory: Directory path to search in
        
    Returns:
        List of dictionaries with search results in JSON format:
        [{"file": "path", "line": 1, "column": 5, "text": "line content"}, ...]
        
    Raises:
        FileNotFoundError: If directory doesn't exist
        RuntimeError: If ripgrep is not available
    """
    # Validate directory exists
    dir_path = Path(directory)
    if not dir_path.exists() or not dir_path.is_dir():
        raise FileNotFoundError(f"Directory not found: {directory}")
    
    # Check if ripgrep is available
    rg_path = shutil.which("rg")
    if not rg_path:
        raise RuntimeError("ripgrep (rg) not found on PATH. Please install ripgrep.")
    
    # Build ripgrep command
    cmd = [
        rg_path,
        "--json",           # Output in JSON format
        "--ignore-case",    # Case insensitive search
        "--line-number",    # Include line numbers
        "--column",         # Include column numbers
        "--max-columns", "200",  # Limit line length
        pattern,
        str(dir_path)
    ]
    
    try:
        # Run ripgrep command
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        
        # Parse JSON output
        results = []
        if stdout:
            for line in stdout.decode().strip().split('\n'):
                if line:
                    try:
                        data = json.loads(line)
                        # Only process match records (not begin/end/summary)
                        if data.get('type') == 'match':
                            match_data = data['data']
                            result = {
                                'file': str(Path(match_data['path']['text']).relative_to(dir_path)),
                                'line': match_data['line_number'],
                                'column': match_data['submatches'][0]['start'] + 1,  # 1-indexed
                                'text': match_data['lines']['text'].rstrip('\n\r')
                            }
                            results.append(result)
                    except (json.JSONDecodeError, KeyError):
                        # Skip malformed JSON lines
                        continue
        
        return results
        
    except Exception as e:
        raise RuntimeError(f"Error running ripgrep: {e}")