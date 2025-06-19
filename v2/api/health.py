# api/health.py
import logging
import psutil
from datetime import datetime
from typing import Dict, Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from config import settings
from utils import format_health_check
from core.session import get_session_count, get_pending_approval_count

logger = logging.getLogger(__name__)

# FastAPI 라우터 생성
router = APIRouter(tags=["Health"])


@router.get("/")
async def root():
    """
    루트 엔드포인트 - 정적 파일 반환

    Returns:
        FileResponse: index.html 파일
    """
    return FileResponse("static/index.html")


@router.get("/health")
async def health_check():
    """
    헬스 체크 엔드포인트

    Returns:
        dict: 시스템 상태 정보
    """
    try:
        # supervisor_app 상태 확인 (전역에서 가져오기)
        from app import supervisor_app  # 임시 방식, 나중에 개선

        supervisor_initialized = supervisor_app is not None

        # 세션 및 승인 통계
        active_sessions = get_session_count()
        pending_approvals = get_pending_approval_count()

        # 기본 헬스체크 응답
        health_data = format_health_check(
            supervisor_initialized=supervisor_initialized,
            active_sessions=active_sessions,
            pending_approvals=pending_approvals,
        )

        logger.info(
            f"💊 헬스체크 [슈퍼바이저: {supervisor_initialized}] "
            f"[세션: {active_sessions}개] [승인: {pending_approvals}개]"
        )

        return health_data

    except Exception as e:
        logger.error(f"❌ 헬스체크 오류: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now().isoformat(),
        }


@router.get("/health/detailed")
async def detailed_health_check():
    """
    상세 헬스 체크 엔드포인트

    Returns:
        dict: 상세 시스템 상태 정보
    """
    try:
        # 기본 헬스체크 데이터
        from app import supervisor_app

        supervisor_initialized = supervisor_app is not None
        active_sessions = get_session_count()
        pending_approvals = get_pending_approval_count()

        # 시스템 리소스 정보
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage("/")

        # 데이터베이스 연결 테스트
        db_status = await test_database_connection()

        # Google Cloud 설정 확인
        gc_status = test_google_cloud_config()

        detailed_data = {
            "status": (
                "healthy"
                if supervisor_initialized and db_status["connected"]
                else "unhealthy"
            ),
            "timestamp": datetime.now().isoformat(),
            # 앱 상태
            "application": {
                "supervisor_initialized": supervisor_initialized,
                "active_sessions": active_sessions,
                "pending_approvals": pending_approvals,
                "environment": settings.environment,
                "version": settings.app_version,
            },
            # 시스템 리소스
            "system": {
                "memory_usage_percent": memory.percent,
                "memory_available_gb": round(memory.available / (1024**3), 2),
                "disk_usage_percent": disk.percent,
                "disk_free_gb": round(disk.free / (1024**3), 2),
                "cpu_count": psutil.cpu_count(),
                "load_average": (
                    psutil.getloadavg() if hasattr(psutil, "getloadavg") else None
                ),
            },
            # 외부 서비스 상태
            "services": {
                "database": db_status,
                "google_cloud": gc_status,
                "langfuse": {
                    "enabled": settings.langfuse.enabled,
                    "configured": bool(settings.langfuse.public_key),
                },
            },
            # 설정 상태
            "configuration": {
                "db_host": settings.database.host,
                "gc_project": settings.google_cloud.project,
                "server_port": settings.server.port,
                "debug_mode": settings.server.debug,
            },
        }

        logger.info(
            f"💊 상세 헬스체크 [상태: {detailed_data['status']}] "
            f"[메모리: {memory.percent}%] [디스크: {disk.percent}%] "
            f"[DB: {db_status['connected']}]"
        )

        return detailed_data

    except Exception as e:
        logger.error(f"❌ 상세 헬스체크 오류: {e}")
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat(),
        }
