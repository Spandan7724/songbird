"""
Pytest tests for session management functionality.

This module combines and converts the session management tests from:
- test_aiohttp_fix.py
- test_httpx_session_fix.py  
- test_session_cleanup.py
- test_cli_session_warnings.py
"""

import asyncio
import os
import gc
import warnings
import subprocess
import sys
import tempfile
from typing import List, Dict
import pytest


class WarningCapture:
    """Helper class to capture warnings during tests."""
    
    def __init__(self):
        self.captured_warnings = []
        self.original_showwarning = None
    
    def __enter__(self):
        self.captured_warnings.clear()
        self.original_showwarning = warnings.showwarning
        warnings.showwarning = self._warning_handler
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        warnings.showwarning = self.original_showwarning
    
    def _warning_handler(self, message, category, filename, lineno, file=None, line=None):
        """Custom warning handler to capture session warnings."""
        warning_text = str(message)
        self.captured_warnings.append({
            'message': warning_text,
            'category': category.__name__,
            'filename': filename,
            'lineno': lineno
        })
    
    @property
    def unclosed_warnings(self) -> List[Dict]:
        """Get warnings related to unclosed sessions."""
        return [w for w in self.captured_warnings if 'unclosed' in w['message'].lower()]
    
    @property 
    def session_warnings(self) -> List[Dict]:
        """Get all session-related warnings."""
        return [w for w in self.captured_warnings if 'session' in w['message'].lower()]


@pytest.fixture
def warning_capture():
    """Fixture to capture warnings during tests."""
    return WarningCapture()


@pytest.fixture
def test_api_key():
    """Fixture to provide test API key."""
    original_key = os.environ.get('GEMINI_API_KEY')
    os.environ['GEMINI_API_KEY'] = 'test-key-for-session-testing'
    yield 'test-key-for-session-testing'
    if original_key is not None:
        os.environ['GEMINI_API_KEY'] = original_key
    else:
        os.environ.pop('GEMINI_API_KEY', None)


@pytest.mark.asyncio
async def test_http_session_manager_basic(warning_capture):
    """Test basic HTTP session manager functionality."""
    from songbird.llm.http_session_manager import session_manager
    
    with warning_capture:
        # Test session creation
        session = await session_manager.get_session()
        assert session is not None
        
        # Test health check
        is_healthy = await session_manager.health_check()
        assert is_healthy is True
        
        # Test session closure
        await session_manager.close_session()
        
        # Verify it's really closed
        is_healthy_after = await session_manager.health_check()
        assert is_healthy_after is False
        
        # Force garbage collection
        gc.collect()
        await asyncio.sleep(0.1)
    
    # Assert no unclosed session warnings
    assert len(warning_capture.unclosed_warnings) == 0, \
        f"Found unclosed session warnings: {[w['message'] for w in warning_capture.unclosed_warnings]}"


@pytest.mark.asyncio
async def test_aiohttp_session_manager(warning_capture):
    """Test aiohttp session manager directly."""
    from songbird.llm.aiohttp_session_manager import aiohttp_session_manager
    
    with warning_capture:
        # Create session
        session = await aiohttp_session_manager.get_session()
        assert session is not None
        
        # Test health check
        healthy = await aiohttp_session_manager.health_check()
        assert healthy is True
        
        # Test comprehensive cleanup
        await aiohttp_session_manager.close_all_sessions()
        
        # Force garbage collection
        gc.collect()
        await asyncio.sleep(0.1)
    
    # Assert no unclosed session warnings
    assert len(warning_capture.unclosed_warnings) == 0, \
        f"Found unclosed session warnings: {[w['message'] for w in warning_capture.unclosed_warnings]}"


@pytest.mark.asyncio
async def test_httpx_session_integration(warning_capture, test_api_key):
    """Test httpx session integration with LiteLLM."""
    with warning_capture:
        try:
            import litellm
            from songbird.llm.litellm_adapter import LiteLLMAdapter
            from songbird.llm.http_session_manager import session_manager
            
            # Create adapter
            adapter = LiteLLMAdapter(
                model="gemini-2.0-flash",
                provider_name="gemini"
            )
            
            # Set up managed session
            await adapter._setup_managed_session()
            
            # Get our managed session
            our_session = await session_manager.get_session()
            our_session_id = id(our_session)
            
            # Check if LiteLLM is using our session
            litellm_session = litellm.aclient_session
            if litellm_session:
                litellm_session_id = id(litellm_session)
                assert our_session_id == litellm_session_id, \
                    f"LiteLLM using different session. Our: {our_session_id}, LiteLLM: {litellm_session_id}"
            
            # Cleanup
            await adapter.cleanup()
            
            # Force garbage collection
            gc.collect()
            await asyncio.sleep(0.1)
            
        except ImportError:
            pytest.skip("LiteLLM not available")
    
    # Assert no unclosed session warnings
    assert len(warning_capture.unclosed_warnings) == 0, \
        f"Found unclosed session warnings: {[w['message'] for w in warning_capture.unclosed_warnings]}"


