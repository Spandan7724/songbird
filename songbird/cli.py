from __future__ import annotations

# Apply event loop cleanup patches early to prevent BaseEventLoop.__del__ errors
from .core.loop_cleanup_patch import apply_event_loop_cleanup_patch
apply_event_loop_cleanup_patch()

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
from rich.markdown import Markdown
from .llm.providers import get_default_provider_name, get_provider_info
from .orchestrator import SongbirdOrchestrator
from .memory.optimized_manager import OptimizedSessionManager
from .memory.models import Session
from .commands import CommandInputHandler
from .memory.history_manager import MessageHistoryManager
from .commands.loader import is_command_input, parse_command_input, load_all_commands, is_bash_mode_input, parse_bash_input
from .tools.shell_exec import shell_exec_safe
from .cli_utils import (enhanced_cli, display_enhanced_help)

app = typer.Typer(add_completion=False, rich_markup_mode="rich",
                  help="Songbird - Terminal-based AI coding companion", no_args_is_help=False)
console = Console()


def render_ai_response(content: str, speaker_name: str = "Songbird"):
    """
    Render AI response content as markdown with proper formatting.
    """
    if not content or not content.strip():
        return

    lines = content.split('\n')
    cleaned_lines = []
    
    for line in lines:
        if line.strip().startswith('#'):
            header_text = line.lstrip('#').strip()
            if header_text:
                cleaned_lines.append(f"**{header_text}**")
            else:
                cleaned_lines.append("")
        else:
            cleaned_lines.append(line)
    
    cleaned_content = '\n'.join(cleaned_lines)

    md_renderable = Markdown(cleaned_content, code_theme="github-dark")
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
    if _cleanup_timer:
        _cleanup_timer.cancel()
    
    if _in_status:
        return
    
    sys.stdout.write("\033[s") 
    sys.stdout.write("\033[A")  
    sys.stdout.write("\r\033[2K") 
    sys.stdout.write("\033[90mPress Ctrl+C again to exit\033[0m")  
    sys.stdout.write("\033[u") 
    sys.stdout.flush()
    
    def _clear():
        if not _in_status:
            sys.stdout.write("\033[s") 
            sys.stdout.write("\033[A")  
            sys.stdout.write("\r\033[2K")  
            sys.stdout.write("\033[u") 
            sys.stdout.flush()
        
    _cleanup_timer = Timer(_GRACE, _clear)
    _cleanup_timer.start()

def _sigint(signum, frame):
    global _last, _cleanup_timer
    now = time.monotonic()

    if _last and (now - _last) < _GRACE:        
        if _cleanup_timer:
            _cleanup_timer.cancel()
        signal.signal(signal.SIGINT, signal.default_int_handler)
        
        if _in_status:
            console.print("\n[red]Interrupted![/red]")
        else:
            sys.stdout.write("\033[A\r\033[2K\033[B") 
        
        print()  
        raise KeyboardInterrupt

    if _in_status:
        console.print("\n[dim]Press Ctrl+C again to exit[/dim]")
    else:
        sys.stdout.write("\b\b  \b\b")  
        sys.stdout.flush()
        _flash_notice()
    
    _last = now  


signal.signal(signal.SIGINT, _sigint)

