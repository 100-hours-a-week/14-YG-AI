# config/settings.py
import os
from typing import Optional, List
from pydantic import field_validator
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()


class PostgresSettings(BaseSettings):
    """Postgres 설정"""

    # PostgreSQL 설정
    host: str = os.getenv("PG_HOST")
    port: int = int(os.getenv("PG_PORT"))
    user: str = os.getenv("PG_USER")
    password: str = os.getenv("PG_PASSWORD")
    dbname: str = os.getenv("PG_DBNAME")

    # 벡터 DB 관련
    vector_dimension: int = 4096

    @property
    def connection_params(self) -> dict:
        """psycopg2 연결 파라미터 반환"""
        return {
            "host": self.host,
            "port": self.port,
            "user": self.user,
            "password": self.password,
            "dbname": self.dbname,
        }

    class Config:
        env_prefix = "PG_"
        extra = "ignore"


class MySQLSettings(BaseSettings):
    """MySQL 및 SSH 터널링 설정"""

    # MySQL 설정
    db_host: str = os.getenv("MYSQL_DB_HOST")
    db_port: int = int(os.getenv("MYSQL_DB_PORT"))
    db_user: str = os.getenv("MYSQL_DB_USER")
    db_password: str = os.getenv("MYSQL_DB_PASSWORD")
    db_name: str = os.getenv("MYSQL_DB_NAME")
    db_charset: str = os.getenv("MYSQL_DB_CHARSET")

    # SSH 설정
    ssh_host: str = os.getenv("MYSQL_SSH_HOST")
    ssh_port: int = int(os.getenv("MYSQL_SSH_PORT"))
    ssh_user: str = os.getenv("MYSQL_SSH_USER")
    ssh_pkey_path: str = os.getenv("MYSQL_SSH_PKEY_PATH")

    @property
    def connection_params(self) -> dict:
        """MySQL 연결 파라미터 반환"""
        return {
            "host": self.db_host,
            "port": self.db_port,
            "user": self.db_user,
            "password": self.db_password,
            "database": self.db_name,
            "charset": self.db_charset,
        }

    @property
    def ssh_params(self) -> dict:
        """SSH 터널링 파라미터 반환"""
        return {
            "ssh_host": self.ssh_host,
            "ssh_port": self.ssh_port,
            "ssh_user": self.ssh_user,
            "ssh_pkey_path": self.ssh_pkey_path,
            "remote_host": self.db_host,
            "remote_port": self.db_port,
        }

    class Config:
        env_prefix = "MYSQL_"
        extra = "ignore"


class GoogleCloudSettings(BaseSettings):
    """Google Cloud 및 Vertex AI 설정"""

    project: str = os.getenv("GOOGLE_CLOUD_PROJECT")
    location: str = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
    credentials_path: str = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")

    # LLM 설정
    model_name: str = "gemini-2.0-flash"
    temperature: float = 0.7

    @field_validator("credentials_path")  # @validator 대신 @field_validator
    @classmethod
    def validate_credentials_path(cls, v):
        if not os.path.exists(v):
            raise ValueError(f"Google Cloud 인증 파일을 찾을 수 없습니다: {v}")
        return v

    class Config:
        env_prefix = "GOOGLE_"
        extra = "ignore"


class UpstageSettings(BaseSettings):
    """Upstage API 설정"""

    api_key: str = os.getenv("UPSTAGE_API_KEY")
    base_url: str = "https://api.upstage.ai/v1"
    embedding_model: str = "embedding-query"

    class Config:
        env_prefix = "UPSTAGE_"
        extra = "ignore"


class LangfuseSettings(BaseSettings):
    """Langfuse 트레이싱 설정"""

    enabled: bool = True
    public_key: Optional[str] = None
    secret_key: Optional[str] = None
    host: Optional[str] = None

    # 추가 설정들 (타입 수정)
    debug: bool = False
    flush_at: int = 15  # 자동 flush할 이벤트 수
    flush_interval: float = 0.5  # flush 간격 (초) - float로 명시
    request_timeout: int = 10  # 요청 타임아웃 (초)

    # 트레이싱 설정
    trace_sampling_rate: float = 1.0  # 샘플링 비율 (0.0-1.0)
    session_max_events: int = 1000  # 세션당 최대 이벤트 수

    @property
    def is_configured(self) -> bool:
        """Langfuse가 제대로 설정되었는지 확인"""
        return (
            self.enabled and self.public_key is not None and self.secret_key is not None
        )

    @property
    def client_config(self) -> dict:
        """Langfuse 클라이언트 설정 반환"""
        config = {
            "debug": self.debug,
            "flush_at": self.flush_at,
            "flush_interval": self.flush_interval,
            "request_timeout": self.request_timeout,
        }

        if self.host:
            config["host"] = self.host

        return config

    class Config:
        env_prefix = "LANGFUSE_"
        extra = "ignore"


