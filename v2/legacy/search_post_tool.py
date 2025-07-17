import asyncio
import sys
import os
import psycopg2
import re
import json
from typing import List, Optional, Dict, Tuple
from datetime import datetime, timedelta
from langchain_core.tools import tool
from langchain_google_vertexai import ChatVertexAI
from langchain_core.messages import SystemMessage, HumanMessage
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


# Google Vertex AI 클라이언트 (LLM용)
def get_vertex_ai_client(temp: float = 0.0):
    """Vertex AI 클라이언트 생성"""
    return ChatVertexAI(
        model_name=settings.google_cloud.model_name,
        temperature=temp,
        project=settings.google_cloud.project,
        location=settings.google_cloud.location,
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
        if len(embedding) != settings.postgres.vector_dimension:
            raise ValueError(
                f"임베딩 차원 불일치: 예상 {settings.postgres.vector_dimension}, "
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


async def boolean_filter_results_with_llm(
    query: str,
    rows: List[Tuple],
    cols: List[str],
    conditions: Dict,
    vertex_ai_client: ChatVertexAI,
) -> Tuple[List[Tuple], Dict]:
    """
    Boolean 방식 LLM 필터링 - 각 공구마다 True/False 판단

    Returns:
        Tuple[필터링된 결과, 분석 정보]
    """

    if not rows:
        return rows, {"filter_applied": False, "reasoning": "검색 결과 없음"}

    print(f"\n🤖 Boolean LLM 필터링 시작: {len(rows)}개 공구 평가")

    try:
        # 1. 각 공구 정보를 명확하게 정리
        items_for_evaluation = []
        for i, row in enumerate(rows):
            item = dict(zip(cols, row))

            # 평가용 공구 정보 (명확하고 간단하게)
            item_info = {
                "index": i,
                "title": str(item.get("title", "")).strip(),
                "product_name": str(item.get("name", "")).strip(),
                "unit_price": (
                    int(item.get("unit_price", 0)) if item.get("unit_price") else 0
                ),
                "left_amount": (
                    int(item.get("left_amount", 0)) if item.get("left_amount") else 0
                ),
            }
            items_for_evaluation.append(item_info)

        # 2. Boolean 평가용 프롬프트 구성
        system_prompt = """당신은 공동구매 상품 평가 전문가입니다.

사용자의 요구사항과 각 공구 상품을 비교하여, 각 상품이 사용자에게 적합한지 True/False로 판단해주세요.
여러가지 의미를 가지는 이름의 경우 모든 의미를 포함하고 있다고 판단해주세요.

평가 기준:
1. 제품명/제목이 사용자 요구와 관련이 있는가?
2. 재고가 있는가? (left_amount > 0)

중요: 각 상품마다 정확히 True 또는 False로만 답변하세요.

응답 형식 (JSON):
{
  "evaluations": [true, false, true, false, true],
  "reasoning": "간단한 평가 이유"
}

evaluations 배열의 순서는 입력된 상품 순서와 정확히 일치해야 합니다."""

        # 3. 사용자 요구사항과 상품 목록 구성
        user_prompt = f"""사용자 요구사항: "{query}"

평가할 공구 목록:
"""

        for i, item in enumerate(items_for_evaluation):
            user_prompt += f"{i}. 제목: {item['title']}\n"
            user_prompt += f"   상품명: {item['product_name']}\n"
            user_prompt += f"   가격: {item['unit_price']:,}원\n"
            user_prompt += f"   재고: {item['left_amount']}개\n\n"

        user_prompt += f"\n각 상품({len(items_for_evaluation)}개)이 사용자 요구사항 '{query}'에 적합한지 순서대로 True/False로 평가해주세요."

        # 4. LLM API 호출
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ]

        response = await vertex_ai_client.ainvoke(messages)
        response_text = response.content

        print(f"🤖 LLM 평가 응답: {response_text[:200]}...")

        # 5. Boolean 응답 파싱
        try:
            # JSON 부분 추출
            json_start = response_text.find("{")
            json_end = response_text.rfind("}") + 1
            if json_start != -1 and json_end > json_start:
                json_text = response_text[json_start:json_end]
                llm_result = json.loads(json_text)
            else:
                # JSON이 없으면 직접 파싱 시도
                raise json.JSONDecodeError("JSON 형식 아님", response_text, 0)

            evaluations = llm_result.get("evaluations", [])
            reasoning = llm_result.get("reasoning", "평가 완료")

            # 6. 평가 결과 검증
            if len(evaluations) != len(rows):
                print(f"⚠️ 평가 개수 불일치: 예상 {len(rows)}, 실제 {len(evaluations)}")
                # 길이가 맞지 않으면 원본 반환
                return rows, {"filter_applied": False, "reasoning": "평가 개수 불일치"}

            # 7. Boolean 필터링 적용
            filtered_rows = []
            true_count = 0
            false_count = 0

            for i, (row, is_suitable) in enumerate(zip(rows, evaluations)):
                if isinstance(is_suitable, bool) and is_suitable:
                    filtered_rows.append(row)
                    true_count += 1
                else:
                    false_count += 1
                    # 디버깅용 로그
                    item = dict(zip(cols, row))
                    print(f"   ❌ 제외: {item.get('title', '')[:30]}...")

            print(f"📊 Boolean 필터링 결과:")
            print(f"   ✅ 적합: {true_count}개")
            print(f"   ❌ 부적합: {false_count}개")
            print(f"   📝 이유: {reasoning}")

            # 8. 분석 정보 구성
            analysis_info = {
                "filter_applied": true_count
                < len(rows),  # 필터링이 실제로 적용되었는지
                "confidence": 0.9,  # Boolean 방식이라 높은 신뢰도
                "reasoning": reasoning,
                "user_intent": f"총 {len(rows)}개 중 {true_count}개가 요구사항에 적합",
                "suggestions": "",
                "original_count": len(rows),
                "filtered_count": len(filtered_rows),
                "evaluation_details": {
                    "suitable_count": true_count,
                    "unsuitable_count": false_count,
                    "evaluations": evaluations,  # 디버깅용
                },
            }

            # 9. 결과가 너무 적으면 경고
            if len(filtered_rows) == 0:
                print("⚠️ 모든 상품이 부적합으로 판단됨")
                # 전체 제외는 위험하므로 최소 1-2개는 반환
                # filtered_rows = rows[:2]
                analysis_info["reasoning"] += "모든 상품 부적합 판단"

            return filtered_rows, analysis_info

        except json.JSONDecodeError as e:
            print(f"⚠️ LLM 응답 파싱 실패: {e}")
            print(f"원본 응답: {response_text}")

            # 파싱 실패 시 간단한 패턴 매칭 시도
            return try_simple_boolean_parsing(response_text, rows, cols)

    except Exception as e:
        print(f"💥 Boolean LLM 필터링 중 오류: {e}")
        return rows, {"filter_applied": False, "reasoning": f"오류: {e}"}


def try_simple_boolean_parsing(
    response_text: str, rows: List[Tuple], cols: List[str]
) -> Tuple[List[Tuple], Dict]:
    """JSON 파싱 실패 시 간단한 Boolean 패턴 매칭"""

    try:
        print("🔄 간단한 Boolean 패턴 매칭 시도...")

        # true/false 패턴 찾기
        import re

        # 다양한 패턴으로 boolean 값들 찾기
        boolean_patterns = [
            r"\[(true|false)(?:,\s*(true|false))*\]",  # [true, false, true]
            r"(true|false)(?:,\s*(true|false))*",  # true, false, true
        ]

        boolean_values = []

        for pattern in boolean_patterns:
            matches = re.findall(pattern, response_text.lower())
            if matches:
                # 첫 번째 매치에서 boolean 값들 추출
                match_text = (
                    matches[0] if isinstance(matches[0], str) else str(matches[0])
                )
                boolean_strs = re.findall(r"(true|false)", match_text)
                boolean_values = [s == "true" for s in boolean_strs]
                break

        if boolean_values and len(boolean_values) == len(rows):
            print(f"✅ 패턴 매칭 성공: {len(boolean_values)}개 평가")

            filtered_rows = [
                row for row, is_suitable in zip(rows, boolean_values) if is_suitable
            ]

            return filtered_rows, {
                "filter_applied": True,
                "confidence": 0.7,  # 패턴 매칭이라 신뢰도 낮춤
                "reasoning": "패턴 매칭으로 필터링 적용",
                "original_count": len(rows),
                "filtered_count": len(filtered_rows),
            }

    except Exception as e:
        print(f"패턴 매칭도 실패: {e}")

    # 모든 방법 실패 시 원본 반환
    return rows, {"filter_applied": False, "reasoning": "Boolean 파싱 완전 실패"}


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
        (r"한\s*개|하나|1개", lambda x: 1),
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

    # 2. 가격 조건 추출
    price_patterns = [
        (r"(\d+)\s*천원?\s*보다\s*(비싼|큰)", "min_1k_exclusive"),
        (r"(\d+)\s*천원?\s*보다\s*(싼|작은)", "max_1k_exclusive"),
        (r"(\d+)\s*만원?\s*보다\s*(비싼|큰)", "min_10k_exclusive"),
        (r"(\d+)\s*만원?\s*보다\s*(싼|작은)", "max_10k_exclusive"),
        (r"(\d+)\s*원?\s*보다\s*(비싼|큰)", "min_exclusive"),
        (r"(\d+)\s*원?\s*보다\s*(싼|작은)", "max_exclusive"),
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
        (r"(\d+)\s*천원?(?=\s|$)", "max_1k"),
        (r"(\d+)\s*만원?(?=\s|$)", "max_10k"),
    ]

    for pattern, price_type in price_patterns:
        match = re.search(pattern, query)
        if match:
            price_value = int(match.group(1))

            # 가격 변환 매핑
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

    # 4. 검색 타입 결정
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


# 기존 함수를 Boolean 방식으로 교체
async def format_search_results_structured(
    rows, cols, conditions: Dict, query: str
) -> str:
    """Boolean LLM 필터링이 적용된 결과 포맷팅"""

    import json

    if not rows:
        empty_result = {
            "search_type": get_search_type_display(conditions["search_type"]),
            "query": query,
            "total_count": 0,
            "results": [],
        }
        json_result = json.dumps(empty_result, ensure_ascii=False, indent=2)
        return f"STRUCTURED_RESULT_START\n{json_result}\nSTRUCTURED_RESULT_END"

    # LLM으로 결과 필터링 - Boolean 방식으로 변경!
    print(f"\n🛒 검색 결과 전처리: {len(rows)}개")

    try:
        # Vertex AI 클라이언트 생성
        vertex_ai_client = get_vertex_ai_client(temp=0.1)

        # Boolean 방식 LLM 필터링 적용
        filtered_rows, analysis_info = await boolean_filter_results_with_llm(
            query, rows, cols, conditions, vertex_ai_client
        )

        print(f"🧠 Boolean LLM 필터링 완료:")
        print(f"   원본: {analysis_info.get('original_count', len(rows))}개")
        print(
            f"   필터링 후: {analysis_info.get('filtered_count', len(filtered_rows))}개"
        )
        print(f"   신뢰도: {analysis_info.get('confidence', 0):.2f}")
        print(f"   사용자 의도: {analysis_info.get('user_intent', '파악 안됨')}")

        # 필터링된 결과 사용
        final_rows = filtered_rows

    except Exception as e:
        print(f"⚠️ LLM 필터링 실패, 원본 결과 사용: {e}")
        final_rows = rows
        analysis_info = {"filter_applied": False, "reasoning": f"오류: {e}"}

    print(f"\n🛒 구조화된 검색 결과 생성: {len(final_rows)}개")

    # DB 결과를 웹 UI용 형태로 변환
    results = []
    for row in final_rows:
        item = dict(zip(cols, row))

        # 안전한 데이터 변환
        formatted_item = {
            "id": f"{item.get('id', '')}",
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

    # 구조화된 결과 생성 (LLM 분석 정보 포함)
    search_result = {
        "search_type": search_type_display,
        "query": query,
        "total_count": len(results),
        "results": results,
        # LLM 분석 정보 추가
        "analysis": {
            "filter_applied": analysis_info.get("filter_applied", False),
            "confidence": analysis_info.get("confidence", 0),
            "user_intent": analysis_info.get("user_intent", ""),
            "reasoning": analysis_info.get("reasoning", ""),
            "suggestions": analysis_info.get("suggestions", ""),
            "original_count": analysis_info.get("original_count", len(results)),
        },
    }

    # JSON 형태로 반환
    json_result = json.dumps(search_result, ensure_ascii=False, indent=2)
    final_result = f"STRUCTURED_RESULT_START\n{json_result}\nSTRUCTURED_RESULT_END"

    print(f"📦 구조화된 결과 생성 완료")
    print(f"   📊 JSON 데이터 크기: {len(json_result)} 문자")
    print(f"   🎯 전체 결과 크기: {len(final_result)} 문자")

    # LLM 분석 결과 로깅
    if analysis_info.get("filter_applied"):
        print(f"   🧠 LLM 필터링: {analysis_info.get('confidence', 0):.2f} 신뢰도")
        print(
            f"   💡 사용자 의도: {analysis_info.get('user_intent', '파악 안됨')[:50]}..."
        )

    return final_result


def get_search_type_display(search_type: str) -> str:
    """검색 타입에 따른 표시명 반환"""
    search_type_map = {
        "keyword": "🎯 키워드 검색",
        "vector": "🧠 의미 검색",
        "condition_only": "📋 조건 검색",
    }
    return search_type_map.get(search_type, "🔍 검색")


@tool
async def search_group_buy(query: str) -> str:
    """
    공구 게시글을 검색합니다.

    ⚠️ 중요:  사용자의 요구사항을 그대로 전달하세요! 필요하면 맥락을 파악해서 요구사항을 판단하고 진행하세요.

    지원하는 검색:
    1. 키워드 검색: 매우 구체적인 상품명 (코카콜라, 이클립스 피치맛등)
    2. 벡터 검색: 대부분의 범용적 카테고리 (간식, 음료, 과자, 간편식, 콜라, 이클립스 등)
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
        conn = psycopg2.connect(**settings.postgres.connection_params)
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

        print(f"\n✅ DB 검색 완료: {len(rows)}개")

        # 5. LLM 필터링이 포함된 구조화된 결과 반환
        result = await format_search_results_structured(rows, cols, conditions, query)

        cur.close()
        conn.close()
        print(result)
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
