"""Provider mapping configuration loader with user extensibility support."""

import tomllib
from pathlib import Path
from typing import Dict, Any, Optional, List
from rich.console import Console

console = Console()

class MappingConfig:
    def __init__(self, config_data: Dict[str, Any]):
        self.data = config_data
        self.defaults = config_data.get("defaults", {})
        self.urls = config_data.get("urls", {})
        self.models = config_data.get("models", {})
        self.provider_config = config_data.get("provider_config", {})
    
    def get_default_model(self, provider: str) -> Optional[str]:
        return self.defaults.get(provider)
    
    def get_api_base(self, provider: str) -> Optional[str]:
        return self.urls.get(provider)
    
    def get_model_mapping(self, provider: str, model: str) -> Optional[str]:
        provider_models = self.models.get(provider, {})
        return provider_models.get(model)
    
    def get_available_models(self, provider: str) -> List[str]:
        return list(self.models.get(provider, {}).keys())
    
    def get_provider_config(self, provider: str) -> Dict[str, Any]:
        return self.provider_config.get(provider, {})
    
    def resolve_model_string(self, provider: str, model: Optional[str] = None) -> str:
        if model:
            mapped = self.get_model_mapping(provider, model)
            if mapped:
                return mapped
            
            # Fallback: construct LiteLLM string
            console.print(f"[yellow]Warning: Model '{model}' not found in mapping for provider '{provider}'. Using constructed string: {provider}/{model}[/yellow]")
            return f"{provider}/{model}"
        else:
            # Use default model
            default = self.get_default_model(provider)
            if default:
                return default
            
            # Ultimate fallback
            console.print(f"[red]Error: No default model found for provider '{provider}'[/red]")
            raise ValueError(f"No default model configured for provider: {provider}")


def validate_mapping_config(config_data: Dict[str, Any]) -> List[str]:
    issues = []
    
    # Most providers use standard provider/model format
    # Special cases: OpenRouter (nested), Ollama (no prefix), Copilot (custom)
    
    # Check required sections
    if "defaults" not in config_data:
        issues.append("Missing 'defaults' section in configuration")
    
    if "models" not in config_data:
        issues.append("Missing 'models' section in configuration")
    
    # Validate defaults section
    defaults = config_data.get("defaults", {})
    for provider, model_string in defaults.items():
        if not isinstance(model_string, str):
            issues.append(f"Default model for '{provider}' must be a string, got {type(model_string)}")
        elif _should_validate_provider_format(provider, model_string):
            issues.append(f"Default model for '{provider}' should use LiteLLM format 'provider/model': {model_string}")
    
    # Validate models section
    models = config_data.get("models", {})
    for provider, provider_models in models.items():
        if not isinstance(provider_models, dict):
            issues.append(f"Models for provider '{provider}' must be a dictionary")
            continue
        
        for model, model_string in provider_models.items():
            if not isinstance(model_string, str):
                issues.append(f"Model mapping '{provider}.{model}' must be a string")
            elif _should_validate_provider_format(provider, model_string):
                issues.append(f"Model mapping '{provider}.{model}' should use LiteLLM format: {model_string}")
    
    # Validate URLs section if present
    urls = config_data.get("urls", {})
    for provider, url in urls.items():
        if not isinstance(url, str):
            issues.append(f"URL for provider '{provider}' must be a string")
        elif not url.startswith(("http://", "https://")):
            issues.append(f"URL for provider '{provider}' should start with http:// or https://: {url}")
    
    return issues


def _should_validate_provider_format(provider: str, model_string: str) -> bool:
    # Copilot uses custom provider, no validation needed
    if provider == "copilot":
        return False
    
    # OpenRouter and Ollama have special format rules
    if provider in {"openrouter", "ollama"}:
        return False
    
    # For all other providers (openai, claude, gemini), require provider/model format
    return "/" not in model_string