def show_banner():
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

    sessions.sort(key=lambda s: s.updated_at, reverse=True)
    max_sessions = min(30, console.height - 10 if console.height > 10 else 20)
    display_sessions = sessions[:max_sessions]
    
    options = []
    for session in display_sessions:
        created = format_time_ago(session.created_at)
        modified = format_time_ago(session.updated_at)
        
        user_msg_count, last_user_msg = _get_session_display_info(session_manager, session.id)

        if last_user_msg:
            summary = last_user_msg[:35]  
            if len(last_user_msg) > 35:
                summary += "..."
        else:
            summary = "Empty session"
        
        provider_info = ""
        if session.provider_config:
            provider = session.provider_config.get("provider", "unknown")
            provider_info = f"[{provider}]"
        else:
            provider_info = "[unknown]"
        
        option = f"{modified} | {created} | {user_msg_count} msgs | {provider_info} | {summary}"
        options.append(option)
    
    options.append("Start new session")
    
    if len(sessions) > max_sessions:
        console.print(f"[yellow]Showing {max_sessions} most recent sessions out of {len(sessions)} total[/yellow]\n")
    
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
    from .tools.file_operations import display_diff_preview

    i = 0
    while i < len(session.messages):
        msg = session.messages[i]

        if msg.role == "system":
            i += 1
            continue

        elif msg.role == "user":
            console.print(f"\n[bold cyan]You[/bold cyan]: {msg.content}")
            i += 1

        elif msg.role == "assistant":
            if msg.tool_calls:
                tool_result_idx = i + 1

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
                        
                        # Use Rich syntax highlighting for proper restoration
                        from rich.syntax import Syntax
                        from rich.panel import Panel
                        from pathlib import Path
                        
                        # Get lexer from file extension
                        path = Path(file_path)
                        try:
                            # Lexer mapping for file extensions
                            lexer_map = {
                                '.py': 'python', 
                                '.js': 'javascript', 
                                '.ts': 'typescript',
                                '.html': 'html', 
                                '.css': 'css', 
                                '.json': 'json',
                                '.yaml': 'yaml', 
                                '.yml': 'yaml', 
                                '.md': 'markdown',
                                '.sh': 'bash', 
                                '.c': 'c', 
                                '.cpp': 'cpp', 
                                '.java': 'java'
                            }
                            
                            lexer = lexer_map.get(path.suffix, 'text')
                        except:
                            lexer = 'text'
                        
                        # Create syntax highlighted content
                        syntax = Syntax(
                            content,
                            lexer=lexer,
                            theme="github-dark",
                            line_numbers=True,
                            word_wrap=False
                        )
                        
                        # Create panel to match live session formatting
                        panel = Panel(
                            syntax,
                            title=f"New file: {path.name}",
                            title_align="left",
                            border_style="green",
                            expand=False,
                            width=min(console.width - 2, 120)
                        )
                        
                        console.print("")
                        console.print(panel)
                        console.print("")

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



async def interactive_set_default():
    """Interactive menu for setting default provider and model."""
    from .commands.model_command import ModelCommand
    from .conversation import safe_interactive_menu
    
    # Get available providers (disable discovery to avoid event loop issues, use quiet mode)
    provider_info = get_provider_info(use_discovery=False, quiet=True)
    available_providers = [name for name, info in provider_info.items() if info["ready"]]
    
    if not available_providers:
        console.print("[red]No providers are ready (missing API keys or services not running)[/red]")
        console.print("[yellow]Configure providers first:[/yellow]")
        console.print("  export OPENAI_API_KEY='...'")
        console.print("  export ANTHROPIC_API_KEY='...'") 
        console.print("  export GEMINI_API_KEY='...'")
        console.print("  ollama serve  # For local models")
        return
    
    # Provider selection
    console.print("\n[bold cornflower_blue]Select Default Provider:[/bold cornflower_blue]")
    provider_options = available_providers + ["Cancel"]
    
    provider_idx = await safe_interactive_menu(
        "Choose default provider:", 
        provider_options,
        default_index=0
    )
    
    if provider_idx is None or provider_idx == len(available_providers):
        console.print("[white dim]Default setting cancelled[/white dim]")
        return
    
    selected_provider = available_providers[provider_idx]
    
    # Model selection for the chosen provider
    console.print(f"\n[bold cornflower_blue]Select Default Model for {selected_provider}:[/bold cornflower_blue]")
    
    # Get models for this provider (use same method as /model command for consistency)
    try:
        model_cmd = ModelCommand()
        if selected_provider == "copilot":
            models = await model_cmd._get_copilot_models()
        else:
            models = await model_cmd._get_litellm_models(selected_provider)
    except Exception as e:
        console.print(f"[yellow]Could not get models for {selected_provider}: {e}[/yellow]")
        # Use provider's default model
        await set_default_provider_and_model(selected_provider, None)
        return
    
    if not models:
        console.print(f"[yellow]No models available for {selected_provider}[/yellow]")
        await set_default_provider_and_model(selected_provider, None)
        return
    
    # Add cancel option
    model_options = models + ["Cancel"]
    
    model_idx = await safe_interactive_menu(
        f"Choose default model for {selected_provider}:",
        model_options,
        default_index=0
    )
    
    if model_idx is None or model_idx == len(models):
        console.print("[white dim]Model selection cancelled[/white dim]")
        return
    
    selected_model = models[model_idx]
    await set_default_provider_and_model(selected_provider, selected_model)


