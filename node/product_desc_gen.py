# node/generate.py

from langchain_core.prompts import PromptTemplate
from llm.factory import get_desc_gen_client
from config import PRODUCT_DESC_GEN_PROMPT, node_log
from typing import Dict

# 1) LLM 클라이언트와 프롬프트 준비
llm = get_desc_gen_client()
prompt_template = PromptTemplate.from_template(PRODUCT_DESC_GEN_PROMPT)


def product_desc_gen(state: Dict) -> Dict:
    """
    LangGraph 노드: RAG로부터 받은 documents를
    Summarizer 프롬프트에 넣고 LLM으로 요약을 생성합니다.
    """
    # node_log("GENERATE")
    node_log("GENERATE PRODUCT DESCRIPTION")
    docs = state["web_search"]
    # <document> 태그로 wrapping
    context = "\n\n".join(
        f"<document><content>{doc.page_content}</content></document>"
        for doc in docs
    )
    # 프롬프트 포맷팅 및 호출
    prompt = prompt_template.format(context=context)
    summary = llm.chat(prompt)
    state["generation"]["summary"] = summary
    # return state
    return {"generation": state["generation"]}
