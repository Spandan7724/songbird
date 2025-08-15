import asyncio
import os
import platform
from pathlib import Path
from typing import Dict, Any, Optional
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

console = Console()


async def shell_exec(
    command: str, 
    working_dir: Optional[str] = None,
    timeout: float = 30.0,
    max_output_size: int = 32768,  
    show_live_output: bool = True
) -> Dict[str, Any]:

    # Execute a shell command safely with output capture and limits.
    
    # Args:
    #     command: Shell command to execute
    #     working_dir: Working directory for command (defaults to current dir)
    #     timeout: Timeout in seconds (default: 30)
    #     max_output_size: Maximum output size in bytes (default: 32KB)
    #     show_live_output: Whether to show output as it streams (default: True)
        
    # Returns:
    #     Dictionary with execution results

    try:

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
        

        console.print(f"\n[bold cyan]Executing command:[/bold cyan] {command}")
        console.print(f"[dim]Working directory: {working_dir}[/dim]\n")
        
        if platform.system() == "Windows":
            cmd_args = ["cmd", "/c", command]
            shell_prompt = ">"
        else:
            cmd_args = ["/bin/bash", "-c", command]
            shell_prompt = "$"
        
        shell_display = Text()
        shell_display.append(f"{shell_prompt} ", style="bold aquamarine1")
        shell_display.append(command, style="bold white")
        console.print(Panel(shell_display, title="Shell", title_align="left", border_style="aquamarine1"))
        
        process = await asyncio.create_subprocess_exec(
            *cmd_args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=working_dir
        )
        
        stdout_lines = []
        stderr_lines = []
        
        async def read_stream(stream, output_list, style=""):
            while True:
                line = await stream.readline()
                if not line:
                    break
                decoded_line = line.decode('utf-8', errors='replace')
                output_list.append(decoded_line)
                if show_live_output:
                    console.print(decoded_line.rstrip(), style=style)
        
        if show_live_output:
            console.print("\n[bold]Output:[/bold]")
            console.rule(style="dim")
        
        try:
            await asyncio.wait_for(
                asyncio.gather(
                    read_stream(process.stdout, stdout_lines),
                    read_stream(process.stderr, stderr_lines, style="red")
                ),
                timeout=timeout
            )
            
            await asyncio.wait_for(process.wait(), timeout=1.0)
            
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
            
            console.print(f"\n[bold red]Command timed out after {timeout} seconds![/bold red]")
            
            return {
                "success": False,
                "error": f"Command timed out after {timeout} seconds",
                "command": command,
                "working_dir": working_dir,
                "timeout": True
            }
        
        stdout = ''.join(stdout_lines)
        stderr = ''.join(stderr_lines)
        
        output_truncated = False
        if len(stdout) > max_output_size:
            stdout = stdout[:max_output_size] + "\n... (output truncated)"
            output_truncated = True
        if len(stderr) > max_output_size:
            stderr = stderr[:max_output_size] + "\n... (output truncated)"
            output_truncated = True
        
        exit_code = process.returncode
        success = (exit_code == 0)
        
        # Show completion status
        if show_live_output:
            console.rule(style="dim")
            if success:
                console.print(f"[dim]✓ Command completed successfully[/dim] (exit code: {exit_code})")
            else:
                console.print(f"[dim red]✗ Command failed[/dim red] (exit code: {exit_code})")
        
        result = {
            "success": success,
            "exit_code": exit_code,
            "stdout": stdout,
            "stderr": stderr,
            "command": command,
            "working_dir": working_dir,
            "output_displayed": show_live_output
        }
        
        if output_truncated:
            result["output_truncated"] = True
            
        if not success and not stderr:
            result["error"] = f"Command failed with exit code {exit_code}"
            
        return result
        
    except FileNotFoundError as e:
        error_msg = f"Command not found: {str(e).split(':')[-1].strip()}"
        console.print(f"\n[bold red]Error:[/bold red] {error_msg}")
        
        return {
            "success": False,
            "error": error_msg,
            "command": command,
            "working_dir": working_dir or os.getcwd()
        }
    except PermissionError as e:
        error_msg = f"Permission denied: {e}"
        console.print(f"\n[bold red]Error:[/bold red] {error_msg}")
        
        return {
            "success": False,
            "error": error_msg,
            "command": command,
            "working_dir": working_dir or os.getcwd()
        }
    except Exception as e:
        error_msg = f"Error executing command: {e}"
        console.print(f"\n[bold red]Error:[/bold red] {error_msg}")
        
        return {
            "success": False,
            "error": error_msg,
            "command": command,
            "working_dir": working_dir or os.getcwd()
        }


def is_command_safe(command: str) -> bool:
    # Check if a command is considered safe to execute.
    dangerous_patterns = [
        "rm -rf /",
        "rm -rf /*",
        "mkfs",
        "dd if=/dev/zero",
        "dd if=/dev/urandom", 
        ":(){ :|:& };:",  
        "sudo rm -rf",
        "format c:",
        "format /",
        "> /dev/sda",
        "chmod -R 777 /",
        "chown -R",
        "del /f /s /q c:",
        "deltree /y c:",
    ]
    
    command_lower = command.lower().strip()
    
    for pattern in dangerous_patterns:
        if pattern.lower() in command_lower:
            return False
    
    if platform.system() == "Windows":
        win_dangerous = ["format ", "cipher /w:", "sfc /scannow", "dism "]
        for pattern in win_dangerous:
            if pattern in command_lower:
                return False
    
    return True


async def shell_exec_safe(
    command: str, 
    working_dir: Optional[str] = None,
    timeout: float = 30.0,
    max_output_size: int = 32768,
    show_live_output: bool = True
) -> Dict[str, Any]:
    if not is_command_safe(command):
        console.print("\n[bold red]Safety check failed![/bold red] This command appears potentially dangerous.")
        console.print(f"Command: {command}")
        
        return {
            "success": False,
            "error": "Command blocked by safety check - appears potentially dangerous",
            "command": command,
            "working_dir": working_dir or os.getcwd(),
            "safety_blocked": True
        }
    
    return await shell_exec(
        command=command,
        working_dir=working_dir,
        timeout=timeout,
        max_output_size=max_output_size,
        show_live_output=show_live_output
    )