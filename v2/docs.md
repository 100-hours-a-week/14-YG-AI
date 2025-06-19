# 🛒 공구 챗봇 프로젝트 구조 문서

# 구조 바뀔때마다 업데이트 해야함! 

## 📋 프로젝트 개요

**프로젝트명**: 공구 챗봇 API  
**버전**: 5.0.0-hitl  
**설명**: LangGraph 기반 멀티 에이전트 시스템을 활용한 공구 검색 및 생성 챗봇  
**주요 기술**: FastAPI, LangChain, LangGraph, PostgreSQL, Google Vertex AI

---

## 📁 전체 디렉토리 구조

```
0618-moongsan-chatbot/
├── app.py                              # 🚀 메인 애플리케이션 진입점
├── requirements.txt                    # 📦 Python 의존성 목록
├── .env                               # 🔐 환경변수 (git 제외)
├── .env.example                       # 📝 환경변수 예제
├── .gitignore                         # 🚫 Git 제외 파일 목록
├── deft-observer-456807-c5-e9dda0532301.json  # 🔑 Google Cloud 인증 (git 제외)
├── 
├── config/                            # ⚙️ 설정 관리
│   ├── __init__.py                    # 📄 패키지 초기화 및 export
│   └── settings.py                    # 🔧 Pydantic 기반 설정 클래스들
│
├── api/                               # 🌐 FastAPI 라우터들
│   ├── __init__.py                    # 📄 라우터 통합 관리
│   ├── chat.py                        # 💬 채팅 관련 엔드포인트
│   ├── approval.py                    # ✅ 승인 관련 엔드포인트
│   └── health.py                      # 💊 헬스체크 및 시스템 상태
│
├── core/                              # 🎯 핵심 비즈니스 로직
│   ├── __init__.py                    # 📄 핵심 기능 export
│   ├── session.py                     # 👥 세션 및 승인 데이터 관리
│   ├── message.py                     # 📨 메시지 처리 및 워크플로우 실행
│   └── streaming.py                   # 📡 SSE 스트리밍 처리
│
├── workflow/                          # 🤖 LangGraph 워크플로우 시스템
│   ├── __init__.py                    # 📄 워크플로우 시스템 초기화
│   ├── supervisor.py                  # 👑 메인 워크플로우 및 상태 관리
│   ├── agents.py                      # 🎭 에이전트 생성 및 팩토리
│   ├── prompts.py                     # 📝 에이전트 프롬프트 템플릿
│   └── routing.py                     # 🧭 지능형 메시지 라우팅
│
├── tools/                             # 🔧 에이전트 도구들
│   ├── __init__.py                    # 📄 도구 패키지 초기화
│   └── search_post_tool.py            # 🔍 공구 검색 도구 (PostgreSQL + 벡터)
│
├── utils/                             # 🛠️ 유틸리티 함수들
│   ├── __init__.py                    # 📄 유틸리티 export
│   └── formatting.py                 # 🎨 메시지 포맷팅 및 변환
│
├── models/                            # 📊 데이터 모델들
│   ├── __init__.py                    # 📄 모델 export
│   ├── chat.py                        # 💬 채팅 관련 Pydantic 모델
│   └── approval.py                    # ✅ 승인 관련 Pydantic 모델
│
├── static/                            # 🌐 정적 파일 (임시 프론트엔드)
│   └── index.html                     # 🎨 웹 채팅 인터페이스
│
└── venv/                              # 🐍 Python 가상환경 (git 제외)
```

---

## 🗂️ 주요 파일 상세 설명

### 🚀 **메인 애플리케이션**

#### `app.py` (80줄)
- **역할**: FastAPI 애플리케이션 진입점
- **주요 기능**:
  - FastAPI 앱 초기화 및 설정
  - CORS 미들웨어 설정
  - API 라우터 등록
  - 워크플로우 시스템 초기화
- **주요 변경사항**: 410줄 → 80줄로 대폭 간소화

---

### ⚙️ **설정 관리 (config/)**

#### `config/settings.py` (250줄)
- **역할**: Pydantic 기반 통합 설정 관리
- **설정 클래스들**:
  - `DatabaseSettings`: PostgreSQL 연결 설정
  - `GoogleCloudSettings`: Vertex AI 및 인증 설정
  - `UpstageSettings`: 임베딩 API 설정
  - `LangfuseSettings`: 트레이싱 설정
  - `ServerSettings`: FastAPI 서버 설정
  - `WorkflowSettings`: 워크플로우 파라미터
  - `LoggingSettings`: 로깅 레벨 및 포맷
- **환경변수**: DB_*, GOOGLE_*, UPSTAGE_* 등 prefix 기반

