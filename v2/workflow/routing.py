# workflow/routing.py
import json
import re
import logging
from typing import Dict, Any, List

from langchain_core.messages import BaseMessage, HumanMessage

from config import settings
from .agents import AgentFactory
from .prompts import format_supervisor_prompt, get_supervisor_prompt


logger = logging.getLogger(__name__)


class RouterDecision:
    """라우팅 결정 결과를 담는 클래스"""

    def __init__(
        self,
        selected_agent: str,
        confidence: float,
        reasoning: str,
        task_description: str = "",
    ):
        self.selected_agent = selected_agent
        self.confidence = confidence
        self.reasoning = reasoning
        self.task_description = task_description

    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return {
            "selected_agent": self.selected_agent,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "task_description": self.task_description,
        }

    def __str__(self) -> str:
        return (
            f"RouterDecision(agent={self.selected_agent}, confidence={self.confidence})"
        )


class MessageRouter:
    """메시지 라우팅을 담당하는 클래스"""

    def __init__(self):
        self.supervisor_llm = AgentFactory.get_supervisor_llm()
        self.agent_mapping = {
            "CHAT": "chat",
            "SEARCH": "search",
            "PARTICIPATE": "participate",
            "CREATE": "create",
        }
        # ❗️ 프롬프트 템플릿을 인스턴스 변수로 저장
        self.supervisor_prompt_template = get_supervisor_prompt()

    async def route_message(self, messages: List[BaseMessage]) -> RouterDecision:
        """
        메시지 리스트(전체 대화 맥락)를 분석하여 적절한 에이전트로 라우팅
        """
        if not messages:
            return self._create_fallback_decision("메시지가 없습니다.")

        try:
            # LLM을 통한 지능형 라우팅
            decision = await self._llm_based_routing(
                messages
            )  # 이제 전체 messages를 전달

            # 결정 후처리
            decision = self._post_process_decision(decision)

            logger.info(
                f"🧠 라우팅 결정 [마지막 메시지: {messages[-1].content[:30]}...] "
                f"[선택: {decision.selected_agent}] [신뢰도: {decision.confidence:.2f}]"
            )

            return decision

        except Exception as e:
            logger.error(f"❌ 라우팅 오류: {e}", exc_info=True)
            return self._create_fallback_decision(f"라우팅 처리 중 오류: {str(e)}")

    async def _llm_based_routing(self, messages: List[BaseMessage]) -> RouterDecision:
        """
        LLM을 사용한 지능형 라우팅 (전체 대화 맥락 사용)
        """
        # 1. 프롬프트에 필요한 정보 추출
        last_message = messages[-1].content

        chat_history = ""
        current_agent = "None"  # 기본값

        # 마지막 메시지를 제외하고 대화 기록 생성
        for msg in reversed(messages[:-1]):
            role = "User" if isinstance(msg, HumanMessage) else "Assistant"
            chat_history += f"{role}: {msg.content}\n"

            # 마지막 AI 응답에서 에이전트 이름 찾기 (가장 최근 것만)
            if role == "Assistant" and current_agent == "None":
                current_agent = msg.additional_kwargs.get("agent", "None")

        # 2. 슈퍼바이저 프롬프트 생성
        final_prompt = self.supervisor_prompt_template.format(
            last_message=last_message,
            chat_history=chat_history.strip(),
            current_agent=current_agent,
        )
        print("-----------------------")
        print("대화 기록:\n", chat_history.strip())
        print("-----------------------")
        # LLM 호출
        response = await self.supervisor_llm.ainvoke(final_prompt)

        # JSON 응답 파싱
        decision_data = self._parse_llm_response(response.content)

        # RouterDecision 객체 생성
        return RouterDecision(
            selected_agent=decision_data.get("selected_agent", "CHAT"),
            confidence=decision_data.get("confidence", 0.5),
            reasoning=decision_data.get("reasoning", "LLM 응답 파싱 결과"),
            task_description=decision_data.get("task_description", ""),
        )

    def _parse_llm_response(self, response_content: str) -> Dict[str, Any]:
        """
        LLM 응답에서 JSON 파싱

        Args:
            response_content: LLM 응답 내용

        Returns:
            Dict[str, Any]: 파싱된 결정 데이터
        """
        try:
            # JSON 블록 찾기
            json_match = re.search(r"\{.*\}", response_content, re.DOTALL)
            if json_match:
                decision_data = json.loads(json_match.group())

                # 필수 필드 검증
                required_fields = ["selected_agent", "confidence", "reasoning"]
                for field in required_fields:
                    if field not in decision_data:
                        raise ValueError(f"필수 필드 누락: {field}")

                return decision_data
            else:
                raise ValueError("JSON 형식을 찾을 수 없음")

        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"⚠️ LLM 응답 파싱 실패: {e}")

            # 규칙 기반 폴백
            return self._rule_based_fallback(response_content)

    def _rule_based_fallback(self, message: str) -> Dict[str, Any]:
        """
        규칙 기반 폴백 라우팅

        Args:
            message: 분석할 메시지

        Returns:
            Dict[str, Any]: 폴백 결정 데이터
        """
        message_lower = message.lower()

        # 공구 생성 관련 키워드
        create_keywords = [
            "공구 만들",
            "공구 생성",
            "공구 올려",
            "새 공구",
            "공구 개설",
        ]
        if any(keyword in message_lower for keyword in create_keywords):
            return {
                "selected_agent": "CREATE",
                "confidence": 0.8,
                "reasoning": "규칙 기반: 공구 생성 키워드 감지",
                "task_description": "공구 생성 요청",
            }

        # 검색 관련 키워드
        search_keywords = [
            "있어?",
            "찾아",
            "검색",
            "추천",
            "뭐 있",
        ]
        if any(keyword in message_lower for keyword in search_keywords):
            return {
                "selected_agent": "SEARCH",
                "confidence": 0.7,
                "reasoning": "규칙 기반: 검색 키워드 감지",
                "task_description": "공구 검색 요청",
            }

        # 기본값: 채팅
        return {
            "selected_agent": "CHAT",
            "confidence": 0.6,
            "reasoning": "규칙 기반: 기본 대화로 처리",
            "task_description": "일반 대화",
        }

    def _post_process_decision(self, decision: RouterDecision) -> RouterDecision:
        """
        라우팅 결정 후처리

        Args:
            decision: 원본 결정

        Returns:
            RouterDecision: 후처리된 결정
        """
        # 에이전트 이름 매핑
        if decision.selected_agent in self.agent_mapping:
            decision.selected_agent = self.agent_mapping[decision.selected_agent]

        # 신뢰도가 낮으면 CHAT으로 폴백
        if decision.confidence < 0.7:
            decision.selected_agent = "chat"
            decision.reasoning += " (낮은 신뢰도로 인한 CHAT 폴백)"

        return decision

    def _create_fallback_decision(self, reason: str) -> RouterDecision:
        """
        폴백 라우팅 결정 생성

        Args:
            reason: 폴백 사유

        Returns:
            RouterDecision: 폴백 결정
        """
        return RouterDecision(
            selected_agent="chat",
            confidence=0.5,
            reasoning=f"폴백 라우팅: {reason}",
            task_description="기본 대화",
        )


