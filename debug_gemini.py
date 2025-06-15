#!/usr/bin/env python3

import os
import asyncio
import warnings
warnings.filterwarnings("ignore", message=".*non-text parts.*")

from songbird.llm.providers import get_provider
from songbird.conversation import ConversationOrchestrator  
from songbird.tools.executor import ToolExecutor

async def test_gemini_function_calling():
    # Set up the test
    os.environ['GOOGLE_API_KEY'] = 'AIzaSyC-nfnquCpVhTiTVMUc0_B59e_v4nixZ5Y'
    
    print("Testing Gemini function calling...")
    
    # Create provider and orchestrator
    from songbird.llm.providers import GeminiProvider
    provider = GeminiProvider(api_key='AIzaSyC-nfnquCpVhTiTVMUc0_B59e_v4nixZ5Y')
    tool_executor = ToolExecutor()
    orchestrator = ConversationOrchestrator(provider, tool_executor)
    
    # Test simple file creation
    print("\n=== Testing file creation ===")
    response = await orchestrator.chat('create a file called debug_test.txt with content: Hello World')
    print(f"Response: {response}")
    
    # Check if file was created
    if os.path.exists('debug_test.txt'):
        print("✅ File was created successfully!")
        with open('debug_test.txt', 'r') as f:
            content = f.read()
        print(f"Content: {content}")
        os.remove('debug_test.txt')  # Clean up
    else:
        print("❌ File was NOT created")

if __name__ == '__main__':
    asyncio.run(test_gemini_function_calling())