# app.py (HITL 지원 버전)
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import asyncio
import json
import uuid
from typing import Dict, AsyncGenerator, List, Optional
import logging
from datetime import datetime

# BaseMessage 관련 임포트
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage

from langfuse import get_client, Langfuse
from langfuse.langchain import CallbackHandler

langfuse: Langfuse = get_client()

# HITL 지원이 추가된 워크플로우를 임포트
from supervisor_workflow import create_supervisor_workflow

# =============================================================================
# 로깅 및 전역 변수 설정
# =============================================================================
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

app = FastAPI(title="공구 챗봇 API", version="5.0.0-hitl")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")

# 세션 관리를 위한 전역 변수
SESSION_DATA: Dict[str, List[BaseMessage]] = {}
PENDING_APPROVALS: Dict[str, Dict] = {}  # 승인 대기 중인 작업들
supervisor_app = None


# =============================================================================
# Pydantic 모델 및 유틸리티 함수
# =============================================================================
class ChatMessage(BaseModel):
    message: str
    session_id: str


class ApprovalRequest(BaseModel):
    approved: bool
    reason: Optional[str] = None


def basemessage_to_dict(message: BaseMessage) -> dict:
    """BaseMessage를 프론트엔드 전송용 딕셔너리로 변환"""
    agent_name = "user"
    if isinstance(message, AIMessage):
        agent_name = message.additional_kwargs.get("agent", "assistant") or "assistant"

    return {
        "content": message.content,
        "role": "user" if isinstance(message, HumanMessage) else "assistant",
        "agent": agent_name,
        "timestamp": datetime.now().isoformat(),
        # HITL 관련 추가 정보
        "approval_required": message.additional_kwargs.get("approval_required", False),
        "approval_id": message.additional_kwargs.get("approval_id"),
        "task_description": message.additional_kwargs.get("task_description"),
    }


async def format_sse_data(data: dict) -> str:
    """SSE(Server-Sent Events) 형식으로 데이터 포맷팅"""
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


# =============================================================================
# FastAPI 이벤트 핸들러 및 엔드포인트
# =============================================================================
@app.on_event("startup")
async def startup_event():
    global supervisor_app
    try:
        supervisor_app = create_supervisor_workflow()
        logger.info("✅ Supervisor workflow 초기화 완료 (HITL 지원)")
    except Exception as e:
        logger.error(f"❌ Supervisor workflow 초기화 실패: {e}", exc_info=True)
        supervisor_app = None


@app.get("/")
async def root():
    return FileResponse("static/index.html")


