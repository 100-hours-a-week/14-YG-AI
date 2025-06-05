# import pytest
# from main import app
# from fastapi.testclient import TestClient

# client = TestClient(app)

# @pytest.mark.parametrize("url, exp_keyword, exp_price, exp_count", [
#     (
#         "https://www.myprotein.co.kr/p/sports-nutrition/essential-omega-3/10529329/",
#         "오메가", 12600, 1
#     ),
#     (
#         "https://www.myprotein.co.kr/p/sports-nutrition/flavour-drops/10530471/",
#         "플레이브 드롭스", 22900, 1
#     )
# ])

# @pytest.mark.asyncio
# async def test_generation_success(url, exp_keyword, exp_price, exp_count):
#     resp = client.post(
#         "/generation/description",
#         json={"url": url},
#         headers={"Cookie": "AccessToken=your_access_token"},
#         timeout=120
#     )
#     assert resp.status_code == 200

#     body = resp.json()
#     # 메시지 확인
#     assert body["message"] == "상품 상세 설명이 생성되었습니다."
#     # 데이터 필드 확인
#     data = body["data"]
#     assert exp_keyword in data["title"], (
#         f"'{exp_keyword}' not in '{data['title']}'"
#     )
#     # assert data["total_price"] == exp_price
#     assert data["count"] == exp_count

#     assert isinstance(data["summary"], str) and len(data["summary"]) > 0
