# core/session.py
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from langchain_core.messages import BaseMessage

from config import settings

logger = logging.getLogger(__name__)

# 전역 세션 데이터 저장소
SESSION_DATA: Dict[str, List[BaseMessage]] = {}
PENDING_APPROVALS: Dict[str, Dict] = {}  # 승인 대기 중인 작업들
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

    def __init__(
        self, user_id: int, user_name: str, access_token: str, session_id: str
    ):
        self.context_data = {
            "user_id": user_id,
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

    # 해당 세션의 승인 대기 항목도 삭제
    approvals_to_delete = [
        aid
        for aid, info in PENDING_APPROVALS.items()
        if info["session_id"] == session_id
    ]

    deleted_approvals = 0
    for aid in approvals_to_delete:
        del PENDING_APPROVALS[aid]
        deleted_approvals += 1

    logger.info(
        f"🗑️ 세션 데이터 삭제 완료 [세션: {session_id[:8]}...] "
        f"[메시지: {message_count}개] [승인: {deleted_approvals}개]"
    )

    return deleted_approvals


def get_session_count() -> int:
    """
    전체 세션 수 조회

    Returns:
        int: 활성 세션 수
    """
    return len(SESSION_DATA)


def cleanup_old_sessions() -> int:
    """
    오래된 세션 정리 (현재는 수동 호출, 추후 스케줄러 연동 가능)

    Returns:
        int: 삭제된 세션 수
    """
    # 현재는 간단한 구현 (메시지 수 기준)
    # 추후 마지막 활동 시간 기준으로 개선 가능

    sessions_to_delete = []
    max_sessions = settings.server.max_sessions

    if len(SESSION_DATA) > max_sessions:
        # 메시지가 적은 세션부터 삭제
        session_items = [(sid, len(messages)) for sid, messages in SESSION_DATA.items()]
        session_items.sort(key=lambda x: x[1])  # 메시지 수 기준 오름차순

        excess_count = len(SESSION_DATA) - max_sessions
        sessions_to_delete = [item[0] for item in session_items[:excess_count]]

    deleted_count = 0
    for session_id in sessions_to_delete:
        clear_session_data(session_id)
        deleted_count += 1

    if deleted_count > 0:
        logger.info(f"🧹 오래된 세션 정리 완료 [삭제된 세션: {deleted_count}개]")

    return deleted_count


# ======================= 승인 관리 함수들 =======================


def add_pending_approval(
    approval_id: str, session_id: str, task_description: str, state: Dict
) -> None:
    """
    승인 대기 항목 추가

    Args:
        approval_id: 승인 ID
        session_id: 세션 ID
        task_description: 작업 설명
        state: 워크플로우 상태
    """
    PENDING_APPROVALS[approval_id] = {
        "session_id": session_id,
        "task_description": task_description,
        "timestamp": datetime.now(),
        "state": state,
    }

    logger.info(
        f"🔔 승인 대기 항목 추가 [ID: {approval_id[:8]}...] "
        f"[세션: {session_id[:8]}...] [작업: {task_description}]"
    )

    # 승인 대기 항목 수 제한
    if len(PENDING_APPROVALS) > settings.workflow.max_pending_approvals:
        cleanup_old_approvals()


def get_pending_approval(approval_id: str) -> Optional[Dict]:
    """
    승인 대기 항목 조회

    Args:
        approval_id: 승인 ID

    Returns:
        Optional[Dict]: 승인 정보 또는 None
    """
    return PENDING_APPROVALS.get(approval_id)


def remove_pending_approval(approval_id: str) -> bool:
    """
    승인 대기 항목 삭제

    Args:
        approval_id: 승인 ID

    Returns:
        bool: 삭제 성공 여부
    """
    if approval_id in PENDING_APPROVALS:
        approval_info = PENDING_APPROVALS[approval_id]
        del PENDING_APPROVALS[approval_id]

        logger.info(
            f"✅ 승인 항목 삭제 완료 [ID: {approval_id[:8]}...] "
            f"[세션: {approval_info['session_id'][:8]}...]"
        )
        return True

    logger.warning(f"⚠️ 승인 항목을 찾을 수 없음 [ID: {approval_id[:8]}...]")
    return False


def get_session_pending_approvals(session_id: str) -> List[Dict]:
    """
    특정 세션의 승인 대기 항목들 조회

    Args:
        session_id: 세션 ID

    Returns:
        List[Dict]: 승인 대기 항목 리스트
    """
    pending = []
    for aid, info in PENDING_APPROVALS.items():
        if info["session_id"] == session_id:
            pending.append(
                {
                    "approval_id": aid,
                    "task_description": info["task_description"],
                    "timestamp": info["timestamp"],
                }
            )

    return pending


def get_pending_approval_count() -> int:
    """
    전체 승인 대기 항목 수 조회

    Returns:
        int: 승인 대기 항목 수
    """
    return len(PENDING_APPROVALS)


def clear_session_approvals(session_id: str) -> int:
    """
    특정 세션의 모든 승인 대기 항목 삭제

    Args:
        session_id: 세션 ID

    Returns:
        int: 삭제된 승인 항목 수
    """
    approvals_to_delete = [
        aid
        for aid, info in PENDING_APPROVALS.items()
        if info["session_id"] == session_id
    ]

    deleted_count = 0
    for aid in approvals_to_delete:
        del PENDING_APPROVALS[aid]
        deleted_count += 1

    if deleted_count > 0:
        logger.info(
            f"🗑️ 세션 승인 항목 삭제 완료 [세션: {session_id[:8]}...] "
            f"[삭제된 승인: {deleted_count}개]"
        )

    return deleted_count


def cleanup_old_approvals() -> int:
    """
    오래된 승인 대기 항목 정리

    Returns:
        int: 삭제된 승인 항목 수
    """
    timeout_minutes = settings.workflow.approval_timeout_minutes
    cutoff_time = datetime.now() - timedelta(minutes=timeout_minutes)

    approvals_to_delete = [
        aid
        for aid, info in PENDING_APPROVALS.items()
        if info["timestamp"] < cutoff_time
    ]

    deleted_count = 0
    for aid in approvals_to_delete:
        approval_info = PENDING_APPROVALS[aid]
        del PENDING_APPROVALS[aid]
        deleted_count += 1

        logger.info(
            f"⏰ 타임아웃된 승인 항목 삭제 [ID: {aid[:8]}...] "
            f"[세션: {approval_info['session_id'][:8]}...] "
            f"[경과시간: {timeout_minutes}분 초과]"
        )

    return deleted_count


def extend_approval_timeout(approval_id: str, minutes: int) -> bool:
    """
    승인 타임아웃 연장

    Args:
        approval_id: 승인 ID
        minutes: 연장할 시간(분)

    Returns:
        bool: 연장 성공 여부
    """
    if approval_id not in PENDING_APPROVALS:
        return False

    # 타임스탬프를 현재 시간으로 업데이트하여 타임아웃 연장
    PENDING_APPROVALS[approval_id]["timestamp"] = datetime.now()

    logger.info(f"⏰ 승인 타임아웃 연장 [ID: {approval_id[:8]}...] [연장: {minutes}분]")

    return True


# ======================= 통계 함수들 =======================


def get_all_session_stats() -> Dict[str, Any]:
    """
    전체 세션 통계 조회

    Returns:
        Dict[str, Any]: 세션 통계 데이터
    """
    total_sessions = len(SESSION_DATA)
    total_messages = sum(len(messages) for messages in SESSION_DATA.values())
    total_pending = len(PENDING_APPROVALS)

    average_messages = total_messages / total_sessions if total_sessions > 0 else 0.0

    return {
        "total_sessions": total_sessions,
        "total_messages": total_messages,
        "total_pending_approvals": total_pending,
        "average_messages_per_session": round(average_messages, 2),
    }


def get_all_approval_stats() -> Dict[str, Any]:
    """
    전체 승인 통계 조회

    Returns:
        Dict[str, Any]: 승인 통계 데이터
    """
    total_pending = len(PENDING_APPROVALS)

    # 세션별 승인 수 계산
    by_session = {}
    oldest_timestamp = None

    for aid, info in PENDING_APPROVALS.items():
        session_id = info["session_id"]
        timestamp = info["timestamp"]

        by_session[session_id] = by_session.get(session_id, 0) + 1

        if oldest_timestamp is None or timestamp < oldest_timestamp:
            oldest_timestamp = timestamp

    # 세션당 평균 승인 수
    active_sessions = len(by_session)
    average_per_session = (
        total_pending / active_sessions if active_sessions > 0 else 0.0
    )

    return {
        "total_pending": total_pending,
        "by_session": by_session,
        "oldest_timestamp": oldest_timestamp.isoformat() if oldest_timestamp else None,
        "average_per_session": round(average_per_session, 2),
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
    pending_approvals = get_session_pending_approvals(session_id)

    # 메시지 타입별 통계
    from langchain_core.messages import HumanMessage, AIMessage

    human_count = sum(1 for msg in messages if isinstance(msg, HumanMessage))
    ai_count = sum(1 for msg in messages if isinstance(msg, AIMessage))

    return {
        "session_id": session_id,
        "total_messages": len(messages),
        "human_messages": human_count,
        "ai_messages": ai_count,
        "pending_approvals": len(pending_approvals),
        "last_activity": (
            messages[-1].additional_kwargs.get("timestamp") if messages else None
        ),
    }