async def process_message_stream(
    message: str, session_id: str
) -> AsyncGenerator[str, None]:
    if supervisor_app is None:
        yield await format_sse_data(
            {"type": "error", "content": "Supervisor가 초기화되지 않았습니다."}
        )
        return

    try:
        # 세션 데이터에서 기존 대화 기록 가져오기
        if session_id not in SESSION_DATA:
            SESSION_DATA[session_id] = []
        conversation_history = SESSION_DATA[session_id]

        initial_message_count = len(conversation_history)

        # 새 사용자 메시지 추가
        user_message = HumanMessage(content=message)
        conversation_history.append(user_message)

        yield await format_sse_data({"type": "processing", "content": "분석 중..."})

        # LangFuse 트레이싱을 위한 span 생성
        with langfuse.start_as_current_span(
            name="chat-message",
            input={"message": message, "session_id": session_id},
        ) as span:
            # 트레이스 속성 설정 (세션별 그룹화)
            span.update_trace(
                name="Chat Session",
                session_id=(
                    session_id.split("-")[0] if "-" in session_id else session_id
                ),
                tags=["chat", "web"],
                metadata={
                    "message_count": len(conversation_history),
                    "timestamp": datetime.now().isoformat(),
                },
            )

            # 초기 상태 구성 ... (이하 동일)
            workflow_input = {
                "messages": conversation_history,
                "next_agent": "supervisor",
                "human_approval_required": False,
                "human_approved": False,
                "current_task": None,
                "approval_id": None,
                "session_id": session_id,
                "user_id": (
                    session_id.split("-")[0] if "-" in session_id else session_id
                ),
            }

            logger.info(
                f"🚀 워크플로우 호출 [세션: {session_id}] [전달 메시지: {len(workflow_input['messages'])}개]"
            )

            # LangChain 콜백 핸들러 생성
            langfuse_handler = CallbackHandler()

            # 워크플로우 실행
            final_state = await supervisor_app.ainvoke(
                workflow_input,
                config={
                    "callbacks": [langfuse_handler],
                    "metadata": {"session_id": session_id},
                },
            )

            # 결과 처리
            if final_state and final_state.get("messages"):
                new_history = final_state["messages"]
                new_messages = new_history[initial_message_count + 1 :]
                SESSION_DATA[session_id] = new_history

                logger.info(
                    f"✅ 워크플로우 완료 [세션: {session_id}] [신규 응답: {len(new_messages)}개]"
                )

                # span의 최종 output은 유지하되, 모든 새 메시지를 개별적으로 기록
                span.update(
                    output={
                        "ai_response": (
                            new_messages[-1].content if new_messages else ""
                        ),
                    }
                )

                # ## <<-- 여기가 핵심 수정 부분입니다 -- ##
                # 새로운 메시지들을 처리하며, 각 AI 메시지를 Langfuse에 'generation'으로 수동 기록
                for new_msg in new_messages:
                    if isinstance(new_msg, AIMessage):
                        response_dict = basemessage_to_dict(new_msg)
                        agent_name = response_dict.get("agent", "unknown_agent")

                        with langfuse.start_as_current_generation(
                            name=agent_name,
                        ) as generation:
                            # 세션 뷰를 위한 generation 수동 기록
                            generation.update(
                                name=agent_name,  # 세션 뷰에서 어떤 에이전트가 말했는지 보여줌
                                input=user_message.content,  # 이 generation을 유발한 사용자 입력
                                output=new_msg.content,  # 이 generation의 실제 결과물
                                model="gemini-2.0-flash",  # 사용된 모델 (하드코딩 또는 동적으로 가져오기)
                                metadata=response_dict,  # 프론트엔드에 보낸 모든 메타데이터 포함
                                session_id=session_id,  # 이 generation이 속한 세션
                                trace_id=span.trace_id,  # 이 generation을 전체 Trace에 연결
                                parent_observation_id=span.id,  # Trace 내에서 chat-message span의 자식으로 연결
                            )

                        # 승인이 필요한 경우 (기존 로직 유지)
                        if response_dict.get("approval_required"):
                            approval_id = response_dict.get("approval_id")

                            # 승인 정보 저장
                            PENDING_APPROVALS[approval_id] = {
                                "session_id": session_id,
                                "task_description": response_dict.get(
                                    "task_description"
                                ),
                                "timestamp": datetime.now(),
                                "state": final_state,
                            }

                            logger.info(
                                f"🔔 승인 요청 생성 [ID: {approval_id}] [작업: {response_dict.get('task_description')}]"
                            )
                            # 승인 요청 이벤트 전송
                            yield await format_sse_data(
                                {
                                    "type": "approval_required",
                                    "approval_id": approval_id,
                                    "task_description": response_dict.get(
                                        "task_description"
                                    ),
                                    "content": response_dict["content"],
                                    "agent": response_dict["agent"],
                                    "timestamp": response_dict["timestamp"],
                                }
                            )
                        else:
                            # 일반 AI 응답
                            logger.info(
                                f"   - 전송할 AI 메시지 [에이전트: {response_dict['agent']}]"
                            )
                            yield await format_sse_data(
                                {
                                    "type": "ai_response",
                                    "content": response_dict["content"],
                                    "agent": response_dict["agent"],
                                    "timestamp": response_dict["timestamp"],
                                }
                            )

        yield await format_sse_data({"type": "complete"})

        # LangFuse 플러시
        langfuse.flush()

    except Exception as e:
        logger.error(f"❌ 메시지 처리 중 오류 [세션: {session_id}]: {e}", exc_info=True)
        yield await format_sse_data(
            {"type": "error", "content": f"처리 중 오류가 발생했습니다: {str(e)}"}
        )


