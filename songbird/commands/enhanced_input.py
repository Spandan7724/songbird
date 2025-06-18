"""Enhanced input handler with message history navigation."""
import sys
import os
from typing import Optional
from rich.console import Console
from ..memory.history_manager import MessageHistoryManager


def getch():
    """Get a single character from stdin, cross-platform (adapted from conversation.py)."""
    if os.name == 'nt':  # Windows
        import msvcrt
        ch1 = msvcrt.getch()
        if ch1 in (b'\x00', b'\xe0'):          # arrow / function key prefix
            ch2 = msvcrt.getch()
            if ch2 == b'H':                    # Up
                return '\x1b[A'
            elif ch2 == b'P':                  # Down
                return '\x1b[B'
            elif ch2 == b'K':                  # Left
                return '\x1b[D'  
            elif ch2 == b'M':                  # Right
                return '\x1b[C'
            else:
                return ''                      # ignore other special keys
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


def get_input_with_history(
    prompt: str, 
    history_manager: Optional[MessageHistoryManager] = None,
    console: Optional[Console] = None
) -> str:
    """
    Get user input with arrow key history navigation support.
    
    Args:
        prompt: The prompt to display
        history_manager: Optional history manager for navigation
        console: Rich console for output
        
    Returns:
        The user's input string
    """
    if console is None:
        console = Console()
    
    # If no history manager or not TTY, fall back to regular input
    if history_manager is None or not sys.stdin.isatty():
        console.print(f"[bold cyan]{prompt}[/bold cyan]: ", end="")
        return input().strip()
    
    console.print(f"[bold cyan]{prompt}[/bold cyan]: ", end="")
    
    # Track current input and cursor position
    current_input = ""
    cursor_pos = 0
    in_history_mode = False
    
    while True:
        # Display current input
        # Clear line and rewrite
        sys.stdout.write('\r')
        sys.stdout.write('\x1b[K')  # Clear to end of line
        console.print(f"[bold cyan]{prompt}[/bold cyan]: {current_input}", end="")
        
        # Position cursor
        if cursor_pos < len(current_input):
            # Move cursor back to correct position
            moves_back = len(current_input) - cursor_pos
            sys.stdout.write(f'\x1b[{moves_back}D')
        
        sys.stdout.flush()
        
        # Get next character
        ch = getch()
        
        # Handle non-TTY fallback
        if ch == '':
            # Fall back to regular input if getch() fails
            sys.stdout.write('\n')
            return input().strip()
        
        # Handle special keys
        if ch == '\x1b':  # Escape sequence start (Unix/Linux)
            try:
                seq = getch() + getch()
                if seq == '[A':  # Up arrow
                    if history_manager.get_history_count() > 0:
                        if not in_history_mode:
                            # Start history navigation
                            current_input = history_manager.start_navigation(current_input)
                            in_history_mode = True
                        else:
                            # Navigate up in history
                            prev_msg = history_manager.navigate_up()
                            if prev_msg is not None:
                                current_input = prev_msg
                        cursor_pos = len(current_input)
                elif seq == '[B':  # Down arrow
                    if in_history_mode:
                        next_msg = history_manager.navigate_down()
                        if next_msg is not None:
                            current_input = next_msg
                            if history_manager.is_navigating():
                                cursor_pos = len(current_input)
                            else:
                                # Back to original input
                                in_history_mode = False
                                cursor_pos = len(current_input)
                elif seq == '[D':  # Left arrow
                    if cursor_pos > 0:
                        cursor_pos -= 1
                elif seq == '[C':  # Right arrow
                    if cursor_pos < len(current_input):
                        cursor_pos += 1
            except:
                pass  # Ignore malformed escape sequences
                
        elif ch == '\x1b[A':  # Up arrow (Windows-mapped)
            if history_manager.get_history_count() > 0:
                if not in_history_mode:
                    current_input = history_manager.start_navigation(current_input)
                    in_history_mode = True
                else:
                    prev_msg = history_manager.navigate_up()
                    if prev_msg is not None:
                        current_input = prev_msg
                cursor_pos = len(current_input)
                
        elif ch == '\x1b[B':  # Down arrow (Windows-mapped)
            if in_history_mode:
                next_msg = history_manager.navigate_down()
                if next_msg is not None:
                    current_input = next_msg
                    if history_manager.is_navigating():
                        cursor_pos = len(current_input)
                    else:
                        in_history_mode = False
                        cursor_pos = len(current_input)
                        
        elif ch == '\x1b[D':  # Left arrow (Windows-mapped)
            if cursor_pos > 0:
                cursor_pos -= 1
                
        elif ch == '\x1b[C':  # Right arrow (Windows-mapped)
            if cursor_pos < len(current_input):
                cursor_pos += 1
        
        elif ch in ('\r', '\n'):  # Enter
            sys.stdout.write('\n')
            # Reset history navigation
            if in_history_mode:
                history_manager.reset_navigation()
            return current_input.strip()
            
        elif ch == '\x03':  # Ctrl+C - simulate proper signal behavior
            # Exit raw mode temporarily and send SIGINT to allow double-tap logic
            import signal
            import os
            if in_history_mode:
                history_manager.reset_navigation()
            # Send SIGINT to current process to trigger the signal handler
            os.kill(os.getpid(), signal.SIGINT)
            
        elif ch == '\x04':  # Ctrl+D
            sys.stdout.write('\n')
            if in_history_mode:
                history_manager.reset_navigation()
            raise KeyboardInterrupt
            
        elif ch == '\x7f' or ch == '\x08':  # Backspace
            if cursor_pos > 0:
                current_input = current_input[:cursor_pos-1] + current_input[cursor_pos:]
                cursor_pos -= 1
                # Exit history mode if user starts editing
                if in_history_mode:
                    history_manager.reset_navigation()
                    in_history_mode = False
                    
        elif ch == '\x1b':  # Escape key alone
            if in_history_mode:
                # Cancel history navigation and restore original input
                current_input = history_manager.reset_navigation()
                cursor_pos = len(current_input)
                in_history_mode = False
        
        elif len(ch) == 1 and ord(ch) >= 32:  # Regular printable character
            # Insert character at cursor position
            current_input = current_input[:cursor_pos] + ch + current_input[cursor_pos:]
            cursor_pos += 1
            # Exit history mode if user starts typing
            if in_history_mode:
                history_manager.reset_navigation()
                in_history_mode = False