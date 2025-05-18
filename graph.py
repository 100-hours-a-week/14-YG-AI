from typing_extensions import TypedDict, Annotated, Any
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from node.tool.fetch_html import fetch_html_tool
from node.tool.parse_image_text import parse_image_text
from node.tool.web_search import web_search_tool
from node.tool.fetch_coupang import fetch_coupang_tool


from node.route_logic import route_logic
from node.page_data_gate import page_data_gate, page_data_check
from node.rag_retrieve import rag_retrieve

# from node.generate import generate
from node.rewrite_retrieve_query import (
    transform_retrieve_query,
    transform_web_search_query,
)
from node.groundness_check import grade_generation_v_documents_and_annc_parser
from node.product_annc_parser import product_annc_parser
from node.product_desc_gen import product_desc_gen
from node.product_title_gen import product_title_gen


class GraphState(TypedDict):
    url: Annotated[str, "url"]
    page: Annotated[list, "page"]
    page_meta: Annotated[str, "page_meta"]

    retriever_query: Annotated[str, "retriever_query"]
    web_search_query: Annotated[str, "web_search_query"]
    documents: Annotated[list, "docs"]
    web_search: Annotated[list, "web_search"]
    generation: Annotated[str, "summary"]


# 그래프 상태 초기화
workflow = StateGraph(GraphState)

# 노드 정의
workflow.add_node("fetch_html_tool", fetch_html_tool)  # HTML 문서 가져오기
workflow.add_node("fetch_coupang_tool", fetch_coupang_tool)
workflow.add_node("parse_image_text", parse_image_text)
workflow.add_node("web_search_tool", web_search_tool)  # 웹 서칭

workflow.add_node("page_data_gate", page_data_gate)  # 페이지 데이터 게이트
workflow.add_node("rag_retrieve", rag_retrieve)  # RAG 문서 검색

workflow.add_node("product_annc_parser", product_annc_parser)  # 상품 정보 파싱
workflow.add_node("product_desc_gen", product_desc_gen)  # 상품 설명 생성
workflow.add_node("transform_retrieve_query", transform_retrieve_query)  # 질의 재작성
workflow.add_node("transform_web_search_query", transform_web_search_query)
workflow.add_node("product_title_gen", product_title_gen)  # HTML 문서 가져오기


# 엣지 정의
workflow.add_conditional_edges(
    START,
    route_logic,
    {
        "fetch_html_tool": "fetch_html_tool",
        "fetch_coupang_tool": "fetch_coupang_tool",
    },
)
workflow.add_edge("fetch_coupang_tool", "page_data_gate")
workflow.add_edge("fetch_html_tool", "page_data_gate")

workflow.add_conditional_edges(
    "page_data_gate",
    page_data_check,
    {"parse_image_text": "parse_image_text", "next": "rag_retrieve"},
)
workflow.add_edge("parse_image_text", "page_data_gate")
workflow.add_edge("rag_retrieve", "product_annc_parser")

workflow.add_conditional_edges(
    "product_annc_parser",
    grade_generation_v_documents_and_annc_parser,
    {
        "hallucination": "transform_retrieve_query",
        "relevant": "web_search_tool",
    },
)
workflow.add_edge("transform_retrieve_query", "rag_retrieve")
workflow.add_edge("web_search_tool", "product_desc_gen")

workflow.add_edge("product_desc_gen", "product_title_gen")

workflow.add_edge("product_title_gen", END)

# 그래프 컴파일
app = workflow.compile(checkpointer=MemorySaver())
