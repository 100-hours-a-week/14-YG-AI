# core/streaming.py
import logging
from typing import AsyncGenerator, Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

from utils import (
    format_sse_data,
    format_error_response,
    format_ai_response,
    format_processing_message,
    format_completion_message,
    format_structured_search_response,  # 추가
)


async def create_chat_stream(
    message_processor, message: str, session_id: str
) -> AsyncGenerator[str, None]:
    """채팅 메시지를 스트리밍 방식으로 처리"""

    try:
        # 처리 시작 메시지 전송
        yield await format_sse_data(format_processing_message("분석 중..."))

        # 메시지 처리
        result = await message_processor.process_user_message(message, session_id)

        if not result["success"]:
            yield await format_sse_data(format_error_response(result["error"]))
            return

        # 새로운 메시지들 스트리밍 전송
        for message_data in result["new_messages"]:
            # AI 응답 - 구조화된 검색 결과 확인
            if (
                message_data.get("agent") == "search_agent"
                and "STRUCTURED_RESULT_START" in message_data["content"]
            ):
                # 구조화된 검색 결과 처리
                formatted_response = format_structured_search_response(
                    content=message_data["content"],
                    agent=message_data["agent"],
                    timestamp=message_data["timestamp"],
                )
            else:
                # 일반 AI 응답
                formatted_response = format_ai_response(
                    content=message_data["content"],
                    agent=message_data["agent"],
                    timestamp=message_data["timestamp"],
                )

            yield await format_sse_data(formatted_response)

        # 완료 메시지 전송
        yield await format_sse_data(format_completion_message())

    except Exception as e:
        logger.error(f"❌ 스트리밍 처리 오류: {e}", exc_info=True)
        yield await format_sse_data(
            format_error_response(f"스트리밍 처리 중 오류가 발생했습니다: {str(e)}")
        )


async def create_error_stream(error_message: str) -> AsyncGenerator[str, None]:
    """
    에러 전용 스트림 생성

    Args:
        error_message: 에러 메시지

    Yields:
        str: 에러 SSE 데이터
    """
    yield await format_sse_data(format_error_response(error_message))


async def create_info_stream(
    message: str, event_type: str = "info"
) -> AsyncGenerator[str, None]:
    """
    정보 메시지 스트림 생성

    Args:
        message: 정보 메시지
        event_type: 이벤트 타입

    Yields:
        str: 정보 SSE 데이터
    """
    yield await format_sse_data(
        {
            "type": event_type,
            "content": message,
            "timestamp": datetime.now().isoformat(),
        }
    )


def validate_stream_request(message: str, session_id: str) -> Dict[str, Any]:
    """
    스트리밍 요청 유효성 검사

    Args:
        message: 사용자 메시지
        session_id: 세션 ID

    Returns:
        Dict[str, Any]: 검증 결과
    """
    if not message or not message.strip():
        return {"valid": False, "error": "메시지가 비어있습니다."}

    if not session_id or not session_id.strip():
        return {"valid": False, "error": "세션 ID가 필요합니다."}

    return {"valid": True}


async def handle_chat_stream(
    message_processor, message: str, session_id: str
) -> AsyncGenerator[str, None]:
    """
    채팅 스트림 처리 (메인 엔트리포인트)

    Args:
        message_processor: 메시지 처리기
        message: 사용자 메시지
        session_id: 세션 ID

    Yields:
        str: SSE 형식의 응답 데이터
    """
    # 요청 검증
    validation = validate_stream_request(message, session_id)
    if not validation["valid"]:
        async for chunk in create_error_stream(validation["error"]):
            yield chunk
        return

    # 스트리밍 처리
    async for chunk in create_chat_stream(message_processor, message, session_id):
        yield chunk


class StreamingManager:
    """스트리밍 관리자 - 스트리밍 기능을 통합 관리"""

    def __init__(self, supervisor_app):
        """
        StreamingManager 초기화

        Args:
            supervisor_app: LangGraph 워크플로우 앱
        """
        from .message import create_message_processor

        self.message_processor = create_message_processor(supervisor_app)

    async def stream_chat_response(
        self, message: str, session_id: str
    ) -> AsyncGenerator[str, None]:
        """
        채팅 응답 스트리밍

        Args:
            message: 사용자 메시지
            session_id: 세션 ID

        Yields:
            str: SSE 형식의 응답 데이터
        """
        async for chunk in handle_chat_stream(
            self.message_processor, message, session_id
        ):
            yield chunk


def create_streaming_manager(supervisor_app) -> StreamingManager:
    """
    StreamingManager 인스턴스 생성

    Args:
        supervisor_app: LangGraph 워크플로우 앱

    Returns:
        StreamingManager: 스트리밍 관리자 인스턴스
    """
    return StreamingManager(supervisor_app)
