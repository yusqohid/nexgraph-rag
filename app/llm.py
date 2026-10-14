"""Shared Gemini client and concurrency limit."""
import asyncio
from google import genai
from app.config import settings

request_semaphore = asyncio.Semaphore(5)
_client: genai.Client | None = None


def get_client() -> genai.Client:
    global _client
    if _client is None:
        api_key = settings.LLM_API_KEY.get_secret_value()
        if not api_key:
            raise RuntimeError("Set LLM_API_KEY to a Google AI Studio API key")
        _client = genai.Client(api_key=api_key)
    return _client


async def close_client() -> None:
    global _client
    if _client is not None:
        await _client.aio.aclose()
        _client.close()
        _client = None
