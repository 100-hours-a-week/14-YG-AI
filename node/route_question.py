# node/route_question.py
from typing import Literal, Dict
from pydantic import BaseModel, Field

from llm.factory import get_router_client
from config import ROUTER_PROMPT, node_log


# Pydantic 데이터모델
class RouteQuery(BaseModel):
    datasource: Literal["fetch_html_tool", "fetch_coupang_tool", "parse_image_text"] = (
        Field(..., description="어떤 도구로 라우팅할지 선택합니다.")
    )


# LLM 클라이언트
llm = get_router_client()


def route_question(state: Dict) -> str:
    node_log("ROUTE QUESTION")

    prompt = (
        ROUTER_PROMPT.strip()
        + "\n\n"
        + "URL: "
        + state["url"]
        + "\n\n"
        + "== 응답 형식 ==\n"
        + "fetch_html_tool, fetch_coupang_tool, parse_image_text\n"
    )

    data = llm.chat(prompt).strip()

    return data