def load_provider_mapping() -> MappingConfig:
    default_config_path = Path(__file__).parent / "provider_mapping.toml"
    
    if not default_config_path.exists():
        raise FileNotFoundError(f"Default provider mapping not found: {default_config_path}")
    
    # Load default configuration
    with open(default_config_path, "rb") as f:
        config_data = tomllib.load(f)
    
    # Load user configuration if it exists
    user_config_path = Path.home() / ".songbird_models.toml"
    if user_config_path.exists():
        try:
            with open(user_config_path, "rb") as f:
                user_config = tomllib.load(f)
            
            # Deep merge user config into default config
            config_data = _deep_merge(config_data, user_config)
            console.print(f"[dim]Loaded user configuration from {user_config_path}[/dim]")
            
        except Exception as e:
            console.print(f"[yellow]Warning: Failed to load user config from {user_config_path}: {e}[/yellow]")
    
    # Validate the final merged configuration
    validation_issues = validate_mapping_config(config_data)
    if validation_issues:
        console.print("[yellow]⚠️  Configuration validation warnings:[/yellow]")
        for issue in validation_issues[:5]:  # Limit to first 5 issues
            console.print(f"[yellow]   • {issue}[/yellow]")
        if len(validation_issues) > 5:
            console.print(f"[yellow]   ... and {len(validation_issues) - 5} more issues[/yellow]")
        console.print("[yellow]   LiteLLM may still work with these issues, but expect warnings[/yellow]")
    
    return MappingConfig(config_data)


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """Deep merge two dictionaries, with override taking precedence."""
    result = base.copy()
    
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    
    return result


def validate_mapping_config_instance(config: MappingConfig) -> List[str]:
    issues = []
    
    # Check that all providers have defaults
    expected_providers = ["openai", "claude", "gemini", "ollama", "openrouter"]
    for provider in expected_providers:
        if not config.get_default_model(provider):
            issues.append(f"No default model configured for provider: {provider}")
    
    # Check that provider configs exist
    for provider in expected_providers:
        provider_config = config.get_provider_config(provider)
        if not provider_config:
            issues.append(f"No provider configuration found for: {provider}")
            continue
        
        # Check required fields
        required_fields = ["supports_function_calling", "supports_streaming", "requires_api_key"]
        for field in required_fields:
            if field not in provider_config:
                issues.append(f"Missing required field '{field}' in config for provider: {provider}")
    
    return issues


def get_available_providers() -> List[str]:
    try:
        config = load_provider_mapping()
        return list(config.defaults.keys())
    except Exception:
        # Fallback to hardcoded list
        return ["openai", "claude", "gemini", "ollama", "openrouter"]


def create_example_user_config() -> str:
    """Create an example ~/.songbird_models.toml file content."""
    return '''# User-specific Songbird LiteLLM configuration
# This file extends the default provider mappings
# Place this file at ~/.songbird_models.toml

[defaults]
# Override default models
# openai = "openai/gpt-4-turbo"
# claude = "anthropic/claude-3-opus-20240229"

[urls]
# Add custom API endpoints
# local_ollama = "http://192.168.1.100:11434"
# custom_openai = "https://my-proxy.example.com/v1"

[models.custom_provider]
# Add your own provider models
# "my-model" = "custom_provider/my-model"

[provider_config.custom_provider]
# Configure your custom provider
# supports_function_calling = true
# supports_streaming = true
# requires_api_key = true
# api_key_env_var = "CUSTOM_API_KEY"
'''


if __name__ == "__main__":
    # Test the configuration loading
    try:
        config = load_provider_mapping()
        issues = validate_mapping_config_instance(config)
        
        if issues:
            console.print("[red]Configuration Issues:[/red]")
            for issue in issues:
                console.print(f"  - {issue}")
        else:
            console.print("[green]Configuration loaded successfully![/green]")
            
        # Show available providers
        providers = get_available_providers()
        console.print(f"Available providers: {', '.join(providers)}")
        
        # Test model resolution
        for provider in providers:
            try:
                default_model = config.resolve_model_string(provider)
                console.print(f"{provider}: {default_model}")
            except Exception as e:
                console.print(f"{provider}: [red]Error - {e}[/red]")
                
    except Exception as e:
        console.print(f"[red]Failed to load configuration: {e}[/red]")