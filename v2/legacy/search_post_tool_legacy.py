import asyncio
import sys
import os
import psycopg2
import re
import json
from typing import List, Optional, Dict, Tuple
from datetime import datetime, timedelta
from langchain_core.tools import tool
from openai import AsyncOpenAI
from config.settings import settings

import logging

# 로깅 레벨 설정
logging.getLogger("langchain_google_vertexai").setLevel(logging.WARNING)
logging.getLogger("google").setLevel(logging.WARNING)
logging.getLogger("langchain_core").setLevel(logging.WARNING)


# Upstage 임베딩 클라이언트 (설정 클래스 사용)
async_openai_client = AsyncOpenAI(
    api_key=settings.upstage.api_key,
    base_url=settings.upstage.base_url,
)


async def embed_text_async(text: str) -> List[float]:
    """Upstage 임베딩 API 호출 (검증 로직 포함)"""
    try:
        response = await async_openai_client.embeddings.create(
            input=text, model=settings.upstage.embedding_model
        )
        embedding = response.data[0].embedding

        # 1. 기본 검증
        if not embedding or not isinstance(embedding, list):
            raise ValueError("임베딩 결과가 비어 있음")

        # 2. 차원 검증 (DatabaseSettings의 vector_dimension 사용)
        if len(embedding) != settings.database.vector_dimension:
            raise ValueError(
                f"임베딩 차원 불일치: 예상 {settings.database.vector_dimension}, "
                f"실제 {len(embedding)}"
            )

        # 3. 값 타입 검증
        if not all(isinstance(x, (int, float)) for x in embedding):
            raise ValueError("임베딩에 숫자가 아닌 값이 포함됨")

        # 4. 값 범위 검증 (선택적 - 일반적으로 임베딩은 정규화됨)
        import math

        magnitude = math.sqrt(sum(x * x for x in embedding))
        if magnitude == 0:
            raise ValueError("임베딩 벡터의 크기가 0입니다")

        print(f"✅ 임베딩 검증 완료: 차원={len(embedding)}, 크기={magnitude:.4f}")
        return embedding

    except Exception as e:
        raise RuntimeError(f"임베딩 실패: {e}")


