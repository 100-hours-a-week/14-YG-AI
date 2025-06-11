from typing import Dict
from config import node_log


def page_data_gate(state: Dict):
    """
    다양한 소스(fetch 계열 도구들)에서 가져온 페이지 데이터의 유효성 검사 및 다음 노드 결정
    """
    page_data_check(state)
    return state


def page_data_check(state: Dict) -> str:
    """
    페이지 데이터의 유무를 확인하고 다음 노드를 결정합니다.
    """
    if not state["page"]:
        return "parse_image_text"
    else:
        return "next"
