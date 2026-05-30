"""
AI/ML API wrapper — used exclusively by SignalJobs endpoints.
Groq remains the AI for all other engines.
"""

import os
import httpx
from loguru import logger

AIML_API_KEY  = os.getenv("AIML_API_KEY", "")
AIML_BASE_URL = os.getenv("AIML_BASE_URL", "https://api.aimlapi.com/v1")


async def aiml_chat(prompt: str, max_tokens: int = 1200) -> str:
    """Call AI/ML API. Returns text, or '' on any failure (never raises)."""
    if not AIML_API_KEY:
        logger.warning("AIML_API_KEY not set - SignalJobs AI disabled")
        return ""
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            res = await client.post(
                f"{AIML_BASE_URL}/chat/completions",
                headers={"Authorization": f"Bearer {AIML_API_KEY}",
                         "Content-Type": "application/json"},
                json={"model": "gpt-4o",
                      "messages": [{"role": "user", "content": prompt}],
                      "temperature": 0.2, "max_tokens": max_tokens},
            )
            res.raise_for_status()
            return res.json()["choices"][0]["message"]["content"]
    except Exception as e:
        logger.error(f"AI/ML API error: {e}")
        return ""
