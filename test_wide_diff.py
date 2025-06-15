#!/usr/bin/env python3
"""
Test the wider diff display
"""
import asyncio
import tempfile
from pathlib import Path
from songbird.tools.file_operations import file_edit, display_diff_preview

async def test_wide_diff():
    """Test the wider diff display."""
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        original_content = """def hello_world():
    print("Hello, World!")
    return "greeting"

def calculate(x, y):
    return x + y
"""
        f.write(original_content)
        f.flush()
        
        new_content = """def hello_world():
    print("Hello, Claude Code!")  # This is a longer line to test diff width
    print("This is an additional line with more content")
    return "greeting"

def calculate(x, y, z=0):
    # Added optional parameter with longer comment line
    return x + y + z

def new_function_with_a_very_long_name():
    return "This is a new function with a very long line that should test the diff box width properly"
"""
        
        print("Testing wider diff display...\n")
        
        result = await file_edit(f.name, new_content)
        
        if result["success"] and result["changes_made"]:
            display_diff_preview(result["diff_preview"], "example_file_with_long_name.py")
        
        # Clean up
        Path(f.name).unlink()

if __name__ == "__main__":
    asyncio.run(test_wide_diff())