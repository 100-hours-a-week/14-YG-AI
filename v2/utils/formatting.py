# utils/formatting.py
import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage

logger = logging.getLogger(__name__)


def basemessage_to_dict(message: BaseMessage) -> dict:
    """
    BaseMessage를 프론트엔드 전송용 딕셔너리로 변환

    Args:
        message: LangChain BaseMessage 객체

    Returns:
        dict: 프론트엔드에서 사용할 메시지 딕셔너리
    """
    # 에이전트 이름 결정
    agent_name = "user"
    if isinstance(message, AIMessage):
        agent_name = message.additional_kwargs.get("agent", "assistant") or "assistant"

    return {
        "content": message.content,
        "role": "user" if isinstance(message, HumanMessage) else "assistant",
        "agent": agent_name,
        "timestamp": datetime.now().isoformat(),
        "hidden": message.additional_kwargs.get("hidden", False),  # ✅ 추가
        # HITL 관련 추가 정보
        "task_description": message.additional_kwargs.get("task_description"),
    }


async def format_sse_data(data: dict) -> str:
    """
    SSE(Server-Sent Events) 형식으로 데이터 포맷팅

    Args:
        data: 전송할 데이터 딕셔너리

    Returns:
        str: SSE 형식의 문자열
    """
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


def format_error_response(error_message: str, error_type: str = "error") -> dict:
    """
    에러 응답 포맷팅

    Args:
        error_message: 에러 메시지
        error_type: 에러 타입 (error, warning, info)

    Returns:
        dict: 에러 응답 딕셔너리
    """
    return {
        "type": error_type,
        "content": error_message,
        "timestamp": datetime.now().isoformat(),
    }


def format_ai_response(
    content: str, agent: str, timestamp: Optional[str] = None
) -> dict:
    """
    AI 응답 메시지 포맷팅

    Args:
        content: 응답 내용
        agent: 에이전트 이름
        timestamp: 타임스탬프 (None이면 현재 시간)

    Returns:
        dict: AI 응답 딕셔너리
    """
    return {
        "type": "ai_response",
        "content": content,
        "agent": agent,
        "timestamp": timestamp or datetime.now().isoformat(),
    }


def format_processing_message(message: str = "분석 중...") -> dict:
    """
    처리 중 메시지 포맷팅

    Args:
        message: 처리 중 메시지

    Returns:
        dict: 처리 중 메시지 딕셔너리
    """
    return {
        "type": "processing",
        "content": message,
        "timestamp": datetime.now().isoformat(),
    }


def format_completion_message() -> dict:
    """
    완료 메시지 포맷팅

    Returns:
        dict: 완료 메시지 딕셔너리
    """
    return {
        "type": "complete",
        "timestamp": datetime.now().isoformat(),
    }


def format_chat_history(messages: list) -> dict:
    """
    채팅 히스토리 포맷팅

    Args:
        messages: BaseMessage 리스트

    Returns:
        dict: 포맷된 채팅 히스토리
    """
    dict_messages = [basemessage_to_dict(msg) for msg in messages]
    return {
        "messages": dict_messages,
        "total_count": len(dict_messages),
        "last_updated": datetime.now().isoformat(),
    }


def format_health_check(supervisor_initialized: bool, active_sessions: int) -> dict:
    """
    헬스체크 응답 포맷팅

    Args:
        supervisor_initialized: 슈퍼바이저 초기화 상태
        active_sessions: 활성 세션 수

    Returns:
        dict: 헬스체크 응답
    """
    return {
        "status": "healthy" if supervisor_initialized else "unhealthy",
        "supervisor_initialized": supervisor_initialized,
        "active_sessions": active_sessions,
        "timestamp": datetime.now().isoformat(),
    }


def format_session_cleared(session_id: str) -> dict:
    """
    세션 삭제 응답 포맷팅

    Args:
        session_id: 삭제된 세션 ID

    Returns:
        dict: 세션 삭제 응답
    """
    return {
        "status": "cleared",
        "session_id": session_id,
        "timestamp": datetime.now().isoformat(),
    }


# 에이전트 이름 표시용 매핑
AGENT_DISPLAY_NAMES = {
    "chat_agent": "대화",
    "search_agent": "검색",
    "participate_agent": "공구생성",
    "system": "시스템",
    "assistant": "어시스턴트",
    "user": "사용자",
    "supervisor": "관리자",
}


def get_agent_display_name(agent_name: str) -> str:
    """
    에이전트 이름을 표시용 이름으로 변환

    Args:
        agent_name: 에이전트 내부 이름

    Returns:
        str: 표시용 이름
    """
    return AGENT_DISPLAY_NAMES.get(agent_name, agent_name)


def truncate_content(content: str, max_length: int = 100) -> str:
    """
    컨텐츠를 지정된 길이로 자르기 (로깅용)

    Args:
        content: 원본 컨텐츠
        max_length: 최대 길이

    Returns:
        str: 잘린 컨텐츠
    """
    if len(content) <= max_length:
        return content
    return content[:max_length] + "..."


def safe_json_dumps(data: Any, **kwargs) -> str:
    """
    안전한 JSON 직렬화 (한글 지원)

    Args:
        data: 직렬화할 데이터
        **kwargs: json.dumps에 전달할 추가 인자

    Returns:
        str: JSON 문자열
    """
    default_kwargs = {
        "ensure_ascii": False,
        "separators": (",", ":"),
        "default": str,  # datetime 등 직렬화 안되는 객체는 문자열로 변환
    }
    default_kwargs.update(kwargs)

    try:
        return json.dumps(data, **default_kwargs)
    except (TypeError, ValueError) as e:
        # 직렬화 실패시 에러 메시지 반환
        return json.dumps(
            {
                "error": "JSON 직렬화 실패",
                "details": str(e),
                "data_type": str(type(data)),
            },
            **default_kwargs,
        )


def parse_structured_search_result(content: str) -> Optional[dict]:
    """
    구조화된 검색 결과 파싱

    Args:
        content: AI 응답 내용

    Returns:
        Optional[dict]: 파싱된 검색 결과 또는 None
    """
    try:
        start_marker = "STRUCTURED_RESULT_START\n"
        end_marker = "\nSTRUCTURED_RESULT_END"

        start_index = content.find(start_marker)
        end_index = content.find(end_marker)

        if start_index == -1 or end_index == -1:
            return None

        json_str = content[start_index + len(start_marker) : end_index]
        return json.loads(json_str)

    except (json.JSONDecodeError, ValueError) as e:
        logger.warning(f"⚠️ 구조화된 결과 파싱 실패: {e}")
        return None


def format_structured_search_response(content: str, agent: str, timestamp: str) -> dict:
    """
    구조화된 검색 결과를 프론트엔드용으로 포맷팅

    Args:
        content: AI 응답 내용
        agent: 에이전트 이름
        timestamp: 타임스탬프

    Returns:
        dict: 포맷된 응답
    """
    # 구조화된 결과 파싱 시도
    parsed_result = parse_structured_search_result(content)

    if parsed_result:
        # 구조화된 검색 결과인 경우 특별한 타입으로 표시
        return {
            "type": "structured_search_result",
            "content": content,  # 원본 내용 유지 (프론트엔드에서 파싱)
            "agent": agent,
            "timestamp": timestamp,
            "search_data": parsed_result,  # 파싱된 데이터도 포함
        }
    else:
        # 일반 AI 응답
        return format_ai_response(content, agent, timestamp)
