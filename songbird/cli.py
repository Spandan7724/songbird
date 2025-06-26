# songbird/cli.py
from __future__ import annotations
import asyncio
import os
import signal
import sys
import time
from threading import Timer
from typing import Optional
from datetime import datetime
import json
import typer
from rich.console import Console
from rich.status import Status
from rich.panel import Panel
from rich.syntax import Syntax
from rich.markdown import Markdown
from . import __version__
from .llm.providers import get_provider, get_default_provider, get_default_provider_name, list_available_providers, get_provider_info
from .orchestrator import SongbirdOrchestrator
from .memory.optimized_manager import OptimizedSessionManager
from .memory.models import Session
from .commands import CommandInputHandler, get_command_registry
from .memory.history_manager import MessageHistoryManager
from .commands.loader import is_command_input, parse_command_input, load_all_commands
from .enhanced_interface import (
    enhanced_cli, display_enhanced_help, display_version_info,
    create_provider_status_table, create_banner
)

app = typer.Typer(add_completion=False, rich_markup_mode="rich",
                  help="Songbird - Terminal-first AI coding companion", no_args_is_help=False)
console = Console()


def render_ai_response(content: str, speaker_name: str = "Songbird"):
    """
    Render AI response content as markdown with proper formatting.
    Avoids using # headers to prevent box formation in terminal.
    """
    if not content or not content.strip():
        return
    
    # Clean up the content - remove any # headers and replace with **bold**
    lines = content.split('\n')
    cleaned_lines = []
    
    for line in lines:
        # Convert # headers to **bold** text to avoid boxes
        if line.strip().startswith('#'):
            # Remove # symbols and make bold
            header_text = line.lstrip('#').strip()
            if header_text:
                cleaned_lines.append(f"**{header_text}**")
            else:
                cleaned_lines.append("")
        else:
            cleaned_lines.append(line)
    
    cleaned_content = '\n'.join(cleaned_lines)
    
    # Create markdown renderable
    md_renderable = Markdown(cleaned_content, code_theme="github-dark")
    
    # Print speaker name with color, then markdown content
    console.print(f"\n[medium_spring_green]{speaker_name}[/medium_spring_green]:")
    console.print(md_renderable)


# ------------------------------------------------------------------ #
#  Ctrl-C double-tap guard (global)
# ------------------------------------------------------------------ #
_GRACE = 2.0           # seconds between taps
_last = None           # time of previous SIGINT
_cleanup_timer = None  # track active cleanup timer for resource safety
_in_status = False     # track if we're in a status/thinking state

def _flash_notice():
    global _cleanup_timer
    # Cancel any existing cleanup timer to prevent accumulation
    if _cleanup_timer:
        _cleanup_timer.cancel()
    
    # If we're in status mode, use console.print instead of raw output
    if _in_status:
        # Don't try to manipulate cursor during status
        return
    
    # Normal mode - use ANSI escape sequences
    sys.stdout.write("\033[s")  # Save cursor position
    sys.stdout.write("\033[A")  # Move up one line
    sys.stdout.write("\r\033[2K")  # Clear that line
    sys.stdout.write("\033[90mPress Ctrl+C again to exit\033[0m")  # Gray notice
    sys.stdout.write("\033[u")  # Restore cursor position
    sys.stdout.flush()
    
    # Schedule cleanup: clear the notice line above
    def _clear():
        if not _in_status:
            sys.stdout.write("\033[s")  # Save cursor position
            sys.stdout.write("\033[A")  # Move up one line
            sys.stdout.write("\r\033[2K")  # Clear that line
            sys.stdout.write("\033[u")  # Restore cursor position
            sys.stdout.flush()
        
    _cleanup_timer = Timer(_GRACE, _clear)
    _cleanup_timer.start()

def _sigint(signum, frame):
    global _last, _cleanup_timer
    now = time.monotonic()

    if _last and (now - _last) < _GRACE:          # second tap → quit
        # Cancel any pending cleanup timer before exit
        if _cleanup_timer:
            _cleanup_timer.cancel()
        signal.signal(signal.SIGINT, signal.default_int_handler)
        
        if _in_status:
            # Force stop the status if active
            console.print("\n[red]Interrupted![/red]")
        else:
            # Clear the notice line if it exists
            sys.stdout.write("\033[A\r\033[2K\033[B")  # Up, clear, down
        
        print()  # Clean newline before exit
        raise KeyboardInterrupt

    # First tap handling
    if _in_status:
        # During status/thinking, just show a console message
        console.print("\n[dim]Press Ctrl+C again to exit[/dim]")
    else:
        # Normal input mode - erase ^C and show notice
        sys.stdout.write("\b\b  \b\b")  # Backspace over ^C
        sys.stdout.flush()
        _flash_notice()
    
    _last = now               # start grace window

