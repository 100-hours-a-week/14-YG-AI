# workflow/agents.py
import os
from datetime import datetime
from typing import List

from langchain_google_vertexai import ChatVertexAI
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent

from config import settings
from tools.search_post_tool import search_group_buy
from tools.create_post_tool import create_post

# =============================================================================
# 공통 도구들
# =============================================================================


@tool
def get_current_time() -> str:
    """현재 시간을 가져옵니다."""
    print(f"--- [TOOL] get_current_time() ---")
    return datetime.now().strftime("%Y년 %m월 %d일 %H시 %M분")


# @tool
# def request_human_approval(task_description: str, details: str) -> str:
#     """사용자 승인을 요청합니다."""
#     return f"🔔 사용자 승인이 필요합니다.\n작업: {task_description}\n상세: {details}"


@tool
def request_additional_info(question: str, context: str = "") -> str:
    """추가 정보 요청 (승인과 무관)"""
    return f"❓ {question}\n{context}"


# =============================================================================
# LLM 생성 함수
# =============================================================================


def create_base_llm(temperature: float = None) -> ChatVertexAI:
    """
    기본 LLM 인스턴스 생성

    Args:
        temperature: 온도 설정 (None이면 기본값 사용)

    Returns:
        ChatVertexAI: LLM 인스턴스
    """
    temp = (
        temperature
        if temperature is not None
        else settings.workflow.default_agent_temperature
    )

    return ChatVertexAI(
        model_name=settings.google_cloud.model_name,
        temperature=temp,
        project=settings.google_cloud.project,
        location=settings.google_cloud.location,
    )


# =============================================================================
# 에이전트 생성 함수들
# =============================================================================


def create_chat_agent():
    """일상 대화 및 감정 지원 에이전트"""

    llm = create_base_llm(temperature=0.7)
    tools = [get_current_time]

    from .prompts import get_chat_agent_prompt

    prompt = get_chat_agent_prompt()

    return create_react_agent(
        model=llm,
        tools=tools,
        name="chat_agent",
        prompt=prompt,
    )


def create_search_agent():
    """공구 검색 및 추천 에이전트"""

    llm = create_base_llm(temperature=0.0)
    tools = [search_group_buy]

    from .prompts import get_search_agent_prompt

    prompt = get_search_agent_prompt()

    return create_react_agent(
        model=llm,
        tools=tools,
        name="search_agent",
        prompt=prompt,
    )


def create_create_agent():
    """공구 생성 에이전트"""

    llm = create_base_llm(temperature=0.0)
    tools = [create_post, request_additional_info]

    from .prompts import get_create_agent_prompt

    prompt = get_create_agent_prompt()

    return create_react_agent(
        model=llm,
        tools=tools,
        name="create_agent",
        prompt=prompt,
    )


def create_participate_agent():
    """공구 참여 및 생성 에이전트"""

    llm = create_base_llm(temperature=0.0)
    tools = [request_additional_info]

    from .prompts import get_participate_agent_prompt

    prompt = get_participate_agent_prompt()

    return create_react_agent(
        model=llm,
        tools=tools,
        name="participate_agent",
        prompt=prompt,
    )


def create_supervisor_llm():
    """슈퍼바이저용 LLM 생성"""
    return create_base_llm(temperature=settings.workflow.supervisor_temperature)


# =============================================================================
# 에이전트 팩토리 클래스
# =============================================================================


class AgentFactory:
    """에이전트 생성을 관리하는 팩토리 클래스"""

    _agents_cache = {}

    @classmethod
    def get_chat_agent(cls):
        """캐시된 채팅 에이전트 반환"""
        if "chat_agent" not in cls._agents_cache:
            cls._agents_cache["chat_agent"] = create_chat_agent()
        return cls._agents_cache["chat_agent"]

    @classmethod
    def get_search_agent(cls):
        """캐시된 검색 에이전트 반환"""
        if "search_agent" not in cls._agents_cache:
            cls._agents_cache["search_agent"] = create_search_agent()
        return cls._agents_cache["search_agent"]

    @classmethod
    def get_participate_agent(cls):
        """캐시된 참여 에이전트 반환"""
        if "participate_agent" not in cls._agents_cache:
            cls._agents_cache["participate_agent"] = create_participate_agent()
        return cls._agents_cache["participate_agent"]

    @classmethod
    def get_create_agent(cls):
        """캐시된 공구 생성 에이전트 반환"""
        if "create_agent" not in cls._agents_cache:
            cls._agents_cache["create_agent"] = create_create_agent()
        return cls._agents_cache["create_agent"]

    @classmethod
    def get_supervisor_llm(cls):
        """캐시된 슈퍼바이저 LLM 반환"""
        if "supervisor_llm" not in cls._agents_cache:
            cls._agents_cache["supervisor_llm"] = create_supervisor_llm()
        return cls._agents_cache["supervisor_llm"]

    @classmethod
    def clear_cache(cls):
        """에이전트 캐시 초기화"""
        cls._agents_cache.clear()

    @classmethod
    def get_all_agents(cls) -> dict:
        """모든 에이전트 반환"""
        return {
            "chat_agent": cls.get_chat_agent(),
            "search_agent": cls.get_search_agent(),
            "participate_agent": cls.get_participate_agent(),
            "create_agent": cls.get_create_agent(),
        }


