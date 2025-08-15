"""Songbird AI Agent Prompts Module

This module provides centralized access to all system prompts used by the Songbird AI agent.
"""

import os
from pathlib import Path
from typing import Dict, Optional
import re


class PromptManager:
    """Manages loading and accessing system prompts."""
    
    def __init__(self):
        self.prompts_dir = Path(__file__).parent
        self.prompts_file = self.prompts_dir / "agent.txt"
        self._prompts_cache: Optional[Dict[str, str]] = None
    
    def _load_prompts(self) -> Dict[str, str]:
        """Load all prompts from the agent.txt file."""
        if self._prompts_cache is not None:
            return self._prompts_cache
        
        prompts = {}
        
        if not self.prompts_file.exists():
            # Fallback to empty prompts if file doesn't exist
            return prompts
        
        try:
            with open(self.prompts_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Parse sections using regex
            sections = re.split(r'^## (.+)$', content, flags=re.MULTILINE)
            
            # Process sections (skip first empty section)
            for i in range(1, len(sections), 2):
                if i + 1 < len(sections):
                    section_name = sections[i].strip()
                    section_content = sections[i + 1].strip()
                    
                    # Remove leading/trailing separators
                    section_content = re.sub(r'^---\n?', '', section_content)
                    section_content = re.sub(r'\n?---$', '', section_content)
                    section_content = section_content.strip()
                    
                    # Store with normalized key
                    key = section_name.lower().replace(' ', '_').replace('-', '_')
                    prompts[key] = section_content
            
            self._prompts_cache = prompts
            
        except Exception as e:
            # If loading fails, return empty dict
            print(f"Warning: Failed to load prompts from {self.prompts_file}: {e}")
            prompts = {}
        
        return prompts
    
    def get_core_system_prompt(self) -> str:
        prompts = self._load_prompts()
        return prompts.get('core_agent_system_prompt', self._get_fallback_system_prompt())
    
    def get_planning_prompt_template(self) -> str:
        prompts = self._load_prompts()
        return prompts.get('planning_generation_prompt_template', self._get_fallback_planning_prompt())
    
    def get_todo_completion_prompt_template(self) -> str:
        prompts = self._load_prompts()
        return prompts.get('todo_auto_completion_prompt_template', self._get_fallback_todo_prompt())
    
    def _get_fallback_system_prompt(self) -> str:
        return """You are Songbird, an AI coding assistant with access to powerful tools.

CORE PRINCIPLES:
1. Use tools to gather information before making assumptions
2. Always verify results before proceeding
3. Explain your reasoning and what you're doing

AVAILABLE TOOLS:
- file_read, file_create, file_edit, file_search
- shell_exec, ls, glob, grep
- todo_read, todo_write, multi_edit

Remember: You have no prior knowledge of the file system. Always explore and verify using tools."""
    
    def _get_fallback_planning_prompt(self) -> str:
        """Fallback planning prompt template."""
        return """TASK: {user_request}

Create a step-by-step execution plan in JSON format with the following structure:
{
    "goal": "Brief description",
    "steps": [
        {
            "step_id": "step_1",
            "action": "tool_name",
            "args": {"arg1": "value1"},
            "description": "What this step does"
        }
    ]
}

Please respond with ONLY the JSON plan."""
    
    def _get_fallback_todo_prompt(self) -> str:
        return """Analyze this user message: "{message}"

Current todos: {todos_json}

Return ONLY a JSON array of completed todo IDs: ["id1", "id2"]"""
    
    def reload_prompts(self) -> None:
        self._prompts_cache = None


# Global prompt manager instance
_prompt_manager = PromptManager()

# Convenience functions
def get_core_system_prompt() -> str:
    return _prompt_manager.get_core_system_prompt()

def get_planning_prompt_template() -> str:
    return _prompt_manager.get_planning_prompt_template()

def get_todo_completion_prompt_template() -> str:
    return _prompt_manager.get_todo_completion_prompt_template()

def reload_prompts() -> None:
    _prompt_manager.reload_prompts()