#### `config/__init__.py` (30줄)
- **역할**: 설정 클래스들의 export 및 편의 함수 제공

---

### 🌐 **API 라우터 (api/)**

#### `api/chat.py` (200줄)
- **역할**: 채팅 관련 엔드포인트
- **엔드포인트**:
  - `POST /chat/stream`: SSE 스트리밍 채팅
  - `GET /chat/history/{session_id}`: 채팅 히스토리 조회
  - `DELETE /chat/session/{session_id}`: 세션 삭제
  - `GET /chat/sessions/stats`: 세션 통계
- **특징**: 스트리밍 매니저를 통한 실시간 응답 처리

#### `api/approval.py` (150줄)
- **역할**: 사용자 승인(HITL) 관련 엔드포인트
- **엔드포인트**:
  - `POST /chat/approve/{session_id}/{approval_id}`: 승인/거부 처리
  - `GET /chat/pending-approvals/{session_id}`: 대기 중인 승인 조회
  - `GET /chat/approvals/stats`: 승인 통계
  - `DELETE /chat/approvals/{session_id}`: 세션별 승인 삭제
  - `POST /chat/approvals/{approval_id}/extend`: 승인 타임아웃 연장

#### `api/health.py` (200줄)
- **역할**: 시스템 상태 및 헬스체크
- **엔드포인트**:
  - `GET /`: 루트 페이지 (index.html)
  - `GET /health`: 기본 헬스체크
  - `GET /health/detailed`: 상세 시스템 정보
  - `GET /health/database`: DB 전용 헬스체크
  - `GET /metrics`: 시스템 메트릭 (모니터링용)
  - `GET /status`: 간단한 상태 확인 (로드밸런서용)
  - `GET /ping`: 핑 엔드포인트
  - `GET /version`: 서비스 버전 정보
  - `GET /config/public`: 공개 설정 정보

#### `api/__init__.py` (25줄)
- **역할**: 모든 라우터를 FastAPI 앱에 일괄 등록

---

### 🎯 **핵심 비즈니스 로직 (core/)**

#### `core/session.py` (400줄)
- **역할**: 세션 및 승인 데이터 관리
- **전역 데이터**:
  - `SESSION_DATA`: 세션별 메시지 히스토리
  - `PENDING_APPROVALS`: 승인 대기 중인 작업들
- **주요 함수**:
  - 세션 관리: `get_session_data()`, `add_message_to_session()`, `clear_session_data()`
  - 승인 관리: `add_pending_approval()`, `get_pending_approval()`, `remove_pending_approval()`
  - 정리 기능: `cleanup_old_sessions()`, `cleanup_old_approvals()`
  - 통계: `get_all_session_stats()`, `get_all_approval_stats()`

#### `core/message.py` (250줄)
- **역할**: 메시지 처리 및 워크플로우 실행
- **주요 클래스**:
  - `MessageProcessor`: 사용자 메시지 처리 및 워크플로우 실행
  - `ApprovalProcessor`: 승인/거부 처리
- **특징**: LangFuse 트레이싱, 유효성 검사, 에러 처리 포함

#### `core/streaming.py` (200줄)
- **역할**: SSE 스트리밍 처리
- **주요 함수**:
  - `create_chat_stream()`: 채팅 스트리밍 생성
  - `create_approval_stream()`: 승인 결과 스트리밍
  - `handle_chat_stream()`: 검증 포함 스트리밍 처리
- **특징**: 에러 처리, 검증, 구조화된 응답 지원

#### `core/__init__.py` (50줄)
- **역할**: 핵심 기능들의 통합 export

---

### 🤖 **워크플로우 시스템 (workflow/)**

#### `workflow/supervisor.py` (400줄)
- **역할**: LangGraph 기반 메인 워크플로우
- **상태 정의**: `WorkflowState` (메시지, 에이전트, 승인 상태 등)
- **노드 함수들**:
  - `supervisor_routing_node()`: 지능형 라우팅
  - `run_chat_agent_node()`, `run_search_agent_node()`, `run_participate_agent_node()`
  - `human_approval_node()`: 사용자 승인 처리
- **워크플로우 관리**: `WorkflowManager` 클래스로 생성/초기화/재설정

#### `workflow/agents.py` (350줄)
- **역할**: 에이전트 생성 및 관리
- **에이전트들**:
  - `create_chat_agent()`: 일상 대화 에이전트 (온도: 0.7)
  - `create_search_agent()`: 공구 검색 에이전트 (온도: 0.0)
  - `create_participate_agent()`: 공구 생성 에이전트 (온도: 0.2)
- **관리 클래스**: `AgentFactory` (캐싱, 검증, 안전 실행)
- **도구들**: `get_current_time()`, `create_group_buy_post()`, `request_human_approval()`