def parse_user_query(query: str) -> Dict:
    """사용자 쿼리 분석하여 검색 조건 추출"""

    conditions = {
        "search_type": None,
        "product_terms": [],
        "max_price": None,
        "min_price": None,
        "post_status": "OPEN",
        "sort_by": None,
        "sort_order": "ASC",
        "top_k": 5,
        "price_type": "unit",
        "due_date_filter": None,
        "pickup_date_filter": None,
    }

    print(f"🔍 쿼리 분석: '{query}'")

    # 현재 시간
    now = datetime.now()
    today = now.date()
    tomorrow = today + timedelta(days=1)

    # 1. 개수 추출
    count_patterns = [
        (r"(\d+)\s*개", lambda x: int(x)),
        (r"(\d+)\s*건", lambda x: int(x)),
        (r"(\d+)\s*가지", lambda x: int(x)),
        (r"두\s*개|2개", lambda x: 2),
        (r"세\s*개|3개", lambda x: 3),
        (r"네\s*개|4개", lambda x: 4),
        (r"다섯\s*개|5개", lambda x: 5),
    ]

    for pattern, converter in count_patterns:
        match = re.search(pattern, query)
        if match:
            try:
                conditions["top_k"] = converter(
                    match.group(1) if match.groups() else None
                )
                print(f"   📊 개수: {conditions['top_k']}개")
                break
            except:
                pass

    # 2. 가격 조건 추출 (우선순위 순서 중요!)
    price_patterns = [
        # "보다 비싼/보다 싼" (가장 구체적)
        (r"(\d+)\s*천원?\s*보다\s*(비싼|큰)", "min_1k_exclusive"),
        (r"(\d+)\s*천원?\s*보다\s*(싼|작은)", "max_1k_exclusive"),
        (r"(\d+)\s*만원?\s*보다\s*(비싼|큰)", "min_10k_exclusive"),
        (r"(\d+)\s*만원?\s*보다\s*(싼|작은)", "max_10k_exclusive"),
        (r"(\d+)\s*원?\s*보다\s*(비싼|큰)", "min_exclusive"),
        (r"(\d+)\s*원?\s*보다\s*(싼|작은)", "max_exclusive"),
        # "이상/이하/미만"
        (r"(\d+)\s*천원?\s*이상", "min_1k"),
        (r"(\d+)\s*천원?\s*이하", "max_1k"),
        (r"(\d+)\s*천원?\s*미만", "max_1k_exclusive"),
        (r"최소\s*(\d+)\s*천원?", "min_1k"),
        (r"최대\s*(\d+)\s*천원?", "max_1k"),
        (r"(\d+)\s*만원?\s*이상", "min_10k"),
        (r"(\d+)\s*만원?\s*이하", "max_10k"),
        (r"(\d+)\s*만원?\s*미만", "max_10k_exclusive"),
        (r"최소\s*(\d+)\s*만원?", "min_10k"),
        (r"최대\s*(\d+)\s*만원?", "max_10k"),
        (r"(\d+)\s*원?\s*이상", "min"),
        (r"(\d+)\s*원?\s*이하", "max"),
        (r"(\d+)\s*원?\s*미만", "max_exclusive"),
        (r"최소\s*(\d+)\s*원?", "min"),
        (r"최대\s*(\d+)\s*원?", "max"),
        # 단독 숫자+단위 (마지막, 이하로 간주)
        (r"(\d+)\s*천원?(?=\s|$)", "max_1k"),
        (r"(\d+)\s*만원?(?=\s|$)", "max_10k"),
    ]

    for pattern, price_type in price_patterns:
        match = re.search(pattern, query)
        if match:
            price_value = int(match.group(1))

            # 가격 변환
            price_map = {
                "min_10k": lambda x: setattr(conditions, "min_price", x * 10000),
                "min_10k_exclusive": lambda x: setattr(
                    conditions, "min_price", x * 10000 + 1
                ),
                "max_10k": lambda x: setattr(conditions, "max_price", x * 10000),
                "max_10k_exclusive": lambda x: setattr(
                    conditions, "max_price", x * 10000 - 1
                ),
                "min_1k": lambda x: setattr(conditions, "min_price", x * 1000),
                "min_1k_exclusive": lambda x: setattr(
                    conditions, "min_price", x * 1000 + 1
                ),
                "max_1k": lambda x: setattr(conditions, "max_price", x * 1000),
                "max_1k_exclusive": lambda x: setattr(
                    conditions, "max_price", x * 1000 - 1
                ),
                "min": lambda x: setattr(conditions, "min_price", x),
                "min_exclusive": lambda x: setattr(conditions, "min_price", x + 1),
                "max": lambda x: setattr(conditions, "max_price", x),
                "max_exclusive": lambda x: setattr(conditions, "max_price", x - 1),
            }

            price_map[price_type](price_value)
            final_price = conditions.get("max_price") or conditions.get("min_price")
            condition_type = "max_price" if conditions.get("max_price") else "min_price"
            print(
                f"   💰 가격: {price_type} {price_value} → {condition_type}: {final_price}원"
            )
            break

    # 3. 가격 타입 (개당 vs 총액)
    if any(word in query for word in ["총", "전체", "모두", "다 합쳐서"]):
        conditions["price_type"] = "total"
        print(f"   💵 가격 타입: 총액")
    else:
        conditions["price_type"] = "unit"
        print(f"   💵 가격 타입: 개당")

    # 4. 상태 조건
    if any(word in query for word in ["마감된", "종료된", "끝난"]):
        conditions["post_status"] = "CLOSED" if "마감된" in query else "ENDED"
        print(f"   🔒 상태: {conditions['post_status']} (이미 마감/종료)")
    elif any(word in query for word in ["마감인", "마감되는", "마감 예정"]):
        conditions["post_status"] = "OPEN"
        print(f"   🔒 상태: OPEN (마감 예정)")

    # 5. 날짜 조건
    date_patterns = [
        (r"오늘\s*(마감인|마감되는|마감)", lambda: f"DATE(due_date) = '{today}'"),
        (r"내일\s*(마감인|마감되는|마감)", lambda: f"DATE(due_date) = '{tomorrow}'"),
        (
            r"이번\s*주\s*(안에|내에)?\s*(마감인|마감되는|마감)",
            lambda: f"DATE(due_date) BETWEEN '{today}' AND '{today + timedelta(days=6-today.weekday())}'",
        ),
        (
            r"(\d+)일\s*(이내|안에|내에)\s*(마감인|마감되는|마감)",
            lambda m: f"DATE(due_date) BETWEEN '{today}' AND '{today + timedelta(days=int(m.group(1)))}'",
        ),
        (r"오늘\s*(픽업|받는)", lambda: f"DATE(pickup_date) = '{today}'"),
        (r"내일\s*(픽업|받는)", lambda: f"DATE(pickup_date) = '{tomorrow}'"),
        (
            r"다음\s*주\s*(픽업|받는)",
            lambda: f"DATE(pickup_date) BETWEEN '{today + timedelta(days=7-today.weekday())}' AND '{today + timedelta(days=13-today.weekday())}'",
        ),
        (
            r"이번\s*주\s*(픽업|받는)",
            lambda: f"DATE(pickup_date) BETWEEN '{today}' AND '{today + timedelta(days=6-today.weekday())}'",
        ),
    ]

    for pattern, date_func in date_patterns:
        match = re.search(pattern, query)
        if match:
            if "마감" in pattern:
                conditions["due_date_filter"] = (
                    date_func(match) if callable(date_func) else date_func()
                )
                conditions["post_status"] = "OPEN"
                print(f"   📅 마감일 조건 설정")
            else:
                conditions["pickup_date_filter"] = (
                    date_func(match) if callable(date_func) else date_func()
                )
                print(f"   📦 픽업일 조건 설정")
            break

    # 6. 정렬 조건
    sort_keywords = {
        ("제일 싼", "가장 싼", "최저가", "저렴한"): ("price", "ASC"),
        ("제일 비싼", "가장 비싼", "최고가", "비싼"): ("price", "DESC"),
        ("인기", "많이 본", "조회수 높은"): ("view_count", "DESC"),
        ("관심 많은", "관심 높은"): ("wish_count", "DESC"),
        ("참여 많은", "참여자 많은"): ("participant_count", "DESC"),
        ("최신", "새로운", "방금 올라온"): ("created_at", "DESC"),
    }

    for keywords, (sort_col, sort_ord) in sort_keywords.items():
        if any(keyword in query for keyword in keywords):
            conditions["sort_by"] = sort_col
            conditions["sort_order"] = sort_ord
            print(f"   📈 정렬: {sort_col} {sort_ord}")
            break

    # 7. 검색 타입 결정
    specific_products = [
        "콜라",
        "펩시",
        "코카콜라",
        "사이다",
        "스프라이트",
        "환타",
        "이클립스",
        "곤약젤리",
        "초콜릿",
        "과자",
        "라면",
        "컵라면",
        "치킨",
        "피자",
        "햄버거",
        "커피",
        "아이스크림",
        "케이크",
    ]

    general_categories = [
        "간식",
        "음료",
        "먹을거",
        "음식",
        "디저트",
        "과자류",
        "생활용품",
        "전자제품",
        "책",
        "문구류",
        "의류",
        "화장품",
    ]

    found_specific = [p for p in specific_products if p in query]
    found_general = [c for c in general_categories if c in query]

    if found_specific:
        conditions["search_type"] = "keyword"
        conditions["product_terms"] = found_specific
        print(f"   🎯 검색 타입: 키워드 ({found_specific})")
    elif found_general:
        conditions["search_type"] = "vector"
        conditions["product_terms"] = found_general
        print(f"   🎯 검색 타입: 벡터 ({found_general})")
    else:
        conditions["search_type"] = "condition_only"
        print(f"   🎯 검색 타입: 조건만")

    print(f"✅ 분석 완료")
    return conditions


