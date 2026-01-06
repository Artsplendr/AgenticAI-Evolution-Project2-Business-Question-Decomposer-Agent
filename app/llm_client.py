from __future__ import annotations
import os
from openai import OpenAI
from .config import settings

def get_client() -> OpenAI:
    # Read at call-time to avoid early-import/ordering issues
    api_key = os.getenv("OPENAI_API_KEY") or settings.openai_api_key
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is missing. Put it in .env or environment variables.")
    return OpenAI(api_key=api_key)