import json
from typing import Dict
from pydantic import BaseModel, Field, ValidationError

from llm.factory import get_grader_client
from config import RAG_HALLU_PROMPT, WEB_HALLU_PROMPT, node_log


class Groundedness(BaseModel):
    binary_score: str = Field(..., description="'yes' or 'no'")


# LLM 클라이언트 초기화
llm = get_grader_client()


def _grade(state: Dict, docs_key: str) -> str:
    """
    주어진 문서 키(docs_key)와 state['generation']를 바탕으로 grounding 여부를 평가합니다.
    """
    node_log(f"CHECK HALLUCINATION ({docs_key})")

    # 1) 문서 리스트를 flatten
    docs = state.get(docs_key, [])
    docs_str = "\n\n".join(
        f"<document><content>{doc.page_content}</content></document>"
        for doc in docs
    )
    if docs_key == "web_search":
        gen = state.get("generation", "")["summary"]
        HALLU_PROMPT = WEB_HALLU_PROMPT
    else:
        gen = state.get("generation", "")
        HALLU_PROMPT = RAG_HALLU_PROMPT

    # 2) prompt 생성
    prompt = (
        f"{HALLU_PROMPT.strip()}\n\n"
        f"Set of facts:\n\n{docs_str}\n\n"
        f"LLM generation:\n\n{gen}\n\n"
        f"== RESPONSE FORMAT (JSON) ==\n"
        f'{{"binary_score":"<yes|no>"}}'
    )

    # 3) LLM 호출 및 파싱
    raw = llm.chat(prompt).strip()
    try:
        result = Groundedness.parse_raw(raw)
        score = result.binary_score.lower()
    except (ValidationError, json.JSONDecodeError):
        score = "yes" if "yes" in raw.lower() else "no"

    # 4) decision 및 반환
    if score == "yes":
        node_log("DECISION: GENERATION IS GROUNDED IN DOCUMENTS")
        return "relevant"
    else:
        node_log("DECISION: GENERATION IS NOT GROUNDED IN DOCUMENTS, RE-TRY")
        return "hallucination"


def grade_generation_v_documents_and_annc_parser(state: Dict) -> str:
    """
    RAG 문서와 annc parser 결과를 바탕으로 grounding 여부 평가
    """
    return _grade(state, docs_key="documents")


def grade_generation_v_documents_and_desc_gen(state: Dict) -> str:
    """
    웹 검색 결과와 desc_gen 결과를 바탕으로 grounding 여부 평가
    """
    return _grade(state, docs_key="web_search")
