# songbird/tools/shell_exec.py
"""
Shell command execution tool for running terminal commands safely.
"""
import asyncio
import os
import platform
import shlex
from pathlib import Path
from typing import Dict, Any, Optional


async def shell_exec(
    command: str, 
    working_dir: Optional[str] = None,
    timeout: float = 30.0,
    max_output_size: int = 4096
) -> Dict[str, Any]:
    """
    Execute a shell command safely with output capture and limits.
    
    Args:
        command: Shell command to execute
        working_dir: Working directory for command (defaults to current dir)
        timeout: Timeout in seconds (default: 30)
        max_output_size: Maximum output size in bytes (default: 4KB)
        
    Returns:
        Dictionary with execution results
    """
    try:
        # Validate working directory
        if working_dir:
            work_path = Path(working_dir)
            if not work_path.exists() or not work_path.is_dir():
                return {
                    "success": False,
                    "error": f"Working directory does not exist: {working_dir}"
                }
            working_dir = str(work_path.resolve())
        else:
            working_dir = os.getcwd()
        
        # Prepare command for execution
        if platform.system() == "Windows":
            # On Windows, use cmd.exe
            cmd_args = ["cmd", "/c", command]
        else:
            # On Unix-like systems, use shell
            cmd_args = ["/bin/bash", "-c", command]
        
        # Create subprocess
        process = await asyncio.create_subprocess_exec(
            *cmd_args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=working_dir
        )
        
        # Wait for completion with timeout
        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                process.communicate(), 
                timeout=timeout
            )
        except asyncio.TimeoutError:
            # Kill the process if it times out
            process.kill()
            await process.wait()
            return {
                "success": False,
                "error": f"Command timed out after {timeout} seconds",
                "command": command,
                "working_dir": working_dir
            }
        
        # Decode output
        stdout = stdout_bytes.decode('utf-8', errors='replace')
        stderr = stderr_bytes.decode('utf-8', errors='replace')
        
        # Check for output truncation
        output_truncated = False
        if len(stdout) > max_output_size:
            stdout = stdout[:max_output_size]
            output_truncated = True
        if len(stderr) > max_output_size:
            stderr = stderr[:max_output_size]
            output_truncated = True
        
        # Determine success based on exit code
        exit_code = process.returncode
        success = (exit_code == 0)
        
        result = {
            "success": success,
            "exit_code": exit_code,
            "stdout": stdout,
            "stderr": stderr,
            "command": command,
            "working_dir": working_dir
        }
        
        if output_truncated:
            result["output_truncated"] = True
            
        if not success:
            result["error"] = f"Command failed with exit code {exit_code}"
            
        return result
        
    except FileNotFoundError as e:
        return {
            "success": False,
            "error": f"Command not found: {e}",
            "command": command,
            "working_dir": working_dir or os.getcwd()
        }
    except PermissionError as e:
        return {
            "success": False,
            "error": f"Permission denied: {e}",
            "command": command,
            "working_dir": working_dir or os.getcwd()
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Error executing command: {e}",
            "command": command,
            "working_dir": working_dir or os.getcwd()
        }


def is_command_safe(command: str) -> bool:
    """
    Check if a command is considered safe to execute.
    This is a basic safety check - in production you might want more restrictions.
    
    Args:
        command: Command to check
        
    Returns:
        True if command appears safe, False otherwise
    """
    dangerous_patterns = [
        "rm -rf /",
        "mkfs",
        "dd if=",
        ":(){ :|:& };:",  # Fork bomb
        "sudo rm",
        "sudo dd",
        "format",
        "> /dev/",
        "chmod 777 /",
    ]
    
    command_lower = command.lower()
    return not any(pattern in command_lower for pattern in dangerous_patterns)