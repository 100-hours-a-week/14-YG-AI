# api/approval.py
import logging
from datetime import datetime
from typing import List, Dict

from fastapi import APIRouter, HTTPException
from langchain_core.messages import HumanMessage, AIMessage

from utils import format_approval_processed, format_pending_approvals
from core.session import (
    get_session_data,
    add_message_to_session,
    get_pending_approval,
    remove_pending_approval,
    get_session_pending_approvals,
)
from models.approval import ApprovalRequest

logger = logging.getLogger(__name__)

# FastAPI 라우터 생성
router = APIRouter(prefix="/chat", tags=["Approval"])


@router.post("/approve/{session_id}/{approval_id}")
async def approve_task(
    session_id: str, approval_id: str, approval_request: ApprovalRequest
):
    """
    사용자 승인/거부 처리

    Args:
        session_id: 세션 ID
        approval_id: 승인 ID
        approval_request: 승인 요청 데이터 (approved, reason)

    Returns:
        dict: 승인 처리 결과
    """
    logger.info(
        f"📝 승인 요청 처리 [세션: {session_id[:8]}...] "
        f"[승인ID: {approval_id[:8]}...] [승인: {approval_request.approved}]"
    )

    try:
        # 승인 정보 확인
        approval_info = get_pending_approval(approval_id)
        if not approval_info:
            raise HTTPException(status_code=404, detail="승인 요청을 찾을 수 없습니다.")

        # 세션 확인
        if approval_info["session_id"] != session_id:
            raise HTTPException(status_code=403, detail="잘못된 세션입니다.")

        # 세션 데이터 가져오기
        conversation_history = get_session_data(session_id)
        if not conversation_history:
            raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.")

        # 승인/거부 메시지 추가
        if approval_request.approved:
            approval_message = HumanMessage(
                content=f"✅ 작업을 승인합니다. {approval_request.reason or ''}"
            )
            logger.info(f"   ✅ 작업 승인됨: {approval_request.reason or '사유 없음'}")
        else:
            approval_message = HumanMessage(
                content=f"❌ 작업을 거부합니다. {approval_request.reason or ''}"
            )
            logger.info(f"   ❌ 작업 거부됨: {approval_request.reason or '사유 없음'}")

        # 세션에 승인/거부 메시지 추가
        add_message_to_session(session_id, approval_message)

        # 승인된 경우 완료 메시지 추가
        if approval_request.approved:
            completion_message = AIMessage(
                content="✅ 요청하신 작업이 완료되었습니다!",
                additional_kwargs={"agent": "system"},
            )
            add_message_to_session(session_id, completion_message)
            logger.info("   📋 완료 메시지 추가됨")
        else:
            # 거부된 경우 안내 메시지
            rejection_message = AIMessage(
                content="작업이 취소되었습니다. 다시 시도하시려면 말씀해주세요.",
                additional_kwargs={"agent": "system"},
            )
            add_message_to_session(session_id, rejection_message)
            logger.info("   📋 취소 메시지 추가됨")

        # 승인 정보 삭제
        remove_pending_approval(approval_id)
        logger.info(f"   🗑️ 승인 정보 삭제됨 [ID: {approval_id[:8]}...]")

        return format_approval_processed(
            approved=approval_request.approved,
            session_id=session_id,
            approval_id=approval_id,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"❌ 승인 처리 오류 [세션: {session_id[:8]}...] "
            f"[승인ID: {approval_id[:8]}...]: {e}",
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="승인 처리 중 오류가 발생했습니다.")


@router.get("/pending-approvals/{session_id}")
async def get_pending_approvals(session_id: str):
    """
    세션의 승인 대기 중인 작업 조회

    Args:
        session_id: 세션 ID

    Returns:
        dict: 대기 중인 승인 목록
    """
    try:
        pending_list = get_session_pending_approvals(session_id)

        # 타임스탬프를 ISO 형식으로 변환
        formatted_pending = []
        for approval in pending_list:
            formatted_approval = {
                "approval_id": approval["approval_id"],
                "task_description": approval["task_description"],
                "timestamp": (
                    approval["timestamp"].isoformat()
                    if hasattr(approval["timestamp"], "isoformat")
                    else str(approval["timestamp"])
                ),
            }
            formatted_pending.append(formatted_approval)

        logger.info(
            f"📋 승인 대기 목록 조회 [세션: {session_id[:8]}...] "
            f"[대기중: {len(formatted_pending)}개]"
        )

        return format_pending_approvals(session_id, formatted_pending)

    except Exception as e:
        logger.error(f"❌ 승인 대기 목록 조회 오류 [세션: {session_id[:8]}...]: {e}")
        raise HTTPException(
            status_code=500, detail="승인 대기 목록 조회 중 오류가 발생했습니다."
        )


@router.get("/approvals/stats")
async def get_approval_stats():
    """
    전체 승인 통계 조회

    Returns:
        dict: 승인 통계 데이터
    """
    try:
        from core.session import get_all_approval_stats

        stats = get_all_approval_stats()

        return {
            "total_pending_approvals": stats["total_pending"],
            "approvals_by_session": stats["by_session"],
            "oldest_pending_timestamp": stats["oldest_timestamp"],
            "average_pending_per_session": stats["average_per_session"],
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"❌ 승인 통계 조회 오류: {e}")
        raise HTTPException(
            status_code=500, detail="승인 통계 조회 중 오류가 발생했습니다."
        )


@router.delete("/approvals/{session_id}")
async def clear_session_approvals(session_id: str):
    """
    특정 세션의 모든 대기 중인 승인 삭제

    Args:
        session_id: 세션 ID

    Returns:
        dict: 삭제 결과
    """
    try:
        from core.session import clear_session_approvals as clear_approvals

        deleted_count = clear_approvals(session_id)

        logger.info(
            f"🗑️ 세션 승인 삭제 완료 [세션: {session_id[:8]}...] "
            f"[삭제된 승인: {deleted_count}개]"
        )

        return {
            "status": "cleared",
            "session_id": session_id,
            "deleted_approvals": deleted_count,
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"❌ 세션 승인 삭제 오류 [세션: {session_id[:8]}...]: {e}")
        raise HTTPException(status_code=500, detail="승인 삭제 중 오류가 발생했습니다.")


@router.post("/approvals/{approval_id}/extend")
async def extend_approval_timeout(approval_id: str, minutes: int = 30):
    """
    승인 타임아웃 연장

    Args:
        approval_id: 승인 ID
        minutes: 연장할 시간 (분)

    Returns:
        dict: 연장 결과
    """
    try:
        from core.session import extend_approval_timeout as extend_timeout

        if minutes <= 0 or minutes > 120:  # 최대 2시간
            raise HTTPException(
                status_code=400, detail="연장 시간은 1-120분 사이여야 합니다."
            )

        success = extend_timeout(approval_id, minutes)
        if not success:
            raise HTTPException(status_code=404, detail="승인 요청을 찾을 수 없습니다.")

        logger.info(
            f"⏰ 승인 타임아웃 연장 [ID: {approval_id[:8]}...] [연장: {minutes}분]"
        )

        return {
            "status": "extended",
            "approval_id": approval_id,
            "extended_minutes": minutes,
            "timestamp": datetime.now().isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 승인 타임아웃 연장 오류 [ID: {approval_id[:8]}...]: {e}")
        raise HTTPException(
            status_code=500, detail="승인 타임아웃 연장 중 오류가 발생했습니다."
        )
