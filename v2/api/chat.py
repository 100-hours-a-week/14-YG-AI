# api/chat.py
import sys
import uuid
import asyncio
from typing import AsyncGenerator
from datetime import datetime
import logging

from fastapi import APIRouter, HTTPException, Cookie, Depends
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
    # format_processing_message,
    # format_completion_message,
    truncate_content,
)
from core.session import (
    get_session_data,
    add_message_to_session,
)

logger = logging.getLogger(__name__)

# FastAPI 라우터 생성
router = APIRouter(prefix="/chat", tags=["Chat"])

# LangFuse 클라이언트
langfuse = get_client()

from pydantic import BaseModel, field_validator
from typing import Optional


class ChatMessage(BaseModel):
    """채팅 메시지 모델"""

    message: str
    session_id: Optional[str] = None
    # user_id: int
    # user_name: str # user_name-> nickname으로 긴급 변경
    nickname: str

    @field_validator("message")
    def validate_message(cls, v):
        if not v or not v.strip():
            raise ValueError("메시지는 비어있을 수 없습니다")
        if len(v) > 5000:
            raise ValueError("메시지가 너무 깁니다 (최대 5000자)")
        return v.strip()

    @field_validator("session_id")
    def validate_session_id(cls, v):
        if v is None:
            return None
        return str(v).strip() if str(v).strip() else None

    @field_validator("nickname")
    def validate_user_name(cls, v):
        if not v or not v.strip():
            raise ValueError("사용자 이름은 필수입니다")
        return v.strip()

    # @field_validator("user_id")
    # def validate_user_id(cls, v):
    #     if not v or v <= 0:
    #         raise ValueError("유효한 사용자 ID가 필요합니다")
    #     return v


from core.session import UserContext