# Register the signal handler
signal.signal(signal.SIGINT, _sigint)
# ------------------------------------------------------------------ #
def show_banner():
    """Display the Songbird ASCII banner in blue."""
    banner = """
███████╗ ██████╗ ███╗   ██╗ ██████╗ ██████╗ ██╗██████╗ ██████╗ 
██╔════╝██╔═══██╗████╗  ██║██╔════╝ ██╔══██╗██║██╔══██╗██╔══██╗
███████╗██║   ██║██╔██╗ ██║██║  ███╗██████╔╝██║██████╔╝██║  ██║
╚════██║██║   ██║██║╚██╗██║██║   ██║██╔══██╗██║██╔══██╗██║  ██║
███████║╚██████╔╝██║ ╚████║╚██████╔╝██████╔╝██║██║  ██║██████╔╝
╚══════╝ ╚═════╝ ╚═╝  ╚═══╝ ╚═════╝ ╚═════╝ ╚═╝╚═╝  ╚═╝╚═════╝
"""
    console.print(banner, style="bold blue")


def format_time_ago(dt: datetime) -> str:
    """Format a datetime as a human-readable time ago string."""
    now = datetime.now()
    diff = now - dt

    if diff.days > 7:
        return dt.strftime("%Y-%m-%d")
    elif diff.days > 0:
        return f"{diff.days}d ago"
    elif diff.seconds > 3600:
        return f"{diff.seconds // 3600}h ago"
    elif diff.seconds > 60:
        return f"{diff.seconds // 60}m ago"
    else:
        return "just now"