#### `workflow/prompts.py` (400줄)
- **역할**: 에이전트 프롬프트 중앙 관리
- **프롬프트들**:
  - `get_chat_agent_prompt()`: 친근한 대화 어시스턴트
  - `get_search_agent_prompt()`: 구조화된 검색 결과 처리 규칙
  - `get_participate_agent_prompt()`: 3단계 공구 생성 프로세스
  - `get_supervisor_prompt()`: 라우팅 결정 프롬프트
- **관리 클래스**: `PromptManager` (프롬프트 검증, 메타데이터, 동적 업데이트)

#### `workflow/routing.py` (350줄)
- **역할**: 지능형 메시지 라우팅
- **주요 클래스**:
  - `RouterDecision`: 라우팅 결정 결과
  - `MessageRouter`: LLM 기반 스마트 라우팅
  - `RoutingAnalyzer`: 라우팅 통계 및 분석
- **라우팅 방식**: LLM 기반 → 규칙 기반 폴백 → 기본값 (chat)
- **분석 기능**: 라우팅 히스토리, 통계, 신뢰도 추적

#### `workflow/__init__.py` (100줄)
- **역할**: 워크플로우 시스템 통합 관리
- **기능**: 패키지 정보, 의존성 검증, 시스템 초기화

---

### 🔧 **도구 및 유틸리티**

#### `tools/search_post_tool.py` (625줄)
- **역할**: 공구 검색 도구 (PostgreSQL + 벡터 검색)
- **검색 기능**:
  - 키워드 검색: 구체적인 상품명
  - 벡터 검색: 의미 기반 카테고리 검색  
  - 조건 검색: 가격, 정렬, 날짜 조건
- **결과 포맷**: 구조화된 JSON (웹 UI 카드 형태)
- **DB 연동**: psycopg2, pgvector, Upstage 임베딩

#### `utils/formatting.py` (400줄)
- **역할**: 메시지 포맷팅 및 변환
- **주요 함수**:
  - `basemessage_to_dict()`: LangChain 메시지 → 프론트엔드용
  - `format_sse_data()`: SSE 형식 포맷팅
  - `format_*_response()`: 각종 응답 포맷터들
- **구조화된 검색**: `parse_structured_search_result()`, `format_structured_search_response()`

---

### 📊 **데이터 모델 (models/)**

#### `models/chat.py` (40줄)
- **모델들**:
  - `ChatMessage`: 채팅 메시지 요청
  - `ChatResponse`: 채팅 응답
  - `SessionStats`: 세션 통계
- **검증**: Pydantic field_validator 사용

#### `models/approval.py` (50줄)
- **모델들**:
  - `ApprovalRequest`: 승인 요청
  - `ApprovalInfo`: 승인 정보
  - `ApprovalResponse`: 승인 처리 응답
  - `PendingApprovals`: 대기 중인 승인 목록
  - `ApprovalStats`: 승인 통계

---

### 🌐 **프론트엔드 (static/)**

#### `static/index.html` (1000줄)
- **역할**: 웹 채팅 인터페이스 (임시, 추후 분리 예정)
- **주요 기능**:
  - SSE 기반 실시간 채팅
  - 구조화된 검색 결과 카드 표시
  - 승인 요청 UI
  - 세션 관리
- **스타일**: CSS Grid, Flexbox, 반응형 디자인
- **JavaScript**: 바닐라 JS, SSE EventSource, JSON 파싱

---

## 🔄 **데이터 플로우**

### 📨 **메시지 처리 플로우**

```
1. 사용자 메시지 입력 (index.html)
   ↓
2. POST /chat/stream (api/chat.py)
   ↓
3. StreamingManager.stream_chat_response() (core/streaming.py)
   ↓
4. MessageProcessor.process_user_message() (core/message.py)
   ↓
5. supervisor_workflow.ainvoke() (workflow/supervisor.py)
   ↓
6. supervisor_routing_node() → MessageRouter (workflow/routing.py)
   ↓
7. 선택된 에이전트 실행 (workflow/agents.py)
   ↓
8. 도구 실행 (tools/search_post_tool.py 등)
   ↓
9. 응답 포맷팅 (utils/formatting.py)
   ↓
10. SSE 스트리밍 응답 (브라우저)
```

### ✅ **승인 처리 플로우**

```
1. 공구 생성 요청
   ↓
2. participate_agent 실행
   ↓
3. request_human_approval() 도구 호출
   ↓
4. human_approval_node() 실행
   ↓
5. 승인 요청 UI 표시
   ↓
6. 사용자 승인/거부 (index.html)
   ↓
7. POST /chat/approve/{session_id}/{approval_id} (api/approval.py)
   ↓
8. ApprovalProcessor.process_approval() (core/message.py)
   ↓
9. 승인 결과 메시지 생성
   ↓
10. 완료/취소 메시지 표시
```