class ServerSettings(BaseSettings):
    """서버 설정"""

    # FastAPI 설정
    host: str = os.getenv("FASTAPI_HOST")
    port: int = os.getenv("FASTAPI_PORT")
    reload: bool = True
    debug: bool = True

    # CORS 설정
    cors_origins: List[str] = ["*"]
    cors_allow_credentials: bool = True
    cors_allow_methods: List[str] = ["*"]
    cors_allow_headers: List[str] = ["*"]

    # 세션 설정
    session_timeout_minutes: int = 60
    max_sessions: int = 1000

    # 메시지 설정
    max_message_length: int = 5000
    max_history_per_session: int = 100

    class Config:
        env_prefix = "SERVER_"
        extra = "ignore"


class WorkflowSettings(BaseSettings):
    """워크플로우 설정"""

    # 에이전트 설정
    default_agent_temperature: float = 0.2
    supervisor_temperature: float = 0.1

    # 검색 설정
    default_search_limit: int = 5
    max_search_limit: int = 20

    class Config:
        env_prefix = "WORKFLOW_"
        extra = "ignore"


class LoggingSettings(BaseSettings):
    """로깅 설정"""

    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    # 파일 로깅
    log_to_file: bool = False
    log_file_path: str = "logs/chatbot.log"
    log_max_bytes: int = 10 * 1024 * 1024  # 10MB
    log_backup_count: int = 5

    # 외부 라이브러리 로깅 레벨
    langchain_log_level: str = "WARNING"
    google_log_level: str = "WARNING"

    class Config:
        env_prefix = "LOG_"
        extra = "ignore"


class Settings(BaseSettings):
    """전체 애플리케이션 설정"""

    # 앱 정보
    app_name: str = "뭉치면 산다 챗봇 API"
    app_version: str = "v1.0.0"
    description: str = (
        "뭉치면 산다 공동구매 게시물의 검색부터 생성까지 관련 내용은 무엇이든 물어보세요!"
    )

    # 환경 설정
    environment: str = "development"

    # 하위 설정들
    postgres: PostgresSettings = PostgresSettings()
    mysql: MySQLSettings = MySQLSettings()
    google_cloud: GoogleCloudSettings = GoogleCloudSettings()
    upstage: UpstageSettings = UpstageSettings()
    langfuse: LangfuseSettings = LangfuseSettings()
    server: ServerSettings = ServerSettings()
    workflow: WorkflowSettings = WorkflowSettings()
    logging: LoggingSettings = LoggingSettings()

    @property
    def is_development(self) -> bool:
        return self.environment.lower() in ["dev", "development", "local"]

    @property
    def is_production(self) -> bool:
        return self.environment.lower() in ["prod", "production"]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


# 전역 설정 인스턴스
settings = Settings()


# 편의 함수들
def get_settings() -> Settings:
    """설정 인스턴스 반환"""
    return settings


def get_pg_config() -> dict:
    """PostgreSQL 연결 설정 반환"""
    return settings.postgres.connection_params


def get_mysql_config() -> dict:
    """MySQL 연결 설정 반환"""
    return settings.mysql.connection_params


def get_mysql_ssh_config() -> dict:
    """MySQL SSH 터널링 설정 반환"""
    return settings.mysql.ssh_params


def get_google_cloud_config() -> dict:
    """Google Cloud 설정 반환"""
    return {
        "project": settings.google_cloud.project,
        "location": settings.google_cloud.location,
        "model_name": settings.google_cloud.model_name,
        "temperature": settings.google_cloud.temperature,
    }


def get_upstage_config() -> dict:
    """Upstage 설정 반환"""
    return {
        "api_key": settings.upstage.api_key,
        "base_url": settings.upstage.base_url,
        "model": settings.upstage.embedding_model,
    }


if __name__ == "__main__":
    # 설정 테스트
    print("🔧 설정 정보:")
    print(f"  앱 이름: {settings.app_name}")
    print(f"  버전: {settings.app_version}")
    print(f"  환경: {settings.environment}")
    print(f"  PG 호스트: {settings.postgres.host}")
    print(f"  MySQL 호스트: {settings.mysql.db_host}")
    print(f"  MySQL SSH 호스트: {settings.mysql.ssh_host}")
    print(f"  서버 포트: {settings.server.port}")
    print(f"  구글 프로젝트: {settings.google_cloud.project}")
    print(f"  개발 환경: {settings.is_development}")