async def process_message_stream(
    message: str,
    session_id: str,
    # user_id: int,
    user_name: str,
    supervisor_app,
    access_token: str,
) -> AsyncGenerator[str, None]:
    """
    메시지를 스트리밍 방식으로 처리

    Args:
        message: 사용자 메시지
        session_id: 세션 ID
        user_id: 사용자 ID (백엔드에서 검증됨) # 제거
        # user_name: 사용자 이름 (백엔드에서 검증됨)
        nickname: 닉네임
        supervisor_app: 워크플로우 앱
        access_token : 사용자 인증 토큰

    Yields:
        str: SSE 형식의 응답 데이터
    """
    print(session_id, user_name, message, access_token, "세션아이디 테스트")
    if supervisor_app is None:
        yield await format_sse_data(
            format_error_response("Supervisor가 초기화되지 않았습니다.")
        )
        return

    # 사용자 컨텍스트 설정
    with UserContext(
        # user_id=user_id,
        user_name=user_name,
        access_token=access_token,
        session_id=session_id,
    ):
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

            # # 첫 번째 사용자 메시지인 경우 시스템 메시지 추가
            # user_messages = [
            #     msg
            #     for msg in conversation_history
            #     if hasattr(msg, "type") and msg.type == "human"
            # ]
            if len(conversation_history) == 0 and user_name:  # 첫 대화 + 유저 정보 있음
                system_message = AIMessage(
                    content=f"💡 시스템: 현재 대화 중인 사용자는 `{user_name}`님 입니다. 대화에 참고해 주세요",
                    additional_kwargs={"agent": "system", "hidden": True},
                )
                # 대화 기록 맨 앞에 추가 (첫 번째 사용자 메시지 다음)
                conversation_history.insert(-1, system_message)
                # add_message_to_session(session_id, system_message)

            # yield await format_sse_data(format_processing_message("분석 중..."))

            # 새 사용자 메시지 추가
            user_message = HumanMessage(content=message)
            add_message_to_session(session_id, user_message)
            conversation_history = get_session_data(session_id)

            # yield await format_sse_data(
            #     format_processing_message("분석 중...", session_id)
            # )

            with langfuse.start_as_current_span(
                name="chat-message",
                input={
                    "message": message,
                    "session_id": session_id,
                    # "user_id": user_id,
                    "user_name": user_name,
                },
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
                    "messages": conversation_history.copy(),  # .copy() 추가!
                    "next_agent": "supervisor",
                    "current_task": None,
                    "session_id": session_id,
                    # "user_id": user_id,
                    "user_name": user_name,
                    "access_token": access_token,
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
                            # 승인 필요 에이전트인 경우 자동으로 승인 플래그 설정

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

                            # hidden 플래그가 있으면 스킵
                            if response_dict.get("hidden"):
                                continue  # ✅ 프론트엔드로 전송하지 않음

                            else:
                                # 일반 AI 응답
                                logger.info(
                                    f"   - AI 응답 전송 [에이전트: {response_dict['agent']}] "
                                    f"[내용: {truncate_content(response_dict['content'], 50)}]"
                                )
                                print(f"[내용:{response_dict['content']}")
                                yield await format_sse_data(
                                    format_ai_response(
                                        content=response_dict["content"],
                                        agent=response_dict["agent"],
                                        timestamp=response_dict["timestamp"],
                                        session_id=session_id,
                                    )
                                )

            # yield await format_sse_data(format_completion_message(session_id))

            # LangFuse 플러시
            langfuse.flush()

        except Exception as e:
            logger.error(
                f"❌ 메시지 처리 중 오류 [세션: {session_id[:8]}...]: {e}",
                exc_info=True,
            )
            yield await format_sse_data(
                format_error_response(f"처리 중 오류가 발생했습니다: {str(e)}")
            )


def get_supervisor_app():
    """범용 워크플로우 앱 의존성 함수"""
    supervisor_app = None

    # 1순위: 현재 실행 중인 메인 모듈에서 가져오기
    main_module = sys.modules.get("__main__")
    if main_module and hasattr(main_module, "supervisor_app"):
        supervisor_app = getattr(main_module, "supervisor_app")

    # 2순위: app.py에서 가져오기 시도
    if supervisor_app is None:
        try:
            import app

            supervisor_app = getattr(app, "supervisor_app", None)
        except ImportError:
            pass

    # 3순위: local.py에서 가져오기 시도
    if supervisor_app is None:
        try:
            import local

            supervisor_app = getattr(local, "supervisor_app", None)
        except ImportError:
            pass

    if supervisor_app is None:
        raise HTTPException(
            status_code=503, detail="워크플로우가 초기화되지 않았습니다"
        )
    return supervisor_app


@router.post("/stream")
async def chat_stream_endpoint(
    chat_message: ChatMessage,
    access_token: str = Cookie(None, alias="AccessToken"),
    supervisor_app=Depends(get_supervisor_app),
):
    """
    스트리밍 방식 채팅 엔드포인트

    Args:
        chat_message: 채팅 메시지 (message, session_id, user_name)
        access_token: 사용자 인증 토큰 (쿠키에서 가져옴, httpOnly 방식)

    Returns:
        StreamingResponse: SSE 스트리밍 응답
    """
    # print()
    print(access_token)
    # if not access_token:
    #     raise HTTPException(status_code=401, detail="인증 토큰이 없습니다.")

    if not chat_message.message.strip():
        raise HTTPException(status_code=400, detail="메시지가 비어있습니다.")

    session_id = chat_message.session_id or str(uuid.uuid4())

    # user_id = chat_message.user_id
    user_name = chat_message.nickname  # user_name -> nickname으로 긴급 변경

    # 디버깅 로그 추가
    print(f"🔍 디버깅:")
    print(f"  - 받은 chat_message: {chat_message}")
    # print(f"  - user_id: {user_id}")
    print(f"  - user_name: {user_name}")
    print(f"  - access_token: {access_token}")
    print(f"  - access_token type: {type(access_token)}")

    if not user_name:
        raise HTTPException(status_code=400, detail="사용자 정보가 없습니다.")

    return StreamingResponse(
        process_message_stream(
            chat_message.message,
            session_id,
            # user_id,
            user_name,
            supervisor_app,
            access_token,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Nginx 버퍼링 비활성화
            "Access-Control-Allow-Origin": "http://localhost:3000",
            "Content-Type": "text/event-stream",
        },
    )
