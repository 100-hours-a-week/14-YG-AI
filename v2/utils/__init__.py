# utils/__init__.py
"""
유틸리티 모듈

공통으로 사용되는 유틸리티 함수들을 모아둔 패키지입니다.

사용 예시:
    from utils.formatting import basemessage_to_dict, format_sse_data
    from utils import format_error_response, format_ai_response
"""

from .formatting import (
    basemessage_to_dict,
    format_sse_data,
    format_error_response,
    format_ai_response,
    format_processing_message,
    format_completion_message,
    format_chat_history,
    format_health_check,
    format_session_cleared,
    get_agent_display_name,
    truncate_content,
    safe_json_dumps,
    parse_structured_search_result,
    format_structured_search_response,
)

__all__ = [
    # 메시지 포맷팅
    "basemessage_to_dict",
    "format_sse_data",
    # 응답 포맷팅
    "format_error_response",
    "format_ai_response",
    "format_processing_message",
    "format_completion_message",
    # 데이터 포맷팅
    "format_chat_history",
    "format_health_check",
    "format_session_cleared",
    # 유틸리티
    "get_agent_display_name",
    "truncate_content",
    "safe_json_dumps",
    "parse_structured_search_result",
    "format_structured_search_response",
]