async def set_default_provider_and_model(provider_name: str, model_name: Optional[str] = None):
    """Set the default provider and optionally model in configuration."""
    from .config.config_manager import get_config_manager
    from .commands.model_command import ModelCommand
    
    # Validate provider
    valid_providers = ["openai", "claude", "gemini", "ollama", "openrouter", "copilot"]
    if provider_name not in valid_providers:
        console.print(f"[red]Error: Invalid provider '{provider_name}'[/red]")
        console.print(f"[yellow]Valid providers: {', '.join(valid_providers)}[/yellow]")
        return
    
    # Check if provider has prerequisites
    model_cmd = ModelCommand()
    is_ready, error_msg = model_cmd._check_provider_prerequisites(provider_name)
    if not is_ready:
        console.print(f"[red]Error: Provider '{provider_name}' is not ready[/red]")
        console.print(f"[yellow]{error_msg}[/yellow]")
        return
    
    # Get configuration manager
    config_manager = get_config_manager()
    config = config_manager.get_config()
    
    # If no model specified, use provider's current default
    if model_name is None:
        model_name = config.llm.default_models.get(provider_name)
        if not model_name:
            # Use hardcoded defaults as fallback
            fallback_models = {
                "openai": "gpt-4o",
                "claude": "claude-3-5-sonnet-20241022",
                "gemini": "gemini-2.0-flash",
                "ollama": "qwen2.5-coder:7b",
                "openrouter": "deepseek/deepseek-chat-v3-0324:free",
                "copilot": "gpt-4o"
            }
            model_name = fallback_models.get(provider_name, "")
    
    # Validate model for the provider (optional - just warn if invalid)
    try:
        if provider_name == "copilot":
            available_models = await model_cmd._get_copilot_models()
        else:
            available_models = await model_cmd._get_litellm_models(provider_name)
        
        if model_name and available_models and model_name not in available_models:
            console.print(f"[yellow]Warning: Model '{model_name}' may not be available for {provider_name}[/yellow]")
            console.print(f"[yellow]Available models: {', '.join(available_models[:5])}{'...' if len(available_models) > 5 else ''}[/yellow]")
            
            # Ask for confirmation
            response = input("Continue anyway? (y/N): ").strip().lower()
            if response not in ['y', 'yes']:
                console.print("[white dim]Default setting cancelled[/white dim]")
                return
    except Exception as e:
        # Non-critical - model validation failed, but continue anyway
        console.print(f"[dim]Could not validate model availability: {e}[/dim]")
    
    # Update configuration
    config.llm.default_provider = provider_name
    if model_name:
        config.llm.default_models[provider_name] = model_name
    
    # Save configuration
    config_manager.save_config(config)
    
    # Show confirmation
    console.print(f"[green]✓ Default provider set to:[/green] [bold]{provider_name}[/bold]")
    if model_name:
        console.print(f"[green]✓ Default model for {provider_name} set to:[/green] [bold]{model_name}[/bold]")
    
    console.print(f"\n[dim]Configuration saved to: {config_manager.config_file}[/dim]")
    console.print("[dim]Use 'songbird' without --provider to use these defaults[/dim]")


async def execute_print_mode(message: str, provider: Optional[str] = None, provider_url: Optional[str] = None, ultra_quiet: bool = False):
    try:
        # Determine provider
        provider_name = provider or get_default_provider_name()
        
        # Get default model from configuration
        model_name = None
        try:
            from .config.config_manager import get_config_manager
            config_manager = get_config_manager()
            config = config_manager.get_config()
            model_name = config.llm.default_models.get(provider_name)
        except Exception:
            pass
        
        if not model_name:
            # Fallback to hardcoded defaults
            fallback_models = {
                "openai": "gpt-4o",
                "claude": "claude-3-5-sonnet-20241022",
                "gemini": "gemini-2.0-flash",
                "ollama": "qwen2.5-coder:7b",   
                "openrouter": "deepseek/deepseek-chat-v3-0324:free",
                "copilot": "gpt-4o"
            }
            model_name = fallback_models.get(provider_name, fallback_models.get("ollama"))
        
        # Create provider instance with quiet mode
        if provider_name == "copilot":
            from .llm.providers import get_copilot_provider
            provider_instance = get_copilot_provider(model=model_name, quiet=True)
        else:
            # Use LiteLLM for all other providers
            from .llm.providers import get_litellm_provider
            provider_instance = get_litellm_provider(
                provider_name=provider_name,
                model=model_name,
                api_base=provider_url,
                session_metadata=None
            )

        orchestrator = SongbirdOrchestrator(
            provider=provider_instance,
            working_directory=os.getcwd(),
            session=None, 
            ui_layer=None, 
            quiet_mode=True  
        )
        
        if ultra_quiet:
            import sys
            import io
            from contextlib import redirect_stdout, redirect_stderr
            
            captured_output = io.StringIO()
            with redirect_stdout(captured_output), redirect_stderr(captured_output):
                response = await orchestrator.chat_single_message(message)
            
          
            if response and response.strip():
                print(response)
        else:
            
            response = await orchestrator.chat_single_message(message)
           
        
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)



