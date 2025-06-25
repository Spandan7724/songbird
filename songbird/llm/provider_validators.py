"""
Validators and fixers for provider-specific issues.
"""
import json
import re
from typing import Dict, Any, Optional


def validate_and_fix_tool_arguments(arguments: Any, provider_name: str) -> Dict[str, Any]:
    """
    Validate and fix tool arguments based on provider quirks.
    
    Args:
        arguments: Raw arguments from provider
        provider_name: Name of the provider (openai, gemini, etc.)
        
    Returns:
        Fixed arguments dictionary
    """
    # If already a dict, validate it
    if isinstance(arguments, dict):
        return arguments
    
    # If it's a string, try to parse it
    if isinstance(arguments, str):
        try:
            # Direct JSON parse
            return json.loads(arguments)
        except json.JSONDecodeError:
            # Try to fix common issues
            fixed = fix_malformed_json(arguments, provider_name)
            if fixed:
                return fixed
    
    # If it's something else, try to convert
    try:
        return dict(arguments)
    except:
        return {}


def fix_malformed_json(json_str: str, provider_name: str) -> Optional[Dict[str, Any]]:
    """
    Fix common JSON malformations from different providers.
    """
    try:
        # Remove any markdown code block markers
        json_str = re.sub(r'^```json\s*', '', json_str)
        json_str = re.sub(r'\s*```$', '', json_str)
        
        # Fix unquoted property names
        json_str = re.sub(r'(\{|,)\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*:', r'\1"\2":', json_str)
        
        # Fix single quotes to double quotes
        json_str = json_str.replace("'", '"')
        
        # Fix trailing commas
        json_str = re.sub(r',\s*}', '}', json_str)
        json_str = re.sub(r',\s*]', ']', json_str)
        
        # Provider-specific fixes
        if provider_name == "gemini":
            # Gemini sometimes adds extra escaping
            json_str = json_str.replace('\\\\n', '\\n')
            json_str = json_str.replace('\\\\t', '\\t')
        
        elif provider_name == "openrouter":
            # OpenRouter may have encoding issues
            json_str = json_str.encode('utf-8', errors='ignore').decode('utf-8')
        
        # Try to parse again
        return json.loads(json_str)
        
    except Exception:
        return None 