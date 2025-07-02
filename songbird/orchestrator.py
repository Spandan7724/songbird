# songbird/orchestrator.py
"""New clean orchestrator using separated UI/Agent/Tools architecture."""

from typing import Optional
from .llm.providers import BaseProvider
from .llm.unified_interface import create_provider_adapter
from .ui.ui_layer import UILayer
from .ui.data_transfer import UIMessage, AgentOutput
from .agent.agent_core import AgentCore
from .tools.tool_runner import ToolRunner
from .memory.models import Session
from .memory.optimized_manager import OptimizedSessionManager
from .config.config_manager import get_config_manager
from .core.signal_handler import setup_graceful_shutdown


class SongbirdOrchestrator:
    """Clean orchestrator that coordinates UI, Agent, and Tools layers."""
    
    def __init__(
        self, 
        provider: BaseProvider, 
        working_directory: str = ".",
        session: Optional[Session] = None,
        ui_layer: Optional[UILayer] = None
    ):
        self.provider = provider
        self.working_directory = working_directory
        self.session = session
        
        # Get configuration
        self.config_manager = get_config_manager()
        self.config = self.config_manager.get_config()
        
        # Create provider adapter for unified interface
        self.provider_adapter = create_provider_adapter(provider)
        
        # Initialize optimized session manager
        self.session_manager = OptimizedSessionManager(
            working_directory=working_directory,
            flush_interval=self.config.session.flush_interval,
            batch_size=self.config.session.batch_size
        )
        
        # Setup graceful shutdown handling
        self.shutdown_handler = setup_graceful_shutdown(
            session_manager=self.session_manager,
            console=None,  # Will use default console
            enable_async=True
        )
        
        # Initialize layers
        self.ui = ui_layer or UILayer()
        self.tool_runner = ToolRunner(working_directory, session.id if session else None, self.ui)
        
        # Register UI for shutdown
        self.shutdown_handler.register_ui_layer(self.ui)
        
        # Initialize agent core
        self.agent = AgentCore(
            provider=provider,
            tool_runner=self.tool_runner,
            session=session,
            session_manager=self.session_manager
        )
        
        # Register agent for shutdown
        self.shutdown_handler.register_conversation(self.agent)
    
    async def start_conversation(self) -> None:
        """Start the conversation loop."""
        # Display banner and welcome
        self.ui.display_banner()
        self.ui.display_welcome(
            provider_name=getattr(self.provider, '__class__', type(self.provider)).__name__.lower().replace('provider', ''),
            model_name=getattr(self.provider, 'model', 'unknown')
        )
        
        # Main conversation loop
        while True:
            try:
                # Get user input
                response = await self.ui.get_user_input("You")
                
                # Check for exit commands
                if response.content.lower() in ["exit", "quit", "bye"]:
                    self.ui.display_goodbye()
                    break
                
                # Skip empty input
                if not response.content.strip():
                    continue
                
                # Check if user cancelled
                if response.metadata and response.metadata.get("cancelled"):
                    continue
                
                # Show thinking indicator
                await self.ui.show_thinking("Processing...")
                
                try:
                    # Process message through agent
                    agent_output = await self.agent.handle_message(response.content)
                    
                    # Hide thinking indicator
                    await self.ui.hide_thinking()
                    
                    # Handle agent output
                    await self._handle_agent_output(agent_output)
                    
                except Exception as e:
                    await self.ui.hide_thinking()
                    error_message = UIMessage.error(f"Error processing request: {str(e)}")
                    await self.ui.display_message(error_message)
                    
            except KeyboardInterrupt:
                await self.ui.hide_thinking()
                self.ui.display_goodbye()
                await self.cleanup()
                break
            except Exception as e:
                await self.ui.hide_thinking()
                error_message = UIMessage.error(f"Unexpected error: {str(e)}")
                await self.ui.display_message(error_message)
    
    async def _handle_agent_output(self, output: AgentOutput) -> None:
        """Handle output from the agent core."""
        # Display any message
        if output.message:
            await self.ui.display_message(output.message)
        
        # Handle errors
        if output.error:
            error_message = UIMessage.error(output.error)
            await self.ui.display_message(error_message)
        
        # Handle choice prompts
        if output.choice_prompt:
            choice_response = await self.ui.present_choice(output.choice_prompt)
            # TODO: Pass choice back to agent if needed
        
        # Handle tool calls display (optional - tools may display their own output)
        if output.tool_calls:
            # Tool execution is handled internally by agent, but we could show progress here
            pass
    
    async def chat_single_message(self, message: str) -> str:
        """Process a single message and return the response (for testing)."""
        try:
            agent_output = await self.agent.handle_message(message)
            
            if agent_output.error:
                return f"Error: {agent_output.error}"
            elif agent_output.message:
                return agent_output.message.content
            else:
                return "No response generated"
                
        except Exception as e:
            return f"Error processing message: {str(e)}"
    
    async def chat(self, message: str, status=None) -> str:
        """Process a message and return the response (CLI compatibility)."""
        return await self.chat_single_message(message)
    
    @property
    def conversation_history(self) -> list:
        """Get the conversation history (CLI compatibility)."""
        return self.agent.get_conversation_history()
    
    @conversation_history.setter
    def conversation_history(self, value: list) -> None:
        """Set the conversation history (CLI compatibility)."""
        self.agent.conversation_history = value
    
    def get_conversation_history(self) -> list:
        """Get the conversation history."""
        return self.agent.get_conversation_history()
    
    def get_session(self) -> Optional[Session]:
        """Get the current session."""
        return self.session
    
    def set_session(self, session: Session) -> None:
        """Set the current session."""
        self.session = session
        self.agent.session = session
        # Update tool runner session ID
        self.tool_runner.session_id = session.id
    
    async def cleanup(self) -> None:
        """Cleanup resources and shutdown gracefully."""
        try:
            # Flush any pending session data
            if self.session_manager:
                await self.session_manager.shutdown()
            
            # Cleanup UI resources
            if hasattr(self.ui, 'cleanup'):
                await self.ui.cleanup()
            
            # Cleanup agent resources
            if hasattr(self.agent, 'cleanup'):
                await self.agent.cleanup()
                
        except Exception as e:
            # Don't let cleanup errors prevent shutdown
            print(f"Warning: Error during cleanup: {e}")
    
    def get_provider_info(self) -> dict:
        """Get information about the current provider."""
        return self.provider_adapter.get_provider_capabilities()
    
    def get_infrastructure_stats(self) -> dict:
        """Get statistics about infrastructure components."""
        stats = {
            "session_manager": self.session_manager.get_stats(),
            "provider": self.get_provider_info(),
            "config": {
                "flush_interval": self.config.session.flush_interval,
                "batch_size": self.config.session.batch_size,
                "max_iterations": self.config.agent.max_iterations,
                "token_budget": self.config.agent.token_budget
            }
        }
        
        if hasattr(self.tool_runner, 'get_stats'):
            stats["tool_runner"] = self.tool_runner.get_stats()
        
        return stats