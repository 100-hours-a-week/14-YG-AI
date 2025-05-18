# llm/vertex_client.py

from typing import Any, Dict
import vertexai
from vertexai.generative_models import GenerativeModel, GenerationConfig
from llm.client import LLMClient
import os
from dotenv import load_dotenv

load_dotenv()


class VertexClient(LLMClient):
    def __init__(self, model_name: str, temperature: float = 0):
        # 1) 프로젝트 및 리전 초기화
        vertexai.init(
            project=os.getenv("GCP_PROJECT"),
            location=os.getenv("GCP_LOCATION"),
        )
        # 2) GenerativeModel 로딩
        self.model = GenerativeModel(model_name)
        # 3) temperature 저장 (send_message 호출 시 사용)
        self.temperature = temperature
        # 4) 채팅 세션 생성 (기본 옵션)
        self.chat_session = self.model.start_chat()

    def chat(self, prompt: str, **kwargs) -> str:
        """
        단일 프롬프트에 대해 응답 텍스트를 반환합니다.
        """
        # GenerationConfig 생성
        gen_config = GenerationConfig(temperature=self.temperature)
        # send_message 에 generation_config 전달
        response = self.chat_session.send_message(
            prompt, generation_config=gen_config, **kwargs
        )
        return response.text

    def chat_structured(self, prompt_template, inputs: Dict[str, Any] = None):
        """
        프롬프트 템플릿과 입력을 받아 형식화된 chat 함수를 반환합니다.
        """

        def _run(inp: Dict[str, Any]) -> str:
            text_prompt = prompt_template.format(**inp)
            return self.chat(text_prompt)

        if inputs is None:
            return _run
        return _run(inputs)
