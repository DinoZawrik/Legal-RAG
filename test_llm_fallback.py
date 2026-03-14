"""Test LLM fallback: Gemini -> OpenRouter"""
import asyncio
import os
import sys
sys.path.insert(0, '.')

from dotenv import load_dotenv
load_dotenv()

async def test():
    from core.ai_inference_core import EnhancedInferenceEngine
    engine = EnhancedInferenceEngine()
    await engine.initialize()
    
    model = engine.model_name
    llm_type = type(engine.llm).__name__
    print(f"Engine initialized! Model: {model}")
    print(f"LLM type: {llm_type}")
    
    # Quick test
    result = await engine.generate_response("Привет! Ответь одним словом.")
    success = result.get("success")
    text = result.get("response", result.get("error", "NO RESPONSE"))
    print(f"Response success: {success}")
    print(f"Response: {text[:300]}")

asyncio.run(test())
