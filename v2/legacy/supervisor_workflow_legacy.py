# supervisor_workflow.py
import asyncio
import os
import json
import re
from typing import List, Literal, TypedDict, Optional
from datetime import datetime
import uuid

from langchain_google_vertexai import ChatVertexAI
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
from langgraph.prebuilt import create_react_agent
from langgraph.graph import StateGraph, END
from langchain_core.runnables import RunnableConfig
from datetime import datetime
from tools.search_post_tool import search_group_buy
import logging
from dotenv import load_dotenv

# 로그 레벨 설정
logging.basicConfig(level=logging.INFO)
logging.getLogger("langchain_google_vertexai").setLevel(logging.WARNING)
logging.getLogger("google").setLevel(logging.WARNING)

load_dotenv()


# =============================================================================
# 상태 정의 (HITL 필드 추가)
# =============================================================================
class WorkflowState(TypedDict):
    messages: List[BaseMessage]
    next_agent: str
    human_approval_required: bool
    human_approved: bool
    current_task: Optional[str]
    approval_id: Optional[str]


# =============================================================================
# 도구 정의
# =============================================================================


@tool
def get_current_time() -> str:
    """현재 시간을 가져옵니다."""
    print(f"--- [TOOL] get_current_time() ---")
    return datetime.now().strftime("%Y년 %m월 %d일 %H시 %M분")


@tool
def create_group_buy_post(
    title: str,
    product_name: str,
    unit_price: int,
    total_amount: int,
    unit_amount: int,
    due_date: str,
    pickup_date: str,
    description: str = "",
    location: str = "카카오테크 부트캠프 교육장",
) -> str:
    """공구 게시글을 생성합니다."""

    post_data = {
        "title": title,
        "product_name": product_name,
        "unit_price": unit_price,
        "total_amount": total_amount,
        "unit_amount": unit_amount,
        "due_date": due_date,
        "pickup_date": pickup_date,
        "description": description,
        "location": location,
        "created_at": datetime.now().isoformat(),
    }

    post_id = f"GB_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    return f"✅ 공구 게시글이 성공적으로 생성되었습니다!\n게시글 ID: {post_id}\n제목: {title}\n상품: {product_name}\n개당 가격: {unit_price:,}원"


@tool
def request_human_approval(task_description: str, details: str) -> str:
    """사용자 승인을 요청합니다."""
    return f"🔔 사용자 승인이 필요합니다.\n작업: {task_description}\n상세: {details}"


# =============================================================================
# 에이전트 생성 함수들
# =============================================================================


def create_chat_agent():
    """일상 대화 및 감정 지원 에이전트"""

    llm = ChatVertexAI(
        model_name="gemini-2.0-flash",
        temperature=0.7,
        project=os.getenv("GOOGLE_CLOUD_PROJECT"),
        location="us-central1",
    )

    tools = [get_current_time]

    return create_react_agent(
        model=llm,
        tools=tools,
        name="chat_agent",
        prompt="""
        당신은 공구 플랫폼의 친근한 대화 어시스턴트입니다. 💬
        
        ## 주요 역할:
        - 따뜻하고 친근한 일상 대화
        - 사용자의 감정과 상황에 공감
        - 시간, 날씨 등 기본 정보 제공
        - 플랫폼 이용에 대한 일반적인 안내
        
        ## 대화 스타일:
        - 자연스럽고 친근한 톤 사용
        - 이모지 적절히 활용 (과하지 않게)
        - 사용자의 기분이나 상황에 맞춰 공감
        - 긍정적이고 도움이 되는 분위기 조성
        
        ## 공구 관련 질문 시:
        만약 사용자가 공구 검색이나 생성에 대해 물어본다면, 시스템에서 자동으로 
        전문 에이전트가 처리할 것이라고 자연스럽게 안내하고, 대화를 이어가세요.
        
        예: "공구 검색은 저희 전문 검색 시스템이 도와드릴 거예요! 그 외에 다른 이야기도 언제든 나눠요 😊"
        
        사용자와 자연스럽고 즐거운 대화를 나누세요!
        """,
    )


