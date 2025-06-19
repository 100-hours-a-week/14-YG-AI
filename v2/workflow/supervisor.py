# workflow/supervisor.py
import uuid
import logging
from typing import List, Literal, TypedDict, Optional

from langchain_core.messages import BaseMessage, AIMessage
from langgraph.graph import StateGraph, END
from langchain_core.runnables import RunnableConfig

from .agents import AgentFactory, get_agent_by_name, run_agent_safe
from .routing import get_global_router, get_global_analyzer

logger = logging.getLogger(__name__)


# =============================================================================
# 워크플로우 상태 정의
# =============================================================================


class WorkflowState(TypedDict):
    """워크플로우 상태 타입 정의"""

    messages: List[BaseMessage]
    next_agent: str
    human_approval_required: bool
    human_approved: bool
    current_task: Optional[str]
    approval_id: Optional[str]
    session_id: Optional[str]
    user_id: Optional[str]


# =============================================================================
# 워크플로우 노드 함수들
# =============================================================================


async def supervisor_routing_node(state: WorkflowState) -> WorkflowState:
    """슈퍼바이저 라우팅 노드"""

    logger.info(f"🧠 슈퍼바이저 라우팅 시작 [메시지 수: {len(state['messages'])}]")

    if not state["messages"]:
        state["next_agent"] = "__end__"
        return state

    try:
        # 메시지 라우터를 통한 지능형 라우팅
        router = get_global_router()
        decision = await router.route_message(state["messages"])

        # 라우팅 기록 저장
        analyzer = get_global_analyzer()
        last_message = state["messages"][-1].content
        analyzer.add_routing_record(last_message, decision)

        # 상태 업데이트
        state["next_agent"] = decision.selected_agent
        state["human_approval_required"] = decision.human_approval_required
        state["current_task"] = decision.task_description

        # PARTICIPATE는 항상 승인 필요
        if decision.selected_agent == "participate":
            state["human_approval_required"] = True

        logger.info(
            f"✅ 라우팅 결정 완료 [다음 에이전트: {decision.selected_agent}] "
            f"[신뢰도: {decision.confidence:.2f}] [승인 필요: {decision.human_approval_required}]"
        )

    except Exception as e:
        logger.error(f"❌ 슈퍼바이저 라우팅 오류: {e}", exc_info=True)
        # 오류 시 기본 채팅 에이전트로 폴백
        state["next_agent"] = "chat"
        state["human_approval_required"] = False
        state["current_task"] = "라우팅 오류로 인한 기본 대화"

    return state


async def run_chat_agent_node(
    state: WorkflowState, config: RunnableConfig
) -> WorkflowState:
    """채팅 에이전트 실행 노드"""
    return await run_agent_node(state, config, "chat")


async def run_search_agent_node(
    state: WorkflowState, config: RunnableConfig
) -> WorkflowState:
    """검색 에이전트 실행 노드"""
    return await run_agent_node(state, config, "search")


async def run_participate_agent_node(
    state: WorkflowState, config: RunnableConfig
) -> WorkflowState:
    """참여 에이전트 실행 노드"""
    return await run_agent_node(state, config, "participate")


async def run_agent_node(
    state: WorkflowState, config: RunnableConfig, agent_name: str
) -> WorkflowState:
    """
    공통 에이전트 실행 노드

    Args:
        state: 워크플로우 상태
        config: 실행 설정
        agent_name: 실행할 에이전트 이름

    Returns:
        WorkflowState: 업데이트된 상태
    """
    logger.info(f"🤖 {agent_name.upper()} 에이전트 실행 시작")

    if not state["messages"]:
        state["next_agent"] = "__end__"
        return state

    try:
        # 에이전트 가져오기
        agent = get_agent_by_name(agent_name)
        if not agent:
            logger.error(f"❌ 에이전트를 찾을 수 없음: {agent_name}")
            state["next_agent"] = "__end__"
            return state

        # 에이전트 실행
        result = await run_agent_safe(agent, state["messages"], config)

        if not result["success"]:
            logger.error(f"❌ {agent_name} 에이전트 실행 실패: {result['error']}")
            # 에러 메시지를 응답으로 추가
            error_message = AIMessage(
                content=f"죄송합니다. {agent_name} 처리 중 오류가 발생했습니다.",
                additional_kwargs={"agent": "system"},
            )
            state["messages"].append(error_message)
            state["next_agent"] = "__end__"
            return state

        # 성공적인 결과 처리
        agent_response = result["result"]["messages"][-1]
        # 🔧 에이전트 이름을 additional_kwargs에 명시적으로 설정
        if hasattr(agent_response, "additional_kwargs"):
            agent_response.additional_kwargs["agent"] = agent_name  # 이 줄 추가
        else:
            agent_response.additional_kwargs = {"agent": agent_name}  # 이 줄 추가

        state["messages"].append(agent_response)

        logger.info(
            f"✅ {agent_name.upper()} 에이전트 실행 완료 "
            f"[응답 길이: {len(agent_response.content)}자]"
        )

        # 승인이 필요한 경우 확인
        if (
            agent_name == "participate"
            and "승인이 필요합니다" in agent_response.content
        ):
            state["human_approval_required"] = True
            state["approval_id"] = str(uuid.uuid4())
            state["next_agent"] = "human_approval"
        else:
            state["next_agent"] = "__end__"

    except Exception as e:
        logger.error(f"❌ {agent_name} 에이전트 노드 오류: {e}", exc_info=True)
        error_message = AIMessage(
            content="처리 중 오류가 발생했습니다. 다시 시도해주세요.",
            additional_kwargs={"agent": "system"},
        )
        state["messages"].append(error_message)
        state["next_agent"] = "__end__"

    return state


