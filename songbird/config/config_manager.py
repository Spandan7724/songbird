"""Configuration management system for Songbird."""

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional
from dataclasses import dataclass, asdict, field


@dataclass
class LLMConfig:
    default_provider: str = "gemini"
    default_models: Dict[str, str] = field(default_factory=lambda: {
        "openai": "gpt-4o",
        "claude": "claude-3-5-sonnet-20241022", 
        "gemini": "gemini-2.0-flash",
        "ollama": "qwen2.5-coder:7b",
        "openrouter": "deepseek/deepseek-chat-v3-0324:free"
    })
    max_tokens: int = 4096
    temperature: float = 0.7
    timeout: int = 120  # Increased for long conversations


@dataclass
class SessionConfig:
    """Configuration for session management."""
    flush_interval: int = 30  # Seconds
    batch_size: int = 10      # Messages before auto-flush
    max_sessions: int = 100   # Max sessions to keep
    auto_save: bool = True
    compress_old_sessions: bool = True


@dataclass
class ToolConfig:
    """Configuration for tool execution."""
    default_timeout: int = 60  # Increased for long tasks
    max_parallel_tools: int = 5
    enable_confirmations: bool = True
    auto_backup: bool = False
    shell_timeout: int = 120  # Increased for long-running commands


@dataclass
class UIConfig:
    """Configuration for user interface."""
    theme: str = "monokai"
    show_token_usage: bool = False
    verbose_logging: bool = False
    progress_indicators: bool = True
    syntax_highlighting: bool = True


@dataclass
class AgentConfig:
    """Configuration for agent behavior."""
    max_iterations: int = 50  # Increased for long tasks
    token_budget: int = 150000  # Increased for complex tasks
    planning_enabled: bool = True
    auto_todo_completion: bool = True
    adaptive_termination: bool = True



@dataclass
class SongbirdConfig:
    """Main configuration class for Songbird."""
    llm: LLMConfig = field(default_factory=LLMConfig)
    session: SessionConfig = field(default_factory=SessionConfig)
    tools: ToolConfig = field(default_factory=ToolConfig)
    ui: UIConfig = field(default_factory=UIConfig)
    agent: AgentConfig = field(default_factory=AgentConfig)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SongbirdConfig':
        """Create from dictionary."""
        return cls(
            llm=LLMConfig(**data.get('llm', {})),
            session=SessionConfig(**data.get('session', {})),
            tools=ToolConfig(**data.get('tools', {})),
            ui=UIConfig(**data.get('ui', {})),
            agent=AgentConfig(**data.get('agent', {}))
        )


