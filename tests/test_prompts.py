"""Tests for the unified prompts system."""

from pathlib import Path

from songbird.prompts import (
    PromptManager,
    get_core_system_prompt,
    get_planning_prompt_template,
    get_todo_completion_prompt_template,
    reload_prompts
)


class TestPromptManager:
    """Test the PromptManager class."""
    
    def test_prompt_manager_initialization(self):
        """Test that PromptManager initializes correctly."""
        manager = PromptManager()
        assert manager.prompts_dir.exists()
        assert manager.prompts_file.name == "agent.txt"
    
    def test_load_prompts(self):
        """Test loading prompts from file."""
        manager = PromptManager()
        prompts = manager._load_prompts()
        
        # Should have loaded prompts if file exists
        assert isinstance(prompts, dict)
        
        # If file exists, should have the expected sections
        if manager.prompts_file.exists():
            assert len(prompts) > 0
    
    def test_get_core_system_prompt(self):
        """Test getting the core system prompt."""
        manager = PromptManager()
        prompt = manager.get_core_system_prompt()
        
        assert isinstance(prompt, str)
        assert len(prompt) > 0
        assert "Songbird" in prompt
        assert "AI coding assistant" in prompt
    
    def test_get_planning_prompt_template(self):
        """Test getting the planning prompt template."""
        manager = PromptManager()
        template = manager.get_planning_prompt_template()
        
        assert isinstance(template, str)
        assert len(template) > 0
        assert "{user_request}" in template
    
    def test_get_todo_completion_prompt_template(self):
        """Test getting the todo completion prompt template."""
        manager = PromptManager()
        template = manager.get_todo_completion_prompt_template()
        
        assert isinstance(template, str)
        assert len(template) > 0
        assert "{message}" in template
        assert "{todos_json}" in template
    
    def test_reload_prompts(self):
        """Test reloading prompts."""
        manager = PromptManager()
        
        # Load prompts initially
        manager._load_prompts()
        initial_cache = manager._prompts_cache
        
        # Force reload
        manager.reload_prompts()
        
        # Cache should be cleared
        assert manager._prompts_cache is None
        
        # Loading again should work
        new_prompts = manager._load_prompts()
        assert isinstance(new_prompts, dict)


class TestGlobalPromptFunctions:
    """Test the global prompt access functions."""
    
    def test_get_core_system_prompt_function(self):
        """Test the global get_core_system_prompt function."""
        prompt = get_core_system_prompt()
        
        assert isinstance(prompt, str)
        assert len(prompt) > 0
        assert "Songbird" in prompt
    
    def test_get_planning_prompt_template_function(self):
        """Test the global get_planning_prompt_template function."""
        template = get_planning_prompt_template()
        
        assert isinstance(template, str)
        assert len(template) > 0
        assert "{user_request}" in template
    
    def test_get_todo_completion_prompt_template_function(self):
        """Test the global get_todo_completion_prompt_template function."""
        template = get_todo_completion_prompt_template()
        
        assert isinstance(template, str)
        assert len(template) > 0
        assert "{message}" in template
        assert "{todos_json}" in template
    
    def test_reload_prompts_function(self):
        """Test the global reload_prompts function."""
        # Should not raise an exception
        reload_prompts()


class TestPromptTemplateFormatting:
    """Test that prompt templates can be properly formatted."""
    
    def test_planning_template_formatting(self):
        """Test that planning template can be formatted with user request."""
        template = get_planning_prompt_template()
        
        formatted = template.format(user_request="Create a simple hello world script")
        
        assert "Create a simple hello world script" in formatted
        assert "{user_request}" not in formatted
    
    def test_todo_template_formatting(self):
        """Test that todo template can be formatted with message and todos."""
        template = get_todo_completion_prompt_template()
        
        test_message = "I finished implementing the login system"
        test_todos = '{"todo1": "Implement user authentication"}'
        
        formatted = template.format(message=test_message, todos_json=test_todos)
        
        assert test_message in formatted
        assert test_todos in formatted
        assert "{message}" not in formatted
        assert "{todos_json}" not in formatted


class TestFallbackBehavior:
    """Test fallback behavior when prompts file is missing or corrupted."""
    
    def test_missing_file_fallback(self):
        """Test behavior when prompts file is missing."""
        manager = PromptManager()
        
        # Temporarily point to non-existent file
        original_file = manager.prompts_file
        manager.prompts_file = Path("non_existent_file.txt")
        
        try:
            # Should still return valid prompts using fallbacks
            prompt = manager.get_core_system_prompt()
            assert isinstance(prompt, str)
            assert len(prompt) > 0
            
            template = manager.get_planning_prompt_template()
            assert isinstance(template, str)
            assert "{user_request}" in template
            
            todo_template = manager.get_todo_completion_prompt_template()
            assert isinstance(todo_template, str)
            assert "{message}" in todo_template
            
        finally:
            # Restore original file path
            manager.prompts_file = original_file