async def human_approval_node(state: WorkflowState) -> WorkflowState:
    """사용자 승인 대기 노드"""

    logger.info(
        f"🔔 사용자 승인 대기 [작업: {state.get('current_task', '알 수 없음')}]"
    )

    # 승인 요청 메시지 생성
    approval_message = AIMessage(
        content=f"🔔 사용자 승인이 필요합니다.\n작업: {state.get('current_task', '알 수 없음')}",
        additional_kwargs={
            "agent": "system",
            "approval_required": True,
            "approval_id": state.get("approval_id", str(uuid.uuid4())),
            "task_description": state.get("current_task", ""),
        },
    )
    state["messages"].append(approval_message)

    # 승인 대기 상태로 전환
    state["next_agent"] = "__end__"

    return state


# =============================================================================
# 워크플로우 조건부 라우팅
# =============================================================================


def should_continue(
    state: WorkflowState,
) -> Literal["chat", "search", "participate", "human_approval", "__end__"]:
    """
    다음 단계 결정 함수

    Args:
        state: 현재 워크플로우 상태

    Returns:
        str: 다음 노드 이름
    """
    next_agent = state.get("next_agent", "__end__")

    logger.debug(f"🧭 다음 단계 결정: {next_agent}")

    # 승인이 필요하고 아직 승인되지 않은 경우
    if (
        state.get("human_approval_required", False)
        and not state.get("human_approved", False)
        and next_agent == "human_approval"
    ):
        return "human_approval"

    # 유효한 에이전트인 경우
    if next_agent in ["chat", "search", "participate", "human_approval"]:
        return next_agent

    # 기본값: 종료
    return "__end__"


# =============================================================================
# 워크플로우 생성 및 관리
# =============================================================================


class WorkflowManager:
    """워크플로우 관리 클래스"""

    def __init__(self):
        self.workflow_app = None
        self._initialized = False

    def initialize(self):
        """워크플로우 초기화"""
        if self._initialized:
            return self.workflow_app

        try:
            logger.info("🚀 워크플로우 초기화 시작...")

            # StateGraph 생성
            workflow = StateGraph(WorkflowState)

            # 노드 추가
            workflow.add_node("supervisor", supervisor_routing_node)
            workflow.add_node("chat", run_chat_agent_node)
            workflow.add_node("search", run_search_agent_node)
            workflow.add_node("participate", run_participate_agent_node)
            workflow.add_node("human_approval", human_approval_node)

            # 진입점 설정
            workflow.set_entry_point("supervisor")

            # 조건부 엣지 (슈퍼바이저에서 각 에이전트로)
            workflow.add_conditional_edges(
                "supervisor",
                should_continue,
                {
                    "chat": "chat",
                    "search": "search",
                    "participate": "participate",
                    "__end__": END,
                },
            )

            # 각 에이전트에서의 조건부 엣지
            for agent in ["chat", "search", "participate"]:
                workflow.add_conditional_edges(
                    agent,
                    should_continue,
                    {
                        "human_approval": "human_approval",
                        "__end__": END,
                    },
                )

            # human_approval에서의 엣지
            workflow.add_conditional_edges(
                "human_approval",
                should_continue,
                {
                    "__end__": END,
                },
            )

            # 워크플로우 컴파일
            self.workflow_app = workflow.compile()
            self._initialized = True

            logger.info("✅ 워크플로우 초기화 완료")
            return self.workflow_app

        except Exception as e:
            logger.error(f"❌ 워크플로우 초기화 실패: {e}", exc_info=True)
            raise

    def get_workflow_app(self):
        """워크플로우 앱 반환 (초기화되지 않았으면 초기화)"""
        if not self._initialized:
            return self.initialize()
        return self.workflow_app

    def reset(self):
        """워크플로우 재설정"""
        self.workflow_app = None
        self._initialized = False
        AgentFactory.clear_cache()
        logger.info("🔄 워크플로우 재설정 완료")


# =============================================================================
# 팩토리 함수 및 유틸리티
# =============================================================================

