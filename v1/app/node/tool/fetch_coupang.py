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


async def extract_product_data(html) -> str:
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

    try:
        connector = aiohttp.TCPConnector(ssl=False)
        async with aiohttp.ClientSession(connector=connector) as client:
            async with client.get(url, proxy=proxy2) as resp:
                resp.raise_for_status()
                html = await resp.content.read(10000)
    except Exception as e:
        node_log(f"requests failed ({e}), falling back to Selenium")
        opts = Options()
        opts.add_argument("--headless")
        opts.add_argument(f"--proxy-server={proxy2}")
        driver = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()), options=opts
        )
        driver.get(url)
        html = driver.page_source
        driver.quit()

    if not html:
        node_log("FETCH_HTML: BLOCKED OR EMPTY")
        state["page"] = []
        state["page_meta"] = []
        return state

    state["page"] = await extract_product_data(html)
    state["page_meta"] = ""

    # task(썸네일 업로드) 완수
    try:
        upload_key = await thumbnail_task
        # upload_key = "test"
    except Exception as e:
        node_log(f"crawl_thumbnail 작업 중 예외 발생: {e}")
        upload_key = None

    state["generation"]["upload_image_key"] = upload_key

    return state
