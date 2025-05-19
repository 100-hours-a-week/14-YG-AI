# node/route_question.py
from typing import Dict
from config import node_log  # , html_domain


def route_logic(state: Dict) -> str:
    node_log("ROUTE LOGIC")

    domain = state["url"]

    # for d in html_domain:
    #     if d in domain:
    #         return "fetch_html_tool"

    if "coupang.com" in domain:
        return "fetch_coupang_tool"
    else:
        return "fetch_html_tool"
