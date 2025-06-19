# api/chat.py
import uuid
import asyncio
from typing import AsyncGenerator
from datetime import datetime
import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
from langfuse import get_client
from langfuse.langchain import CallbackHandler

from config import settings
from utils import (
    basemessage_to_dict,
    format_sse_data,
    format_error_response,
    format_ai_response,
    format_approval_request,
    format_processing_message,
    format_completion_message,
    format_chat_history,
    format_session_cleared,
    truncate_content,
)
from core.session import (
    get_session_data,
    add_message_to_session,
    clear_session_data,
    add_pending_approval,
    get_session_message_count,
)
from models.chat import ChatMessage

logger = logging.getLogger(__name__)

# FastAPI 라우터 생성
router = APIRouter(prefix="/chat", tags=["Chat"])

# LangFuse 클라이언트
langfuse = get_client()


async def process_message_stream(
    message: str, session_id: str, supervisor_app
) -> AsyncGenerator[str, None]:
    """
    메시지를 스트리밍 방식으로 처리

    Args:
        message: 사용자 메시지
        session_id: 세션 ID
        supervisor_app: 워크플로우 앱

    Yields:
        str: SSE 형식의 응답 데이터
    """
    if supervisor_app is None:
        yield await format_sse_data(
            format_error_response("Supervisor가 초기화되지 않았습니다.")
        )
        return

    try:
        # 세션 데이터 가져오기
        conversation_history = get_session_data(session_id)
        initial_message_count = len(conversation_history)

        # 메시지 길이 체크
        if len(message) > settings.server.max_message_length:
            yield await format_sse_data(
                format_error_response(
                    f"메시지가 너무 깁니다. (최대 {settings.server.max_message_length}자)"
                )
            )
            return

        # 세션당 최대 메시지 수 체크
        if len(conversation_history) >= settings.server.max_history_per_session:
            yield await format_sse_data(
                format_error_response(
                    f"세션당 최대 메시지 수를 초과했습니다. (최대 {settings.server.max_history_per_session}개)"
                )
            )
            return

        # 새 사용자 메시지 추가
        user_message = HumanMessage(content=message)
        add_message_to_session(session_id, user_message)
        conversation_history = get_session_data(session_id)

        yield await format_sse_data(format_processing_message("분석 중..."))

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
                    "message_length": len(message),
                },
            )

            # 워크플로우 입력 구성
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
                f"🚀 워크플로우 호출 [세션: {session_id[:8]}...] "
                f"[메시지: {len(workflow_input['messages'])}개] "
                f"[내용: {truncate_content(message, 50)}]"
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

                # 세션 데이터 업데이트
                for new_msg in new_messages:
                    add_message_to_session(session_id, new_msg)

                logger.info(
                    f"✅ 워크플로우 완료 [세션: {session_id[:8]}...] "
                    f"[신규 응답: {len(new_messages)}개]"
                )

                # span의 최종 output 업데이트
                span.update(
                    output={
                        "ai_response": (
                            new_messages[-1].content if new_messages else ""
                        ),
                        "response_count": len(new_messages),
                    }
                )

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
                                name=agent_name,
                                input=user_message.content,
                                output=new_msg.content,
                                model=settings.google_cloud.model_name,
                                metadata=response_dict,
                                session_id=session_id,
                                trace_id=span.trace_id,
                                parent_observation_id=span.id,
                            )

                        # 승인이 필요한 경우
                        if response_dict.get("approval_required"):
                            approval_id = response_dict.get("approval_id")

                            # 승인 정보 저장
                            add_pending_approval(
                                approval_id=approval_id,
                                session_id=session_id,
                                task_description=response_dict.get("task_description"),
                                state=final_state,
                            )

                            logger.info(
                                f"🔔 승인 요청 생성 [ID: {approval_id}] "
                                f"[작업: {response_dict.get('task_description')}]"
                            )

                            # 승인 요청 이벤트 전송
                            yield await format_sse_data(
                                format_approval_request(
                                    approval_id=approval_id,
                                    task_description=response_dict.get(
                                        "task_description"
                                    ),
                                    content=response_dict["content"],
                                    agent=response_dict["agent"],
                                )
                            )
                        else:
                            # 일반 AI 응답
                            logger.info(
                                f"   - AI 응답 전송 [에이전트: {response_dict['agent']}] "
                                f"[내용: {truncate_content(response_dict['content'], 50)}]"
                            )
                            yield await format_sse_data(
                                format_ai_response(
                                    content=response_dict["content"],
                                    agent=response_dict["agent"],
                                    timestamp=response_dict["timestamp"],
                                )
                            )

        yield await format_sse_data(format_completion_message())

        # LangFuse 플러시
        langfuse.flush()

    except Exception as e:
        logger.error(
            f"❌ 메시지 처리 중 오류 [세션: {session_id[:8]}...]: {e}", exc_info=True
        )
        yield await format_sse_data(
            format_error_response(f"처리 중 오류가 발생했습니다: {str(e)}")
        )


