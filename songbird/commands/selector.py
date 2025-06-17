# songbird/commands/selector.py
"""
Interactive command selector with arrow navigation and filtering.
"""

import os
import sys
from typing import List, Optional, Tuple
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from .base import BaseCommand
from .registry import CommandRegistry


def getch():
    """Get a single character from stdin, cross-platform."""
    if os.name == 'nt':  # Windows
        import msvcrt
        ch1 = msvcrt.getch()
        if ch1 in (b'\x00', b'\xe0'):          # arrow / function key prefix
            ch2 = msvcrt.getch()
            if ch2 == b'H':                    # Up
                return '\x1b[A'
            elif ch2 == b'P':                  # Down
                return '\x1b[B'
            elif ch2 == b'M':                  # Right
                return '\x1b[C'
            elif ch2 == b'K':                  # Left
                return '\x1b[D'
            else:
                return ''                      # ignore other keys
        elif ch1 == b'\r':                     # Enter
            return '\r'
        elif ch1 == b'\x08':                   # Backspace
            return '\x08'
        elif ch1 == b'\x1b':                   # Escape
            return '\x1b'
        return ch1.decode('utf-8', 'ignore')
    else:  # Unix/Linux/macOS
        # Check if stdin is a TTY
        if not sys.stdin.isatty():
            return ''  # Fallback for non-TTY environments

        import tty
        import termios
        try:
            fd = sys.stdin.fileno()
            old = termios.tcgetattr(fd)
            try:
                tty.setraw(fd)
                return sys.stdin.read(1)
            finally:
                termios.tcsetattr(fd, termios.TCSADRAIN, old)
        except:
            return ''  # Fallback on any termios error


class CommandSelector:
    """Interactive command selector with filtering and navigation."""
    
    def __init__(self, registry: CommandRegistry, console: Console):
        self.registry = registry
        self.console = console
        self.max_display = 10  # Maximum commands to display at once
    
    def select_command(self, initial_filter: str = "") -> Optional[Tuple[BaseCommand, str]]:
        """
        Interactive command selection with filtering.
        Returns (command, args) tuple or None if cancelled.
        """
        # Start with all commands
        commands = self.registry.get_all_commands()
        if not commands:
            return None
        
        # Sort commands by name
        commands.sort(key=lambda c: c.name)
        
        current_filter = initial_filter
        selected_index = 0
        
        # Hide cursor
        self.console.print("\x1b[?25l", end="")
        
        try:
            while True:
                # Filter commands based on current filter
                if current_filter:
                    filtered_commands = [
                        cmd for cmd in commands 
                        if current_filter.lower() in cmd.name.lower() or 
                           current_filter.lower() in cmd.description.lower()
                    ]
                else:
                    filtered_commands = commands[:self.max_display]
                
                if not filtered_commands:
                    filtered_commands = commands[:self.max_display]
                
                # Ensure selected index is valid
                if selected_index >= len(filtered_commands):
                    selected_index = len(filtered_commands) - 1
                if selected_index < 0:
                    selected_index = 0
                
                # Clear screen and display
                self._display_commands(filtered_commands, selected_index, current_filter)
                
                # Get user input
                key = getch()
                
                if key == '\r':  # Enter - select command
                    if filtered_commands:
                        selected_cmd = filtered_commands[selected_index]
                        # Clear the display
                        self._clear_display()
                        return selected_cmd, ""
                
                elif key == '\x1b':  # Escape - cancel
                    self._clear_display()
                    return None
                
                elif key == '\x1b[A':  # Up arrow
                    if selected_index > 0:
                        selected_index -= 1
                
                elif key == '\x1b[B':  # Down arrow
                    if selected_index < len(filtered_commands) - 1:
                        selected_index += 1
                
                elif key == '\x08':  # Backspace
                    if current_filter:
                        current_filter = current_filter[:-1]
                        selected_index = 0
                
                elif key and key.isprintable():  # Regular character
                    current_filter += key
                    selected_index = 0
        
        finally:
            # Show cursor
            self.console.print("\x1b[?25h", end="")
    
    def _display_commands(self, commands: List[BaseCommand], selected_index: int, filter_text: str):
        """Display the command list with current selection."""
        # Move cursor up to overwrite previous display
        if hasattr(self, '_last_display_lines'):
            self.console.print(f"\x1b[{self._last_display_lines}A", end="")
        
        # Create display
        lines = []
        
        # Header
        header = f"Commands (/{filter_text})" if filter_text else "Commands (/)"
        lines.append(f"[bold blue]{header}[/bold blue]")
        lines.append("Use ↑↓ arrows to navigate, Enter to select, Esc to cancel")
        lines.append("")
        
        # Commands
        for i, cmd in enumerate(commands):
            prefix = ">" if i == selected_index else " "
            style = "bold green" if i == selected_index else "dim"
            
            # Format command line
            cmd_line = f"{prefix} /{cmd.name}"
            if cmd.aliases:
                cmd_line += f" ({', '.join('/' + a for a in cmd.aliases)})"
            cmd_line += f" - {cmd.description}"
            
            lines.append(f"[{style}]{cmd_line}[/{style}]")
        
        # Add empty lines if needed
        while len(lines) < self.max_display + 3:
            lines.append("")
        
        # Display all lines
        display_text = "\n".join(lines)
        self.console.print(display_text)
        
        # Store line count for next clear
        self._last_display_lines = len(lines)
    
    def _clear_display(self):
        """Clear the command display."""
        if hasattr(self, '_last_display_lines'):
            # Move cursor up and clear lines
            self.console.print(f"\x1b[{self._last_display_lines}A", end="")
            for _ in range(self._last_display_lines):
                self.console.print("\x1b[2K")  # Clear line
            self.console.print(f"\x1b[{self._last_display_lines}A", end="")  # Move back up