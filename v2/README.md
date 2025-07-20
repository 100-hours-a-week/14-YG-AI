### 🤖 뭉치면 산다 AI 어시스턴트
뭉치면 산다(뭉산) V2 AI 어시스턴트는 LangGraph 기반 멀티 에이전트 시스템을 활용하여 자연어로 공동구매 플랫폼의 기능을 이용할 수 있는 지능형 대화형 AI입니다.
🎯 핵심 특징
🤖 4개 전문 에이전트 시스템

💬 Chat Agent: 일상 대화 및 감정 지원 (온도: 0.7)
🔍 Search Agent: 공구 검색 및 추천 (온도: 0.0)
🔗 URL Search Agent: URL 기반 상품 검색 (온도: 0.0)
✨ Create Agent: 공구 생성 (온도: 0.0)

🧠 지능형 라우팅 시스템
사용자 메시지를 분석하여 가장 적절한 에이전트를 자동 선택
사용자 메시지 → LLM 기반 의도 분석 → 에이전트 선택
                     ↓ (실패시)
                규칙 기반 키워드 매칭
                     ↓ (실패시)  
                  기본 채팅 에이전트
📡 실시간 스트리밍 채팅

SSE (Server-Sent Events) 기반 실시간 응답
타이핑 효과로 자연스러운 대화 경험
JWT 쿠키 인증 (AccessToken)

🔍 하이브리드 검색 시스템

키워드 검색: 구체적인 상품명 검색
벡터 검색: 의미 기반 카테고리 검색 (pgvector + Upstage 임베딩)
조건 검색: 가격, 마감일, 정렬 옵션

🎨 구조화된 UI 응답
검색 결과를 카드형 UI로 표시하기 위한 특별한 JSON 형식
STRUCTURED_RESULT_START
{"search_type": "🎯 키워드 검색", "results": [...]}
STRUCTURED_RESULT_END

📁 디렉토리 구조
v2/
├── 🚀 app.py                      # FastAPI 메인 애플리케이션 (103줄)
├── 📦 requirements.txt            # Python 의존성
├── 🔧 .env / env_sample          # 환경변수 설정
│
├── 📡 api/                       # REST API 엔드포인트
│   ├── chat.py                   # 채팅 API (387줄)
│   └── health.py                 # 헬스체크 API (177줄)
│
├── ⚙️ config/                    # 설정 관리
│   └── settings.py               # Pydantic 기반 통합 설정 (325줄)
│
├── 🎯 core/                      # 핵심 비즈니스 로직
│   ├── session.py                # 세션 & 승인 데이터 관리
│   ├── message.py                # 메시지 처리 & 워크플로우 실행
│   └── streaming.py              # SSE 스트리밍 처리
│
├── 🤖 workflow/                  # LangGraph 워크플로우 시스템
│   ├── supervisor.py             # 메인 워크플로우 & 상태 관리 (434줄)
│   ├── agents.py                 # 4개 에이전트 생성 & 팩토리 (360줄)
│   ├── prompts.py                # 에이전트 프롬프트 템플릿
│   └── routing.py                # 지능형 메시지 라우팅
│
├── 🔧 tools/                     # 에이전트 도구들
│   ├── search_post_tool.py       # 공구 검색 도구 (1004줄)
│   ├── create_post_tool.py       # 공구 생성 도구
│   └── search_urls_tool.py       # URL 검색 도구
│
├── 🛠️ utils/                     # 유틸리티 함수들
│   └── formatting.py             # 메시지 포맷팅 & 변환
│
├── 🌐 static/                    # 웹 인터페이스 (임시)
│   └── index.html                # 대화형 웹 UI (1328줄)
│
└── 🐍 venv/                      # Python 가상환경

🌐 API 명세
📡 채팅 API
POST /chat/stream - 실시간 스트리밍 채팅
🔐 인증: JWT 토큰을 AccessToken 쿠키로 전송
Request:
json{
  "message": "콜라 공구 있어?",
  "session_id": "user13-20250714-001",  // 선택사항
  "user_id": 13,
  "user_name": "이정택"
}
Response (SSE Stream):
json// 1. 처리 시작
data: {"type": "processing", "content": "분석 중...", "timestamp": "2025-07-14T10:00:00Z"}

// 2. AI 응답  
data: {"type": "ai_response", "content": "응답 내용", "agent": "search", "timestamp": "..."}

