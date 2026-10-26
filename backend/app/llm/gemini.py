from __future__ import annotations

import os
import sys

from google import genai
from google.genai import types

from app.config import gemini_key
from app.llm.llm import Reply
from app.llm.retry import retry

DEFAULT_MODEL = "gemini-3.8-flash"  # override with the LLM_MODEL environment variable
DEFAULT_THINKING = "LOW"  # override with LLM_THINKING: MINIMAL, LOW, MEDIUM, HIGH, or DEFAULT for the model's own choice
# Override with LLM_TEMPERATURE: a number, or DEFAULT for the model's own (1.0). Google advises leaving Gemini 3 models at their
# default, as lower values can cause looping; 0 stays the default here because every saved answer was made with it.
DEFAULT_TEMPERATURE = "0"


def model_and_level() -> tuple[str, str]:
    """The model and thinking level in use. Together they are part of every cache key, because they change the answers."""
    return os.environ.get("LLM_MODEL", DEFAULT_MODEL), os.environ.get("LLM_THINKING", DEFAULT_THINKING).upper()


def temperature_setting() -> tuple[float | None, str]:
    """(temperature to send, or None to send none; the words for the cache key). At the default the key says nothing,
    so it stays the key every saved answer was made with."""
    value = os.environ.get("LLM_TEMPERATURE", DEFAULT_TEMPERATURE).strip().upper()
    if value == "DEFAULT":
        return None, ";temperature=DEFAULT"
    number = float(value)
    return (number, "") if number == float(DEFAULT_TEMPERATURE) else (number, f";temperature={number}")


class GeminiLLM:
    def __init__(self) -> None:
        key_name, key = gemini_key()
        self.client = genai.Client(api_key=key)
        self.model, level = model_and_level()
        self.temperature, temperature_key = temperature_setting()
        self.thinking = None if level == "DEFAULT" else types.ThinkingConfig(thinking_level=level)
        self.settings = f"thinking={level}{temperature_key}"
        print(f"[llm] key={key_name} model={self.model} thinking={level}{temperature_key}", file=sys.stderr)

    def generate(self, system: str, user: str) -> Reply:
        config = types.GenerateContentConfig(
            system_instruction=system, response_mime_type="application/json", temperature=self.temperature,
            thinking_config=self.thinking,
        )
        response = retry(lambda: self.client.models.generate_content(model=self.model, contents=user, config=config))
        usage = response.usage_metadata
        return Reply(
            text=response.text,
            input_tokens=usage.prompt_token_count or 0,
            output_tokens=(usage.candidates_token_count or 0) + (usage.thoughts_token_count or 0),
        )

    def transcribe(self, png: bytes, prompt: str) -> Reply:
        config = types.GenerateContentConfig(temperature=self.temperature, thinking_config=self.thinking)
        contents = [types.Part.from_bytes(data=png, mime_type="image/png"), prompt]
        response = retry(lambda: self.client.models.generate_content(model=self.model, contents=contents, config=config))
        usage = response.usage_metadata
        return Reply(
            text=response.text or "",
            input_tokens=usage.prompt_token_count or 0,
            output_tokens=(usage.candidates_token_count or 0) + (usage.thoughts_token_count or 0),
        )

    def count_tokens(self, system: str, user: str) -> int:
        """Gemini's own count of a question's input tokens. The Gemini API will not take a system instruction here, so the
        instruction is counted as a first part of the message."""
        return retry(lambda: self.client.models.count_tokens(model=self.model, contents=[system, user])).total_tokens or 0

