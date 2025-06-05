# import pytest
# from main import app
# from fastapi.testclient import TestClient

# client = TestClient(app)

# @pytest.mark.parametrize("url, exp_keyword, exp_price, exp_count", [
#     (
#         "https://brand.naver.com/monsterenergy/products/6697660209",
#         "몬스터", 37170, 24
#     ),
#     (
#         "https://brand.naver.com/nongshim/products/9744402416",
#         "김치사발면", 20680, 24
#     ),
#     (
#         "https://smartstore.naver.com/twostarmall/products/10002872902",
#         "핫식스", 16700, 12
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