// 3. 완료
data: {"type": "completion", "content": "응답 완료", "timestamp": "..."}
🔍 구조화된 검색 결과
Search Agent는 검색 결과를 카드형 UI로 표시하기 위해 특별한 형식으로 응답:
jsondata: {
  "type": "ai_response",
  "content": "STRUCTURED_RESULT_START\n{\"search_type\": \"🎯 키워드 검색\", \"query\": \"콜라\", \"total_count\": 3, \"results\": [...]}\nSTRUCTURED_RESULT_END\n\n참여하고 싶은 공구가 있으신가요?",
  "agent": "search"
}

🤖 챗봇 에이전트 시스템
💬 Chat Agent - 일상 대화

역할: 친근한 일상 대화 및 감정 지원
온도: 0.7 (창의적 응답)
도구: get_current_time()

예시:
👤 안녕하세요!
🤖 안녕하세요 이정택님! 😊 저는 공구 도우미입니다. 
   🔍 공구 검색, ✨ 공구 생성, 💬 일상 대화 등을 도와드려요!
🔍 Search Agent - 공구 검색

역할: 기존 공구 검색 및 추천
온도: 0.0 (정확한 검색)
도구: search_post() - PostgreSQL + 벡터 검색

검색 방식:

키워드 검색: "신라면", "콜라" 등 구체적 상품명
벡터 검색: "간식", "생필품" 등 의미 기반 카테고리
조건 검색: 가격, 마감일, 참여자 수 필터링

예시:
👤 콜라 공구 있어?
🤖 [카드형 검색 결과 3개 표시]
   📦 코카콜라 500ml 24개 - 15,000원
   👥 8/20명 참여 | ⏰ D-3 마감
🔗 URL Search Agent - URL 기반 검색

역할: URL에서 상품 정보 추출 및 검색
온도: 0.0 (정확한 처리)
도구: search_urls() - 쿠팡, 11번가 등 지원

예시:
👤 https://www.coupang.com/vp/products/123456 이걸로 공구 있어?
🤖 URL에서 상품 정보를 추출하고 있어요! 🔍
   [해당 상품 관련 기존 공구 검색 결과]
✨ Create Agent - 공구 생성

역할: 새로운 공구 생성
온도: 0.0 (안정적 생성)
도구: create_post() - 공구 게시글 생성

예시:
👤 콜라 공구 만들어줘
🤖 ✅ 공구 게시글이 성공적으로 생성되었습니다!
   새로운 콜라 공구가 등록되었어요! 🎉

🎯 사용자 활용 예시
💬 일상 대화
👤 안녕! 심심해
🤖 안녕하세요! 😊 심심하시군요! 
   재미있는 간식 공구를 둘러보시는 건 어떨까요? 🍪
   "과자 공구 찾아줘"라고 말씀해 주세요!
🔍 공구 검색
👤 신라면 공구 있어?
🤖 신라면 공구를 찾고 있어요! 🍜

[구조화된 카드 결과]
📦 신라면 멀티팩 40개입
💰 28,000원 | 👥 15/20명 | ⏰ D-3
📍 픽업: 강남역 | 🔗 [참여하기]
🔗 URL로 공구 생성
👤 https://www.coupang.com/vp/products/123456 이걸로 공구 만들어줘
🤖 제공해주신 URL의 상품 정보를 확인하고 있어요! 🔗
   ✅ 공구 게시글이 성공적으로 생성되었습니다!
🎨 조건별 검색
👤 천원 이하 간식 찾아줘
🤖 1,000원 이하 간식 공구를 찾고 있어요! 🔍

[4개 카드 결과]
🍪 오레오 미니 - 800원
🍬 하이츄 딸기맛 - 950원  
🍫 킨더조이 - 990원
🥜 허니버터칩 - 1,000원

⚙️ 기술 스택 & 설정
🛠️ 핵심 기술

AI/ML: LangChain, LangGraph, Google Vertex AI (Gemini 2.0 Flash)
Backend: FastAPI, Pydantic, uvicorn
Database: PostgreSQL (pgvector), MySQL (SSH 터널링)
임베딩: Upstage API
모니터링: LangFuse
Frontend: HTML5/CSS3 + Vanilla JS (임시)

🚀 실행 방법
bash# 1. 가상환경 설정
python3 -m venv venv
source venv/bin/activate

# 2. 의존성 설치
pip install -r requirements.txt

# 3. 환경변수 설정 (.env)
GOOGLE_CLOUD_PROJECT=your-project
UPSTAGE_API_KEY=your-key
PG_HOST=localhost
MYSQL_DB_HOST=your-host

# 4. 실행
python app.py

# 5. 접속: http://localhost:8000
⚠️ 주요 제한사항

메시지 길이: 1-1000자
인증: AccessToken 쿠키 필수
세션: 메모리 기반 (서버 재시작시 초기화)
타임아웃: 장시간 무응답시 연결 종료