@app.post("/chat/stream")
async def chat_stream_endpoint(chat_message: ChatMessage):
    if not chat_message.message.strip():
        raise HTTPException(status_code=400, detail="메시지가 비어있습니다.")

    session_id = chat_message.session_id or str(uuid.uuid4())

    return StreamingResponse(
        process_message_stream(chat_message.message, session_id),
        media_type="text/event-stream",
    )


@app.post("/chat/approve/{session_id}/{approval_id}")
async def approve_task(
    session_id: str, approval_id: str, approval_request: ApprovalRequest
):
    """사용자 승인/거부 처리"""

    logger.info(
        f"📝 승인 요청 처리 [세션: {session_id}] [승인ID: {approval_id}] [승인: {approval_request.approved}]"
    )

    # 승인 정보 확인
    if approval_id not in PENDING_APPROVALS:
        raise HTTPException(status_code=404, detail="승인 요청을 찾을 수 없습니다.")

    approval_info = PENDING_APPROVALS[approval_id]

    # 세션 확인
    if approval_info["session_id"] != session_id:
        raise HTTPException(status_code=403, detail="잘못된 세션입니다.")

    # 세션 데이터 가져오기
    if session_id not in SESSION_DATA:
        raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.")

    conversation_history = SESSION_DATA[session_id]

    # 승인/거부 메시지 추가
    if approval_request.approved:
        approval_message = HumanMessage(
            content=f"✅ 작업을 승인합니다. {approval_request.reason or ''}"
        )
    else:
        approval_message = HumanMessage(
            content=f"❌ 작업을 거부합니다. {approval_request.reason or ''}"
        )

    conversation_history.append(approval_message)

    # 승인된 경우 워크플로우 계속 진행
    if approval_request.approved:
        # 여기서 실제로 공구 생성 등의 작업을 수행
        # 현재는 간단히 완료 메시지만 추가
        completion_message = AIMessage(
            content="✅ 요청하신 작업이 완료되었습니다!",
            additional_kwargs={"agent": "system"},
        )
        conversation_history.append(completion_message)
    else:
        # 거부된 경우 안내 메시지
        rejection_message = AIMessage(
            content="작업이 취소되었습니다. 다시 시도하시려면 말씀해주세요.",
            additional_kwargs={"agent": "system"},
        )
        conversation_history.append(rejection_message)

    # 승인 정보 삭제
    del PENDING_APPROVALS[approval_id]

    return {
        "status": "processed",
        "approved": approval_request.approved,
        "session_id": session_id,
        "approval_id": approval_id,
    }


@app.get("/chat/history/{session_id}")
async def get_chat_history(session_id: str):
    if session_id in SESSION_DATA:
        history = SESSION_DATA[session_id]
        dict_messages = [basemessage_to_dict(msg) for msg in history]
        return {"messages": dict_messages, "session_id": session_id}
    return {"messages": [], "session_id": session_id}


@app.delete("/chat/session/{session_id}")
async def clear_session(session_id: str):
    if session_id in SESSION_DATA:
        del SESSION_DATA[session_id]
        logger.info(f"🗑️ 세션 데이터 삭제됨: {session_id}")

    # 해당 세션의 승인 대기 항목도 삭제
    approvals_to_delete = [
        aid
        for aid, info in PENDING_APPROVALS.items()
        if info["session_id"] == session_id
    ]
    for aid in approvals_to_delete:
        del PENDING_APPROVALS[aid]

    return {"status": "cleared", "session_id": session_id}


@app.get("/chat/pending-approvals/{session_id}")
async def get_pending_approvals(session_id: str):
    """세션의 승인 대기 중인 작업 조회"""
    pending = [
        {
            "approval_id": aid,
            "task_description": info["task_description"],
            "timestamp": info["timestamp"].isoformat(),
        }
        for aid, info in PENDING_APPROVALS.items()
        if info["session_id"] == session_id
    ]

    return {"session_id": session_id, "pending_approvals": pending}


@app.get("/health")
async def health_check():
    """헬스 체크 엔드포인트"""
    return {
        "status": "healthy",
        "supervisor_initialized": supervisor_app is not None,
        "active_sessions": len(SESSION_DATA),
        "pending_approvals": len(PENDING_APPROVALS),
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True, log_config=None)
