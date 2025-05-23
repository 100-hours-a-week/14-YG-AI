from langchain_core.prompts import PromptTemplate
from llm.factory import get_title_gen_client
from config import PRODUCT_TITLE_GEN_PROMPT, node_log
from typing import Dict

# 1) LLM 클라이언트와 프롬프트 준비
llm = get_title_gen_client()
prompt_template = PromptTemplate.from_template(PRODUCT_TITLE_GEN_PROMPT)


def product_title_gen(state: Dict) -> Dict:
    """
    LangGraph 노드: 상품 정보를 바탕으로 LLM으로 상품 제목을 생성합니다.
    """
    node_log("GENERATE PRODUCT TITLE")

    prompt = prompt_template.format(
        context=state["generation"],
        product_lower_name=state["generation"]["product_lower_name"],
    )
    summary = llm.chat(prompt)
    state["generation"]["title"] = summary

    return {"generation": state["generation"]}
