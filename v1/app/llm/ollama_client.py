import requests
from llm.client import LLMClient
from typing import Dict, Any
import os
from dotenv import load_dotenv

load_dotenv()


class OllamaClient(LLMClient):
    def __init__(self, model_name: str):
        self.base_url = os.getenv("OLLAMA_HOST", "http://localhost:11434")
        self.model_name = model_name

    def chat(self, prompt: str, **kwargs) -> str:
        resp = requests.post(
            f"{self.base_url}/api/generate",
            json={
                "model": self.model_name,
                "prompt": prompt,
                **kwargs,  # optional: temperature, stream, etc.
            },
            timeout=60,
        )
        resp.raise_for_status()
        return resp.json()["response"]

    def chat_structured(self, prompt_template, inputs=None):
        def _runner(inp: Dict[str, Any]) -> str:
            value = prompt_template.invoke(inp)
            text = getattr(value, "content", value)
            return self.chat(text)

        if inputs is None:
            return _runner
        return _runner(inputs)
