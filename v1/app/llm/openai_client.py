# llm/openai_client.py

from langchain_openai import ChatOpenAI
from llm.client import LLMClient
import os
from dotenv import load_dotenv

load_dotenv()


class OpenAIClient(LLMClient):
    def __init__(self, model_name: str, temperature: float = 0):
        # ChatOpenAI 자체가 Runnable 이므로 invoke() 를 직접 씁니다
        self._llm = ChatOpenAI(
            model=model_name, temperature=temperature, openai_api_key=os.getenv("OPENAI_API_KEY")
        )

    def chat(self, prompt: str, **kwargs) -> str:
        """
        prompt: 순수 문자열
        invoke() → ChatPromptValue 혹은 BaseMessage 가 올 수 있으니 .content 로 꺼내기
        """
        result = self._llm.invoke(prompt)
        # ChatPromptValue 나 BaseMessage 에는 .content 가 있으니 꺼내보고
        if hasattr(result, "content"):
            return result.content
        # 아니면 str() 로 변환
        return str(result)

    def chat_structured(self, prompt_template, inputs=None):
        """
        prompt_template.invoke(inputs) → ChatPromptValue
        그 content 를 LLM에 다시 넘겨서 최종 문자열 얻기
        """

        def _runner(inp):
            # 1) prompt_template → ChatPromptValue
            value = prompt_template.invoke(inp)
            text = getattr(value, "content", str(value))
            # 2) 그 문자열을 chat() 으로 다시 호출
            return self.chat(text)

        if inputs is None:
            return _runner
        return _runner(inputs)