def _get_session_display_info(session_manager, session_id: str) -> tuple[int, str]:
    """Get user message count and last user message for session display."""
    try:
        # Try to get from session manager's storage directory
        storage_dir = session_manager.storage_dir
        session_file = storage_dir / f"{session_id}.jsonl"
        
        if not session_file.exists():
            return 0, ""
        
        user_messages = []
        
        with open(session_file, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                
                try:
                    data = json.loads(line)
                    if data.get("type") == "message" and data.get("role") == "user":
                        user_messages.append(data.get("content", ""))
                except json.JSONDecodeError:
                    continue
        
        user_count = len(user_messages)
        last_user_msg = user_messages[-1] if user_messages else ""
        
        return user_count, last_user_msg
        
    except Exception:
        return 0, ""


def display_session_selector(sessions: list[Session], session_manager) -> Optional[Session]:
    """Display an interactive session selector with better terminal handling."""
    if not sessions:
        console.print("No previous sessions found.", style="yellow")
        return None

    # Sort sessions by updated_at descending
    sessions.sort(key=lambda s: s.updated_at, reverse=True)
    
    # Limit sessions to avoid terminal overflow
    max_sessions = min(30, console.height - 10 if console.height > 10 else 20)
    display_sessions = sessions[:max_sessions]
    
    # Prepare options
    options = []
    for session in display_sessions:
        created = format_time_ago(session.created_at)
        modified = format_time_ago(session.updated_at)
        
        # Get actual message count and last user message from session file
        user_msg_count, last_user_msg = _get_session_display_info(session_manager, session.id)
        
        # Use last user message as summary, truncated
        if last_user_msg:
            summary = last_user_msg[:35]  # Slightly shorter to make room for provider info
            if len(last_user_msg) > 35:
                summary += "..."
        else:
            summary = "Empty session"
        
        # Add provider type information
        provider_info = ""
        if session.provider_config:
            provider = session.provider_config.get("provider", "unknown")
            if session.is_litellm_session():
                provider_info = f"[LiteLLM:{provider}]"
            else:
                provider_info = f"[{provider}]"
        else:
            provider_info = "[legacy]"
        
        option = f"{modified} | {created} | {user_msg_count} msgs | {provider_info} | {summary}"
        options.append(option)
    
    options.append("Start new session")
    
    if len(sessions) > max_sessions:
        console.print(f"[yellow]Showing {max_sessions} most recent sessions out of {len(sessions)} total[/yellow]\n")
    
    # Use interactive menu (synchronous)
    from .conversation import interactive_menu
    try:
        selected_idx = interactive_menu(
            "Select a session to resume:",
            options,
            default_index=0
        )
    except KeyboardInterrupt:
        console.print("\nOperation cancelled by user.")
        return None
    
    if selected_idx == len(display_sessions):
        return None
        
    return display_sessions[selected_idx]


def replay_conversation(session: Session):
    """Replay the conversation history to show it as the user saw it."""
    # Import here to avoid circular dependency
    from .tools.file_operations import display_diff_preview

    # Group messages with their tool calls and results
    i = 0
    while i < len(session.messages):
        msg = session.messages[i]

        if msg.role == "system":
            # Skip system messages in replay
            i += 1
            continue

        elif msg.role == "user":
            console.print(f"\n[bold cyan]You[/bold cyan]: {msg.content}")
            i += 1

        elif msg.role == "assistant":
            # Check if this is a tool-calling message
            if msg.tool_calls:
                # Show thinking message
                console.print(
                    "\n[medium_spring_green]Songbird[/medium_spring_green] (thinking...)", style="dim")

                # Track tool index for matching with tool results
                tool_result_idx = i + 1

                # Process each tool call
                for tool_call in msg.tool_calls:
                    function_name = tool_call["function"]["name"]
                    arguments = tool_call["function"]["arguments"]

                    # Parse arguments if they're a string
                    if isinstance(arguments, str):
                        arguments = json.loads(arguments)

                    # Get the corresponding tool result
                    tool_result = None
                    if tool_result_idx < len(session.messages) and session.messages[tool_result_idx].role == "tool":
                        tool_result = json.loads(
                            session.messages[tool_result_idx].content)
                        tool_result_idx += 1

                    # Display tool execution based on type
                    if function_name == "file_create" and tool_result:
                        file_path = tool_result.get(
                            "file_path", arguments.get("file_path", "unknown"))
                        content = arguments.get("content", "")

                        console.print(f"\nCreating new file: {file_path}")
                        # Determine language from file extension
                        ext = file_path.split(
                            '.')[-1] if '.' in file_path else 'text'
                        # Create numbered lines manually to match original formatting
                        lines = content.split('\n')
                        numbered_lines = []
                        for idx, line in enumerate(lines, 1):
                            numbered_lines.append(f"  {idx:2d} {line}")
                        formatted_content = '\n'.join(numbered_lines)
                        console.print(
                            f"╭─ New file: {file_path} {'─' * (console.width - len(file_path) - 15)}╮")
                        console.print(formatted_content)
                        console.print(f"╰{'─' * (console.width - 2)}╯")

                    elif function_name == "file_edit" and tool_result:
                        file_path = tool_result.get(
                            "file_path", arguments.get("file_path", "unknown"))
                        if "diff_preview" in tool_result:
                            display_diff_preview(
                                tool_result["diff_preview"], file_path)
                            console.print("\nApply these changes?\n")
                            console.print("[green]▶ Yes[/green]")
                            console.print("  No")
                            console.print("\nSelected: Yes")

                    elif function_name == "shell_exec" and tool_result:
                        command = tool_result.get(
                            "command", arguments.get("command", ""))
                        cwd = tool_result.get("working_directory", "")

                        console.print(f"\nExecuting command: {command}")
                        if cwd:
                            console.print(f"Working directory: {cwd}")

                        # Match the exact shell panel style
                        console.print(
                            f"\n╭─ Shell {'─' * (console.width - 10)}╮")
                        console.print(
                            f"│ > {command}{' ' * (console.width - len(command) - 5)}│")
                        console.print(f"╰{'─' * (console.width - 2)}╯")

                        if "stdout" in tool_result and tool_result["stdout"]:
                            console.print("\nOutput:")
                            console.print("─" * console.width)
                            console.print(tool_result["stdout"].rstrip())
                            console.print("─" * console.width)

                        if "stderr" in tool_result and tool_result["stderr"]:
                            console.print("\nError output:", style="red")
                            console.print(
                                tool_result["stderr"].rstrip(), style="red")

                        exit_code = tool_result.get("exit_code", 0)
                        if exit_code == 0:
                            console.print(
                                f"✓ Command completed successfully (exit code: {exit_code})", style="green")
                        else:
                            console.print(
                                f"✗ Command failed (exit code: {exit_code})", style="red")

                    elif function_name == "file_search" and tool_result:
                        pattern = arguments.get("pattern", "")
                        console.print(f"\nSearching for: {pattern}")

                        # Display search results if available
                        if "matches" in tool_result and tool_result["matches"]:
                            from rich.table import Table
                            table = Table(
                                title=f"Search results for '{pattern}'")
                            table.add_column("File", style="cyan")
                            table.add_column("Line", style="yellow")
                            table.add_column("Content", style="white")

                            # Show first 10
                            for match in tool_result["matches"][:10]:
                                table.add_row(
                                    match.get("file", ""),
                                    str(match.get("line_number", "")),
                                    match.get("line_content", "").strip()
                                )
                            console.print(table)

                    elif function_name == "file_read" and tool_result:
                        file_path = arguments.get("file_path", "")
                        console.print(f"\nReading file: {file_path}")

                        if "content" in tool_result:
                            content = tool_result["content"]
                            # Show first 20 lines
                            lines = content.split('\n')[:20]
                            preview = '\n'.join(lines)
                            if len(content.split('\n')) > 20:
                                preview += "\n... (truncated)"

                            ext = file_path.split(
                                '.')[-1] if '.' in file_path else 'text'
                            syntax = Syntax(
                                preview, ext, theme="monokai", line_numbers=True)
                            console.print(
                                Panel(syntax, title=f"File: {file_path}", border_style="blue"))

                # Skip to after all tool results
                i = tool_result_idx

                # If there's content after tool calls, show it
                if msg.content:
                    render_ai_response(msg.content)

            else:
                # Regular assistant message
                if msg.content:
                    render_ai_response(msg.content)
                i += 1

        elif msg.role == "tool":
            # Tool results are handled inline above, skip
            i += 1
            continue
        else:
            i += 1


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    provider: Optional[str] = typer.Option(
        None, "--provider", "-p", help="LLM provider to use (openai, claude, gemini, ollama, openrouter)"),
    list_providers: bool = typer.Option(
        False, "--list-providers", help="List available providers and exit"),
    continue_session: bool = typer.Option(
        False, "--continue", "-c", help="Continue the latest session"),
    resume_session: bool = typer.Option(
        False, "--resume", "-r", help="Resume a previous session from a list"),
    use_litellm: bool = typer.Option(
        False, "--litellm", help="Use LiteLLM unified interface (default when legacy unavailable)"),
    provider_url: Optional[str] = typer.Option(
        None, "--provider-url", help="Custom API base URL for provider", hidden=True)
):
    """
    Songbird - Terminal-first AI coding companion
    
    Run 'songbird' to start an interactive chat session with AI and tools.
    Run 'songbird --continue' to continue your latest session.
    Run 'songbird --resume' to select and resume a previous session.
    Run 'songbird --litellm' to use the new LiteLLM unified interface.
    Run 'songbird version' to show version information.
    """
    if list_providers:
        from .llm.providers import get_provider_info
        
        provider_info = get_provider_info()
        default = get_default_provider_name()
        
        console.print("Available LLM Providers:", style="bold cornflower_blue")
        console.print()
        
        for provider_name, info in provider_info.items():
            status_text = ""
            if provider_name == default:
                status_text = " [bright_green](default)[/bright_green]"
            elif not info["available"]:
                status_text = " [red](unavailable)[/red]"
            
            console.print(f"[bold]{provider_name}[/bold]{status_text}")
            
            # Show discovery status
            discovery_status = "✓ Live Discovery" if info.get("models_discovered", False) else "Fallback Models"
            console.print(f"  Models: [dim]{discovery_status}[/dim]")
            
            if info["api_key_env"]:
                key_status = "✓" if info["available"] else "✗"
                console.print(f"  API Key: {info['api_key_env']} [{key_status}]")
            
            if info["models"]:
                model_list = ", ".join(info["models"][:3])
                if len(info["models"]) > 3:
                    model_list += f" (+{len(info['models']) - 3} more)"
                console.print(f"  Models: {model_list}")
            
            console.print()
        
        return

    if ctx.invoked_subcommand is None:
        # No subcommand provided, start chat session
        chat(provider=provider,
             continue_session=continue_session, resume_session=resume_session,
             use_litellm=use_litellm, provider_url=provider_url)


