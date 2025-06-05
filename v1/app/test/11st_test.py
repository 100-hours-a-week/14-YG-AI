import pytest
import asyncio
from main import app
from fastapi.testclient import TestClient

client = TestClient(app)

@pytest.mark.parametrize("url, exp_keyword, exp_price, exp_count", [
    (
        "https://www.11st.co.kr/products/5767448628",
        "옥동자", 23900, 40
    ),
    (
        "https://www.11st.co.kr/products/5233499372",
        "키위", 23160, 1
    )
])

def test_generation_success(url, exp_keyword, exp_price, exp_count):
    resp = client.post(
        "/generation/description",
        json={"url": url},
        headers={"Cookie": "AccessToken=your_access_token"},
        timeout=120
    )
    assert resp.status_code == 200

    body = resp.json()

    assert body["message"] == "상품 상세 설명이 생성되었습니다."

    data = body["data"]
    assert exp_keyword in data["title"], (
        f"'{exp_keyword}' not in '{data['title']}'"
    )

    assert data["count"] == exp_count

    assert isinstance(data["summary"], str) and len(data["summary"]) > 0
