# songbird/commands/input_handler.py
"""
Enhanced input handler for real-time command dropdown like Claude Code.
"""

import os
import sys
import termios
import tty
from typing import Optional, Tuple, List
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from .base import BaseCommand
from .registry import CommandRegistry


class KeyCodes:
    """Key code constants for cross-platform compatibility."""
    UP = '\x1b[A'
    DOWN = '\x1b[B'
    LEFT = '\x1b[D'
    RIGHT = '\x1b[C'
    ENTER = '\r'
    BACKSPACE = '\x7f'
    DELETE = '\x1b[3~'
    ESCAPE = '\x1b'
    CTRL_C = '\x03'
    CTRL_D = '\x04'
    TAB = '\t'


def get_key():
    """Get a single key press, handling escape sequences properly."""
    if os.name == 'nt':  # Windows
        import msvcrt
        key = msvcrt.getch()
        if key == b'\x00' or key == b'\xe0':  # Special key prefix
            key2 = msvcrt.getch()
            if key2 == b'H':  # Up
                return KeyCodes.UP
            elif key2 == b'P':  # Down
                return KeyCodes.DOWN
            elif key2 == b'K':  # Left
                return KeyCodes.LEFT
            elif key2 == b'M':  # Right
                return KeyCodes.RIGHT
            else:
                return ''
        elif key == b'\r':
            return KeyCodes.ENTER
        elif key == b'\x08':
            return KeyCodes.BACKSPACE
        elif key == b'\x1b':
            return KeyCodes.ESCAPE
        elif key == b'\x03':
            return KeyCodes.CTRL_C
        else:
            try:
                return key.decode('utf-8', errors='ignore')
            except:
                return ''
    else:  # Unix/Linux/macOS
        if not sys.stdin.isatty():
            return ''
        
        try:
            fd = sys.stdin.fileno()
            old_settings = termios.tcgetattr(fd)
            try:
                tty.setraw(fd)
                key = sys.stdin.read(1)
                
                if key == '\x1b':  # Escape sequence
                    # Read the next character to see if it's part of an escape sequence
                    key2 = sys.stdin.read(1)
                    if key2 == '[':
                        # Read the final character of the escape sequence
                        key3 = sys.stdin.read(1)
                        if key3 == 'A':
                            return KeyCodes.UP
                        elif key3 == 'B':
                            return KeyCodes.DOWN
                        elif key3 == 'C':
                            return KeyCodes.RIGHT
                        elif key3 == 'D':
                            return KeyCodes.LEFT
                        elif key3 == '3':
                            # Might be delete key, read one more
                            key4 = sys.stdin.read(1)
                            if key4 == '~':
                                return KeyCodes.DELETE
                        return ''
                    else:
                        return KeyCodes.ESCAPE
                elif key == '\n':
                    return KeyCodes.ENTER
                elif key == '\x7f':
                    return KeyCodes.BACKSPACE
                elif key == '\x03':
                    return KeyCodes.CTRL_C
                elif key == '\x04':
                    return KeyCodes.CTRL_D
                elif key == '\t':
                    return KeyCodes.TAB
                else:
                    return key
            finally:
                termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        except:
            return ''