@app.command(hidden=True)
def chat(
    provider: Optional[str] = None,
    continue_session: bool = False,
    resume_session: bool = False,
    use_litellm: bool = False,
    provider_url: Optional[str] = None
) -> None:
    """Start an interactive Songbird session with AI and tools."""
    show_banner()

    # Initialize optimized session manager
    session_manager = OptimizedSessionManager(working_directory=os.getcwd())
    session = None

    # Variables to track provider config
    restored_provider = None
    restored_model = None

    # Handle session continuation/resumption
    if continue_session:
        session = session_manager.get_latest_session()
        if session:
            # IMPORTANT: get_latest_session returns a session with None messages
            # We need to load the full session
            session = session_manager.load_session(session.id)
            
            console.print(
                f"\n[cornflower_blue]Continuing session from {format_time_ago(session.updated_at)}[/cornflower_blue]")
            console.print(f"Summary: {session.summary}", style="dim")

            # Restore provider configuration from session
            if session.provider_config:
                restored_provider = session.provider_config.get("provider")
                restored_model = session.provider_config.get("model")
                # Check if session was using LiteLLM
                if session.is_litellm_session():
                    use_litellm = True
                    console.print(f"[dim]Restored LiteLLM session: {restored_provider} - {restored_model}[/dim]")
                elif restored_provider and restored_model:
                    console.print(
                        f"[dim]Restored: {restored_provider} - {restored_model}[/dim]")

            # Replay the conversation
            replay_conversation(session)
            console.print("\n[dim]--- Session resumed ---[/dim]\n")
        else:
            console.print(
                "\n[yellow]No previous session found. Starting new session.[/yellow]")

    elif resume_session:
        sessions = session_manager.list_sessions()
        if sessions:
            selected_session = display_session_selector(sessions, session_manager)
            if selected_session:
                session = session_manager.load_session(selected_session.id)
                if session:
                    console.print(
                        f"\n[cornflower_blue]Resuming session from {format_time_ago(session.updated_at)}[/cornflower_blue]")
                    console.print(f"Summary: {session.summary}", style="dim")

                    # Restore provider configuration from session
                    if session.provider_config:
                        restored_provider = session.provider_config.get(
                            "provider")
                        restored_model = session.provider_config.get("model")
                        # Check if session was using LiteLLM
                        if session.is_litellm_session():
                            use_litellm = True
                            console.print(f"[dim]Restored LiteLLM session: {restored_provider} - {restored_model}[/dim]")
                        elif restored_provider and restored_model:
                            console.print(
                                f"[dim]Restored: {restored_provider} - {restored_model}[/dim]")

                    # Replay the conversation
                    replay_conversation(session)
                    console.print("\n[dim]--- Session resumed ---[/dim]\n")
            else:
                # User selected "Start new session"
                console.print(
                    "\n[cornflower_blue]Starting new session[/cornflower_blue]")
        else:
            console.print(
                "\n[cornflower_blue]No previous sessions found. Starting new session.[/cornflower_blue]")

    # Create new session if not continuing/resuming
    if not session:
        session = session_manager.create_session()
        console.print(
            "\nWelcome to Songbird - Your AI coding companion!", style="cornflower_blue")

    console.print(
        "Available tools: file_search, file_read, file_create, file_edit, shell_exec, todo_read, todo_write, glob, grep, ls, multi_edit", style="dim")
    console.print(
        "I can search files, manage todos, run shell commands, and perform multi-file operations with full task management.", style="dim")
    console.print(
        "Type [spring_green1]'/'[/spring_green1] for commands, or [spring_green1]'exit'[/spring_green1] to quit.\n", style="dim")

    
    # Create history manager (will be passed to input handler after orchestrator is created)
    history_manager = MessageHistoryManager(session_manager)
    
    # Create command registry and load all commands
    command_registry = load_all_commands()
    command_input_handler = CommandInputHandler(command_registry, console, history_manager)

    # Determine provider and model
    # Use restored values if available, otherwise use defaults
    provider_name = restored_provider or provider or get_default_provider_name()

    # Set default models based on provider
    default_models = {
        "openai": "gpt-4o",
        "claude": "claude-3-5-sonnet-20241022",
        "gemini": "gemini-2.0-flash-001",
        "ollama": "qwen2.5-coder:7b",
        "openrouter": "deepseek/deepseek-chat-v3-0324:free"
    }
    model_name = restored_model or default_models.get(
        provider_name, default_models.get("ollama"))

    # Save initial provider config to session (if we have a session)
    if session:
        session.update_provider_config(provider_name, model_name)
        session_manager.save_session(session)

    # Show LiteLLM usage status
    if use_litellm:
        console.print(
            f"Using LiteLLM provider: {provider_name}, model: {model_name}", style="cornflower_blue")
    else:
        console.print(
            f"Using provider: {provider_name}, model: {model_name}", style="dim")

    # Initialize LLM provider and conversation orchestrator
    try:
        if use_litellm:
            # Use LiteLLM unified provider
            from .llm.providers import get_litellm_provider
            console.print(f"[cornflower_blue]Using LiteLLM unified interface for {provider_name}[/cornflower_blue]")
            
            provider_instance = get_litellm_provider(
                provider_name=provider_name,
                model=model_name,
                api_base=provider_url,
                # Add session metadata tracking
                session_metadata=session.provider_config if session else None
            )
            
            # Update session with LiteLLM configuration if we have a session
            if session:
                session.update_litellm_config(
                    provider=provider_name,
                    model=model_name,
                    litellm_model=provider_instance.model,
                    api_base=provider_url
                )
                session_manager.save_session(session)
        else:
            # Since legacy providers have been removed, get_provider now returns LiteLLM providers
            console.print(f"[cornflower_blue]Using LiteLLM unified interface for {provider_name}[/cornflower_blue]")
            provider_instance = get_provider(provider_name)
            
            # Update session with LiteLLM configuration if we have a session
            if session:
                session.update_litellm_config(
                    provider=provider_name,
                    model=model_name,
                    litellm_model=provider_instance.model,
                    api_base=provider_url
                )
                session_manager.save_session(session)

        # Create UI layer
        from .ui.ui_layer import UILayer
        ui_layer = UILayer(console=console)
        
        # Create orchestrator with session and UI
        orchestrator = SongbirdOrchestrator(
            provider_instance, os.getcwd(), session=session, ui_layer=ui_layer)

        # Start chat loop
        asyncio.run(_chat_loop(orchestrator, command_registry, command_input_handler,
                               provider_name, provider_instance))

    except Exception as e:
        console.print(f"Error starting Songbird: {e}", style="red")
        
        # Provide helpful troubleshooting information based on provider and mode
        provider_mode = "LiteLLM" if use_litellm else "Legacy"
        console.print(f"[dim]Provider mode: {provider_mode}[/dim]")
        
        if use_litellm:
            # LiteLLM-specific guidance
            console.print("\n[bold yellow]LiteLLM Troubleshooting:[/bold yellow]")
            console.print("• Check the LiteLLM adapter initialization above for specific error details", style="dim")
            console.print("• Verify your model string follows LiteLLM format: 'provider/model'", style="dim")
            console.print("• Try running without --litellm flag to use legacy provider as fallback", style="dim")
            
            if provider_url:
                console.print(f"• Custom API base URL in use: {provider_url}", style="dim")
                console.print("• Verify the custom API endpoint is accessible and correct", style="dim")
            
        # Common provider guidance (works for both LiteLLM and legacy)
        if provider_name == "openai":
            console.print(
                "\n[bold]OpenAI Setup:[/bold] Set OPENAI_API_KEY environment variable", style="dim")
            console.print(
                "Get your API key from: https://platform.openai.com/api-keys", style="dim")
        elif provider_name == "claude":
            console.print(
                "\n[bold]Claude Setup:[/bold] Set ANTHROPIC_API_KEY environment variable", style="dim")
            console.print(
                "Get your API key from: https://console.anthropic.com/account/keys", style="dim")
        elif provider_name == "gemini":
            console.print(
                "\n[bold]Gemini Setup:[/bold] Set GOOGLE_API_KEY environment variable", style="dim")
            console.print(
                "Get your API key from: https://aistudio.google.com/app/apikey", style="dim")
        elif provider_name == "openrouter":
            console.print(
                "\n[bold]OpenRouter Setup:[/bold] Set OPENROUTER_API_KEY environment variable", style="dim")
            console.print(
                "Get your API key from: https://openrouter.ai/keys", style="dim")
        elif provider_name == "ollama":
            console.print(
                "\n[bold]Ollama Setup:[/bold] Make sure Ollama is running: ollama serve", style="dim")
            console.print(
                f"And the model is available: ollama pull {model_name}", style="dim")
        
        # Additional LiteLLM guidance
        if use_litellm:
            console.print("\n[bold]LiteLLM Resources:[/bold]", style="dim")
            console.print("• LiteLLM Documentation: https://docs.litellm.ai/", style="dim")
            console.print("• Supported Providers: https://docs.litellm.ai/docs/providers", style="dim")
            console.print("• Model Formats: https://docs.litellm.ai/docs/completion/supported", style="dim")


