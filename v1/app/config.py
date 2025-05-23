import os
from dotenv import load_dotenv

load_dotenv()

## Summerize LLM 설정
LLM_PROVIDER_GENERATOR = os.getenv("LLM_PROVIDER_GENERATOR", "openai")
MODEL_NAME_GENERATOR = os.getenv("MODEL_NAME_GENERATOR", "gpt-4o")

# Hollucination Check LLM 설정
LLM_PROVIDER_GRADER = os.getenv("LLM_PROVIDER_GRADER", "openai")
MODEL_NAME_GRADER = os.getenv("MODEL_NAME_GRADER", "gpt-4o")

# Rewite query LLM 설정
LLM_PROVIDER_REWRITER = os.getenv("LLM_PROVIDER_REWRITER", "openai")
MODEL_NAME_REWRITER = os.getenv("MODEL_NAME_REWRITER", "gpt-4o")

# ── 일반 설정 ───────────────────────────
RECURSION_LIMIT = int(os.getenv("RECURSION_LIMIT", 15))
VERBOSE_NODES = bool(os.getenv("VERBOSE_NODES", True))


def node_log(name: str):
    """
    노드가 실행될 때 한 줄만 찍어주는 헬퍼.
    .env 의 VERBOSE_NODES 에 따라 on/off 됨.
    """
    if VERBOSE_NODES:
        print(f"==== [{name}] ====")


# ────────────── 프롬프트 ─────────────────
RAG_Query = """"({product_name})에서 보여주는 메인 상품의 가격(판매가,정가)과 개수(수량), 무게, 특징과 같은 정보"""

# html logic으로 가는 domain
html_domain = ["myprotein", "11st", "gsshop", "brand.naver"]

PRODUCT_ANNC_PARCER_PROMPT = """
다음은 HTML에서 텍스트만 추출한 상품 페이지 정보입니다.  
여러 종류의 부가 정보(브랜드, 리뷰, 배송 안내, 카테고리, 프로모션 등)가 혼합되어 있습니다.

아래 네 필드를 반드시 JSON 형식으로만 응답하세요:
- product_name (문자열): 실제 상품명. 입력 텍스트에서 가장 먼저 등장하는 정식 상품명을 그대로 사용합니다.
- product_lower_name (문자열): 상품의 대중적인 이름. 상품을 포함하는 카테고리를 의미합니다. 상품명에서 불필요한 정보는 제거합니다. 예: 햇반 직은공기 130g 36개입 -> 햇반
- total_price (정수): 최종 판매가(할인 적용 후). ‘원’ 또는 '₩'를 제거하고 숫자만 추출합니다. 이전 상품 가격은 무시하고, 할인이 적용 된 실제 판매가를 찾습니다.
- count (정수): 판매 단위. 묶음의 개수. “2개”, “'500g x 2팩'에서 2팩” 등 표기된 수량을 파싱합니다. 개수 단위가 있는지 반드시 확인하고 파싱합니다, 수량 표기가 없으면 1로 간주합니다. 단위는 제거합니다.

# context: {context}

# 예시 출력 스키마: {format_instructions}
"""


# 수정 해야함 node_log("Generate Product Description")
PRODUCT_DESC_GEN_PROMPT = """
당신은 특정 제품을 검색한 결과로부터 제품에 대한 특징을 추출해 홍보글을 만들어주는 전문가 AI입니다. 
사용자가 쉽게 이해할 수 있도록 다음과 같은 내용을 지켜주세요.
- 중요한 제품 정보를 한국어로 자세하고 정확하게 요약하세요. 
- 제품의 주요 특징과 장점 등을 포함하되, 단점을 포함하지 마세요. 
- 주어진 내용에 없는 정보는 추측하지 마세요.
- 문장마다 적절한 이모지를 활용하세요.
- 판매하기 위한 홍보글 형식으로 만들어주세요.
- **반드시 두 줄 공백을 문장의 끝에 넣어주세요.**


# context: {context}

# 5문장 이내로 홍보글을 만들어주세요. 
"""

PRODUCT_TITLE_GEN_PROMPT = """
아래 조건에 맞춰 제품 홍보 제목을 생성해주세요.
반드시 조건에 맞춰 작성해 주세요.
반드시 하나의 제목을 작성하고, 제목의 길이를 작성하지 마세요.

제품 정보: {context}

조건
1. {product_lower_name}을 포함해 반드시 최대 30자 이내로 작성
2. 친구에게 말하듯 자연스럽고 친근한 어조로
3. 인터넷 커뮤니터 언어체(음, 슴, ㅇㅇ, ㅋㅋ, ~ 등) 사용
4. 각 문장에 어울리는 이모지 포함
5. 클릭을 부르는 흥미 유발 표현 사용

제목:
"""

RAG_HALLU_PROMPT = """You are a grader assessing whether an LLM generation is grounded in supported by a set of retrieved facts. \n 
Give a binary score 'yes' or 'no'. 'Yes' means that the answer is grounded in supported by the set of facts.
In the set of facts, spelling and wording may not be accurate. Therefore, when comparing, we define that 
there are cases where consonants and vowels or similar pronunciations can be inferred."""

WEB_HALLU_PROMPT = """
You are a hallucination evaluator working with web search results.
You will receive:
- Set of facts: snippets, titles, and URLs retrieved by Tavily for the product.
- LLM generation: the summary text produced by the model.
Your task is to determine whether every statement in the generation is directly supported by at least one snippet or title from the search results.
If all statements are supported, output {"binary_score":"yes"}, otherwise {"binary_score":"no"}.
"""


REWRITE_PROMPT_SYSTEM = """You are a question re-writer that converts an input question to a better version that is optimized \n 
     for vectorstore retrieval. Look at the input and try to reason about the underlying semantic intent / meaning."""

REWRITE_PROMPT_HUMAN = """사용자가 이전에 입력한 검색어는 다음과 같습니다: {retriever_query}
            이 검색어를 검색기에서 가장 관련성 높은 결과를 찾을 수 있도록, 
            구체적인 질의 문장으로 다시 작성해 주세요."""