def build_sql_query(
    conditions: Dict, embedding: Optional[List[float]] = None
) -> Tuple[str, str]:
    """SQL 쿼리 생성"""

    # SELECT 절 - unit_amount 추가
    base_columns = "id, title, name, price, unit_price, total_amount, left_amount, unit_amount, due_date, pickup_date, post_status, view_count, wish_count, participant_count, created_at"

    if conditions["search_type"] == "vector" and embedding:
        select_clause = (
            f"embedding <-> ARRAY{embedding}::vector AS similarity, {base_columns}"
        )
    else:
        select_clause = base_columns

    # WHERE 절
    where_conditions = ["deleted_at IS NULL"]
    where_conditions.append(f"post_status = '{conditions['post_status']}'")

    # 가격 조건
    price_col = "price" if conditions["price_type"] == "total" else "unit_price"
    if conditions["max_price"] is not None:
        where_conditions.append(f"{price_col} <= {conditions['max_price']}")
    if conditions["min_price"] is not None:
        where_conditions.append(f"{price_col} >= {conditions['min_price']}")

    # 날짜 조건
    if conditions.get("due_date_filter"):
        where_conditions.append(conditions["due_date_filter"])
    if conditions.get("pickup_date_filter"):
        where_conditions.append(conditions["pickup_date_filter"])

    # 키워드 검색 조건
    if conditions["search_type"] == "keyword" and conditions["product_terms"]:
        keyword_conditions = []
        for term in conditions["product_terms"]:
            escaped_term = term.replace("'", "''")
            keyword_conditions.append(
                f"(title ILIKE '%{escaped_term}%' OR name ILIKE '%{escaped_term}%')"
            )
        if keyword_conditions:
            where_conditions.append(f"({' OR '.join(keyword_conditions)})")

    # ORDER BY 절
    if conditions["sort_by"]:
        if conditions["sort_by"] == "price":
            sort_column = (
                "price" if conditions["price_type"] == "total" else "unit_price"
            )
        else:
            sort_column = conditions["sort_by"]
        order_clause = f"ORDER BY {sort_column} {conditions['sort_order']}"
    elif conditions["search_type"] == "vector":
        order_clause = "ORDER BY similarity ASC"
    else:
        order_clause = "ORDER BY created_at DESC"

    # 최종 SQL
    sql = f"""
    SELECT {select_clause}
    FROM group_buy
    WHERE {' AND '.join(where_conditions)}
    {order_clause}
    LIMIT {conditions['top_k']}
    """

    return sql, select_clause


