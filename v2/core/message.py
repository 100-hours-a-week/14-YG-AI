# core/message.py
import logging
import uuid
from typing import List, Dict, Any, Optional
from datetime import datetime

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langfuse.langchain import CallbackHandler

from config.settings import settings
from utils import (
    basemessage_to_dict,
    truncate_content,
)
from .session import (
    get_session_data,
    add_message_to_session,
    add_pending_approval,
    get_session_user_info,
)

logger = logging.getLogger(__name__)


def get_langfuse_client():
    """설정에 따른 Langfuse 클라이언트 반환"""
    if not settings.langfuse.is_configured:
        logger.warning("Langfuse가 설정되지 않음 - 트레이싱 비활성화")
        return None

    try:
        from langfuse import get_client

        return get_client(**settings.langfuse.client_config)
    except Exception as e:
        logger.error(f"Langfuse 클라이언트 초기화 실패: {e}")
        return None


langfuse = get_langfuse_client()


class MessageProcessor:
    """메시지 처리 및 워크플로우 실행을 담당하는 클래스"""

    def __init__(self, supervisor_app):
        """
        MessageProcessor 초기화

        Args:
            supervisor_app: LangGraph 워크플로우 앱
        """
        if supervisor_app is None:
            from workflow import create_supervisor_workflow

            supervisor_app = create_supervisor_workflow()

        self.supervisor_app = supervisor_app
        self.langfuse_enabled = settings.langfuse.is_configured

    async def process_user_message(
        self, message: str, session_id: str
    ) -> Dict[str, Any]:
        """
        사용자 메시지를 처리하고 워크플로우 실행

        Args:
            message: 사용자 메시지
            session_id: 세션 ID

        Returns:
            Dict[str, Any]: 처리 결과 및 새로운 메시지들
        """
        # 메시지 유효성 검사
        validation_result = self._validate_message(message, session_id)
        if not validation_result["valid"]:
            return {
                "success": False,
                "error": validation_result["error"],
                "new_messages": [],
            }

        # 사용자 메시지 추가
        user_message = HumanMessage(content=message)
        add_message_to_session(session_id, user_message)

        # 워크플로우 실행
        try:
            result = await self._execute_workflow(message, session_id)
            return result
        except Exception as e:
            logger.error(
                f"❌ 워크플로우 실행 오류 [세션: {session_id[:8]}...]: {e}",
                exc_info=True,
            )
            return {
                "success": False,
                "error": f"워크플로우 실행 중 오류가 발생했습니다: {str(e)}",
                "new_messages": [],
            }

    def _validate_message(self, message: str, session_id: str) -> Dict[str, Any]:
        """
        메시지 유효성 검사

        Args:
            message: 사용자 메시지
            session_id: 세션 ID

        Returns:
            Dict[str, Any]: 검증 결과
        """
        # 메시지 길이 체크
        if len(message) > settings.server.max_message_length:
            return {
                "valid": False,
                "error": f"메시지가 너무 깁니다. (최대 {settings.server.max_message_length}자)",
            }

        # 세션당 최대 메시지 수 체크
        conversation_history = get_session_data(session_id)
        if len(conversation_history) >= settings.server.max_history_per_session:
            return {
                "valid": False,
                "error": f"세션당 최대 메시지 수를 초과했습니다. (최대 {settings.server.max_history_per_session}개)",
            }

        return {"valid": True}

    async def _execute_workflow(self, message: str, session_id: str) -> Dict[str, Any]:
        """
        LangGraph 워크플로우 실행

        Args:
            message: 사용자 메시지
            session_id: 세션 ID

        Returns:
            Dict[str, Any]: 워크플로우 실행 결과
        """
        conversation_history = get_session_data(session_id)
        initial_message_count = len(conversation_history)

        logger.info(
            f"🚀 워크플로우 실행 [세션: {session_id[:8]}...] "
            f"[메시지: {len(conversation_history)}개] "
            f"[내용: {truncate_content(message, 50)}]"
        )

        # 워크플로우 입력 구성
        user_info = get_session_user_info(session_id)

        # 워크플로우 입력 구성
        workflow_input = {
            "messages": conversation_history,
            "next_agent": "supervisor",
            "human_approval_required": False,
            "human_approved": False,
            "current_task": None,
            "approval_id": None,
            "session_id": session_id,
            "user_id": user_info.get("user_id") if user_info else None,  # ✅ 수정
            "user_name": user_info.get("user_name") if user_info else None,  # ✅ 추가
        }

        # 콜백 핸들러 설정
        config = {"metadata": {"session_id": session_id}}

        if self.langfuse_enabled and langfuse:
            try:
                langfuse_handler = CallbackHandler(**settings.langfuse.client_config)
                config["callbacks"] = [langfuse_handler]
            except Exception as e:
                logger.warning(f"Langfuse 콜백 핸들러 생성 실패: {e}")

        # 워크플로우 실행
        try:
            final_state = await self.supervisor_app.ainvoke(
                workflow_input, config=config
            )
        except Exception as e:
            logger.error(f"워크플로우 실행 중 오류: {e}")
            return {
                "success": False,
                "error": f"워크플로우 실행 중 오류가 발생했습니다: {str(e)}",
                "new_messages": [],
            }

        # 결과 처리
        if not final_state or not final_state.get("messages"):
            return {
                "success": False,
                "error": "워크플로우가 응답을 생성하지 못했습니다.",
                "new_messages": [],
            }

        return await self._process_workflow_result(
            final_state, initial_message_count, session_id, None
        )

    async def _run_workflow(
        self,
        message: str,
        session_id: str,
        conversation_history: List,
        initial_message_count: int,
        span=None,
    ) -> Dict[str, Any]:
        """공통 워크플로우 실행 로직"""

        # 워크플로우 입력 구성
        workflow_input = {
            "messages": conversation_history,
            "next_agent": "supervisor",
            "human_approval_required": False,
            "human_approved": False,
            "current_task": None,
            "approval_id": None,
            "session_id": session_id,
            "user_id": (session_id.split("-")[0] if "-" in session_id else session_id),
        }

        # 콜백 핸들러 설정
        config = {"metadata": {"session_id": session_id}}

        if self.langfuse_enabled and langfuse:
            try:
                langfuse_handler = CallbackHandler(**settings.langfuse.client_config)
                config["callbacks"] = [langfuse_handler]
            except Exception as e:
                logger.warning(f"Langfuse 콜백 핸들러 생성 실패: {e}")

        # 워크플로우 실행
        try:
            final_state = await self.supervisor_app.ainvoke(
                workflow_input, config=config
            )
        except Exception as e:
            logger.error(f"워크플로우 실행 중 오류: {e}")
            return {
                "success": False,
                "error": f"워크플로우 실행 중 오류가 발생했습니다: {str(e)}",
                "new_messages": [],
            }

        # 결과 처리
        if not final_state or not final_state.get("messages"):
            return {
                "success": False,
                "error": "워크플로우가 응답을 생성하지 못했습니다.",
                "new_messages": [],
            }

        return await self._process_workflow_result(
            final_state, initial_message_count, session_id, span
        )

    async def _process_workflow_result(
        self, final_state: Dict, initial_message_count: int, session_id: str, span=None
    ) -> Dict[str, Any]:
        """워크플로우 결과 처리"""

        new_history = final_state["messages"]
        new_messages = new_history[initial_message_count:]

        # 새 메시지들을 세션에 추가
        for new_msg in new_messages:
            add_message_to_session(session_id, new_msg)

        logger.info(
            f"✅ 워크플로우 완료 [세션: {session_id[:8]}...] "
            f"[신규 응답: {len(new_messages)}개]"
        )

        # 메시지들을 딕셔너리 형태로 변환 및 승인 처리
        processed_messages = []
        for new_msg in new_messages:
            if isinstance(new_msg, AIMessage):
                processed_msg = self._process_ai_message(
                    new_msg, session_id, final_state, span
                )
                processed_messages.append(processed_msg)
            elif isinstance(new_msg, HumanMessage):
                processed_msg = basemessage_to_dict(new_msg)
                processed_messages.append(processed_msg)

        return {
            "success": True,
            "new_messages": processed_messages,
            "total_messages": len(new_history),
        }

    def _process_ai_message(
        self, message: AIMessage, session_id: str, final_state: Dict, span=None
    ) -> Dict[str, Any]:
        """
        AI 메시지 처리 및 승인 요청 처리 (Langfuse 설정 개선)

        Args:
            message: AI 메시지
            session_id: 세션 ID
            final_state: 워크플로우 최종 상태
            span: LangFuse span (선택적)

        Returns:
            Dict[str, Any]: 처리된 메시지 데이터
        """
        response_dict = basemessage_to_dict(message)
        agent_name = response_dict.get("agent", "unknown_agent")

        # LangFuse generation 기록 (조건부)
        if self.langfuse_enabled and langfuse and span:
            try:
                with langfuse.start_as_current_generation(
                    name=agent_name,
                ) as generation:
                    generation.update(
                        name=agent_name,
                        input=session_id,  # 임시로 세션 ID 사용
                        output=message.content,
                        model=settings.google_cloud.model_name,
                        metadata={
                            **response_dict,
                            "environment": settings.environment,
                            "session_length": len(get_session_data(session_id)),
                        },
                        session_id=session_id,
                        trace_id=span.trace_id,
                        parent_observation_id=span.id,
                    )
            except Exception as e:
                logger.warning(f"Langfuse generation 기록 실패: {e}")

        # 승인이 필요한 경우
        if response_dict.get("approval_required"):
            approval_id = response_dict.get("approval_id") or str(uuid.uuid4())

            # 승인 정보 저장
            add_pending_approval(
                approval_id=approval_id,
                session_id=session_id,
                task_description=response_dict.get("task_description"),
                state=final_state,
            )

            logger.info(
                f"🔔 승인 요청 생성 [ID: {approval_id[:8]}...] "
                f"[작업: {response_dict.get('task_description')}]"
            )

            # 승인 정보를 응답에 포함
            response_dict["approval_id"] = approval_id
            response_dict["requires_approval"] = True
        else:
            response_dict["requires_approval"] = False
            logger.info(
                f"💬 AI 응답 처리 완료 [에이전트: {agent_name}] "
                f"[내용: {truncate_content(message.content, 50)}]"
            )

        return response_dict


