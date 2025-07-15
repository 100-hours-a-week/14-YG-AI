from langchain_core.tools import tool


@tool
async def search_product_urls(query: str, site: str = "coupang") -> str:
    """웹에서 상품 URL 검색 도구"""

    # SerpApi 또는 Google Custom Search 사용
    search_query = f"site:{site}.com {query}"

    results = await call_search_api(search_query)

    # URL 목록 반환
    product_urls = [
        {
            "title": result["title"],
            "url": result["link"],
            "price": extract_price(result["snippet"]),
            "description": result["snippet"],
        }
        for result in results["organic_results"][:5]
    ]

    return format_url_selection(product_urls)
