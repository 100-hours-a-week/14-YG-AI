import asyncio
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from asgi_lifespan import LifespanManager
from main import app

@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop()
    yield loop
    loop.close()

@pytest_asyncio.fixture
async def client():
    async with LifespanManager(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport,
            base_url="http://localhost:8100",
            timeout=120
        ) as ac:
            yield ac

@pytest.mark.parametrize("url, exp_keyword, exp_price, exp_count", [
    (
        "https://www.11st.co.kr/products/5767448628",
        "옥동자", 23900, 40
    ),
    (
        "https://www.11st.co.kr/products/5233499372",
        "키위", 23160, 1
    ), 
    # 쿠팡
    (
        "https://www.coupang.com/vp/products/8107798642?itemId=23374319052&vendorItemId=90882133321",
        "햇반", 30360, 36
    ),
    (
        "https://www.coupang.com/vp/products/29876?vendorItemId=85104068312",
        "올리브유", 199000, 12
    ),
    (
        "https://www.coupang.com/vp/products/6978887378?vendorItemId=85194178297",
        "롯데샌드", 43420, 16
    ),
    # 마이프로틴
        (
        "https://www.myprotein.co.kr/p/sports-nutrition/essential-omega-3/10529329/",
        "오메가", 12600, 1
    ),
    (
        "https://www.myprotein.co.kr/p/sports-nutrition/flavour-drops/10530471/",
        "플레이브 드롭스", 22900, 1
    ),
    # 네이버
        (
        "https://brand.naver.com/monsterenergy/products/6697660209",
        "몬스터", 37170, 24
    ),
    (
        "https://brand.naver.com/nongshim/products/9744402416",
        "김치사발면", 20680, 24
    ),
    # (
    #     "https://smartstore.naver.com/twostarmall/products/10002872902",
    #     "핫식스", 16700, 12
    # )
])

@pytest.mark.asyncio
async def test_generation_success(client, url, exp_keyword, exp_price, exp_count):
    resp = await client.post(
        "/generation/description",
        json={"url": url},
        headers={"Cookie": "AccessToken=your_access_token"},
    )
    assert resp.status_code == 200

    body = resp.json()
    assert body["message"] == "상품 상세 설명이 생성되었습니다."

    data = body["data"]
    assert exp_keyword in data["title"], f"'{exp_keyword}' not in '{data['title']}'"
    assert data["count"] == exp_count
    assert isinstance(data["summary"], str) and len(data["summary"]) > 0
