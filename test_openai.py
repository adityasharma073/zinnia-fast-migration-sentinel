#!/usr/bin/env python3
"""
Quick test to verify OpenAI integration is working
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Add parent dir to path
sys.path.insert(0, str(Path(__file__).parent))

# Load env
load_dotenv()

print("🔍 Testing OpenAI Integration...\n")

# Check .env file
api_key = os.getenv('OPENAI_API_KEY')
if api_key:
    print("✅ OPENAI_API_KEY found in .env")
    print(f"   Key starts with: {api_key[:20]}...")
else:
    print("❌ OPENAI_API_KEY NOT found in .env")
    sys.exit(1)

# Check OpenAI library
try:
    from openai import OpenAI
    print("✅ OpenAI library installed")
except ImportError:
    print("❌ OpenAI library NOT installed")
    print("   Run: pip install openai")
    sys.exit(1)

# Try to initialize client
try:
    client = OpenAI(api_key=api_key)
    print("✅ OpenAI client initialized successfully")
except Exception as e:
    print(f"❌ Failed to initialize OpenAI client: {e}")
    sys.exit(1)

# Quick API test
print("\n🧪 Testing API call (this will use your credits)...")
try:
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Say 'OpenAI integration successful!' in exactly those words."}
        ],
        max_tokens=50
    )
    
    result = response.choices[0].message.content
    print(f"✅ API call successful!")
    print(f"   GPT-4 response: {result}")
    
except Exception as e:
    print(f"❌ API call failed: {e}")
    sys.exit(1)

print("\n" + "="*60)
print("🎉 All tests passed! OpenAI integration is working!")
print("="*60)
