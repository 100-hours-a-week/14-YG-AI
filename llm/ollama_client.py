import requests
from llm.client import LLMClient
from config import OLLAMA_HOST
from typing import Dict, Any


class OllamaClient(LLMClient):
    def __init__(self, model_name: str):
        self.url = f"{OLLAMA_HOST}/v1/models/{model_name}/chat"

    def chat(self, prompt: str, **kwargs) -> str:
        resp = requests.post(self.url, json={"prompt": prompt})
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]

    def chat_structured(self, prompt_template, inputs=None):
        def _runner(inp: Dict[str, Any]) -> str:
            value = prompt_template.invoke(inp)
            text = getattr(value, "content", value)
            return self.chat(text)

        if inputs is None:
            return _runner
        return _runner(inputs)