class CommandInputHandler:
    """Enhanced input handler with real-time command dropdown."""
    
    def __init__(self, registry: CommandRegistry, console: Console):
        self.registry = registry
        self.console = console
        self.max_display = 8
    
    def get_input_with_commands(self, prompt: str = "You") -> str:
        """
        Get input with real-time command dropdown when '/' is typed.
        Returns the final input string.
        """
        self.console.print(f"\n[bold cyan]{prompt}[/bold cyan]: ", end="")
        
        current_input = ""
        showing_commands = False
        selected_index = 0
        live_display = None
        
        try:
            while True:
                key = get_key()
                
                if key == KeyCodes.CTRL_C:
                    if live_display:
                        live_display.stop()
                    raise KeyboardInterrupt()
                
                elif key == KeyCodes.ENTER:
                    if live_display:
                        live_display.stop()
                    
                    if showing_commands:
                        # Select the current command
                        filtered_commands = self._get_filtered_commands(current_input[1:])
                        if filtered_commands and selected_index < len(filtered_commands):
                            selected_cmd = filtered_commands[selected_index]
                            final_input = f"/{selected_cmd.name}"
                            self.console.print(final_input)
                            return final_input
                        else:
                            # No commands or invalid selection, return current input
                            self.console.print(current_input)
                            return current_input
                    else:
                        # Regular input
                        self.console.print(current_input)
                        return current_input
                
                elif key == KeyCodes.ESCAPE:
                    if live_display:
                        live_display.stop()
                    if showing_commands:
                        # Cancel command selection, continue with regular input
                        showing_commands = False
                        self.console.print(current_input, end="")
                    else:
                        # Cancel entire input
                        self.console.print()
                        return ""
                
                elif key == KeyCodes.BACKSPACE:
                    if current_input:
                        current_input = current_input[:-1]
                        
                        # Update display
                        if showing_commands:
                            if not current_input.startswith('/'):
                                # No longer a command
                                if live_display:
                                    live_display.stop()
                                    live_display = None
                                showing_commands = False
                            else:
                                selected_index = 0
                                if live_display:
                                    live_display.update(self._create_command_display(current_input, selected_index))
                        
                        # Redraw input line
                        self.console.print(f"\r[bold cyan]{prompt}[/bold cyan]: {current_input}", end="")
                
                elif key == KeyCodes.UP:
                    if showing_commands:
                        filtered_commands = self._get_filtered_commands(current_input[1:])
                        if filtered_commands and selected_index > 0:
                            selected_index -= 1
                            if live_display:
                                live_display.update(self._create_command_display(current_input, selected_index))
                
                elif key == KeyCodes.DOWN:
                    if showing_commands:
                        filtered_commands = self._get_filtered_commands(current_input[1:])
                        if filtered_commands and selected_index < len(filtered_commands) - 1:
                            selected_index += 1
                            if live_display:
                                live_display.update(self._create_command_display(current_input, selected_index))
                
                elif key and key.isprintable():
                    current_input += key
                    
                    # Check if we should show commands
                    if current_input.startswith('/') and not showing_commands:
                        showing_commands = True
                        selected_index = 0
                        live_display = Live(
                            self._create_command_display(current_input, selected_index),
                            console=self.console,
                            refresh_per_second=10
                        )
                        live_display.start()
                    
                    elif showing_commands:
                        # Update command display
                        selected_index = 0
                        if live_display:
                            live_display.update(self._create_command_display(current_input, selected_index))
                    
                    # Redraw input line
                    self.console.print(f"\r[bold cyan]{prompt}[/bold cyan]: {current_input}", end="")
        
        except Exception as e:
            if live_display:
                live_display.stop()
            raise e
    
    def _get_filtered_commands(self, query: str) -> List[BaseCommand]:
        """Get commands filtered by query."""
        if not query:
            return self.registry.get_all_commands()[:self.max_display]
        
        # Search by name and description
        matches = []
        all_commands = self.registry.get_all_commands()
        
        for cmd in all_commands:
            if (query.lower() in cmd.name.lower() or 
                query.lower() in cmd.description.lower() or
                any(query.lower() in alias.lower() for alias in cmd.aliases)):
                matches.append(cmd)
        
        return matches[:self.max_display]
    
    def _create_command_display(self, current_input: str, selected_index: int):
        """Create the command display panel."""
        query = current_input[1:] if current_input.startswith('/') else ""
        filtered_commands = self._get_filtered_commands(query)
        
        if not filtered_commands:
            return Panel("No matching commands found", title="Commands", border_style="red")
        
        # Create table
        table = Table(show_header=False, show_edge=False, padding=(0, 1))
        table.add_column("Command", style="green")
        table.add_column("Description", style="dim")
        
        for i, cmd in enumerate(filtered_commands):
            cmd_name = f"/{cmd.name}"
            if cmd.aliases:
                cmd_name += f" ({', '.join('/' + a for a in cmd.aliases)})"
            
            if i == selected_index:
                table.add_row(f"[bold white on blue] {cmd_name} [/]", f"[bold white on blue] {cmd.description} [/]")
            else:
                table.add_row(cmd_name, cmd.description)
        
        return Panel(
            table,
            title=f"Commands ({current_input})",
            title_align="left",
            border_style="blue"
        )