# 전역 워크플로우 매니저
_workflow_manager = None


def create_supervisor_workflow():
    """슈퍼바이저 워크플로우 생성"""
    global _workflow_manager
    if _workflow_manager is None:
        _workflow_manager = WorkflowManager()

    return _workflow_manager.get_workflow_app()


def get_workflow_manager() -> WorkflowManager:
    """워크플로우 매니저 반환"""
    global _workflow_manager
    if _workflow_manager is None:
        _workflow_manager = WorkflowManager()
    return _workflow_manager


def validate_workflow_state(state: WorkflowState) -> dict:
    """
    워크플로우 상태 유효성 검증

    Args:
        state: 검증할 상태

    Returns:
        dict: 검증 결과
    """
    errors = []

    # 필수 필드 검증
    required_fields = ["messages", "next_agent"]
    for field in required_fields:
        if field not in state:
            errors.append(f"필수 필드 누락: {field}")

    # 메시지 리스트 검증
    if "messages" in state and not isinstance(state["messages"], list):
        errors.append("messages는 리스트여야 합니다")

    # next_agent 값 검증
    valid_agents = [
        "chat",
        "search",
        "participate",
        "human_approval",
        "__end__",
        "supervisor",
    ]
    if "next_agent" in state and state["next_agent"] not in valid_agents:
        errors.append(f"유효하지 않은 next_agent: {state['next_agent']}")

    return {
        "valid": len(errors) == 0,
        "errors": errors,
    }


def create_initial_state(
    messages: List[BaseMessage], session_id: str = None, user_id: str = None
) -> WorkflowState:
    """
    초기 워크플로우 상태 생성

    Args:
        messages: 초기 메시지 리스트
        session_id: 세션 ID
        user_id: 사용자 ID

    Returns:
        WorkflowState: 초기 상태
    """
    return {
        "messages": messages,
        "next_agent": "supervisor",
        "human_approval_required": False,
        "human_approved": False,
        "approval_id": None,
        "session_id": session_id,
        "user_id": user_id,
    }


def get_workflow_stats() -> dict:
    """워크플로우 통계 반환"""
    analyzer = get_global_analyzer()
    routing_stats = analyzer.get_routing_stats()

    # 에이전트 팩토리 캐시 상태
    agent_cache_status = {
        name: name in AgentFactory._agents_cache
        for name in [
            "chat_agent",
            "search_agent",
            "participate_agent",
            "supervisor_llm",
        ]
    }

    return {
        "routing_stats": routing_stats,
        "agent_cache_status": agent_cache_status,
        "workflow_initialized": _workflow_manager is not None
        and _workflow_manager._initialized,
        "recent_routings": analyzer.get_recent_routings(5),
    }


if __name__ == "__main__":
    # 워크플로우 테스트
    import asyncio
    from datetime import datetime
    from langchain_core.messages import HumanMessage

    async def test_workflow():
        print("🔧 워크플로우 테스트...")

        try:
            # 워크플로우 생성
            app = create_supervisor_workflow()
            print("✅ 워크플로우 생성 완료")

            # 테스트 메시지
            test_message = "안녕하세요!"
            initial_state = create_initial_state(
                messages=[HumanMessage(content=test_message)],
                session_id="test-session",
                user_id="test-user",
            )

            print(f"📝 테스트 메시지: '{test_message}'")

            # 상태 검증
            validation = validate_workflow_state(initial_state)
            if not validation["valid"]:
                print(f"❌ 상태 검증 실패: {validation['errors']}")
                return

            # 워크플로우 실행
            final_state = await app.ainvoke(initial_state)

            print("🎯 실행 결과:")
            print(f"  📊 메시지 수: {len(final_state['messages'])}")
            print(f"  🎭 최종 에이전트: {final_state['next_agent']}")
            print(
                f"  🔒 승인 필요: {final_state.get('human_approval_required', False)}"
            )

            # 메시지 출력
            for i, msg in enumerate(final_state["messages"]):
                role = "USER" if hasattr(msg, "type") and msg.type == "human" else "AI"
                agent = getattr(msg, "additional_kwargs", {}).get("agent", "unknown")
                content = (
                    msg.content[:50] + "..." if len(msg.content) > 50 else msg.content
                )
                print(f"  {i+1}. {role} ({agent}): {content}")

            # 통계 출력
            stats = get_workflow_stats()
            print(f"\n📈 워크플로우 통계:")
            print(f"  🧭 총 라우팅: {stats['routing_stats'].get('total_routings', 0)}")
            print(
                f"  🤖 에이전트 캐시: {sum(stats['agent_cache_status'].values())}/4 로드됨"
            )

        except Exception as e:
            print(f"❌ 워크플로우 테스트 실패: {e}")
            import traceback

            traceback.print_exc()

    asyncio.run(test_workflow())
