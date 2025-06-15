# tests/tools/test_registry.py
import pytest
from songbird.tools.registry import (
    get_tool_schemas, 
    get_tool_function, 
    list_available_tools,
    TOOL_SCHEMAS
)


class TestToolRegistry:
    def test_get_tool_schemas_returns_list(self):
        """Test that get_tool_schemas returns a list of schemas."""
        schemas = get_tool_schemas()
        assert isinstance(schemas, list)
        assert len(schemas) > 0
        
    def test_file_search_schema_structure(self):
        """Test that file_search schema has correct structure."""
        schemas = get_tool_schemas()
        file_search_schema = None
        
        for schema in schemas:
            if schema["function"]["name"] == "file_search":
                file_search_schema = schema
                break
                
        assert file_search_schema is not None
        assert file_search_schema["type"] == "function"
        assert "description" in file_search_schema["function"]
        assert "parameters" in file_search_schema["function"]
        
        params = file_search_schema["function"]["parameters"]
        assert "pattern" in params["properties"]
        assert "directory" in params["properties"]
        assert params["required"] == ["pattern"]
        
    def test_get_tool_function_returns_callable(self):
        """Test that get_tool_function returns callable functions."""
        func = get_tool_function("file_search")
        assert callable(func)
        
    def test_get_tool_function_unknown_tool(self):
        """Test that get_tool_function returns None for unknown tools."""
        func = get_tool_function("nonexistent_tool")
        assert func is None
        
    def test_list_available_tools(self):
        """Test that list_available_tools returns expected tools."""
        tools = list_available_tools()
        assert isinstance(tools, list)
        assert "file_search" in tools