def format_search_results_structured(rows, cols, conditions: Dict, query: str) -> str:
    """검색 결과를 구조화된 JSON으로 포맷팅"""

    import json

    if not rows:
        # 결과가 없는 경우
        empty_result = {
            "search_type": get_search_type_display(conditions["search_type"]),
            "query": query,
            "total_count": 0,
            "results": [],
        }
        json_result = json.dumps(empty_result, ensure_ascii=False, indent=2)
        return f"STRUCTURED_RESULT_START\n{json_result}\nSTRUCTURED_RESULT_END"

    # 결과가 있는 경우
    #TODO: LLM으로 rows가 사용자의 쿼리에 알맞은 결과인지 판단한 다음 알맞은 공구만 전달하는 로직 구현
    print(f"\n🛒 구조화된 검색 결과 생성: {len(rows)}개")

    # DB 결과를 웹 UI용 형태로 변환
    results = []
    for row in rows:
        item = dict(zip(cols, row))

        # 안전한 데이터 변환
        formatted_item = {
            "id": f"GB_{item.get('id', '')}",
            "title": str(item.get("title", "제목 없음")),
            "product_name": str(item.get("name", "상품명 없음")),
            "unit_price": (
                int(item.get("unit_price", 0))
                if item.get("unit_price") is not None
                else 0
            ),
            "total_price": (
                int(item.get("price", 0)) if item.get("price") is not None else 0
            ),
            "total_amount": (
                int(item.get("total_amount", 0))
                if item.get("total_amount") is not None
                else 0
            ),
            "left_amount": (
                int(item.get("left_amount", 0))
                if item.get("left_amount") is not None
                else 0
            ),
            "unit_amount": (
                int(item.get("unit_amount", 1))
                if item.get("unit_amount") is not None
                else 1
            ),
            "due_date": str(item.get("due_date", "")) if item.get("due_date") else "",
            "pickup_date": (
                str(item.get("pickup_date", "")) if item.get("pickup_date") else ""
            ),
            "view_count": (
                int(item.get("view_count", 0))
                if item.get("view_count") is not None
                else 0
            ),
            "wish_count": (
                int(item.get("wish_count", 0))
                if item.get("wish_count") is not None
                else 0
            ),
            "participant_count": (
                int(item.get("participant_count", 0))
                if item.get("participant_count") is not None
                else 0
            ),
            "post_status": str(item.get("post_status", "OPEN")),
        }

        # 벡터 검색의 경우 유사도 추가
        if "similarity" in item and item["similarity"] is not None:
            formatted_item["similarity"] = float(item["similarity"])

        results.append(formatted_item)

    # 검색 타입에 따른 표시명
    search_type_display = get_search_type_display(conditions["search_type"])

    # 구조화된 결과 생성
    search_result = {
        "search_type": search_type_display,
        "query": query,
        "total_count": len(results),
        "results": results,
    }

    # JSON 형태로 반환
    json_result = json.dumps(search_result, ensure_ascii=False, indent=2)
    final_result = f"STRUCTURED_RESULT_START\n{json_result}\nSTRUCTURED_RESULT_END"

    print(f"📦 구조화된 결과 생성 완료")
    print(f"   📊 JSON 데이터 크기: {len(json_result)} 문자")
    print(f"   🎯 전체 결과 크기: {len(final_result)} 문자")

    return final_result


def get_search_type_display(search_type: str) -> str:
    """검색 타입에 따른 표시명 반환"""
    search_type_map = {
        "keyword": "🎯 키워드 검색",
        "vector": "🧠 의미 검색",
        "condition_only": "📋 조건 검색",
    }
    return search_type_map.get(search_type, "🔍 검색")