@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    provider: Optional[str] = typer.Option(
        None, "--provider", help="LLM provider to use (openai, claude, gemini, ollama, openrouter)"),
    list_providers: bool = typer.Option(
        False, "--list-providers", help="List available providers and exit"),
    continue_session: bool = typer.Option(
        False, "--continue", "-c", help="Continue the latest session"),
    resume_session: bool = typer.Option(
        False, "--resume", "-r", help="Resume a previous session from a list"),
    provider_url: Optional[str] = typer.Option(
        None, "--provider-url", help="Custom API base URL for provider", hidden=True),
    set_default: bool = typer.Option(
        False, "--default", help="Set default provider and model interactively"),
    print_mode: Optional[str] = typer.Option(
        None, "--print", "-p", help='Print mode: execute single command and output result only. Use quotes for multi-word messages: -p "your message"'),
    quiet_mode: bool = typer.Option(
        False, "--quiet", "-q", help="Suppress tool output in print mode, show only final answer")
):
    """
    Songbird - Terminal-based AI coding companion
    
    Run 'songbird' to start an interactive chat session with AI and tools.
    Run 'songbird --continue' to continue your latest session.
    Run 'songbird --resume' to select and resume a previous session.
    Run 'songbird --default' to set your default provider and model interactively.
    Run 'songbird -p "message"' for one-off commands with clean output (use quotes for multi-word messages).
    Run 'songbird -p "message" --quiet' for ultra-clean output (final answer only).
    Run 'songbird version' to show version information.
    """
    # Validate that --quiet can only be used with --print
    if quiet_mode and not print_mode:
        console.print("[red]Error: --quiet can only be used with --print mode[/red]")
        console.print("Usage: songbird --print --quiet \"your message\"")
        raise typer.Exit(1)
    
    if set_default:
        # Handle --default flag - always interactive mode
        import asyncio
        asyncio.run(interactive_set_default())
        return
    
    if list_providers:
        provider_info = get_provider_info(use_discovery=True, quiet=False)
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

    if print_mode:
        # Handle print mode - single command execution
        import asyncio
        asyncio.run(execute_print_mode(print_mode, provider, provider_url, quiet_mode))
        return

    if ctx.invoked_subcommand is None:
        # No subcommand provided, start chat session
        chat(provider=provider,
             continue_session=continue_session, resume_session=resume_session,
             provider_url=provider_url)


@app.command()
def default(
    provider: Optional[str] = typer.Argument(None, help="Provider name (openai, claude, gemini, ollama, openrouter, copilot)"),
    model: Optional[str] = typer.Argument(None, help="Model name (optional)")
):
    """Set default provider and optionally model for new sessions."""
    if provider is None:
        # Interactive mode
        import asyncio
        asyncio.run(interactive_set_default())
    else:
        # Direct mode with provider and optional model
        import asyncio
        asyncio.run(set_default_provider_and_model(provider.lower(), model))


