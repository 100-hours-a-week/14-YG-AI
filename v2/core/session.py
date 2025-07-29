# core/session.py
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from langchain_core.messages import BaseMessage

from config import settings

logger = logging.getLogger(__name__)

# 전역 세션 데이터 저장소
SESSION_DATA: Dict[str, List[BaseMessage]] = {}
SESSION_USER_INFO: Dict[str, Dict] = {}

from contextvars import ContextVar
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)

# 스레드별 사용자 컨텍스트 저장
_user_context: ContextVar[Optional[Dict[str, Any]]] = ContextVar(
    "user_context", default=None
)


class UserContext:
    """사용자 인증 컨텍스트 매니저"""

    def __init__(self, user_name: str, access_token: str, session_id: str):
        self.context_data = {
            # "user_id": user_id,
            "user_name": user_name,
            "access_token": access_token,
            "session_id": session_id,
        }

    def __enter__(self):
        """컨텍스트 진입 시 사용자 정보 설정"""
        _user_context.set(self.context_data)
        logger.debug(
            f"🔑 사용자 컨텍스트 설정 [사용자: {self.context_data['user_name']}] [세션: {self.context_data['session_id'][:8]}...]"
        )
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """컨텍스트 종료 시 정리"""
        _user_context.set(None)
        logger.debug("🔓 사용자 컨텍스트 정리 완료")


def get_current_access_token() -> Optional[str]:
    """현재 사용자의 AccessToken 가져오기"""
    context = _user_context.get()
    return context.get("access_token") if context else None


def get_session_data(session_id: str) -> List[BaseMessage]:
    """
    세션의 대화 기록 조회

    Args:
        session_id: 세션 ID

    Returns:
        List[BaseMessage]: 대화 기록 리스트
    """
    if session_id not in SESSION_DATA:
        SESSION_DATA[session_id] = []
        logger.info(f"🆕 새 세션 생성 [세션: {session_id[:8]}...]")

    return SESSION_DATA[session_id]


def add_message_to_session(session_id: str, message: BaseMessage) -> None:
    """
    세션에 메시지 추가

    Args:
        session_id: 세션 ID
        message: 추가할 메시지
    """
    if session_id not in SESSION_DATA:
        SESSION_DATA[session_id] = []

    # 세션당 최대 메시지 수 제한
    if len(SESSION_DATA[session_id]) >= settings.server.max_history_per_session:
        # 가장 오래된 메시지 삭제 (FIFO)
        removed_msg = SESSION_DATA[session_id].pop(0)
        logger.info(
            f"📝 세션 메시지 한도 초과로 오래된 메시지 삭제 "
            f"[세션: {session_id[:8]}...] [삭제된 메시지: {type(removed_msg).__name__}]"
        )

    SESSION_DATA[session_id].append(message)
    logger.debug(
        f"💬 메시지 추가 [세션: {session_id[:8]}...] "
        f"[타입: {type(message).__name__}] [총 메시지: {len(SESSION_DATA[session_id])}개]"
    )


def get_session_message_count(session_id: str) -> int:
    """
    세션의 메시지 개수 조회

    Args:
        session_id: 세션 ID

    Returns:
        int: 메시지 개수
    """
    return len(SESSION_DATA.get(session_id, []))


def clear_session_data(session_id: str) -> int:
    """
    세션 데이터 삭제 (메시지 + 승인 대기 항목)

    Args:
        session_id: 삭제할 세션 ID

    Returns:
        int: 삭제된 승인 대기 항목 수
    """
    # 메시지 데이터 삭제
    message_count = 0
    if session_id in SESSION_DATA:
        message_count = len(SESSION_DATA[session_id])
        del SESSION_DATA[session_id]

    logger.info(
        f"🗑️ 세션 데이터 삭제 완료 [세션: {session_id[:8]}...] "
        f"[메시지: {message_count}개]"
    )

    return message_count


def get_session_count() -> int:
    """
    전체 세션 수 조회

    Returns:
        int: 활성 세션 수
    """
    return len(SESSION_DATA)


# ======================= 통계 함수들 =======================


def get_all_session_stats() -> Dict[str, Any]:
    """
    전체 세션 통계 조회

    Returns:
        Dict[str, Any]: 세션 통계 데이터
    """
    total_sessions = len(SESSION_DATA)
    total_messages = sum(len(messages) for messages in SESSION_DATA.values())

    average_messages = total_messages / total_sessions if total_sessions > 0 else 0.0

    return {
        "total_sessions": total_sessions,
        "total_messages": total_messages,
        "average_messages_per_session": round(average_messages, 2),
    }


def get_session_info(session_id: str) -> Dict[str, Any]:
    """
    특정 세션의 상세 정보 조회

    Args:
        session_id: 세션 ID

    Returns:
        Dict[str, Any]: 세션 상세 정보
    """
    messages = SESSION_DATA.get(session_id, [])
    # 메시지 타입별 통계
    from langchain_core.messages import HumanMessage, AIMessage

    human_count = sum(1 for msg in messages if isinstance(msg, HumanMessage))
    ai_count = sum(1 for msg in messages if isinstance(msg, AIMessage))

    return {
        "session_id": session_id,
        "total_messages": len(messages),
        "human_messages": human_count,
        "ai_messages": ai_count,
        "last_activity": (
            messages[-1].additional_kwargs.get("timestamp") if messages else None
        ),
    }
