import time
import warnings
from bs4 import BeautifulSoup
from config import node_log
from requests.packages.urllib3.exceptions import InsecureRequestWarning
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from node.tool.proxy_session import ProxySession
from node.tool.crawl_thumbnail import crawl_thumbnail

import asyncio
import aiohttp
import json

# SSL 인증서 경고 무시
warnings.filterwarnings("ignore", category=InsecureRequestWarning)


def extract_product_data(html) -> str:
    soup = BeautifulSoup(html, 'html.parser')

    script = soup.find('script', {'src': 'product', 'type': 'application/ld+json'})

    data = json.loads(script.string)
    name = data.get('name')
    description = data.get('description')
    price = data.get('offers', {}).get('price')

    return f'{name}\n{description}\n{price}'


async def fetch_coupang_tool(state):
    node_log("FETCHING COUPANG HTML")
    url = state.get("url")
    if not url:
        raise ValueError("fetch_coupang_tool: state에 'url'이 없습니다.")

    proxy_session = ProxySession()
    session = proxy_session.session
    proxy1 = proxy_session.proxy1
    proxy2 = proxy_session.proxy2

    if "generation" not in state or not isinstance(state["generation"], dict):
        state["generation"] = {}

    thumbnail_task = asyncio.create_task(crawl_thumbnail(url, session, proxy1))
    
    html = None
    try:
        connector = aiohttp.TCPConnector(ssl=False)
        async with aiohttp.ClientSession(connector=connector) as client:
            async with client.get(url, proxy=proxy2) as resp:
                resp.raise_for_status()
                html = await resp.read()

        state["page"] = extract_product_data(html)
        state["page_meta"] = ""
    except Exception as e:
        node_log(f"HTML 요청 실패 ({e})")

    # 썸네일 업로드 명시적 완료
    try:
        upload_key = await thumbnail_task
    except Exception as e:
        node_log(f"crawl_thumbnail 작업 중 예외 발생: {e}")
        upload_key = None

    state["generation"]["upload_image_key"] = upload_key

    if not html:
        node_log("FETCH_HTML: BLOCKED OR EMPTY")
        state["page"] = None
        state["page_meta"] = None
        return state
    return state
