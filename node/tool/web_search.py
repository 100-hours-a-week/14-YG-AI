from langchain_teddynote.tools.tavily import TavilySearch
from langchain_core.documents import Document
from typing import Dict
from config import node_log

from langchain.schema import Document


def parse_search_dict(rec: dict) -> Document:
    title = rec.get("title", "")
    content = rec.get("content", "")

    # 제목과 내용만 page_content로 합치기
    page_content = f"{title}\n\n{content}"

    return Document(page_content=page_content)


def web_search_tool(state: Dict) -> Dict:
    node_log("WEB SEARCH")
    # 1) 블로그 도메인만 포함하도록 TavilySearch 인스턴스 생성
    blog_domains = ["blog.naver.com", "blog.daum.net", "tistory.com"]
    tavily_tool = TavilySearch(include_domains=blog_domains, max_results=3)

    query = state["generation"]["product_lower_name"]
    search_query = f"상품 {query} 장점"
    state["web_search_query"] = search_query

    # 2) 도메인 필터링 옵션을 기본으로 사용
    search_result = tavily_tool.search(
        query=search_query,
        format_output=False,
    )

    try:
        state["web_search"] = [parse_search_dict(rec) for rec in search_result]

        return state
    except Exception as e:
        print(e)
        return "tavily error"