def create_search_agent():
    """공구 검색 및 추천 에이전트"""

    llm = ChatVertexAI(
        model_name="gemini-2.0-flash",
        temperature=0.0,
        project=os.getenv("GOOGLE_CLOUD_PROJECT"),
        location="us-central1",
    )

    tools = [search_group_buy]  # 모의 함수 폴백
    print("⚠️ 모의 검색 도구 사용")

    return create_react_agent(
        model=llm,
        tools=tools,
        name="search_agent",
        prompt="""
        당신은 공구 검색 전문가입니다. 🔍
        
        ## 🚨 매우 중요한 규칙:
        
        1. **search_group_buy 도구를 호출하세요**
        2. **도구가 "STRUCTURED_RESULT_START"로 시작하는 결과를 반환하면:**
           - 그 결과를 **절대 수정하거나 요약하지 마세요**
           - **전체 결과를 그대로 반환하세요**
           - 추가 설명이나 해석을 붙이지 마세요
        3. **일반 텍스트 결과인 경우에만 친근하게 설명하세요**
        
        ## 예시:
        
        **올바른 응답 (구조화된 결과):**
        ```
        STRUCTURED_RESULT_START
        {
          "search_type": "🎯 키워드 검색",
          "query": "이클립스 공구 있어?",
          "total_count": 2,
          "results": [...]
        }
        STRUCTURED_RESULT_END
        ```
        
        **잘못된 응답:**
        ```
        이클립스 공구 검색 결과입니다. 총 2개의 공구가 있습니다...
        ```
        
        ## 처리 방식:
        - 구조화된 결과 (STRUCTURED_RESULT_START 포함) → 그대로 반환
        - 일반 텍스트 결과 → 친근하게 설명
        
        사용자의 쿼리를 정확히 검색하고 적절한 형태로 결과를 반환하세요!
        """,
    )


def create_participate_agent():
    """공구 참여 및 생성 에이전트"""

    llm = ChatVertexAI(
        model_name="gemini-2.0-flash",
        temperature=0.2,
        project=os.getenv("GOOGLE_CLOUD_PROJECT"),
        location="us-central1",
    )

    tools = [create_group_buy_post, request_human_approval]

    return create_react_agent(
        model=llm,
        tools=tools,
        name="participate_agent",
        prompt="""
        당신은 공구 생성 및 참여 전문가입니다. 🎯
        
        ## 전문 분야:
        - 새로운 공구 게시글 생성
        - 공구 정보 수집 및 검증
        - 공구 생성 프로세스 안내
        - 향후 공구 참여 지원 (예정)
        
        ## 공구 생성 프로세스:
        
        ### 1단계: 정보 수집
        사용자로부터 다음 정보를 체계적으로 수집:
        - 📝 게시글 제목 (매력적이고 명확하게)
        - 🛍️ 상품명 (정확한 브랜드/모델명)
        - 💰 개당 가격 (정확한 금액)
        - 📦 전체 수량 (총 몇 개까지)
        - 🔢 주문 단위 (몇 개씩 주문 가능)
        - 📅 마감일 (언제까지 신청 받을지)
        - 📅 픽업일 (언제 받을 수 있는지)
        - 📍 거래 장소 (기본: 카카오테크 부트캠프 교육장)
        - 📄 상세 설명 (선택사항)
        
        ### 2단계: 정보 확인 및 승인 요청
        - 수집된 정보를 정리하여 사용자에게 확인
        - request_human_approval 도구로 승인 요청
        - 승인 받기 전까지는 절대 실제 생성하지 않음
        
        ### 3단계: 공구 생성
        - 사용자 승인 후 create_group_buy_post 도구로 실제 생성
        - 생성 완료 후 게시글 정보 안내
        
        ## 응답 스타일:
        - 단계별로 차근차근 안내
        - 필요한 정보를 친근하게 질문
        - 공구 생성의 중요성 강조
        - 명확하고 정확한 정보 요구
        
        ## 안전 수칙:
        ⚠️ **매우 중요**: 
        - 모든 정보를 수집한 후 반드시 사용자 승인을 받으세요
        - 승인 없이는 절대 create_group_buy_post를 호출하지 마세요
        - 불완전한 정보로는 공구를 생성하지 마세요
        
        ## 정보 부족 시:
        정보가 부족하면:
        - 누락된 정보를 친근하게 질문
        - 예시를 들어 이해를 돕기
        - 일반적인 값 제안 (참고용)
        
        성공적인 공구 생성을 도와드리겠습니다! 🚀
        """,
    )


# =============================================================================
# 라우팅 로직 (정교한 프롬프트 적용)
# =============================================================================


