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
from .llm.providers import get_provider, get_default_provider
from .conversation import ConversationOrchestrator
from .memory.manager import SessionManager
from .memory.models import Session
from .commands import CommandInputHandler, get_command_registry
from .memory.history_manager import MessageHistoryManager
from .commands.loader import is_command_input, parse_command_input, load_all_commands

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


def display_session_selector(sessions: list[Session]) -> Optional[Session]:
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
        msg_count = len(session.messages)
        summary = (session.summary or "Empty session")[:50]
        if len(session.summary or "") > 50:
            summary += "..."
        
        option = f"{modified} | {created} | {msg_count} msgs | {summary}"
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
        False, "--resume", "-r", help="Resume a previous session from a list")
):
    """
    Songbird - Terminal-first AI coding companion
    
    Run 'songbird' to start an interactive chat session with AI and tools.
    Run 'songbird --continue' to continue your latest session.
    Run 'songbird --resume' to select and resume a previous session.
    Run 'songbird version' to show version information.
    """
    if list_providers:
        from .llm.providers import get_provider_info
        
        provider_info = get_provider_info()
        default = get_default_provider()
        
        console.print("Available LLM Providers:", style="bold cornflower_blue")
        console.print()
        
        for provider_name, info in provider_info.items():
            status_text = ""
            if provider_name == default:
                status_text = " [bright_green](default)[/bright_green]"
            elif not info["available"]:
                status_text = " [red](unavailable)[/red]"
            
            console.print(f"[bold]{provider_name}[/bold]{status_text}")
            console.print(f"  Description: {info['description']}")
            
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
             continue_session=continue_session, resume_session=resume_session)


@app.command(hidden=True)
def chat(
    provider: Optional[str] = None,
    continue_session: bool = False,
    resume_session: bool = False
) -> None:
    """Start an interactive Songbird session with AI and tools."""
    show_banner()

    # Initialize session manager
    session_manager = SessionManager(os.getcwd())
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
                if restored_provider and restored_model:
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
            selected_session = display_session_selector(sessions)
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
                        if restored_provider and restored_model:
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
    provider_name = restored_provider or provider or get_default_provider()

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

    console.print(
        f"Using provider: {provider_name}, model: {model_name}", style="dim")

    # Initialize LLM provider and conversation orchestrator
    try:
        provider_class = get_provider(provider_name)

        # Initialize provider based on type
        if provider_name == "ollama":
            provider_instance = provider_class(
                base_url="http://127.0.0.1:11434",
                model=model_name
            )
        else:
            # For all other providers (openai, claude, gemini, openrouter), just pass the model
            provider_instance = provider_class(model=model_name)

        # Create orchestrator with session
        orchestrator = ConversationOrchestrator(
            provider_instance, os.getcwd(), session=session)

        # Start chat loop
        asyncio.run(_chat_loop(orchestrator, command_registry, command_input_handler,
                               provider_name, provider_instance))

    except Exception as e:
        console.print(f"Error starting Songbird: {e}", style="red")
        
        # Provide helpful troubleshooting information based on provider
        if provider_name == "openai":
            console.print(
                "Make sure you have set OPENAI_API_KEY environment variable", style="dim")
            console.print(
                "Get your API key from: https://platform.openai.com/api-keys", style="dim")
        elif provider_name == "claude":
            console.print(
                "Make sure you have set ANTHROPIC_API_KEY environment variable", style="dim")
            console.print(
                "Get your API key from: https://console.anthropic.com/account/keys", style="dim")
        elif provider_name == "gemini":
            console.print(
                "Make sure you have set GOOGLE_API_KEY environment variable", style="dim")
            console.print(
                "Get your API key from: https://aistudio.google.com/app/apikey", style="dim")
        elif provider_name == "openrouter":
            console.print(
                "Make sure you have set OPENROUTER_API_KEY environment variable", style="dim")
            console.print(
                "Get your API key from: https://openrouter.ai/keys", style="dim")
        elif provider_name == "ollama":
            console.print(
                "Make sure Ollama is running: ollama serve", style="dim")
            console.print(
                f"And the model is available: ollama pull {model_name}", style="dim")


# Updated _chat_loop function for cli.py

async def _chat_loop(orchestrator: ConversationOrchestrator, command_registry,
                     command_input_handler, provider_name: str, provider_instance):
    """Run the interactive chat loop with improved status handling."""
    
    while True:
        try:
            # Get user input
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

                            # Update session with new provider config
                            if orchestrator.session:
                                orchestrator.session.update_provider_config(
                                    provider_name, new_model)
                                # Always save session when model changes
                                orchestrator.session_manager.save_session(
                                    orchestrator.session)

                            # Show the model change
                            console.print(
                                f"[dim]Now using: {provider_name} - {new_model}[/dim]")

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
            console.print(f"\nError: {e}", style="red")




@app.command()
def version() -> None:
    """Show Songbird version information."""
    show_banner()
    console.print(f"\nSongbird v{__version__}", style="bold cyan")
    console.print("Terminal-first AI coding companion", style="dim")


if __name__ == "__main__":
    # Running file directly: python -m songbird.cli
    app()
