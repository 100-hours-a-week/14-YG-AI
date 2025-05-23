from tavily import TavilyClient
from langchain_core.documents import Document
from typing import Dict
from config import node_log
import os
from dotenv import load_dotenv

load_dotenv()

from langchain.schema import Document


def parse_search_dict(rec: dict) -> Document:
    title = rec.get("title", "")
    content = rec.get("content", "")

    # 제목과 내용만 page_content로 합치기
    page_content = f"{title}\n\n{content}"

    return Document(page_content=page_content)


def web_search_tool(state: Dict) -> Dict:
    node_log("WEB SEARCH")

    TAVILY_API_KEYS = [
        os.environ.get("TAVILY_API_KEY_tony_taek105"),  
        os.environ.get("TAVILY_API_KEY_tony_0913"),
        os.environ.get("TAVILY_API_KEY_milo_1"),
    ]
    
    blog_domains = ["blog.naver.com", "blog.daum.net", "tistory.com"]
    max_results = 3

    query = state["generation"]["product_lower_name"]
    search_query = f"상품 {query} 장점"

    for api_key in TAVILY_API_KEYS:
        client = TavilyClient(api_key)
        try:
            search_result = client.search(
                query=search_query,
                format_output=False,
                max_results=max_results,
                include_domains=blog_domains
            )

            results = search_result.get("results", [])
            if not results:
                print(f"[{api_key[:15]}...] 결과 없음")
                continue

            state["web_search"] = [parse_search_dict(rec) for rec in results]
            return state

        except Exception as e:
            print(f"예외 발생: {e}")
