# local.py (수정된 버전)
import logging

from fastapi import FastAPI, Depends, HTTPException, Response  # 쉼표 제거
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from config import settings
from api import include_all_routers
from workflow import create_supervisor_workflow, initialize_workflow_system

import nest_asyncio
from pyngrok import ngrok
import os

# ngrok 설정 (개발 환경에서만 사용)
ngrok_auth_token = os.getenv("NGROK_AUTH_TOKEN")
ngrok.set_auth_token(ngrok_auth_token)

# 로깅 설정
logging.basicConfig(level=settings.logging.level, format=settings.logging.format)
logger = logging.getLogger(__name__)

# FastAPI 앱 생성
app = FastAPI(
    title=f"{settings.app_name} (Local Development)",
    version=settings.app_version,
    description=settings.description,
    debug=True,
)

# # CORS 미들웨어
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["localhost:3000"],
#     allow_credentials=True,
#     allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
#     allow_headers=["*"],
# )

# 정적 파일 서빙
app.mount("/static", StaticFiles(directory="static"), name="static")

# 전역 워크플로우 앱
supervisor_app = None


def get_supervisor_app():
    """워크플로우 앱 의존성 함수"""
    global supervisor_app
    if supervisor_app is None:
        raise HTTPException(
            status_code=503, detail="워크플로우가 초기화되지 않았습니다"
        )
    return supervisor_app


@app.get("/")
async def root():
    """루트 경로에서 index.html 반환"""
    return FileResponse("static/index_moongsan.html")


@app.on_event("startup")
async def startup_event():
    """애플리케이션 시작 시 초기화"""
    global supervisor_app

    try:
        logger.info("🚀 개발 애플리케이션 시작...")

        # 워크플로우 시스템 초기화
        init_result = initialize_workflow_system()
        if init_result["status"] != "ok":
            logger.error(f"❌ 워크플로우 시스템 초기화 실패: {init_result['error']}")
            raise RuntimeError(f"워크플로우 초기화 실패: {init_result['error']}")

        # 슈퍼바이저 워크플로우 생성
        supervisor_app = create_supervisor_workflow()

        logger.info("✅ 워크플로우 초기화 완료")
        logger.info(f"📊 환경: {settings.environment}")
        logger.info(f"🌐 서버 포트: 3100 (개발)")

    except Exception as e:
        logger.error(f"❌ 시작 중 오류: {e}", exc_info=True)
        supervisor_app = None
        raise


@app.on_event("shutdown")
async def shutdown_event():
    """애플리케이션 종료 시 정리"""
    logger.info("🛑 개발 애플리케이션 종료...")

    # 워크플로우 정리
    from workflow import get_workflow_manager

    workflow_manager = get_workflow_manager()
    workflow_manager.reset()

    logger.info("✅ 정리 완료")


@app.get("/health")
async def simple_health(supervisor_app=Depends(get_supervisor_app)):
    return {
        "status": "healthy",
        "supervisor_ready": supervisor_app is not None,
        "environment": "production",
    }


@app.options("/chat/stream")
async def options_chat_stream():
    return Response(
        status_code=200,
        headers={
            "Access-Control-Allow-Origin": "http://localhost:3000",
            "Access-Control-Allow-Methods": "POST, OPTIONS",
            # "Access-Control-Allow-Credentials": "true",
            "Access-Control-Allow-Headers": "Content-Type",
        },
    )


# API 라우터 등록
include_all_routers(app)

# 비동기 환경 설정
# nest_asyncio.apply()

# # 기존 ngrok 터널이 있다면 종료
# try:
#     ngrok.kill()
# except:
#     pass

# # ngrok 터널 생성 및 공개 URL 출력
# public_url = ngrok.connect(3100)
# print(f"✅ 스트리밍 채팅 웹 페이지가 준비되었습니다!")
# print(f"💬 채팅 API: {public_url}/chat/completions")

# FastAPI 서버 실행
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,  # 문자열로 모듈:변수 형태
        host="0.0.0.0",
        port=8101,
        # reload=True,
        log_level=None,
    )
