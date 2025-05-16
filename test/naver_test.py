# tests/test_app.py
import pytest
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app import app
from fastapi.testclient import TestClient

client = TestClient(app)

# 1) 정상 동작 케이스: (URL, 예상 lower_name의 키워드, 예상 total_price, 예상 count)
@pytest.mark.parametrize("url, exp_keyword, exp_price, exp_count", [
    (
        "https://brand.naver.com/monsterenergy/products/6697660209",
        "몬스터", 37170, 24
    ),
    (
        "https://brand.naver.com/nongshim/products/9744402416",
        "김치사발면", 22330, 24
    )
])

def test_generation_success(url, exp_keyword, exp_price, exp_count):
    # API 호출
    resp = client.post(
        "/generation/description",
        json={"url": url},
        headers={"Cookie": "AccessToken=your_access_token"},
        timeout=120
    )
    assert resp.status_code == 200

    body = resp.json()
    # 메시지 확인
    assert body["message"] == "상품 상세 설명이 생성되었습니다."
    # 데이터 필드 확인
    data = body["data"]
    assert exp_keyword in data["title"], (
        f"'{exp_keyword}' not in '{data['title']}'"
    )
    assert data["total_price"] == exp_price
    assert data["count"] == exp_count

    assert isinstance(data["summary"], str) and len(data["summary"]) > 0

    # 루트에 screenshot.png 가 생성되었는지 확인
    assert os.path.exists("./img/screenshot.png"), "스크린샷 파일이 없습니다"
    assert os.path.getsize("./img/screenshot.png") > 0, "스크린샷 파일이 비어 있습니다"

    time.sleep(30)


# def test_generation_failure(monkeypatch):
#     import generate_product_announcement as gpa_module

#     def fake_raise(arg):
#         raise RuntimeError("forced error")
#     monkeypatch.setattr(gpa_module, "generate_product_announcement", fake_raise)

#     resp = client.post("/generation/description", json={"url": "https://example.com"})
#     assert resp.status_code == 200

#     body = resp.json()
#     # 오류 메시지 및 data=null 확인
#     assert body["message"] == "서버에서 오류가 발생했습니다. 잠시 후 다시 시도해주세요."
#     assert body["data"] is None