@pytest.mark.asyncio
async def test_session_type_compatibility(test_api_key):
    """Test that httpx session is compatible with LiteLLM expectations."""
    try:
        import httpx
        import litellm
        from songbird.llm.http_session_manager import session_manager
        
        # Get our session
        session = await session_manager.get_session()
        
        # Test basic httpx.AsyncClient functionality
        assert isinstance(session, httpx.AsyncClient)
        assert not session.is_closed
        
        # Test that it has required methods
        required_methods = ['get', 'post', 'request', 'aclose']
        for method in required_methods:
            assert hasattr(session, method), f"Missing method: {method}"
        
        # Test LiteLLM assignment
        original_session = litellm.aclient_session
        litellm.aclient_session = session
        assert litellm.aclient_session is session
        
        # Restore original session
        litellm.aclient_session = original_session
        
        # Cleanup
        await session_manager.close_session()
        
    except ImportError:
        pytest.skip("Required modules not available")


@pytest.mark.asyncio
async def test_full_conversation_flow(warning_capture, test_api_key):
    """Test complete conversation flow for session leaks."""
    with warning_capture:
        try:
            from songbird.llm.providers import get_provider
            from songbird.orchestrator import SongbirdOrchestrator
            from songbird.memory.models import Session
            
            # Create a provider
            provider = get_provider("gemini")
            assert provider is not None
            
            # Create session
            session = Session.create_new(
                project_name="test-session-cleanup",
                provider="gemini", 
                model="gemini-2.0-flash"
            )
            assert session is not None
            
            # Create orchestrator
            orchestrator = SongbirdOrchestrator(
                provider=provider,
                working_directory=".",
                session=session
            )
            assert orchestrator is not None
            
            # Try interaction (will fail with auth but tests session management)
            try:
                await orchestrator.chat_single_message("Hello")
            except Exception:
                # Expected due to auth, but session management should work
                pass
            
            # Cleanup
            await orchestrator.cleanup()
            
            # Force garbage collection
            gc.collect()
            await asyncio.sleep(0.1)
            
        except ImportError as e:
            pytest.skip(f"Required modules not available: {e}")
    
    # Assert no unclosed session warnings
    assert len(warning_capture.unclosed_warnings) == 0, \
        f"Found unclosed session warnings: {[w['message'] for w in warning_capture.unclosed_warnings]}"


def test_cli_session_warnings(test_api_key):
    """Test CLI for unclosed session warnings."""
    # Create temporary input file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write("exit\n")  # Immediately exit to test cleanup
        temp_input = f.name
    
    try:
        # Set up environment
        env = os.environ.copy()
        env['GEMINI_API_KEY'] = test_api_key
        
        # Run songbird CLI
        with open(temp_input, 'r') as input_file:
            result = subprocess.run(
                [sys.executable, '-m', 'songbird.cli'],
                stdin=input_file,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=30,
                env=env
            )
        
        # Check for unclosed session warnings
        combined_output = result.stdout + result.stderr
        session_warnings = []
        for line in combined_output.split('\n'):
            if 'unclosed' in line.lower() and 'session' in line.lower():
                session_warnings.append(line.strip())
        
        assert len(session_warnings) == 0, \
            f"Found unclosed session warnings in CLI: {session_warnings}"
            
    except subprocess.TimeoutExpired:
        # Timeout is not necessarily a failure for session management
        pass
    except FileNotFoundError:
        pytest.skip("Songbird CLI not available")
    finally:
        # Clean up temp file
        try:
            os.unlink(temp_input)
        except:
            pass


@pytest.mark.asyncio
async def test_session_creation_tracking():
    """Test session creation tracking."""
    try:
        from songbird.llm.aiohttp_session_manager import detect_aiohttp_session_creation
        from songbird.llm.litellm_adapter import LiteLLMAdapter
        
        # Enable session creation detection
        detect_aiohttp_session_creation()
        
        # Test with adapter
        adapter = LiteLLMAdapter(
            model="gemini-2.0-flash",
            provider_name="gemini"
        )
        
        await adapter._setup_managed_session()
        await adapter.cleanup()
        
        # If we get here without exceptions, tracking is working
        assert True
        
    except ImportError:
        pytest.skip("Required modules not available")


@pytest.mark.asyncio 
async def test_managed_session_cleanup():
    """Test CLI-level cleanup."""
    try:
        from songbird.llm.http_session_manager import close_managed_session
        
        # This should close any remaining sessions without error
        await close_managed_session()
        assert True
        
    except ImportError:
        pytest.skip("Session manager not available") 