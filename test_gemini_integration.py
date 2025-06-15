#!/usr/bin/env python3
"""
Test script for Gemini integration.
Run with: GOOGLE_API_KEY="your-real-key" python test_gemini_integration.py
"""
import asyncio
import os
import sys
sys.path.insert(0, '.')

from songbird.llm.providers import GeminiProvider
from songbird.tools.registry import get_tool_schemas

async def test_gemini():
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        print("❌ No GOOGLE_API_KEY found. Set the environment variable and try again.")
        print("Get your API key from: https://aistudio.google.com/app/apikey")
        return
    
    if api_key == "test" or "fake" in api_key.lower():
        print("❌ Fake API key detected. Please use a real API key for testing.")
        return
    
    try:
        print("🚀 Testing Gemini provider...")
        provider = GeminiProvider(api_key=api_key, model="gemini-2.0-flash-001")
        
        # Test basic chat
        print("💬 Testing basic chat...")
        response = provider.chat("Hello! Can you say hi back?")
        print(f"✅ Basic chat works: {response.content[:100]}...")
        
        # Test with tools
        print("🔧 Testing with tools...")
        tools = get_tool_schemas()
        response = provider.chat("What tools do you have available?", tools=tools)
        print(f"✅ Tools chat works: {response.content[:100]}...")
        
        # Test function calling
        print("⚙️ Testing function calling...")
        response = provider.chat("Create a file called test.txt with 'Hello World'", tools=tools)
        if response.tool_calls:
            print(f"✅ Function calling works! Tool calls: {len(response.tool_calls)}")
            for i, call in enumerate(response.tool_calls):
                if hasattr(call, 'function'):
                    print(f"  Call {i+1}: {call.function.name}")
                else:
                    print(f"  Call {i+1}: {call}")
        else:
            print("⚠️ No tool calls made (this might be expected depending on the model's response)")
        
        print("🎉 All tests passed! Gemini integration is working.")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        if "API_KEY" in str(e):
            print("Please check your API key is valid and has the required permissions.")

if __name__ == "__main__":
    asyncio.run(test_gemini())