# =============================================================================
# 에이전트 정보 및 유틸리티
# =============================================================================


def get_agent_info() -> dict:
    """에이전트들의 정보 반환"""
    return {
        "chat_agent": {
            "name": "대화 에이전트",
            "description": "일상 대화 및 감정 지원",
            "tools": ["get_current_time"],
            "temperature": 0.7,
        },
        "search_agent": {
            "name": "검색 에이전트",
            "description": "공구 검색 및 추천",
            "tools": ["search_group_buy"],
            "temperature": 0.0,
        },
        "participate_agent": {
            "name": "공구참여 에이전트",
            "description": "공구 참여",
            "tools": ["request_additional_info"],
            "temperature": 0.2,
        },
        "create_agent": {
            "name": "공구생성 에이전트",
            "description": "공구 생성",
            "tools": ["create_post", "request_additional_info"],
            "temperature": 0.0,
        },
    }


def validate_agent_configuration() -> dict:
    """에이전트 설정 검증"""
    try:
        # 기본 LLM 생성 테스트
        test_llm = create_base_llm()

        # 각 에이전트 생성 테스트
        agents_status = {}

        try:
            chat_agent = create_chat_agent()
            agents_status["chat_agent"] = {"status": "ok", "name": chat_agent.name}
        except Exception as e:
            agents_status["chat_agent"] = {"status": "error", "error": str(e)}

        try:
            search_agent = create_search_agent()
            agents_status["search_agent"] = {"status": "ok", "name": search_agent.name}
        except Exception as e:
            agents_status["search_agent"] = {"status": "error", "error": str(e)}

        try:
            participate_agent = create_participate_agent()
            agents_status["participate_agent"] = {
                "status": "ok",
                "name": participate_agent.name,
            }
        except Exception as e:
            agents_status["participate_agent"] = {"status": "error", "error": str(e)}

        try:
            create_agent = create_create_agent()
            agents_status["create_agent"] = {
                "status": "ok",
                "name": create_agent.name,
            }
        except Exception as e:
            agents_status["create_agent"] = {"status": "error", "error": str(e)}

        return {
            "overall_status": "ok",
            "llm_config": {
                "model": settings.google_cloud.model_name,
                "project": settings.google_cloud.project,
                "location": settings.google_cloud.location,
            },
            "agents": agents_status,
        }

    except Exception as e:
        return {
            "overall_status": "error",
            "error": str(e),
            "agents": {},
        }


# =============================================================================
# 에이전트 실행 래퍼 함수들
# =============================================================================


async def run_agent_safe(agent, messages: List, config=None):
    """
    안전한 에이전트 실행 (에러 처리 포함)

    Args:
        agent: 실행할 에이전트
        messages: 메시지 리스트
        config: 실행 설정

    Returns:
        dict: 실행 결과
    """
    try:
        result = await agent.ainvoke({"messages": messages}, config=config)
        return {
            "success": True,
            "result": result,
            "agent_name": agent.name,
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "agent_name": getattr(agent, "name", "unknown"),
        }


def get_agent_by_name(agent_name: str):
    """
    이름으로 에이전트 가져오기

    Args:
        agent_name: 에이전트 이름

    Returns:
        에이전트 인스턴스 또는 None
    """
    agent_map = {
        "chat": AgentFactory.get_chat_agent,
        "search": AgentFactory.get_search_agent,
        "participate": AgentFactory.get_participate_agent,
        "create": AgentFactory.get_create_agent,
    }

    if agent_name in agent_map:
        return agent_map[agent_name]()

    return None


if __name__ == "__main__":
    # 에이전트 설정 검증 테스트
    print("🤖 에이전트 설정 검증 중...")
    validation_result = validate_agent_configuration()

    if validation_result["overall_status"] == "ok":
        print("✅ 모든 에이전트가 정상적으로 설정되었습니다!")
        for agent_name, status in validation_result["agents"].items():
            if status["status"] == "ok":
                print(f"   ✅ {agent_name}: {status['name']}")
            else:
                print(f"   ❌ {agent_name}: {status['error']}")
    else:
        print(f"❌ 에이전트 설정 오류: {validation_result['error']}")
