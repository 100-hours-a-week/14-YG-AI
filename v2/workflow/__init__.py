# workflow/__init__.py
"""
워크플로우 관리 모듈

LangGraph 기반의 멀티 에이전트 워크플로우를 관리하는 패키지입니다.

주요 구성요소:
- agents: 각종 에이전트 생성 및 관리
- prompts: 에이전트 프롬프트 관리
- routing: 메시지 라우팅 로직
- supervisor: 메인 워크플로우 및 슈퍼바이저

사용 예시:
    from workflow import create_supervisor_workflow

    app = create_supervisor_workflow()
    result = await app.ainvoke(initial_state)
"""

# 메인 워크플로우
from .supervisor import (
    create_supervisor_workflow,
    get_workflow_manager,
    WorkflowManager,
    WorkflowState,
    validate_workflow_state,
    create_initial_state,
    get_workflow_stats,
)

# 에이전트 관리
from .agents import (
    AgentFactory,
    create_chat_agent,
    create_search_agent,
    create_participate_agent,
    create_supervisor_llm,
    get_agent_by_name,
    get_agent_info,
    validate_agent_configuration,
    run_agent_safe,
)

# 프롬프트 관리
from .prompts import (
    PromptManager,
    get_chat_agent_prompt,
    get_search_agent_prompt,
    get_participate_agent_prompt,
    get_supervisor_prompt,
    format_supervisor_prompt,
    get_prompt_metadata,
)

# 라우팅 시스템
from .routing import (
    MessageRouter,
    RouterDecision,
    RoutingAnalyzer,
    create_message_router,
    get_global_router,
    get_global_analyzer,
    validate_routing_decision,
    analyze_message_intent,
)

__all__ = [
    # 메인 워크플로우
    "create_supervisor_workflow",
    "get_workflow_manager",
    "WorkflowManager",
    "WorkflowState",
    "validate_workflow_state",
    "create_initial_state",
    "get_workflow_stats",
    # 에이전트 관리
    "AgentFactory",
    "create_chat_agent",
    "create_search_agent",
    "create_participate_agent",
    "create_supervisor_llm",
    "get_agent_by_name",
    "get_agent_info",
    "validate_agent_configuration",
    "run_agent_safe",
    # 프롬프트 관리
    "PromptManager",
    "get_chat_agent_prompt",
    "get_search_agent_prompt",
    "get_participate_agent_prompt",
    "get_supervisor_prompt",
    "format_supervisor_prompt",
    "get_prompt_metadata",
    # 라우팅 시스템
    "MessageRouter",
    "RouterDecision",
    "RoutingAnalyzer",
    "create_message_router",
    "get_global_router",
    "get_global_analyzer",
    "validate_routing_decision",
    "analyze_message_intent",
]


# 패키지 정보
__version__ = "1.0.0"
__author__ = "Chatbot Development Team"
__description__ = "LangGraph 기반 멀티 에이전트 워크플로우 시스템"


def get_package_info() -> dict:
    """패키지 정보 반환"""
    return {
        "name": "workflow",
        "version": __version__,
        "author": __author__,
        "description": __description__,
        "components": {
            "agents": "에이전트 생성 및 관리",
            "prompts": "프롬프트 템플릿 관리",
            "routing": "메시지 라우팅 시스템",
            "supervisor": "메인 워크플로우 관리",
        },
        "dependencies": [
            "langchain-core",
            "langgraph",
            "langchain-google-vertexai",
            "pydantic",
        ],
    }


def validate_package_dependencies() -> dict:
    """패키지 의존성 검증"""
    try:
        import langchain_core
        import langgraph
        import langchain_google_vertexai
        import pydantic

        return {
            "status": "ok",
            "dependencies": {
                "langchain_core": getattr(langchain_core, "__version__", "unknown"),
                "langgraph": getattr(langgraph, "__version__", "unknown"),
                "langchain_google_vertexai": getattr(
                    langchain_google_vertexai, "__version__", "unknown"
                ),
                "pydantic": getattr(pydantic, "__version__", "unknown"),
            },
        }
    except ImportError as e:
        return {
            "status": "error",
            "error": f"의존성 누락: {e}",
        }


def initialize_workflow_system() -> dict:
    """워크플로우 시스템 초기화"""
    try:
        # 의존성 검증
        deps_check = validate_package_dependencies()
        if deps_check["status"] != "ok":
            return deps_check

        # 에이전트 설정 검증
        agent_check = validate_agent_configuration()
        if agent_check["overall_status"] != "ok":
            return {
                "status": "error",
                "error": f"에이전트 설정 오류: {agent_check.get('error', 'unknown')}",
            }

        # 프롬프트 검증
        prompt_check = PromptManager.validate_prompts()
        if prompt_check["status"] != "ok":
            return {"status": "error", "error": "프롬프트 검증 실패"}

        # 워크플로우 생성 테스트
        workflow_app = create_supervisor_workflow()
        if workflow_app is None:
            return {"status": "error", "error": "워크플로우 생성 실패"}

        return {
            "status": "ok",
            "message": "워크플로우 시스템 초기화 완료",
            "components": {
                "agents": len(agent_check["agents"]),
                "prompts": len(prompt_check["prompts"]),
                "workflow": "initialized",
                "routing": "ready",
            },
        }

    except Exception as e:
        return {"status": "error", "error": f"초기화 실패: {e}"}


if __name__ == "__main__":
    # 패키지 초기화 테스트
    print("🚀 워크플로우 패키지 초기화 테스트...")

    # 패키지 정보 출력
    info = get_package_info()
    print(f"📦 패키지: {info['name']} v{info['version']}")
    print(f"📝 설명: {info['description']}")

    # 의존성 검증
    deps = validate_package_dependencies()
    if deps["status"] == "ok":
        print("✅ 의존성 검증 완료")
        for pkg, version in deps["dependencies"].items():
            print(f"   📚 {pkg}: {version}")
    else:
        print(f"❌ 의존성 검증 실패: {deps['error']}")

    # 시스템 초기화
    init_result = initialize_workflow_system()
    if init_result["status"] == "ok":
        print("✅ 워크플로우 시스템 초기화 성공!")
        print(f"   🤖 에이전트: {init_result['components']['agents']}개")
        print(f"   📝 프롬프트: {init_result['components']['prompts']}개")
        print(f"   🔧 워크플로우: {init_result['components']['workflow']}")
        print(f"   🧭 라우팅: {init_result['components']['routing']}")
    else:
        print(f"❌ 초기화 실패: {init_result['error']}")
