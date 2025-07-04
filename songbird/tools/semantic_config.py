# songbird/tools/semantic_config.py
"""
Configuration for semantic matching and LLM-based todo intelligence.
"""

from dataclasses import dataclass


@dataclass
class SemanticConfig:
    """Configuration for semantic matching behavior."""
    
    # Similarity thresholds
    duplicate_threshold: float = 0.7  # Threshold for considering todos as duplicates
    similarity_threshold: float = 0.55  # Threshold for content matching
    input_dedup_threshold: float = 0.7  # Threshold for input batch deduplication
    
    # LLM behavior
    llm_confidence_threshold: float = 0.7  # Minimum confidence for LLM classifications
    enable_llm_similarity: bool = True  # Use LLM for similarity calculations
    enable_llm_priority: bool = True  # Use LLM for priority detection
    enable_llm_classification: bool = True  # Use LLM for message classification
    
    # Auto-todo behavior
    enable_auto_todo_creation: bool = True  # Enable automatic todo creation
    enable_auto_todo_completion: bool = True  # Enable automatic todo completion
    auto_todo_min_words: int = 4  # Minimum words in message to trigger auto-creation
    auto_todo_max_per_message: int = 8  # Maximum todos to create per message
    
    # Fallback behavior
    fallback_to_heuristics: bool = True  # Use heuristics when LLM fails
    cache_llm_results: bool = True  # Cache LLM responses for performance
    max_cache_size: int = 1000  # Maximum number of cached results
    
    # Performance
    similarity_cache_ttl: int = 3600  # Cache time-to-live in seconds
    batch_similarity_requests: bool = False  # Future: batch multiple similarity requests
    parallel_llm_calls: bool = True  # Run LLM calls in parallel when possible


# Default configuration instance
DEFAULT_CONFIG = SemanticConfig()


def get_semantic_config() -> SemanticConfig:
    """Get the current semantic configuration."""
    return DEFAULT_CONFIG


def update_semantic_config(**kwargs) -> None:
    """Update the semantic configuration with new values."""
    global DEFAULT_CONFIG
    for key, value in kwargs.items():
        if hasattr(DEFAULT_CONFIG, key):
            setattr(DEFAULT_CONFIG, key, value)
        else:
            raise ValueError(f"Unknown config parameter: {key}")


def reset_semantic_config() -> None:
    """Reset semantic configuration to defaults."""
    global DEFAULT_CONFIG
    DEFAULT_CONFIG = SemanticConfig()