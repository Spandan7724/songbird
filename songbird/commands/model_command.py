# songbird/commands/model_command.py
"""
Simplified model switching command with clean display.
"""

from typing import Dict, Any, List
from .base import BaseCommand, CommandResult


class ModelCommand(BaseCommand):
    """Command to switch LLM models."""

    def __init__(self):
        super().__init__(
            name="model",
            description="Switch the current LLM model",
            aliases=["m"]
        )

    async def execute(self, args: str, context: Dict[str, Any]) -> CommandResult:
        """Execute the model switching command."""
        provider_name = context.get("provider", "")
        current_model = context.get("model", "")
        provider_instance = context.get("provider_instance")
        orchestrator = context.get("orchestrator")

        if not provider_name:
            return CommandResult(
                success=False,
                message="No provider available in current context"
            )

        # Check if we're using LiteLLM or legacy provider
        is_litellm = self._is_litellm_provider(provider_instance)
        
        # Get available models based on provider type
        if is_litellm:
            models = self._get_litellm_models(provider_name)
        else:
            models = self._get_available_models(provider_name)
            
        if not models:
            return CommandResult(
                success=False,
                message=f"No models available for provider: {provider_name}"
            )

        # If args provided, try to set model directly or handle special commands
        if args.strip():
            arg = args.strip()
            
            # Handle cache invalidation command
            if arg == "--refresh" or arg == "--reload":
                try:
                    from ..llm.providers import invalidate_model_cache
                    invalidate_model_cache(provider_name)
                    return CommandResult(
                        success=True,
                        message=f"Model cache refreshed for {provider_name}"
                    )
                except Exception as e:
                    return CommandResult(
                        success=False,
                        message=f"Failed to refresh cache: {e}"
                    )
            
            new_model = arg
            
            # For LiteLLM, we need to resolve the model string
            if is_litellm:
                resolved_model = self._resolve_litellm_model(provider_name, new_model)
                if resolved_model and self._is_valid_litellm_model(provider_name, new_model):
                    if provider_instance:
                        # Use set_model if available (LiteLLM adapter) for proper state flush
                        if hasattr(provider_instance, 'set_model'):
                            provider_instance.set_model(resolved_model)
                        else:
                            provider_instance.model = resolved_model
                        # Update session if available 
                        if orchestrator and orchestrator.session:
                            orchestrator.session.update_litellm_config(
                                provider=provider_name,
                                model=new_model,
                                litellm_model=resolved_model
                            )
                            orchestrator.session_manager.save_session(orchestrator.session)
                    return CommandResult(
                        success=True,
                        message=f"Switched to model: {new_model} (LiteLLM: {resolved_model})",
                        data={"new_model": new_model}
                    )
                else:
                    return CommandResult(
                        success=False,
                        message=f"Model '{new_model}' not available for LiteLLM provider '{provider_name}'. Use /model to see available models."
                    )
            else:
                # Legacy provider handling
                if new_model in models:
                    if provider_instance:
                        provider_instance.model = new_model
                    return CommandResult(
                        success=True,
                        message=f"Switched to model: {new_model}",
                        data={"new_model": new_model}
                    )
                else:
                    return CommandResult(
                        success=False,
                        message=f"Model '{new_model}' not available. Use /model to see available models."
                    )

        # Show current model info
        self.console.print(
            f"\n[bold]Current: {provider_name} - {current_model}[/bold]")

        # Prepare options for interactive menu
        options = []
        current_index = 0
        
        for i, model in enumerate(models):
            if model == current_model:
                options.append(f"{model} ← current")
                current_index = i
            else:
                options.append(model)
        
        # Add cancel option
        options.append("Cancel (keep current model)")

        # Import the interactive menu function
        from ..conversation import safe_interactive_menu

        # Use interactive menu
        selected_idx = await safe_interactive_menu(
            f"Select model for {provider_name}:",
            options,
            default_index=current_index
        )
        
        if selected_idx is None or selected_idx == len(models):
            # User cancelled or selected cancel option
            return CommandResult(
                success=True,
                message="[white dim]Model selection cancelled[/white dim]",
            )

        selected_model = models[selected_idx]

        if selected_model == current_model:
            return CommandResult(
                success=True,
                message=f"Model unchanged: {selected_model}"
            )

        # Update the model based on provider type
        if is_litellm:
            # For LiteLLM, resolve the model string
            resolved_model = self._resolve_litellm_model(provider_name, selected_model)
            if provider_instance and resolved_model:
                # Use set_model if available (LiteLLM adapter) for proper state flush
                if hasattr(provider_instance, 'set_model'):
                    provider_instance.set_model(resolved_model)
                else:
                    provider_instance.model = resolved_model
                # Update session if available
                if orchestrator and orchestrator.session:
                    orchestrator.session.update_litellm_config(
                        provider=provider_name,
                        model=selected_model,
                        litellm_model=resolved_model
                    )
                    orchestrator.session_manager.save_session(orchestrator.session)
            
            return CommandResult(
                success=True,
                message=f"Switched to model: {selected_model} (LiteLLM: {resolved_model})",
                data={"new_model": selected_model}
            )
        else:
            # Legacy provider handling
            if provider_instance:
                provider_instance.model = selected_model

            return CommandResult(
                success=True,
                message=f"Switched to model: {selected_model}",
                data={"new_model": selected_model}
            )

    def _get_available_models(self, provider_name: str) -> List[str]:
        """Get available models for a provider using dynamic discovery."""
        try:
            # Try dynamic discovery first
            from ..llm.providers import get_models_for_provider
            import asyncio
            
            # Run model discovery
            def run_discovery():
                try:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    return loop.run_until_complete(get_models_for_provider(provider_name, use_cache=True))
                except Exception:
                    return []
                finally:
                    loop.close()
            
            discovered_models = run_discovery()
            
            if discovered_models:
                self.console.print(f"[dim]Found {len(discovered_models)} models via discovery for {provider_name}[/dim]")
                return discovered_models
            
            # Fallback to legacy methods
            self.console.print(f"[dim]Using legacy model discovery for {provider_name}[/dim]")
            
        except Exception as e:
            self.console.print(f"[yellow]Discovery failed for {provider_name}: {e}[/yellow]")
        
        # Legacy fallback methods
        if provider_name == "ollama":
            return self._get_ollama_models()
        elif provider_name == "gemini":
            return [
                "gemini-2.0-flash-001",
                "gemini-1.5-pro",
                "gemini-1.5-flash",
                "gemini-1.0-pro"
            ]
        elif provider_name == "openai":
            return self._get_openai_models()
        elif provider_name == "claude":
            return [
                "claude-3-5-sonnet-20241022",
                "claude-3-5-haiku-20241022",
                "claude-3-opus-20240229",
                "claude-3-sonnet-20240229",
                "claude-3-haiku-20240307"
            ]
        elif provider_name == "openrouter":
            return self._get_openrouter_models()
        else:
            return []

    def _get_ollama_models(self) -> List[str]:
        """Get available Ollama models."""
        try:
            import requests
            response = requests.get(
                "http://localhost:11434/api/tags", timeout=2)
            if response.status_code == 200:
                models = response.json().get('models', [])
                return [model['name'] for model in models]
        except Exception:
            pass

        # Fallback to common models
        return [
            "qwen2.5-coder:7b",
            "qwen2.5-coder:14b", 
            "qwen2.5-coder:32b",
            "llama3.2:latest",
            "codellama:latest",
            "deepseek-coder:6.7b"
        ]

    def _get_openai_models(self) -> List[str]:
        """Get available OpenAI models dynamically."""
        try:
            import os
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                # Return fallback models if no API key
                return [
                    "gpt-4o",
                    "gpt-4o-mini", 
                    "gpt-4-turbo",
                    "gpt-4",
                    "gpt-3.5-turbo"
                ]
            
            import openai
            client = openai.OpenAI(api_key=api_key)
            
            # Fetch models with a short timeout
            models_response = client.models.list()
            
            # Filter for chat completion models only
            chat_models = []
            for model in models_response.data:
                model_id = model.id
                if any(prefix in model_id for prefix in ["gpt-4", "gpt-3.5"]):
                    chat_models.append(model_id)
            
            # Sort models with GPT-4 first
            chat_models.sort(key=lambda x: (
                0 if x.startswith("gpt-4o") else
                1 if x.startswith("gpt-4") else 
                2 if x.startswith("gpt-3.5") else 3
            ))
            
            return chat_models if chat_models else [
                "gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-4", "gpt-3.5-turbo"
            ]
            
        except Exception:
            # Return fallback models on any error
            return [
                "gpt-4o",
                "gpt-4o-mini",
                "gpt-4-turbo", 
                "gpt-4",
                "gpt-3.5-turbo"
            ]

    def _get_openrouter_models(self) -> List[str]:
        """Get available OpenRouter models that support tools from API."""
        try:
            import os
            import httpx
            
            api_key = os.getenv("OPENROUTER_API_KEY")
            if not api_key:
                # Return fallback models if no API key - known tool-capable models
                return [
                    "deepseek/deepseek-chat-v3-0324:free",
                    "anthropic/claude-3.5-sonnet",
                    "openai/gpt-4o",
                    "openai/gpt-4o-mini",
                    "google/gemini-2.0-flash-001"
                ]
            
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            
            # Fetch all models from OpenRouter API
            response = httpx.get(
                "https://openrouter.ai/api/v1/models",
                headers=headers,
                timeout=5.0
            )
            
            if response.status_code == 200:
                models_data = response.json()
                
                # Filter for models that support tools
                tool_capable_models = []
                for model in models_data.get("data", []):
                    model_id = model.get("id", "")
                    supported_parameters = model.get("supported_parameters", [])
                    
                    # Only include models that have "tools" in their supported_parameters
                    if model_id and supported_parameters and "tools" in supported_parameters:
                        tool_capable_models.append(model_id)
                
                # Sort models for better organization
                def sort_key(model_id):
                    if model_id.startswith("anthropic/claude"):
                        return f"0_{model_id}"
                    elif model_id.startswith("openai/"):
                        return f"1_{model_id}"
                    elif model_id.startswith("google/"):
                        return f"2_{model_id}"
                    elif model_id.startswith("meta-llama/"):
                        return f"3_{model_id}"
                    elif model_id.startswith("mistralai/"):
                        return f"4_{model_id}"
                    else:
                        return f"5_{model_id}"
                
                tool_capable_models.sort(key=sort_key)
                
                # Return tool-capable models, or fallback if none found
                if tool_capable_models:
                    return tool_capable_models
                else:
                    print("No tool-capable models found in OpenRouter API")
                    
            else:
                print(f"OpenRouter API error: {response.status_code}")
                
        except Exception as e:
            print(f"Error fetching OpenRouter models: {e}")
        
        # Return fallback models on any error - known tool-capable models
        return [
            "deepseek/deepseek-chat-v3-0324:free",
            "anthropic/claude-3.5-sonnet",
            "openai/gpt-4o",
            "openai/gpt-4o-mini", 
            "google/gemini-2.0-flash-001"
        ]

    def _is_litellm_provider(self, provider_instance) -> bool:
        """Check if the provider instance is a LiteLLM adapter."""
        if not provider_instance:
            return False
        return hasattr(provider_instance, 'vendor_prefix') and hasattr(provider_instance, 'model_name')
    
    def _get_litellm_models(self, provider_name: str) -> List[str]:
        """Get available models for LiteLLM provider using dynamic discovery."""
        try:
            # Try dynamic discovery first
            from ..llm.providers import get_models_for_provider
            import asyncio
            
            # Run model discovery
            def run_discovery():
                try:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    return loop.run_until_complete(get_models_for_provider(provider_name, use_cache=True))
                except Exception:
                    return []
                finally:
                    loop.close()
            
            discovered_models = run_discovery()
            
            if discovered_models:
                self.console.print(f"[dim]Found {len(discovered_models)} models via discovery for {provider_name}[/dim]")
                return discovered_models
            
            # Fallback to configuration-based models
            from ..config import load_provider_mapping
            config = load_provider_mapping()
            
            models = []
            
            # Add default model
            default_model = config.get_default_model(provider_name)
            if default_model:
                # Extract the model name part after the provider prefix
                if "/" in default_model:
                    model_name = default_model.split("/", 1)[1]
                    models.append(model_name)
            
            # Add all mapped models for this provider
            available_models = config.get_available_models(provider_name)
            for model_name in available_models:
                if model_name not in models:
                    models.append(model_name)
            
            # Add some common models if none found
            if not models:
                models = self._get_fallback_litellm_models(provider_name)
            
            return models
            
        except Exception as e:
            self.console.print(f"[yellow]Warning: Failed to load models: {e}[/yellow]")
            return self._get_fallback_litellm_models(provider_name)
    
    def _get_fallback_litellm_models(self, provider_name: str) -> List[str]:
        """Get fallback models for LiteLLM provider."""
        fallback_models = {
            "openai": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo"],
            "claude": ["claude-3-5-sonnet-20241022", "claude-3-5-haiku-20241022"],
            "gemini": ["gemini-2.0-flash-001", "gemini-1.5-pro", "gemini-1.5-flash"],
            "ollama": ["qwen2.5-coder:7b", "llama3.2:latest", "codellama:latest"],
            "openrouter": ["anthropic/claude-3.5-sonnet", "openai/gpt-4o", "deepseek/deepseek-chat-v3-0324:free"]
        }
        return fallback_models.get(provider_name, [])
    
    def _resolve_litellm_model(self, provider_name: str, model_name: str) -> str:
        """Resolve a model name to LiteLLM model string with fallback warnings."""
        try:
            from ..config import load_provider_mapping
            config = load_provider_mapping()
            
            # Try to resolve through configuration
            try:
                resolved = config.resolve_model_string(provider_name, model_name)
                if resolved:
                    return resolved
            except ValueError:
                # Config doesn't have this model, continue to fallback
                pass
            
            # Check if model is in our known models list
            available_models = self._get_litellm_models(provider_name)
            if model_name not in available_models:
                self.console.print(f"[yellow]⚠️  Unknown model '{model_name}' for provider '{provider_name}'[/yellow]")
                self.console.print(f"[yellow]   Available models: {', '.join(available_models[:3])}{'...' if len(available_models) > 3 else ''}[/yellow]")
                self.console.print(f"[yellow]   Attempting to use model anyway with LiteLLM...[/yellow]")
            
            # Fallback: construct model string with warning
            constructed = f"{provider_name}/{model_name}"
            if model_name not in available_models:
                self.console.print(f"[dim]   Using constructed model string: {constructed}[/dim]")
            
            return constructed
            
        except Exception as e:
            # Final fallback with error message
            self.console.print(f"[red]Error resolving model '{model_name}' for provider '{provider_name}': {e}[/red]")
            fallback = f"{provider_name}/{model_name}"
            self.console.print(f"[yellow]Using fallback model string: {fallback}[/yellow]")
            return fallback
    
    def _is_valid_litellm_model(self, provider_name: str, model_name: str) -> bool:
        """Check if a model is valid for the LiteLLM provider with fallback support."""
        try:
            available_models = self._get_litellm_models(provider_name)
            
            # Allow exact matches from our configuration
            if model_name in available_models:
                return True
            
            # Allow unknown models with a warning (LiteLLM might support it)
            self.console.print(f"[dim]Model '{model_name}' not in known list, allowing fallback attempt[/dim]")
            return True
            
        except Exception:
            # If we can't load models, allow the attempt anyway
            return True

    def get_help(self) -> str:
        """Get detailed help for the model command."""
        return """
[bold]Usage:[/bold]
  /model              - Show interactive model selection menu
  /model <name>       - Switch to specific model directly
  /model --refresh    - Refresh model cache and show updated models
  /model --reload     - Same as --refresh

[bold]Examples:[/bold]
  /model              - Opens interactive menu with arrow key navigation
  /model gemini-2.0-flash-exp     - Switch to Gemini 2.0 Flash
  /model qwen2.5-coder:7b         - Switch to Qwen 2.5 Coder
  /model --refresh    - Reload available models from provider APIs

[bold]Interactive Menu:[/bold]
  • Use ↑↓ arrow keys to navigate
  • Press Enter to select
  • Press Ctrl+C to cancel

[bold]Model Discovery:[/bold]
  • Models are automatically discovered from provider APIs
  • Results are cached for 5 minutes for performance
  • Use --refresh to force reload from APIs

[bold]Shortcuts:[/bold]
  /m                  - Same as /model
"""