@app.command(hidden=True)
def chat(
    provider: Optional[str] = None,
    continue_session: bool = False,
    resume_session: bool = False,
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
                    console.print(f"[dim]Restored session: {restored_provider} - {restored_model}[/dim]")
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
                            console.print(f"[dim]Restored session: {restored_provider} - {restored_model}[/dim]")
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

    # Get default model from configuration
    model_name = restored_model
    if not model_name:
        try:
            from .config.config_manager import get_config_manager
            config_manager = get_config_manager()
            config = config_manager.get_config()
            
            # Get configured default model for this provider
            model_name = config.llm.default_models.get(provider_name)
            
            if not model_name:
                # Fallback to hardcoded defaults
                fallback_models = {
                    "openai": "gpt-4o",
                    "claude": "claude-3-5-sonnet-20241022",
                    "gemini": "gemini-2.0-flash",
                    "ollama": "qwen2.5-coder:7b",   
                    "openrouter": "deepseek/deepseek-chat-v3-0324:free",
                    "copilot": "gpt-4o"
                }
                model_name = fallback_models.get(provider_name, fallback_models.get("ollama"))
        except Exception:
            # If config loading fails, use hardcoded defaults
            fallback_models = {
                "openai": "gpt-4o",
                "claude": "claude-3-5-sonnet-20241022", 
                "gemini": "gemini-2.0-flash",
                "ollama": "qwen2.5-coder:7b",   
                "openrouter": "deepseek/deepseek-chat-v3-0324:free",
                "copilot": "gpt-4o"
            }
            model_name = fallback_models.get(provider_name, fallback_models.get("ollama"))

    # Save initial provider config to session (if we have a session)
    if session:
        session.update_provider_config(provider_name, model_name)
        session_manager.save_session(session)

    # Show provider status
    console.print(
        f"Using provider: {provider_name}, model: {model_name}", style="cornflower_blue")

    # Configure aiohttp session management for Google GenAI SDK
    try:
        from .llm.aiohttp_session_manager import configure_google_genai_aiohttp
        configure_google_genai_aiohttp()
    except Exception:
        # Non-critical error, continue without custom session configuration
        pass
    
    # Initialize LLM provider and conversation orchestrator
    try:
        # All providers now use LiteLLM except Copilot (custom provider)
        if provider_name == "copilot":
            from .llm.providers import get_copilot_provider
            provider_instance = get_copilot_provider(model=model_name)
            
            # Update session with custom provider config if we have a session
            if session:
                session.update_provider_config(provider_name, model_name, provider_type="custom")
                session_manager.save_session(session)
        else:
            # Use LiteLLM for all other providers
            from .llm.providers import get_litellm_provider
            
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

        # Create UI layer
        from .ui.ui_layer import UILayer
        ui_layer = UILayer(console=console)
        
        # Create orchestrator with session and UI
        orchestrator = SongbirdOrchestrator(
            provider_instance, os.getcwd(), session=session, ui_layer=ui_layer)

        # Start chat loop with proper event loop management
        async def managed_chat():
            try:
                
                await _chat_loop(orchestrator, command_registry, command_input_handler,
                                provider_name, provider_instance)
            finally:
                # Ensure cleanup even if chat loop exits unexpectedly
                
                try:
                    from .core.event_loop_manager import ensure_clean_shutdown
                    ensure_clean_shutdown()
                except Exception:
                    pass
        
        # Use manual event loop management to prevent BaseEventLoop.__del__ errors
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                # Register the loop for cleanup
                from .core.event_loop_manager import event_loop_manager
                event_loop_manager.register_loop(loop)
                
                # Run the managed chat
                loop.run_until_complete(managed_chat())
            finally:
                try:
                    # Proper event loop cleanup
                    pending_tasks = [task for task in asyncio.all_tasks(loop) if not task.done()]
                    if pending_tasks:
                        # Cancel pending tasks
                        for task in pending_tasks:
                            task.cancel()
                        # Wait for cancellation
                        loop.run_until_complete(asyncio.gather(*pending_tasks, return_exceptions=True))
                    
                    # Close the loop properly
                    loop.close()
                except Exception:
                    # Log cleanup error but don't crash
                    pass
        except Exception:
            # Fallback to asyncio.run if manual management fails
            asyncio.run(managed_chat())

    except Exception as e:
        console.print(f"Error starting Songbird: {e}", style="red")
        
        # Provide helpful troubleshooting information
        if provider_name == "copilot":
            console.print("\n[bold yellow]Copilot Troubleshooting:[/bold yellow]")
            console.print("• Check that COPILOT_ACCESS_TOKEN is properly configured", style="dim")
            console.print("• Verify you have access to GitHub Copilot Chat API", style="dim")
        else:
            console.print("\n[bold yellow]LiteLLM Troubleshooting:[/bold yellow]")
            console.print("• Check the LiteLLM adapter initialization above for specific error details", style="dim")
            console.print("• Verify your model string follows LiteLLM format: 'provider/model'", style="dim")
            console.print("• All providers now use LiteLLM unified interface", style="dim")
            
            if provider_url:
                console.print(f"• Custom API base URL in use: {provider_url}", style="dim")
                console.print("• Verify the custom API endpoint is accessible and correct", style="dim")
            
        # Common provider guidance
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
                "\n[bold]Gemini Setup:[/bold] Set GEMINI_API_KEY environment variable", style="dim")
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
        
        # Additional resources
        if provider_name != "copilot":
            console.print("\n[bold]LiteLLM Resources:[/bold]", style="dim")
            console.print("• LiteLLM Documentation: https://docs.litellm.ai/", style="dim")
            console.print("• Supported Providers: https://docs.litellm.ai/docs/providers", style="dim")
            console.print("• Model Formats: https://docs.litellm.ai/docs/completion/supported", style="dim")