# Updated _chat_loop function for cli.py

async def _chat_loop(orchestrator: SongbirdOrchestrator, command_registry,
                     command_input_handler, provider_name: str, provider_instance):
    """Run the interactive chat loop with improved status handling."""
    
    while True:
        try:
            # Get user input using command input handler (keeps prompt-toolkit history)
            user_input = await command_input_handler.get_input_with_commands("You")
            
            if user_input.lower() in ["exit", "quit", "bye"]:
                console.print("\nGoodbye!", style="bold blue")
                break
                
            if not user_input.strip():
                continue
                
            # Handle commands
            if is_command_input(user_input):
                command_name, args = parse_command_input(user_input)
                command = command_registry.get_command(command_name)

                if command:
                    # Prepare command context with current model
                    context = {
                        "provider": provider_name,
                        "model": provider_instance.model,  # Always use current model
                        "provider_instance": provider_instance,
                        "orchestrator": orchestrator
                    }

                    # Execute command
                    result = await command.execute(args, context)

                    if result.message:
                        if result.success:
                            console.print(f"[green]{result.message}[/green]")
                        else:
                            console.print(f"[red]{result.message}[/red]")

                    # Handle special command results
                    if result.data:
                        if "action" in result.data and result.data["action"] == "clear_history":
                            # Clear conversation history
                            orchestrator.conversation_history = []
                            if orchestrator.session:
                                orchestrator.session.messages = []
                                orchestrator.session_manager.save_session(
                                    orchestrator.session)
                            # Invalidate history cache since we cleared messages
                            command_input_handler.invalidate_history_cache()
                        
                        if result.data.get("new_model"):
                            # Model was changed, update display and save to session
                            new_model = result.data["new_model"]

                            # Determine if we're using LiteLLM
                            is_litellm_provider = hasattr(provider_instance, 'vendor_prefix') and hasattr(provider_instance, 'model_name')
                            
                            # Update session with appropriate provider config
                            if orchestrator.session:
                                if is_litellm_provider:
                                    # For LiteLLM, update with LiteLLM-specific config
                                    orchestrator.session.update_litellm_config(
                                        provider=provider_name,
                                        model=new_model,
                                        litellm_model=provider_instance.model,  # The resolved LiteLLM model string
                                        api_base=getattr(provider_instance, 'api_base', None)
                                    )
                                    console.print(f"[dim]🔄 LiteLLM model changed: {provider_name} - {new_model} -> {provider_instance.model}[/dim]")
                                else:
                                    # For legacy providers, use legacy config
                                    orchestrator.session.update_provider_config(
                                        provider_name, new_model, provider_type="legacy")
                                    console.print(f"[dim]🔄 Legacy model changed: {provider_name} - {new_model}[/dim]")
                                
                                # Always save session when model changes
                                orchestrator.session_manager.save_session(orchestrator.session)
                                
                                # Add synthetic context message to conversation for model change
                                from .memory.models import Message
                                context_msg = Message(
                                    role="system",
                                    content=f"🔄 Model switched to {new_model} via /model command"
                                )
                                orchestrator.session.add_message(context_msg)

                            # Show the model change
                            model_display = f"{provider_name} - {new_model}"
                            if is_litellm_provider:
                                model_display += f" (LiteLLM: {provider_instance.model})"
                            console.print(f"[dim]Now using: {model_display}[/dim]")

                    continue
                else:
                    console.print(
                        f"[red]Unknown command: /{command_name}[/red]")
                    console.print(
                        "Type [green]/help[/green] to see available commands.")
                    continue
            
            # Process with LLM
            global _in_status
            _in_status = True
            
            # Create and manage status properly
            status = Status(
                "[dim]Songbird (thinking…)[/dim]",
                console=console,
                spinner="dots",
                spinner_style="cornflower_blue"
            )
            
            response = None
            try:
                status.start()
                response = await orchestrator.chat(user_input, status=status)
            finally:
                # Always stop status
                status.stop()
                _in_status = False
                # Small delay for clean output
                await asyncio.sleep(0.05)
            
            # Display response with markdown formatting
            if response:
                render_ai_response(response)
                
            # Invalidate history cache
            command_input_handler.invalidate_history_cache()
                
        except KeyboardInterrupt:
            console.print("\nGoodbye!", style="bold blue")
            break
        except Exception as e:
            # Use enhanced error display
            suggestions = [
                "Check your internet connection if using cloud providers",
                "Verify API keys are correctly set in environment variables", 
                "Try switching to a different provider with /model command",
                "Report persistent issues at https://github.com/Spandan7724/songbird/issues"
            ]
            enhanced_cli.display_error_with_suggestions(e, suggestions)
    
    # Clean up resources when exiting chat loop
    try:
        if hasattr(provider_instance, 'cleanup'):
            await provider_instance.cleanup()
    except Exception as cleanup_error:
        # Don't let cleanup errors affect normal exit
        pass  # Silently ignore cleanup errors




