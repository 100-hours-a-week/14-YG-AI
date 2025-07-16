# api/health.py
import sys
import logging
import psutil
from datetime import datetime
from typing import Dict, Any

from fastapi import APIRouter, HTTPException, Depends


from config import settings
from utils import format_health_check
from core.session import get_session_count

logger = logging.getLogger(__name__)

# FastAPI 라우터 생성
router = APIRouter(tags=["Health"])


def get_supervisor_app():
    """범용 워크플로우 앱 의존성 함수"""
    supervisor_app = None
    
    # 1순위: 현재 실행 중인 메인 모듈에서 가져오기
    main_module = sys.modules.get('__main__')
    if main_module and hasattr(main_module, 'supervisor_app'):
        supervisor_app = getattr(main_module, 'supervisor_app')
    
    # 2순위: app.py에서 가져오기 시도
    if supervisor_app is None:
        try:
            import app
            supervisor_app = getattr(app, 'supervisor_app', None)
        except ImportError:
            pass
    
    # 3순위: local.py에서 가져오기 시도
    if supervisor_app is None:
        try:
            import local
            supervisor_app = getattr(local, 'supervisor_app', None)
        except ImportError:
            pass
    
    if supervisor_app is None:
        raise HTTPException(
            status_code=503, detail="워크플로우가 초기화되지 않았습니다"
        )
    return supervisor_app


@router.get("/health")
async def health_check(supervisor_app=Depends(get_supervisor_app)):
    """
    헬스 체크 엔드포인트

    Returns:
        dict: 시스템 상태 정보
    """
    try:
        supervisor_initialized = supervisor_app is not None

        # 세션 및 승인 통계
        active_sessions = get_session_count()

        # 기본 헬스체크 응답
        health_data = format_health_check(
            supervisor_initialized=supervisor_initialized,
            active_sessions=active_sessions,
        )

        logger.info(
            f"💊 헬스체크 [슈퍼바이저: {supervisor_initialized}] "
            f"[세션: {active_sessions}개]"
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
async def detailed_health_check(supervisor_app=Depends(get_supervisor_app)):
    """
    상세 헬스 체크 엔드포인트

    Returns:
        dict: 상세 시스템 상태 정보
    """
    try:
        # 기본 상태 확인
        supervisor_initialized = supervisor_app is not None
        active_sessions = get_session_count()

        # 시스템 리소스 정보
        memory = psutil.virtual_memory()

        # 디스크 사용량 (루트 디렉토리)
        try:
            disk = psutil.disk_usage("/")
        except:
            # Windows나 다른 OS에서는 현재 디렉토리 사용
            disk = psutil.disk_usage(".")

        # CPU 정보
        try:
            load_avg = psutil.getloadavg() if hasattr(psutil, "getloadavg") else None
        except:
            load_avg = None

        # 전체 상태 판단
        overall_status = "healthy" if supervisor_initialized else "unhealthy"

        detailed_data = {
            "status": overall_status,
            "timestamp": datetime.now().isoformat(),
            # 앱 상태
            "application": {
                "supervisor_initialized": supervisor_initialized,
                "active_sessions": active_sessions,
                "environment": settings.environment,
                "version": settings.app_version,
            },
            # 시스템 리소스
            "system": {
                "memory_usage_percent": memory.percent,
                "memory_available_gb": round(memory.available / (1024**3), 2),
                "memory_total_gb": round(memory.total / (1024**3), 2),
                "disk_usage_percent": disk.percent,
                "disk_free_gb": round(disk.free / (1024**3), 2),
                "disk_total_gb": round(disk.total / (1024**3), 2),
                "cpu_count": psutil.cpu_count(),
                "cpu_percent": psutil.cpu_percent(interval=1),  # 1초간 측정
                "load_average": load_avg,
            },
            # 설정 상태
            "configuration": {
                "server_host": settings.server.host,
                "server_port": settings.server.port,
                "debug_mode": settings.server.debug,
                "max_sessions": settings.server.max_sessions,
                "max_message_length": settings.server.max_message_length,
            },
            # LangFuse 상태 (있다면)
            "services": {
                "langfuse": {
                    "enabled": getattr(settings, "langfuse", {}).get("enabled", False),
                    "configured": bool(
                        getattr(settings, "langfuse", {}).get("public_key", False)
                    ),
                }
            },
        }

        logger.info(
            f"💊 상세 헬스체크 [상태: {detailed_data['status']}] "
            f"[메모리: {memory.percent}%] [디스크: {disk.percent}%] "
            f"[세션: {active_sessions}개]"
        )

        return detailed_data

    except Exception as e:
        logger.error(f"❌ 상세 헬스체크 오류: {e}")
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat(),
        }