async def supervisor_routing(state: WorkflowState) -> WorkflowState:
    """슈퍼바이저의 지능형 라우팅 결정"""

    print(f"\n--- [NODE] SUPERVISOR ---")
    print(f"   [INFO] 수신된 메시지 수: {len(state['messages'])}")

    if not state["messages"]:
        state["next_agent"] = "__end__"
        return state

    last_message = state["messages"][-1].content
    conversation_history = "\n".join(
        [f"{m.type}: {m.content}" for m in state["messages"]]
    )
    # LLM 기반 슈퍼바이저 생성
    supervisor_llm = ChatVertexAI(
        model_name="gemini-2.0-flash",
        temperature=0.1,
        project=os.getenv("GOOGLE_CLOUD_PROJECT"),
        location="us-central1",
    )

    # 정교한 슈퍼바이저 프롬프트
    supervisor_prompt = f"""
당신은 공구 플랫폼의 스마트 라우터입니다. 사용자의 메시지를 분석하여 가장 적절한 전문 에이전트를 선택하세요.

## 이용 가능한 에이전트:

### 1. CHAT 에이전트
- **역할**: 일상 대화, 감정 지원, 기본 정보 제공
- **담당 업무**: 인사, 안부, 기분/감정 대화, 시간/날씨 문의, 일반적인 잡담
- **예시**: "안녕하세요", "오늘 날씨 어때요?", "기분이 좋아요", "심심해요"

### 2. SEARCH 에이전트  
- **역할**: 공구 검색, 추천, 가격 비교, 조건 검색
- **담당 업무**: 
  * 특정 상품 공구 찾기 (예: "콜라 공구", "이클립스 있어?")
  * 조건별 검색 (예: "천원 이하", "제일 싼", "인기 있는")
  * 카테고리 추천 (예: "간식 추천", "음료 뭐 있어?")
  * 공구 정보 조회 및 비교
- **예시**: "이클립스 공구 있어?", "간식 추천해줘", "천원 이하 뭐 있어?", "제일 싼 음료"

### 3. PARTICIPATE 에이전트
- **역할**: 공구 생성, 참여, 관리
- **담당 업무**: 새로운 공구 게시글 작성, 공구 개설, 공구 등록
- **중요**: 이 에이전트는 항상 사용자 승인이 필요합니다
- **예시**: "공구 만들고 싶어요", "새 공구 올려줘", "공구 생성해줘"

## 라우팅 가이드라인:

1. **명확한 의도 파악**: 사용자가 무엇을 원하는지 문맥을 고려하여 판단
2. **키워드보다 의도 중심**: 단순 키워드 매칭이 아닌 전체적인 의도 파악
3. **애매한 경우 처리**: 
   - 공구 관련이지만 애매하면 → SEARCH (검색이 더 안전)
   - 완전히 애매하면 → CHAT (친근한 대화로 시작)
4. **복합 의도**: 여러 의도가 섞여있으면 주된 의도를 선택
5. 맥락상 이전에 검색한 공구에 대한 내용을 물어본다면 -> CHAT

## 전체 메시지:
"{last_message}"

## 분석 및 결정:

위 메시지를 분석하여 다음 JSON 형식으로 응답하세요:

{{
    "selected_agent": "CHAT|SEARCH|PARTICIPATE",
    "confidence": 0.0-1.0,
    "reasoning": "선택 이유를 자세히 설명",
    "human_approval_required": true|false,
    "task_description": "구체적인 작업 설명"
}}

**중요**: 
- PARTICIPATE 에이전트 선택 시 human_approval_required는 항상 true
- SEARCH 에이전트는 일반적으로 승인 불필요 (false)
- CHAT 에이전트는 승인 불필요 (false)
- confidence는 0.7 이상일 때만 해당 에이전트 선택
- 확신이 없으면 CHAT 선택하고 낮은 confidence 제시
"""

    try:
        # LLM에게 라우팅 결정 요청
        response = await supervisor_llm.ainvoke(supervisor_prompt)

        # JSON 파싱
        json_match = re.search(r"\{.*\}", response.content, re.DOTALL)
        if json_match:
            decision = json.loads(json_match.group())
        else:
            decision = {
                "selected_agent": "CHAT",
                "confidence": 0.5,
                "reasoning": "JSON 파싱 실패로 기본 Chat 에이전트 선택",
                "human_approval_required": False,
                "task_description": "일반 대화",
            }

        # 에이전트 매핑
        agent_mapping = {
            "CHAT": "chat",
            "SEARCH": "search",
            "PARTICIPATE": "participate",
        }

        selected_agent = agent_mapping.get(
            decision.get("selected_agent", "CHAT").upper(), "chat"
        )

        print(f"\n🧠 LLM 슈퍼바이저 분석:")
        print(f"   메시지: '{last_message}'")
        print(f"   선택된 에이전트: {selected_agent}")
        print(f"   신뢰도: {decision.get('confidence', 0)}")
        print(f"   추론: {decision.get('reasoning', '')}")
        print(f"   사용자 승인 필요: {decision.get('human_approval_required', False)}")
        print(f"   작업 설명: {decision.get('task_description', '')}")

        # 상태 업데이트
        state["next_agent"] = selected_agent
        state["human_approval_required"] = decision.get(
            "human_approval_required", False
        )
        state["current_task"] = decision.get("task_description", "")

        # PARTICIPATE는 항상 승인 필요
        if selected_agent == "participate":
            state["human_approval_required"] = True

        print(f"   [DECISION] 다음 에이전트: {state['next_agent']}")

    except Exception as e:
        print(f"   [ERROR] 파싱 오류, CHAT으로 폴백: {e}")
        state["next_agent"] = "chat"
        state["human_approval_required"] = False
        state["current_task"] = "일반 대화"

    return state


