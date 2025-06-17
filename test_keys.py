#!/usr/bin/env python3
"""
Test key detection for debugging.
"""

from songbird.commands.input_handler import get_key, KeyCodes
from rich.console import Console

def test_keys():
    console = Console()
    console.print("[bold]Key Test - Press keys to see their codes (Ctrl+C to exit)[/bold]")
    console.print("Try: arrow keys, enter, escape, backspace, regular letters")
    console.print()
    
    try:
        while True:
            key = get_key()
            if key == KeyCodes.CTRL_C:
                break
            elif key == KeyCodes.UP:
                console.print("UP arrow detected")
            elif key == KeyCodes.DOWN:
                console.print("DOWN arrow detected")
            elif key == KeyCodes.LEFT:
                console.print("LEFT arrow detected")
            elif key == KeyCodes.RIGHT:
                console.print("RIGHT arrow detected")
            elif key == KeyCodes.ENTER:
                console.print("ENTER detected")
            elif key == KeyCodes.ESCAPE:
                console.print("ESCAPE detected")
            elif key == KeyCodes.BACKSPACE:
                console.print("BACKSPACE detected")
            elif key:
                console.print(f"Character: '{key}' (ord: {ord(key) if len(key)==1 else 'N/A'})")
            else:
                console.print("Unknown key")
    except KeyboardInterrupt:
        pass
    
    console.print("\n[bold green]Key test completed![/bold green]")

if __name__ == "__main__":
    test_keys()