class ApprovalProcessor:
    """승인 처리를 담당하는 클래스 (Langfuse 설정 개선)"""

    def __init__(self):
        """ApprovalProcessor 초기화"""
        self.langfuse_enabled = settings.langfuse.is_configured

    def process_approval(
        self,
        session_id: str,
        approval_id: str,
        approved: bool,
        reason: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        사용자 승인/거부 처리

        Args:
            session_id: 세션 ID
            approval_id: 승인 ID
            approved: 승인 여부
            reason: 승인/거부 사유

        Returns:
            Dict[str, Any]: 처리 결과
        """
        from .session import get_pending_approval, remove_pending_approval

        # 승인 정보 확인
        approval_info = get_pending_approval(approval_id)
        if not approval_info:
            return {"success": False, "error": "승인 요청을 찾을 수 없습니다."}

        # 세션 확인
        if approval_info["session_id"] != session_id:
            return {"success": False, "error": "잘못된 세션입니다."}

        # Langfuse 트레이싱 (조건부)
        if self.langfuse_enabled and langfuse:
            return self._process_approval_with_tracing(
                session_id, approval_id, approved, reason, approval_info
            )
        else:
            return self._process_approval_without_tracing(
                session_id, approval_id, approved, reason, approval_info
            )

    def _process_approval_with_tracing(
        self,
        session_id: str,
        approval_id: str,
        approved: bool,
        reason: Optional[str],
        approval_info: Dict,
    ) -> Dict[str, Any]:
        """Langfuse 트레이싱과 함께 승인 처리"""

        try:
            with langfuse.start_as_current_span(
                name="approval-process",
                input={
                    "approval_id": approval_id,
                    "approved": approved,
                    "reason": reason,
                    "session_id": session_id,
                },
            ) as span:
                # 트레이스 속성 설정
                span.update_trace(
                    name="Approval Decision",
                    session_id=(
                        session_id.split("-")[0] if "-" in session_id else session_id
                    ),
                    tags=["approval", "human-in-loop"],
                    metadata={
                        "approval_id": approval_id,
                        "task_description": approval_info.get("task_description"),
                        "timestamp": datetime.now().isoformat(),
                        "environment": settings.environment,
                    },
                )

                result = self._execute_approval_logic(
                    session_id, approval_id, approved, reason, approval_info
                )

                # span 결과 업데이트
                span.update(
                    output={
                        "approved": approved,
                        "success": result["success"],
                        "message_count": len(result.get("new_messages", [])),
                    }
                )

                return result

        except Exception as e:
            logger.warning(f"Langfuse 트레이싱 중 오류: {e}")
            return self._execute_approval_logic(
                session_id, approval_id, approved, reason, approval_info
            )

    def _process_approval_without_tracing(
        self,
        session_id: str,
        approval_id: str,
        approved: bool,
        reason: Optional[str],
        approval_info: Dict,
    ) -> Dict[str, Any]:
        """트레이싱 없이 승인 처리"""
        logger.info("트레이싱 없이 승인 처리")
        return self._execute_approval_logic(
            session_id, approval_id, approved, reason, approval_info
        )

    def _execute_approval_logic(
        self,
        session_id: str,
        approval_id: str,
        approved: bool,
        reason: Optional[str],
        approval_info: Dict,
    ) -> Dict[str, Any]:
        """승인 처리 핵심 로직"""
        from .session import remove_pending_approval

        # 승인/거부 메시지 생성
        if approved:
            approval_message = HumanMessage(
                content=f"✅ 작업을 승인합니다. {reason or ''}"
            )
            completion_message = AIMessage(
                content="✅ 요청하신 작업이 완료되었습니다!",
                additional_kwargs={"agent": "system"},
            )
            result_messages = [approval_message, completion_message]

            logger.info(
                f"✅ 작업 승인됨 [ID: {approval_id[:8]}...]: {reason or '사유 없음'}"
            )
        else:
            approval_message = HumanMessage(
                content=f"❌ 작업을 거부합니다. {reason or ''}"
            )
            rejection_message = AIMessage(
                content="작업이 취소되었습니다. 다시 시도하시려면 말씀해주세요.",
                additional_kwargs={"agent": "system"},
            )
            result_messages = [approval_message, rejection_message]

            logger.info(
                f"❌ 작업 거부됨 [ID: {approval_id[:8]}...]: {reason or '사유 없음'}"
            )

        # 세션에 메시지들 추가
        for msg in result_messages:
            add_message_to_session(session_id, msg)

        # 승인 정보 삭제
        remove_pending_approval(approval_id)

        # 메시지들을 딕셔너리 형태로 변환
        processed_messages = [basemessage_to_dict(msg) for msg in result_messages]

        return {
            "success": True,
            "approved": approved,
            "new_messages": processed_messages,
            "approval_id": approval_id,
        }


def create_message_processor(supervisor_app) -> MessageProcessor:
    """
    MessageProcessor 인스턴스 생성

    Args:
        supervisor_app: LangGraph 워크플로우 앱

    Returns:
        MessageProcessor: 메시지 처리기 인스턴스
    """
    return MessageProcessor(supervisor_app)


def create_approval_processor() -> ApprovalProcessor:
    """
    ApprovalProcessor 인스턴스 생성

    Returns:
        ApprovalProcessor: 승인 처리기 인스턴스
    """
    return ApprovalProcessor()
