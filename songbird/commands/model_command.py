from typing import Dict, Any, List
from .base import BaseCommand, CommandResult
import os
import asyncio


class ModelCommand(BaseCommand):
    """Command to switch LLM models."""

    def __init__(self):
        super().__init__(
            name="model",
            description="Switch the current LLM model",
            aliases=["m"]
        )

    async def execute(self, args: str, context: Dict[str, Any]) -> CommandResult:
        provider_name = context.get("provider", "")
        current_model = context.get("model", "")
        provider_instance = context.get("provider_instance")
        orchestrator = context.get("orchestrator")

        if not provider_name:
            return CommandResult(
                success=False,
                message="No provider available in current context"
            )

        is_ready, error_msg = self._check_provider_prerequisites(provider_name)
        if not is_ready:
            return CommandResult(
                success=False,
                message=error_msg
            )
        
        # Get available models - all providers use LiteLLM except Copilot
        if provider_name == "copilot":
            models = await self._get_copilot_models()
        else:
            models = await self._get_litellm_models(provider_name)
            
        if not models:
            return CommandResult(
                success=False,
                message=f"No models available for provider: {provider_name}"
            )

        if args.strip():
            arg = args.strip()
            
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
            
            # Handle model switching based on provider type
            if provider_name == "copilot":
                # Copilot uses custom provider - direct model assignment
                if new_model in models:
                    if provider_instance:
                        provider_instance.model = new_model
                        if orchestrator and orchestrator.session:
                            orchestrator.session.update_provider_config(
                                provider_name, new_model, provider_type="custom"
                            )
                            orchestrator.session_manager.save_session(orchestrator.session)
                    return CommandResult(
                        success=True,
                        message=None,
                        data={"new_model": new_model}
                    )
                else:
                    return CommandResult(
                        success=False,
                        message=f"Model '{new_model}' not available for Copilot. Use /model to see available models."
                    )
            else:
                # All other providers use LiteLLM
                resolved_model = self._resolve_litellm_model(provider_name, new_model)
                if resolved_model and self._is_valid_litellm_model(provider_name, new_model):
                    if provider_instance:
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
                        message=None,  # CLI will handle the confirmation
                        data={"new_model": new_model}
                    )
                else:
                    return CommandResult(
                        success=False,
                        message=f"Model '{new_model}' not available for LiteLLM provider '{provider_name}'. Use /model to see available models."
                    )

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
        if provider_name == "copilot":
            if provider_instance:
                provider_instance.model = selected_model
                if orchestrator and orchestrator.session:
                    orchestrator.session.update_provider_config(
                        provider_name, selected_model, provider_type="custom")
                    orchestrator.session_manager.save_session(orchestrator.session)

            return CommandResult(
                success=True,
                message=None,
                data={"new_model": selected_model}
            )
        else:
            resolved_model = self._resolve_litellm_model(provider_name, selected_model)
            if provider_instance and resolved_model:
                if hasattr(provider_instance, 'set_model'):
                    provider_instance.set_model(resolved_model)
                else:
                    provider_instance.model = resolved_model
                if orchestrator and orchestrator.session:
                    orchestrator.session.update_litellm_config(
                        provider=provider_name,
                        model=selected_model,
                        litellm_model=resolved_model
                    )
                    orchestrator.session_manager.save_session(orchestrator.session)
            
            return CommandResult(
                success=True,
                message=None,
                data={"new_model": selected_model}
            )

    async def _run_async_discovery(self, provider_name: str) -> List[str]:
        """Run async model discovery using existing event loop."""
        import asyncio
        from ..llm.providers import get_models_for_provider
        
        return await asyncio.wait_for(
            get_models_for_provider(provider_name, use_cache=True), 
            timeout=5.0
        )


    def _get_openai_models(self) -> List[str]:
        """Get available OpenAI models dynamically."""
        try:
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                # Prerequisites not met - return empty list
                return []
            
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
            
            chat_models.sort(key=lambda x: (
                0 if x.startswith("gpt-4o") else
                1 if x.startswith("gpt-4") else 
                2 if x.startswith("gpt-3.5") else 3
            ))
            
            return chat_models if chat_models else [
                "gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-4", "gpt-3.5-turbo"
            ]
            
        except Exception:
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
            import httpx
            
            api_key = os.getenv("OPENROUTER_API_KEY")
            if not api_key:
                # Prerequisites not met - return empty list
                return []
            
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
                    self.console.print("[yellow]No tool-capable models found in OpenRouter API[/yellow]")
                    
            else:
                self.console.print(f"[yellow]OpenRouter API error: {response.status_code}[/yellow]")
                
        except Exception as e:
            self.console.print(f"[yellow]Error fetching OpenRouter models: {e}[/yellow]")
        
        # Return fallback models on any error - known tool-capable models
        return [
            "deepseek/deepseek-chat-v3-0324:free",
            "anthropic/claude-3.5-sonnet",
            "openai/gpt-4o",
            "openai/gpt-4o-mini", 
            "google/gemini-2.0-flash-001"
        ]

    # Note: _is_litellm_provider method removed - all providers except Copilot use LiteLLM
    
    def _check_provider_prerequisites(self, provider_name: str) -> tuple[bool, str]:
        if provider_name == "openai":
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                return False, "OPENAI_API_KEY environment variable not set\n\n Get your API key from: https://platform.openai.com/api-keys\n Set it with: export OPENAI_API_KEY='your-key-here'"
                
        elif provider_name == "claude":
            api_key = os.getenv("ANTHROPIC_API_KEY")
            if not api_key:
                return False, "ANTHROPIC_API_KEY environment variable not set\n\n Get your API key from: https://console.anthropic.com/account/keys\n Set it with: export ANTHROPIC_API_KEY='your-key-here'"
                
        elif provider_name == "gemini":
            api_key = os.getenv("GEMINI_API_KEY")
            if not api_key:
                return False, "GEMINI_API_KEY environment variable not set\n\n Get your FREE API key from: https://aistudio.google.com/app/apikey\n Set it with: export GEMINI_API_KEY='your-key-here'"
                
        elif provider_name == "openrouter":
            api_key = os.getenv("OPENROUTER_API_KEY")
            if not api_key:
                return False, "OPENROUTER_API_KEY environment variable not set\n\n Get your API key from: https://openrouter.ai/keys\n Set it with: export OPENROUTER_API_KEY='your-key-here'"
                
        elif provider_name == "ollama":
            # Check if Ollama service is running
            try:
                import requests
                response = requests.get("http://localhost:11434/api/version", timeout=2)
                if response.status_code != 200:
                    return False, "Ollama service not responding\n\n Start Ollama with: ollama serve\n Install from: https://ollama.ai"
            except Exception:
                return False, "Ollama not running or not installed\n\n Start Ollama with: ollama serve\n Install from: https://ollama.ai"
                
        elif provider_name == "copilot":
            token = os.getenv("COPILOT_ACCESS_TOKEN")
            if not token:
                return False, "COPILOT_ACCESS_TOKEN environment variable not set\n\n Get your token from GitHub Copilot settings\n Set it with: export COPILOT_ACCESS_TOKEN='your-token-here'"
        
        return True, ""
    
    async def _get_litellm_models(self, provider_name: str) -> List[str]:
        # Special handling for Copilot since it uses a custom provider
        if provider_name == "copilot":
            return await self._get_copilot_models()
        
        try:
            # Try dynamic discovery first using proper async/await
            try:
                discovered_models = await self._run_async_discovery(provider_name)
                if discovered_models:
                    return discovered_models
            except asyncio.TimeoutError:
                self.console.print(f"[yellow]Model discovery timeout for {provider_name} - using fallback[/yellow]")
            except Exception as e:
                if "ollama" in provider_name.lower():
                    self.console.print("[yellow]Ollama not running or no models found - using fallback[/yellow]")
                else:
                    self.console.print(f"[yellow]Discovery failed for {provider_name}: {e} - using fallback[/yellow]")
            
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
            
            # Check prerequisites before showing fallback models
            is_ready, _ = self._check_provider_prerequisites(provider_name)
            if not models and is_ready:
                models = self._get_fallback_litellm_models(provider_name)
            elif not is_ready:
                return []  # Prerequisites not met
            
            return models
            
        except Exception as e:
            self.console.print(f"[yellow]Warning: Failed to load models: {e}[/yellow]")
            return self._get_fallback_litellm_models(provider_name)
    
    def _get_fallback_litellm_models(self, provider_name: str) -> List[str]:
        fallback_models = {
            "openai": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo"],
            "claude": ["claude-3-5-sonnet-20241022", "claude-3-5-haiku-20241022"],
            "gemini": ["gemini-2.0-flash", "gemini-1.5-flash", "gemini-2.0-flash-exp"],
            "ollama": ["qwen2.5-coder:7b", "llama3.2:latest", "codellama:latest"],
            "openrouter": ["anthropic/claude-3.5-sonnet", "openai/gpt-4o", "deepseek/deepseek-chat-v3-0324:free"],
            "copilot": ["gpt-4o", "gpt-4o-mini", "claude-3.5-sonnet"]
        }
        return fallback_models.get(provider_name, [])
    
    async def _get_copilot_models(self) -> List[str]:
        """Get available GitHub Copilot models using the custom provider with API discovery."""
        try:
            from ..llm.providers import get_copilot_provider
            import asyncio
            
            provider = get_copilot_provider(quiet=True)
            
            # Use proper async model discovery 
            try:
                models_data = await asyncio.wait_for(provider.get_models(), timeout=10.0)
                discovered_models = [model.get("id", "") for model in models_data if model.get("id")]
                if discovered_models:
                    return discovered_models
            except asyncio.TimeoutError:
                self.console.print("[yellow]API discovery failed: Network timeout - using fallback models[/yellow]")
            except Exception as discovery_error:
                if "401" in str(discovery_error) or "403" in str(discovery_error):
                    self.console.print("[yellow]API discovery failed: Authentication error - check COPILOT_ACCESS_TOKEN[/yellow]")
                else:
                    self.console.print(f"[yellow]API discovery failed: {discovery_error} - using fallback models[/yellow]")
            
            # Fall back to static available models (sync method)
            try:
                discovered_models = provider.get_available_models()
            except Exception:
                discovered_models = ["gpt-4o", "gpt-4o-mini", "claude-3.5-sonnet"]
            
            if discovered_models:
                self.console.print(f"[dim]Found {len(discovered_models)} Copilot models via API discovery[/dim]")
                return discovered_models
            else:
                # Ultimate fallback
                return ["gpt-4o", "gpt-4o-mini", "claude-3.5-sonnet"]
                
        except Exception as e:
            self.console.print(f"[yellow]Could not get Copilot models: {e}[/yellow]")
            return ["gpt-4o", "gpt-4o-mini", "claude-3.5-sonnet"]
    
    def _resolve_litellm_model(self, provider_name: str, model_name: str) -> str:
        if provider_name == "copilot":
            return model_name  
        
        try:
            from ..config import load_provider_mapping
            config = load_provider_mapping()
            
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
                self.console.print("[yellow]   Attempting to use model anyway with LiteLLM...[/yellow]")
            
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
        try:
            available_models = self._get_litellm_models(provider_name)
            
            if model_name in available_models:
                return True
            
            self.console.print(f"[dim]Model '{model_name}' not in known list, allowing fallback attempt[/dim]")
            return True
            
        except Exception:
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
