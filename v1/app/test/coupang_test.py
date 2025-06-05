# import pytest
# from main import app
# from fastapi.testclient import TestClient

# client = TestClient(app)

# @pytest.mark.parametrize("url, exp_keyword, exp_price, exp_count", [
#     (
#         "https://www.coupang.com/vp/products/8107798642?itemId=23374319052&vendorItemId=90882133321",
#         "햇반", 30360, 36
#     ),
#     (
#         "https://www.coupang.com/vp/products/29876?vendorItemId=85104068312",
#         "올리브유", 199000, 12
#     ),
#     (
#         "https://www.coupang.com/vp/products/6978887378?vendorItemId=85194178297",
#         "롯데샌드", 43420, 16
#     )
# ])

# def test_generation_success(url, exp_keyword, exp_price, exp_count):
#     resp = client.post(
#         "/generation/description",
#         json={"url": url},
#         headers={"Cookie": "AccessToken=your_access_token"},
#         timeout=120
#     )
#     assert resp.status_code == 200

#     body = resp.json()

#     assert body["message"] == "상품 상세 설명이 생성되었습니다."

#     data = body["data"]
#     assert exp_keyword in data["title"], (
#         f"'{exp_keyword}' not in '{data['title']}'"
#     )
#     # assert data["total_price"] == exp_price
#     assert data["count"] == exp_count

#     assert isinstance(data["summary"], str) and len(data["summary"]) > 0