---

## 🔧 **주요 기술 스택**

### **백엔드**
- **FastAPI**: 웹 프레임워크
- **LangChain**: LLM 통합 프레임워크
- **LangGraph**: 멀티 에이전트 워크플로우
- **Pydantic**: 데이터 검증 및 설정 관리
- **PostgreSQL**: 메인 데이터베이스
- **pgvector**: 벡터 검색

### **AI/ML**
- **Google Vertex AI**: Gemini 2.0 Flash 모델
- **Upstage API**: 텍스트 임베딩
- **LangFuse**: AI 트레이싱 및 모니터링

### **프론트엔드 (임시)**
- **HTML5/CSS3**: 웹 인터페이스
- **Vanilla JavaScript**: 클라이언트 로직
- **SSE (Server-Sent Events)**: 실시간 통신

---

## 🚀 **실행 방법**

### **로컬 개발**
```bash
# 가상환경 활성화
source venv/bin/activate

# 의존성 설치
pip install -r requirements.txt

# 환경변수 설정
cp .env.example .env
# .env 파일을 실제 값으로 수정

# 애플리케이션 실행
python app.py
```

### **테스트**
```bash
# 설정 테스트
python -m config.settings

# 워크플로우 테스트
python -m workflow

# 개별 모듈 테스트
python -m workflow.agents
python -m workflow.routing
python -m tools.search_post_tool
```

### **API 테스트**
```bash
# 헬스체크
curl http://localhost:8000/health

# 채팅 테스트 (웹 브라우저)
http://localhost:8000
```

---

## 📝 **환경변수 설정**

### **필수 환경변수**
```bash
# Google Cloud
GOOGLE_PROJECT=deft-observer-456807-c5
GOOGLE_CREDENTIALS_PATH=deft-observer-*.json

# Upstage API
UPSTAGE_API_KEY=your_api_key

# 데이터베이스
DB_HOST=localhost
DB_USER=username
DB_PASSWORD=password
DB_DBNAME=database
```

### **선택적 환경변수**
```bash
# LangFuse (트레이싱)
LANGFUSE_PUBLIC_KEY=pk_*
LANGFUSE_SECRET_KEY=sk_*

# 서버 설정
SERVER_PORT=8000
SERVER_DEBUG=true

# 로깅
LOG_LEVEL=INFO
```

---

## 🔍 **주요 특징 및 개선사항**

### **✨ 새로운 기능**
- **모듈화된 아키텍처**: 기능별 명확한 분리
- **Pydantic 설정 관리**: 타입 안전한 설정 시스템
- **지능형 라우팅**: LLM 기반 + 규칙 기반 폴백
- **구조화된 검색 결과**: JSON 기반 카드형 UI
- **포괄적인 헬스체크**: 시스템 상태 모니터링
- **승인 타임아웃 관리**: 오래된 승인 자동 정리

### **🔧 기술적 개선**
- **코드 분리**: app.py 410줄 → 80줄
- **에러 처리**: 각 레이어별 세밀한 에러 처리
- **로깅**: 구조화된 로깅 시스템
- **캐싱**: 에이전트 및 LLM 인스턴스 캐싱
- **검증**: 입력 데이터 및 설정 검증
- **확장성**: 새로운 에이전트/도구 추가 용이

### **🛡️ 보안 강화**
- **환경변수 분리**: 민감한 정보 .env 관리
- **입력 검증**: Pydantic을 통한 데이터 검증
- **세션 관리**: 세션별 격리 및 타임아웃
- **에러 마스킹**: 내부 오류 정보 숨김

---

## 🔮 **향후 계획**

### **단기 (1-2주)**
- [ ] 프론트엔드 분리 (React/Vue)
- [ ] API 문서화 (Swagger)
- [ ] 단위 테스트 추가
- [ ] Docker 컨테이너화

### **중기 (1-2개월)**
- [ ] 사용자 인증 시스템
- [ ] 공구 참여 기능 구현
- [ ] 알림 시스템 (이메일/푸시)
- [ ] 관리자 대시보드

### **장기 (3-6개월)**
- [ ] 마이크로서비스 분리
- [ ] 결제 시스템 연동
- [ ] 모바일 앱 개발
- [ ] AI 모델 파인튜닝

---

## 📞 **문의 및 지원**

- **개발자**: Chatbot Development Team
- **버전**: 5.0.0-hitl
- **마지막 업데이트**: 2025-06-19

---

*이 문서는 프로젝트 구조 변경시 함께 업데이트되어야 합니다.*