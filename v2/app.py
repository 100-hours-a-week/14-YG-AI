# app.py (리팩토링된 버전)
import logging

from fastapi import FastAPI, Depends, HTTPException

from config import settings
from api import include_all_routers
from workflow import create_supervisor_workflow, initialize_workflow_system

# 로깅 설정
logging.basicConfig(level=settings.logging.level, format=settings.logging.format)
logger = logging.getLogger(__name__)

# FastAPI 앱 생성
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=settings.description,
    debug=settings.server.debug,
)
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


@app.on_event("startup")
async def startup_event():
    """애플리케이션 시작 시 초기화"""
    global supervisor_app

    try:
        logger.info("🚀 애플리케이션 시작...")

        # 워크플로우 시스템 초기화
        init_result = initialize_workflow_system()
        if init_result["status"] != "ok":
            logger.error(f"❌ 워크플로우 시스템 초기화 실패: {init_result['error']}")
            raise RuntimeError(f"워크플로우 초기화 실패: {init_result['error']}")

        # 슈퍼바이저 워크플로우 생성
        supervisor_app = create_supervisor_workflow()

        logger.info("✅ 워크플로우 초기화 완료")
        logger.info(f"📊 환경: {settings.environment}")
        logger.info(f"🌐 서버 포트: {settings.server.port}")

    except Exception as e:
        logger.error(f"❌ 시작 중 오류: {e}", exc_info=True)
        supervisor_app = None
        raise


@app.on_event("shutdown")
async def shutdown_event():
    """애플리케이션 종료 시 정리"""
    logger.info("🛑 애플리케이션 종료...")

    # 워크플로우 정리
    from workflow import get_workflow_manager

    workflow_manager = get_workflow_manager()
    workflow_manager.reset()

    logger.info("✅ 정리 완료")


# 간단한 헬스체크
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
        "app:app",
        host=settings.server.host,
        port=settings.server.port,
        reload=settings.server.reload,
        log_config=None,
    )
