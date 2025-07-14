# api/__init__.py
"""
API 라우터 모듈

FastAPI 라우터들을 모아둔 패키지입니다.

사용 예시:
    from api import chat_router, health_router

    app.include_router(chat_router)
    app.include_router(health_router)
"""

from .chat import router as chat_router
from .health import router as health_router

__all__ = [
    "chat_router",
    "health_router",
]


def include_all_routers(app):
    """
    모든 라우터를 FastAPI 앱에 등록

    Args:
        app: FastAPI 앱 인스턴스
    """
    app.include_router(chat_router)
    app.include_router(health_router)