class ConfigManager:
    """Manages configuration for Songbird with environment variable overrides."""
    
    def __init__(self, config_dir: Optional[Path] = None):
        self.config_dir = config_dir or (Path.home() / ".songbird")
        self.config_dir.mkdir(exist_ok=True)
        self.config_file = self.config_dir / "config.json"
        
        self._config: Optional[SongbirdConfig] = None
        self._env_overrides: Dict[str, Any] = {}
        
        self._load_env_overrides()
    
    def _load_env_overrides(self):
        """Load configuration overrides from environment variables."""
        env_mapping = {
            # LLM Configuration
            "SONGBIRD_DEFAULT_PROVIDER": ("llm", "default_provider"),
            "SONGBIRD_MAX_TOKENS": ("llm", "max_tokens", int),
            "SONGBIRD_TEMPERATURE": ("llm", "temperature", float),
            "SONGBIRD_TIMEOUT": ("llm", "timeout", int),
            
            # Session Configuration
            "SONGBIRD_FLUSH_INTERVAL": ("session", "flush_interval", int),
            "SONGBIRD_BATCH_SIZE": ("session", "batch_size", int),
            "SONGBIRD_MAX_SESSIONS": ("session", "max_sessions", int),
            "SONGBIRD_AUTO_SAVE": ("session", "auto_save", self._str_to_bool),
            
            # Tool Configuration
            "SONGBIRD_TOOL_TIMEOUT": ("tools", "default_timeout", int),
            "SONGBIRD_MAX_PARALLEL_TOOLS": ("tools", "max_parallel_tools", int),
            "SONGBIRD_ENABLE_CONFIRMATIONS": ("tools", "enable_confirmations", self._str_to_bool),
            "SONGBIRD_AUTO_BACKUP": ("tools", "auto_backup", self._str_to_bool),
            "SONGBIRD_SHELL_TIMEOUT": ("tools", "shell_timeout", int),
            
            # UI Configuration
            "SONGBIRD_THEME": ("ui", "theme"),
            "SONGBIRD_SHOW_TOKEN_USAGE": ("ui", "show_token_usage", self._str_to_bool),
            "SONGBIRD_VERBOSE_LOGGING": ("ui", "verbose_logging", self._str_to_bool),
            "SONGBIRD_PROGRESS_INDICATORS": ("ui", "progress_indicators", self._str_to_bool),
            "SONGBIRD_SYNTAX_HIGHLIGHTING": ("ui", "syntax_highlighting", self._str_to_bool),
            
            # Agent Configuration
            "SONGBIRD_MAX_ITERATIONS": ("agent", "max_iterations", int),
            "SONGBIRD_TOKEN_BUDGET": ("agent", "token_budget", int),
            "SONGBIRD_PLANNING_ENABLED": ("agent", "planning_enabled", self._str_to_bool),
            "SONGBIRD_AUTO_TODO_COMPLETION": ("agent", "auto_todo_completion", self._str_to_bool),
            "SONGBIRD_ADAPTIVE_TERMINATION": ("agent", "adaptive_termination", self._str_to_bool),
            
            # Auto-apply for file operations
            "SONGBIRD_AUTO_APPLY": ("tools", "auto_apply", self._str_to_bool),
            
        }
        
        for env_var, config_path in env_mapping.items():
            env_value = os.getenv(env_var)
            if env_value is not None:
                if len(config_path) == 3:
                    # Has type converter
                    section, key, converter = config_path
                    try:
                        converted_value = converter(env_value)
                        self._set_nested_override(section, key, converted_value)
                    except (ValueError, TypeError):
                        print(f"Warning: Invalid value for {env_var}: {env_value}")
                else:
                    # String value
                    section, key = config_path
                    self._set_nested_override(section, key, env_value)
    
    def _str_to_bool(self, value: str) -> bool:
        return value.lower() in ('true', '1', 'yes', 'on', 'y')
    
    def _set_nested_override(self, section: str, key: str, value: Any):
        if section not in self._env_overrides:
            self._env_overrides[section] = {}
        self._env_overrides[section][key] = value
    
    def load_config(self) -> SongbirdConfig:
        if self._config is not None:
            return self._config
        
        # Load from file if exists
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r') as f:
                    data = json.load(f)
                config = SongbirdConfig.from_dict(data)
            except (json.JSONDecodeError, KeyError, TypeError) as e:
                print(f"Warning: Error loading config file: {e}")
                print("Using default configuration.")
                config = SongbirdConfig()
        else:
            # Use defaults
            config = SongbirdConfig()
        
        # Apply environment overrides
        self._apply_env_overrides(config)
        
        self._config = config
        return config
    
    def _apply_env_overrides(self, config: SongbirdConfig):
        for section, overrides in self._env_overrides.items():
            if hasattr(config, section):
                section_config = getattr(config, section)
                for key, value in overrides.items():
                    if hasattr(section_config, key):
                        setattr(section_config, key, value)
    
    def save_config(self, config: Optional[SongbirdConfig] = None):
        """Save configuration to file."""
        if config is None:
            config = self._config
        
        if config is None:
            config = SongbirdConfig()
        
        try:
            with open(self.config_file, 'w') as f:
                json.dump(config.to_dict(), f, indent=2)
        except Exception as e:
            print(f"Warning: Error saving config file: {e}")
    
    def get_config(self) -> SongbirdConfig:
        if self._config is None:
            return self.load_config()
        return self._config
    
    def update_config(self, updates: Dict[str, Any]):
        """Update configuration with new values."""
        config = self.get_config()
        
        for section, values in updates.items():
            if hasattr(config, section):
                section_config = getattr(config, section)
                for key, value in values.items():
                    if hasattr(section_config, key):
                        setattr(section_config, key, value)
        
        self.save_config(config)
    
    def reset_config(self):
        self._config = SongbirdConfig()
        self.save_config()
    
    def get_api_keys(self) -> Dict[str, Optional[str]]:
        return {
            "openai": os.getenv("OPENAI_API_KEY"),
            "claude": os.getenv("ANTHROPIC_API_KEY"),
            "gemini": os.getenv("GEMINI_API_KEY"),
            "openrouter": os.getenv("OPENROUTER_API_KEY"),
            "ollama": None  # Local, no API key needed
        }
    
    def get_available_providers(self) -> Dict[str, bool]:
        api_keys = self.get_api_keys()
        return {
            "openai": bool(api_keys["openai"]),
            "claude": bool(api_keys["claude"]), 
            "gemini": bool(api_keys["gemini"]),
            "openrouter": bool(api_keys["openrouter"]),
            "ollama": True  # Always available if installed
        }
    
    def get_default_provider(self) -> str:
        """Get the best available provider."""
        available = self.get_available_providers()
        config = self.get_config()
        
        # Check if configured default is available
        if available.get(config.llm.default_provider, False):
            return config.llm.default_provider
        
        # Fallback priority
        priority = ["gemini", "claude", "openai", "openrouter", "ollama"]
        for provider in priority:
            if available.get(provider, False):
                return provider
        
        # Last resort
        return "ollama"


_config_manager = ConfigManager()


def get_config() -> SongbirdConfig:
    return _config_manager.get_config()


def get_config_manager() -> ConfigManager:
    return _config_manager