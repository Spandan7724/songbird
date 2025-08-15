import sys
from rich.console import Console
from InquirerPy import inquirer


async def safe_interactive_menu(prompt: str, options: list[str], default_index: int = 0) -> int | None:
    try:
        # Check if we're in an interactive terminal
        if not sys.stdin.isatty() or not sys.stdout.isatty():
            # Non-interactive environment - auto-select default
            console = Console()
            console.print(f"\n{prompt}")
            for i, option in enumerate(options):
                marker = "▶ " if i == default_index else "  "
                console.print(f"{marker}{option}")
            console.print(f"[dim]Auto-selected: {options[default_index]}[/dim]")
            return default_index
        
        # Try the async InquirerPy API first
        return await async_interactive_menu(prompt, options, default_index)
    except KeyboardInterrupt:
        print("\nOperation cancelled by user.")
        return None

async def async_interactive_menu(prompt: str, options: list[str], default_index: int = 0) -> int:
    try:
        result = await inquirer.select(
            message=prompt,
            choices=options,
            default=options[default_index] if default_index < len(options) else options[0]
        ).execute_async()
        
        return options.index(result)
    except Exception:
        # Fall back to sync version if async fails
        return sync_interactive_menu(prompt, options, default_index)

def sync_interactive_menu(prompt: str, options: list[str], default_index: int = 0) -> int:
    try:
        result = inquirer.select(
            message=prompt,
            choices=options,
            default=options[default_index] if default_index < len(options) else options[0]
        ).execute()
        
        return options.index(result)
    except Exception:
        # Ultimate fallback to numbered menu
        return fallback_numbered_menu(prompt, options, default_index)

def fallback_numbered_menu(prompt: str, options: list[str], default_index: int = 0) -> int:
    console = Console()
    
    # Show terminal compatibility message
    if not sys.stdin.isatty():
        console.print(f"\n{prompt}")
        for i, option in enumerate(options):
            style = "bold green" if i == default_index else "white"
            console.print(f"  {i + 1}. {option}", style=style)
        console.print(f"[dim]Auto-selected: {options[default_index]}[/dim]")
        return default_index
    
    try:
        console.print(f"\n{prompt}")
        for i, option in enumerate(options):
            style = "bold green" if i == default_index else "white"
            console.print(f"  {i + 1}. {option}", style=style)
        
        console.print(f"\n[dim]Enter number (1-{len(options)}) or press Enter for default [{default_index + 1}]:[/dim]")
        
        response = input().strip()
        
        if not response:
            return default_index
        
        choice = int(response) - 1
        if 0 <= choice < len(options):
            return choice
        else:
            console.print("[red]Invalid choice. Using default.[/red]")
            return default_index
    except (ValueError, KeyboardInterrupt):
        console.print("[red]Invalid input. Using default.[/red]")
        return default_index
    except Exception:
        # Fall back to numbered menu
        return fallback_numbered_menu(prompt, options, default_index)


def interactive_menu(prompt: str, options: list[str], default_index: int = 0) -> int:
    return sync_interactive_menu(prompt, options, default_index)