# =============================================================================
# 라우팅 유틸리티 함수들
# =============================================================================


def create_message_router() -> MessageRouter:
    """MessageRouter 인스턴스 생성"""
    return MessageRouter()


def validate_routing_decision(decision: RouterDecision) -> Dict[str, Any]:
    """
    라우팅 결정 유효성 검증

    Args:
        decision: 검증할 결정

    Returns:
        Dict[str, Any]: 검증 결과
    """
    valid_agents = ["chat", "search", "participate", "create"]

    errors = []

    if decision.selected_agent not in valid_agents:
        errors.append(f"유효하지 않은 에이전트: {decision.selected_agent}")

    if not (0.0 <= decision.confidence <= 1.0):
        errors.append(f"신뢰도 범위 오류: {decision.confidence}")

    if not decision.reasoning or len(decision.reasoning.strip()) == 0:
        errors.append("라우팅 이유가 비어있음")

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "decision": decision.to_dict(),
    }


def analyze_message_intent(message: str) -> Dict[str, Any]:
    """
    메시지 의도 분석 (라우팅 참고용)

    Args:
        message: 분석할 메시지

    Returns:
        Dict[str, Any]: 의도 분석 결과
    """
    message_lower = message.lower()

    # 키워드 기반 의도 분석
    intent_keywords = {
        "search": ["찾아", "검색", "있어?", "추천", "뭐 있", "어떤", "리스트"],
        "create": ["만들", "생성", "올려", "개설", "등록", "새로운"],
        "chat": ["안녕", "안부", "심심", "기분", "날씨", "시간", "도움말"],
        "question": ["?", "어떻게", "왜", "언제", "어디서", "무엇"],
    }

    detected_intents = []
    for intent, keywords in intent_keywords.items():
        if any(keyword in message_lower for keyword in keywords):
            detected_intents.append(intent)

    # 메시지 특성 분석
    characteristics = {
        "length": len(message),
        "has_question": "?" in message,
        "has_emoji": any(ord(char) > 127 for char in message),
        "word_count": len(message.split()),
        "detected_intents": detected_intents,
        "primary_intent": detected_intents[0] if detected_intents else "unknown",
    }

    return characteristics


# 전역 라우터 인스턴스 (싱글톤 패턴)
_global_router = None
_global_analyzer = None


def get_global_router() -> MessageRouter:
    """전역 라우터 인스턴스 반환"""
    global _global_router
    if _global_router is None:
        _global_router = create_message_router()
    return _global_router


if __name__ == "__main__":
    # 라우팅 테스트
    import asyncio
    from datetime import datetime

    async def test_routing():
        print("🧭 라우팅 시스템 테스트...")

        router = create_message_router()
        test_messages = [
            "안녕하세요!",
            "이클립스 공구 있어?",
            "공구 만들고 싶어요",
            "간식 추천해줘",
            "오늘 기분이 좋아요",
        ]

        for msg in test_messages:
            try:
                # 가짜 메시지 객체 생성
                fake_message = type("Message", (), {"content": msg})()
                decision = await router.route_message([fake_message])

                print(f"📝 메시지: '{msg}'")
                print(f"   🎯 선택된 에이전트: {decision.selected_agent}")
                print(f"   📊 신뢰도: {decision.confidence:.2f}")
                print(f"   💭 이유: {decision.reasoning}")
                print()
            except Exception as e:
                print(f"❌ 테스트 오류 ['{msg}']: {e}")

    asyncio.run(test_routing())