# =============================================================================
# 에이전트 실행 함수들 (HITL 지원)
# =============================================================================


async def run_agent(
    state: WorkflowState, agent_creator, config: RunnableConfig
) -> WorkflowState:
    """공통 에이전트 실행 로직"""
    agent = agent_creator()
    agent_name = agent.name

    print(f"\n--- [NODE] {agent_name.upper()} ---")
    print(f"   [INFO] 수신된 메시지 수: {len(state['messages'])}")

    if not state["messages"]:
        state["next_agent"] = "__end__"
        return state

    # 에이전트 실행
    result = await agent.ainvoke({"messages": state["messages"]}, config=config)
    agent_response = result["messages"][-1].content

    print(f"   [RESPONSE] {agent_response[:100]}...")

    # 결과를 BaseMessage로 변환하여 대화 기록에 추가
    ai_message = AIMessage(
        content=agent_response, additional_kwargs={"agent": agent_name}
    )
    state["messages"].append(ai_message)

    # PARTICIPATE 에이전트의 경우 승인 확인
    if agent_name == "participate_agent" and "승인이 필요합니다" in agent_response:
        state["human_approval_required"] = True
        state["approval_id"] = str(uuid.uuid4())
        state["next_agent"] = "human_approval"
    else:
        state["next_agent"] = "__end__"

    return state


async def run_chat_agent(state: WorkflowState, config: RunnableConfig) -> WorkflowState:
    return await run_agent(state, create_chat_agent, config)


async def run_search_agent(
    state: WorkflowState, config: RunnableConfig
) -> WorkflowState:
    return await run_agent(state, create_search_agent, config)


async def run_participate_agent(
    state: WorkflowState, config: RunnableConfig
) -> WorkflowState:
    return await run_agent(state, create_participate_agent, config)


# =============================================================================
# Human Approval 노드
# =============================================================================


async def human_approval_node(state: WorkflowState) -> WorkflowState:
    """사용자 승인 대기 노드"""

    print(f"\n--- [NODE] HUMAN_APPROVAL ---")
    print(f"   [INFO] 승인 요청: {state.get('current_task', '알 수 없음')}")

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
# 워크플로우 구성
# =============================================================================


def should_continue(
    state: WorkflowState,
) -> Literal["chat", "search", "participate", "human_approval", "__end__"]:
    """다음 단계 결정"""

    next_agent = state.get("next_agent", "__end__")

    # 승인이 필요하고 아직 승인되지 않은 경우
    if (
        state.get("human_approval_required", False)
        and not state.get("human_approved", False)
        and next_agent == "human_approval"
    ):
        return "human_approval"

    if next_agent in ["chat", "search", "participate", "human_approval"]:
        return next_agent

    return "__end__"


def create_supervisor_workflow():
    """수동으로 제어하는 슈퍼바이저 그래프를 생성합니다."""
    workflow = StateGraph(WorkflowState)

    # 노드 추가
    workflow.add_node("supervisor", supervisor_routing)
    workflow.add_node("chat", run_chat_agent)
    workflow.add_node("search", run_search_agent)
    workflow.add_node("participate", run_participate_agent)
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
    # 컴파일 (수동 메모리 관리 모드)
    return workflow.compile()


# =============================================================================
# 테스트용 메인 함수
# =============================================================================


async def main():
    """테스트용 메인 함수"""
    print("🚀 Supervisor Workflow 테스트 (HITL 포함)...")

    app = create_supervisor_workflow()

    # 초기 상태
    initial_state = {
        "messages": [],
        "next_agent": "supervisor",
        "human_approval_required": False,
        "human_approved": False,
        "current_task": None,
        "approval_id": None,
    }

    # 테스트 메시지
    test_message = "공구 만들고 싶어요"
    initial_state["messages"].append(HumanMessage(content=test_message))

    try:
        final_state = await app.ainvoke(initial_state)

        print(f"\n🎯 최종 결과:")
        for msg in final_state["messages"]:
            if isinstance(msg, HumanMessage):
                print(f"   USER: {msg.content}")
            elif isinstance(msg, AIMessage):
                agent = msg.additional_kwargs.get("agent", "unknown")
                print(f"   AI ({agent}): {msg.content[:100]}...")

        print(f"\n📋 최종 상태:")
        print(f"   승인 필요: {final_state.get('human_approval_required', False)}")
        print(f"   승인 ID: {final_state.get('approval_id', 'None')}")
        print(f"   현재 작업: {final_state.get('current_task', 'None')}")

    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
