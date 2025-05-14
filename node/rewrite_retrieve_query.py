# node/rewrite_retrieve_query.py

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from llm.factory import get_rewriter_client
from config import REWRITE_PROMPT_SYSTEM, REWRITE_PROMPT_HUMAN, node_log
from typing import Dict

# 1) Rewriter LLM 클라이언트 가져오기
llm = get_rewriter_client()

# 2) 질의 재작성용 프롬프트 템플릿 정의
rewrite_prompt = ChatPromptTemplate.from_messages(
    [("system", REWRITE_PROMPT_SYSTEM), ("human", REWRITE_PROMPT_HUMAN)]
)

# 3) 프롬프트 + LLM + StrOutputParser 체인 생성
question_rewriter = rewrite_prompt | llm.chat | StrOutputParser()


def transform_retrieve_query(state: Dict) -> Dict:
    """
    LangGraph 노드: retriever_query를 재작성합니다.
    """
    node_log("TRANSFORM QUERY")
    better_query: str = question_rewriter.invoke(
        {
            "retriever_query": state["retriever_query"],
        }
    )
    state["retriever_query"] = better_query
    return state


def transform_web_search_query(state: Dict) -> Dict:
    """
    LangGraph 노드: retriever_query를 재작성합니다.
    """
    node_log("TRANSFORM QUERY")
    # 예: "망고향 스테비아 방울토마토 스윗마토 가격 리뷰"
    product_name = state["generation"]["product_lower_name"]

    # 리뷰만 붙여도 검색결과가 많이 달라짐
    better_query = f"{product_name} 내돈내산"

    state["web_search_query"] = better_query
    return state
