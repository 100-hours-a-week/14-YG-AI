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
            "current_task": None,
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

        return response_dict


def create_message_processor(supervisor_app) -> MessageProcessor:
    """
    MessageProcessor 인스턴스 생성

    Args:
        supervisor_app: LangGraph 워크플로우 앱

    Returns:
        MessageProcessor: 메시지 처리기 인스턴스
    """
    return MessageProcessor(supervisor_app)
