from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Union, Callable


class LLMClient(ABC):
    @abstractmethod
    def chat(self, prompt: str, **kwargs) -> str:
        """단순 텍스트 질의 응답"""
        ...

    @abstractmethod
    def chat_structured(
        self, prompt_template: Any, inputs: Optional[Dict[str, Any]] = None
    ) -> Union[str, Callable[[Dict[str, Any]], str]]:
        """
        • chat_structured(prompt_template) → (inputs)->str 러너블 반환
        • chat_structured(prompt_template, inputs) → 즉시 str 반환
        """
        ...
