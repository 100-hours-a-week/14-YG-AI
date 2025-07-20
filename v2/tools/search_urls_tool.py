import os
import asyncio
import json
import re
from typing import List, Optional, Dict

# --- 라이브러리 Import ---
from langchain_core.tools import tool
from langchain_google_community import GoogleSearchAPIWrapper
from dotenv import load_dotenv

# --- 환경 변수 로드 ---
load_dotenv()

# --- 도구 구현 ---

SITE_MAP = {
    "coupang": "www.coupang.com",
}

try:
    search_wrapper = GoogleSearchAPIWrapper()
except Exception as e:
    search_wrapper = None
    print(f"GoogleSearchAPIWrapper 초기화 실패: {e}")


def _build_search_query(query: str, site_domain: str) -> str:
    """검색어에 "가격"을 추가하여 상품 상세 페이지 검색 확률을 높입니다."""
    return f'"{query}" site:{site_domain}'


# ❗️❗️❗️ 핵심 수정 함수 ❗️❗️❗️
def _extract_and_validate_urls(results: List[dict], max_urls: int = 3) -> List[str]:
    """
    검색 결과에서 '상품 상세 페이지' URL만 최대 max_urls개 추출합니다.
    '검색 결과', '브랜드', '카테고리' 페이지는 명시적으로 제외합니다.
    """
    if not results:
        return []

    valid_urls = []
    # 상품 상세 페이지에 포함될 확률이 높은 경로
    PRODUCT_PATH_KEYWORDS = ["/vp/products/"]

    # ❗️ 제외할 페이지 패턴 추가
    EXCLUDE_PATH_KEYWORDS = [
        "/np/search",  # 쿠팡 검색 결과 페이지
        "/brand-shop",  # 쿠팡 브랜드 페이지
        "/np/categories",  # 쿠팡 카테고리 페이지
        "search?",  # 일반적인 검색 쿼리
        "/login",
        "/cart",
        "/reviews",
        "best",
        "/event",
    ]

    for result in results:
        if len(valid_urls) >= max_urls:
            break

        url = result.get("link", "")
        if not url:
            continue

        # 1단계: 제외 키워드가 포함된 URL은 무조건 건너뛰기
        if any(exclude_kw in url for exclude_kw in EXCLUDE_PATH_KEYWORDS):
            print(f"   - ⚠️  부적합 URL 필터링됨 (브랜드/검색 페이지): {url[:70]}...")
            continue

        # 2단계: 상품 상세 페이지 키워드가 포함된 URL만 최종 후보로 선택
        if any(include_kw in url for include_kw in PRODUCT_PATH_KEYWORDS):
            if url not in valid_urls:
                valid_urls.append(url)

    return valid_urls


def _parse_metadata_from_google_result(result: Dict) -> Optional[Dict]:
    """Google 검색 결과에서 메타데이터를 파싱합니다."""
    title = result.get("title", "")
    snippet = result.get("snippet", "")
    url = result.get("link", "")
    if not all([title, url]):
        return None
    price = 0
    price_pattern = r"(?:가격|₩)?\s*([\d,]+)원?"
    price_match = re.search(price_pattern, snippet + title)
    if price_match:
        try:
            price = int(price_match.group(1).replace(",", ""))
        except:
            price = 0
    product_name = re.sub(r"\s*-\s*(쿠팡|Coupang)", "", title).strip()
    if product_name and len(product_name) > 2:
        return {
            "url": url,
            "product_name": product_name,
            "price": price,
            "source": "google_snippet_parsing",
        }
    return None


@tool
async def search_urls(query: str) -> str:
    """
    사용자가 상품명을 입력하면 '쿠팡(Coupang)'에서 해당 상품을 검색하여, 관련성 높은 '상품 상세 페이지'의 정보(URL, 상품명, 가격)를 최대 3개 찾아 JSON 리스트로 반환합니다.
    """
    if search_wrapper is None:
        return json.dumps({"error": "Google Search API가 제대로 설정되지 않았습니다."})

    print(f"🤖 '{query}' 상품을 쿠팡에서 검색하여 메타데이터를 파싱합니다...")

    site_name, site_domain = "coupang", SITE_MAP["coupang"]
    try:
        search_query = _build_search_query(query, site_domain)
        print(f"   - Google 검색어: {search_query}")

        search_results = await asyncio.to_thread(
            search_wrapper.results, search_query, 10
        )

        product_urls = _extract_and_validate_urls(search_results, max_urls=3)

        if not product_urls:
            print("❌ 유효한 '상품 상세 페이지' URL을 찾지 못했습니다.")
            return json.dumps({"error": "관련 상품 상세 페이지를 찾을 수 없습니다."})

        final_items = []
        for url in product_urls:
            matching_result = next(
                (res for res in search_results if res.get("link") == url), None
            )
            if matching_result:
                item = _parse_metadata_from_google_result(matching_result)
                if item:
                    final_items.append(item)

        if final_items:
            print(f"✅ 총 {len(final_items)}개의 상품 정보를 찾았습니다.")
            return json.dumps(final_items, ensure_ascii=False, indent=2)
        else:
            print("❌ 유효 URL은 찾았으나, 메타데이터 파싱에 실패했습니다.")
            return json.dumps(
                {"error": "상품 정보 파싱에 실패했습니다.", "found_urls": product_urls}
            )

    except Exception as e:
        print(f"   - 💥 검색 중 오류 발생: {e}")
        return json.dumps({"error": f"전체 검색 과정에서 오류가 발생했습니다: {e}"})


# --- 테스트 실행 코드 ---
if __name__ == "__main__":

    async def run_test(query: str):
        print("-" * 60)
        result_json_str = await search_product_urls.ainvoke({"query": query})
        print(f"\n[최종 결과]:")
        try:
            parsed_data = json.loads(result_json_str)
            print(json.dumps(parsed_data, ensure_ascii=False, indent=4))
        except json.JSONDecodeError:
            print(result_json_str)
        print("-" * 60 + "\n")

    async def main():
        # 이제 '햇반' 같은 브랜드를 포함하는 쿼리로 테스트해도 상세 페이지만 나와야 합니다.
        test_cases = ["햇반", "농심 신라면", "코카콜라"]
        print("=" * 60)
        print("🚀 쿠팡 상품 정보 파싱 도구 테스트 (필터링 강화) 🚀")
        print("=" * 60 + "\n")

        if not all([os.getenv("GOOGLE_API_KEY"), os.getenv("GOOGLE_CSE_ID")]):
            print("🛑 중요: GOOGLE_API_KEY와 GOOGLE_CSE_ID를 설정해야 합니다.")
            return

        for query in test_cases:
            await run_test(query)
            await asyncio.sleep(1)

    asyncio.run(main())
