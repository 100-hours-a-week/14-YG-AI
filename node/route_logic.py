# node/route_question.py
from typing import Literal, Dict
from pydantic import BaseModel, Field

from llm.factory import get_router_client
from config import node_log, html_domain


# Pydantic 데이터모델
class RouteQuery(BaseModel):
    datasource: Literal["fetch_html_tool", "fetch_coupang_tool", "parse_image_text"] = (
        Field(..., description="어떤 도구로 라우팅할지 선택합니다.")
    )


# LLM 클라이언트
llm = get_router_client()


def route_logic(state: Dict) -> str:
    node_log("ROUTE LOGIC")

    domain = state["url"]

    for d in html_domain:
        if d in domain:
            return "fetch_html_tool"
    
    if "coupang" in domain:
        return "fetch_coupang_tool"
    
    return "parse_image_text"