# Updated _chat_loop function for cli.py

async def _chat_loop(orchestrator: SongbirdOrchestrator, command_registry,
                     command_input_handler, provider_name: str, provider_instance):
    """Run the interactive chat loop with improved status handling."""
    
    # Register the current event loop for proper cleanup
    try:
        from .core.event_loop_manager import register_current_loop
        register_current_loop()
    except Exception:
        # Non-critical error
        pass
    
    while True:
        try:
            # Get user input using command input handler (keeps prompt-toolkit history)
            user_input = await command_input_handler.get_input_with_commands("You")
            
            if user_input.lower() in ["exit", "quit", "bye"]:
                console.print("\nGoodbye!", style="bold blue")
                break
                
            if not user_input.strip():
                continue
            
            # Handle bash mode commands (starting with !)
            if is_bash_mode_input(user_input):
                bash_command = parse_bash_input(user_input)
                if bash_command:
                    try:
                        # Execute shell command using existing shell_exec tool
                        result = await shell_exec_safe(
                            command=bash_command,
                            working_dir=orchestrator.working_directory,
                            show_live_output=True
                        )
                            
                    except Exception as e:
                        console.print(f"[red]Error executing bash command: {e}[/red]")
                else:
                    console.print("[yellow]Empty bash command[/yellow]")
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
                            console.print(f"[cornflower_blue]{result.message}[/cornflower_blue]")
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
                            # Update session with appropriate provider config
                            if orchestrator.session:
                                if provider_name == "copilot":
                                    # Copilot uses custom provider, not LiteLLM
                                    orchestrator.session.update_provider_config(
                                        provider_name, new_model, provider_type="custom")
                                else:
                                    # All other providers use LiteLLM
                                    orchestrator.session.update_litellm_config(
                                        provider=provider_name,
                                        model=new_model,
                                        litellm_model=provider_instance.model,  # The resolved LiteLLM model string
                                        api_base=getattr(provider_instance, 'api_base', None)
                                    )
                                
                                # Always save session when model changes
                                orchestrator.session_manager.save_session(orchestrator.session)
                                
                                # Add synthetic context message to conversation for model change
                                from .memory.models import Message
                                context_msg = Message(
                                    role="system",
                                    content=f"Model switched to {new_model} via /model command"
                                )
                                orchestrator.session.add_message(context_msg)

                            # Single clean confirmation message
                            console.print(f"[cornflower_blue]Switched to model:[/cornflower_blue] {new_model}")

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
                "",
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
        # Clean up provider resources
        if hasattr(provider_instance, 'cleanup'):
            await provider_instance.cleanup()
        
        # Save session one final time
        if orchestrator.session:
            orchestrator.session_manager.save_session(orchestrator.session)
        
        # Clean up HTTP session manager
        from .llm.http_session_manager import close_managed_session
        await close_managed_session()

        # Clean up aiohttp session manager
        from .llm.aiohttp_session_manager import close_managed_aiohttp_session
        await close_managed_aiohttp_session()
        
        # Clean up event loop manager to prevent BaseEventLoop.__del__ errors
        from .core.event_loop_manager import ensure_clean_shutdown
        ensure_clean_shutdown()
        
        # Additional cleanup
        import gc
        await asyncio.sleep(0.1)  # Give time for cleanup to complete
        gc.collect()
            
    except Exception as cleanup_error:
        # Don't let cleanup errors crash the exit
        console.print(f"[dim yellow]Minor cleanup issue: {cleanup_error}[/dim yellow]")



@app.command()
def version() -> None:
    from .version import show_version
    show_version()


@app.command()
def help() -> None:
    display_enhanced_help(console)



if __name__ == "__main__":
    # Running file directly: python -m songbird.cli
    app()
