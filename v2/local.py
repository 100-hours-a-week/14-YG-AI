# local.py (수정된 버전)
import logging
from datetime import datetime

from fastapi import FastAPI, Depends, HTTPException  # 쉼표 제거
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from config import settings
from api import include_all_routers
from workflow import create_supervisor_workflow, initialize_workflow_system

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

# CORS 미들웨어
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
    return FileResponse("static/index.html")


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


# API 라우터 등록
include_all_routers(app)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "local:app",  # 문자열로 모듈:변수 형태
        host="0.0.0.0",
        port=3100,
        reload=True,
        log_level="debug",
    )