@app.command()
def version() -> None:
    """Show Songbird version information."""
    show_banner()
    console.print(f"\nSongbird v{__version__}", style="bold cyan")
    console.print("Terminal-first AI coding companion", style="dim")


@app.command()
def help() -> None:
    """Show comprehensive help information."""
    display_enhanced_help(console)


@app.command()
def status() -> None:
    """Show system status and provider information."""
    enhanced_cli.display_startup_banner()


@app.command()
def performance(
    enable: bool = typer.Option(False, "--enable", help="Enable performance monitoring"),
    report: bool = typer.Option(False, "--report", help="Show performance report"),
    clear: bool = typer.Option(False, "--clear", help="Clear performance data")
) -> None:
    """Performance monitoring and optimization commands."""
    from .performance import enable_profiling, disable_profiling, get_profiler, clear_profiling, OptimizationSuggestions
    
    if enable:
        enable_profiling()
        enhanced_cli.display_success_message("Performance monitoring enabled")
        return
    
    if clear:
        clear_profiling()
        enhanced_cli.display_success_message("Performance data cleared")
        return
    
    if report:
        profiler = get_profiler()
        report = profiler.generate_report()
        
        if report.operations_count == 0:
            console.print("[yellow]No performance data available. Enable monitoring with --enable first.[/yellow]")
            return
        
        # Display performance report
        console.print("\n[bold]Performance Report:[/bold]")
        console.print(f"Operations: {report.operations_count}")
        console.print(f"Total time: {report.total_duration:.2f}s")
        console.print(f"Average time: {report.avg_duration:.3f}s")
        console.print(f"Memory peak: {report.memory_peak:.1f}MB")
        
        # Show slowest operations
        slowest = report.get_slowest_operations(3)
        if slowest:
            console.print("\n[bold]Slowest Operations:[/bold]")
            for i, op in enumerate(slowest, 1):
                console.print(f"{i}. {op.operation}: {op.duration:.3f}s")
        
        # Show optimization suggestions
        suggestions = OptimizationSuggestions.analyze_report(report)
        if suggestions:
            console.print("\n[bold]Optimization Suggestions:[/bold]")
            for suggestion in suggestions[:5]:
                console.print(f"💡 {suggestion}")
        
        return
    
    # Default: show performance status
    profiler = get_profiler()
    if profiler.enabled:
        console.print("[green]Performance monitoring is enabled[/green]")
        report = profiler.generate_report()
        if report.operations_count > 0:
            console.print(f"Current session: {report.operations_count} operations, {report.total_duration:.2f}s total")
    else:
        console.print("[yellow]Performance monitoring is disabled[/yellow]")
        console.print("Use 'songbird performance --enable' to start monitoring")


if __name__ == "__main__":
    # Running file directly: python -m songbird.cli
    app()