def format_search_results_text(rows, cols, conditions: Dict) -> str:
    """검색 결과를 기존 텍스트 형태로 포맷팅 (폴백용)"""

    if not rows:
        return "검색 조건에 맞는 공구를 찾을 수 없습니다."

    print(f"\n🛒 검색 결과: {len(rows)}개")

    results = []
    for i, row in enumerate(rows, 1):
        item = dict(zip(cols, row))

        # 가격 정보
        if conditions["price_type"] == "total":
            price_str = f"총 {item.get('price', 0):,}원"
        else:
            price_str = f"개당 {item.get('unit_price', 0):,}원"

        # 결과 라인 구성
        title = item.get("title", "제목 없음")
        result_line = f"{i}. {title} - {price_str}"

        # 잔여 수량
        left_amount = item.get("left_amount")
        total_amount = item.get("total_amount")
        if left_amount is not None and total_amount:
            result_line += f" (잔여: {left_amount}/{total_amount})"

        # 마감일
        due_date = item.get("due_date")
        if due_date:
            result_line += f" (마감: {due_date})"

        # 유사도 (벡터 검색 시)
        if "similarity" in item and item["similarity"] is not None:
            result_line += f" [유사도: {item['similarity']:.3f}]"

        results.append(result_line)

    # 헤더
    header = get_search_type_display(conditions["search_type"])
    return f"{header} 결과:\n\n" + "\n".join(results)


@tool
async def search_group_buy(query: str) -> str:
    """
    공구 게시글을 검색합니다.

    ⚠️ 중요: 사용자의 전체 쿼리를 그대로 전달하세요!

    지원하는 검색:
    1. 키워드 검색: 구체적인 상품명 (콜라, 이클립스 등)
    2. 벡터 검색: 범용 카테고리 (간식, 음료 등)
    3. 조건 검색: 가격/정렬 조건만

    지원 조건:
    - 가격: "천원 이하", "5천원보다 비싼", "1만원 이상" 등
    - 개수: "두 개", "5개" 등
    - 정렬: "제일 싼", "인기 있는", "최신" 등
    - 날짜: "오늘 마감인", "내일 픽업" 등

    반환 형식: 구조화된 JSON 데이터 (웹 UI에서 카드 형태로 표시)
    """

    print(f"\n🔧 공구 검색 시작")
    print(f"📝 쿼리: '{query}'")
    print("=" * 60)

    try:
        # 1. 쿼리 분석
        conditions = parse_user_query(query)

        # 2. DB 연결 (설정 클래스 사용)
        conn = psycopg2.connect(**settings.database.connection_params)
        cur = conn.cursor()

        embedding = None

        # 3. 벡터 검색 시 임베딩 생성
        if conditions["search_type"] == "vector":
            print(f"\n🧠 임베딩 생성 중...")
            search_text = " ".join(conditions["product_terms"])
            embedding = await embed_text_async(search_text)
            print(f"✅ 임베딩 완료 (차원: {len(embedding)})")

        # 4. SQL 생성 및 실행
        sql, select_clause = build_sql_query(conditions, embedding)

        cur.execute(sql)
        cols = [c[0] for c in cur.description]
        rows = cur.fetchall()

        print(f"\n✅ 검색 완료: {len(rows)}개")

        # 구조화된 결과 반환
        result = format_search_results_structured(rows, cols, conditions, query)

        # 디버깅 로그
        print(
            f"\n🔍 반환 결과에 STRUCTURED_RESULT_START 포함: {'STRUCTURED_RESULT_START' in result}"
        )
        print(f"📊 결과 길이: {len(result)} 문자")

        cur.close()
        conn.close()

        return result

    except Exception as e:
        print(f"\n💥 오류: {str(e)}")
        # 오류시에도 구조화된 형태로 반환
        error_result = {
            "search_type": "❌ 검색 오류",
            "query": query,
            "total_count": 0,
            "results": [],
            "error": str(e),
        }
        json_result = json.dumps(error_result, ensure_ascii=False, indent=2)
        return f"STRUCTURED_RESULT_START\n{json_result}\nSTRUCTURED_RESULT_END"


# 테스트용 메인 함수
async def main():
    """테스트용 메인 함수"""
    print("🚀 공구 검색 도구 테스트...")

    test_queries = [
        "콜라 공구 있어?",
        "천원 이하 간식 추천해줘",
        "이클립스 제일 싼 거",
        "간식 두 개만",
    ]

    for query in test_queries:
        print(f"\n🔍 테스트 쿼리: '{query}'")
        print("=" * 50)

        try:
            result = await search_group_buy(query)
            print("결과:")
            print(result)
        except Exception as e:
            print(f"오류: {e}")

        print("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())
