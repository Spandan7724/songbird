#!/usr/bin/env python3

import os
import sys
sys.path.insert(0, '.')

from songbird.llm.providers import get_provider_info

print("Testing provider info...")
print("Environment variables:")
print(f"GOOGLE_API_KEY: {repr(os.getenv('GOOGLE_API_KEY'))}")
print(f"OPENAI_API_KEY: {repr(os.getenv('OPENAI_API_KEY'))}")
print(f"ANTHROPIC_API_KEY: {repr(os.getenv('ANTHROPIC_API_KEY'))}")
print()

provider_info = get_provider_info()

for name, info in provider_info.items():
    if name in ['gemini', 'openai']:
        print(f"{name}:")
        print(f"  available: {info['available']}")
        print(f"  api_key_env: {info['api_key_env']}")
        print(f"  description: {info['description']}")
        print()