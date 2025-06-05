from typing import Dict
from config import node_log 


def router(state: Dict) -> str:
    node_log("ROUTING")

    domain = state["url"]

    # for d in html_domain:
    #     if d in domain:
    #         return "fetch_html_tool"

    if "coupang.com" in domain:
        return "fetch_coupang_tool"
    else:
        return "fetch_html_tool"