@router.post("/stream")
async def chat_stream_endpoint(chat_message: ChatMessage):
    """
    스트리밍 방식 채팅 엔드포인트

    Args:
        chat_message: 채팅 메시지 (message, session_id)

    Returns:
        StreamingResponse: SSE 스트리밍 응답
    """
    if not chat_message.message.strip():
        raise HTTPException(status_code=400, detail="메시지가 비어있습니다.")

    session_id = chat_message.session_id or str(uuid.uuid4())

    # supervisor_app은 전역에서 가져와야 함 (의존성 주입으로 개선 예정)
    from app import supervisor_app  # 임시 방식, 나중에 개선

    return StreamingResponse(
        process_message_stream(chat_message.message, session_id, supervisor_app),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Nginx 버퍼링 비활성화
        },
    )


@router.get("/history/{session_id}")
async def get_chat_history(session_id: str):
    """
    채팅 히스토리 조회

    Args:
        session_id: 세션 ID

    Returns:
        dict: 채팅 히스토리 데이터
    """
    try:
        conversation_history = get_session_data(session_id)
        history_data = format_chat_history(conversation_history)
        history_data["session_id"] = session_id

        logger.info(
            f"📖 히스토리 조회 [세션: {session_id[:8]}...] [메시지: {len(conversation_history)}개]"
        )

        return history_data
    except Exception as e:
        logger.error(f"❌ 히스토리 조회 오류 [세션: {session_id[:8]}...]: {e}")
        raise HTTPException(
            status_code=500, detail="히스토리 조회 중 오류가 발생했습니다."
        )


@router.delete("/session/{session_id}")
async def clear_session(session_id: str):
    """
    세션 데이터 삭제

    Args:
        session_id: 삭제할 세션 ID

    Returns:
        dict: 삭제 결과
    """
    try:
        # 세션 데이터 및 승인 대기 항목 삭제
        message_count = get_session_message_count(session_id)
        deleted_approvals = clear_session_data(session_id)

        logger.info(
            f"🗑️ 세션 삭제 완료 [세션: {session_id[:8]}...] "
            f"[메시지: {message_count}개] [승인: {deleted_approvals}개]"
        )

        return format_session_cleared(session_id)
    except Exception as e:
        logger.error(f"❌ 세션 삭제 오류 [세션: {session_id[:8]}...]: {e}")
        raise HTTPException(status_code=500, detail="세션 삭제 중 오류가 발생했습니다.")


@router.get("/sessions/stats")
async def get_session_stats():
    """
    전체 세션 통계 조회

    Returns:
        dict: 세션 통계 데이터
    """
    try:
        from core.session import get_all_session_stats

        stats = get_all_session_stats()

        return {
            "total_sessions": stats["total_sessions"],
            "total_messages": stats["total_messages"],
            "total_pending_approvals": stats["total_pending_approvals"],
            "average_messages_per_session": stats["average_messages_per_session"],
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        logger.error(f"❌ 세션 통계 조회 오류: {e}")
        raise HTTPException(
            status_code=500, detail="세션 통계 조회 중 오류가 발생했습니다."
        )
