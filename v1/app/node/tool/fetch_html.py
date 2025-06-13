import re, json, logging
from bs4 import BeautifulSoup
from langchain_core.documents import Document
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import WebDriverException
from typing import Dict, Any
from config import node_log
from node.tool.proxy_session import ProxySession
from node.tool.crawl_thumbnail import crawl_thumbnail

import asyncio
import aiohttp

logger = logging.getLogger(__name__)


def clean_html(state: Dict[str, Any]):
    html = (
        state["page"][0].page_content
        if isinstance(state["page"], list) and hasattr(state["page"][0], "page_content")
        else state["page"]
    )

    soup = BeautifulSoup(html, "html.parser")
    state["page"] = soup.get_text(separator="\n", strip=True)

    pieces: list[str] = []

    # filter: <title>, meta.description, og:description, og:title 
    if soup.title and soup.title.string:
        pieces.append(soup.title.string.strip())
    for sel in ("meta[name='description']", "meta[property='og:description']"):
        tag = soup.select_one(sel)
        if tag and tag.has_attr("content"):
            pieces.append(tag["content"].strip())
    tag = soup.select_one("meta[property='og:title']")
    if tag and tag.has_attr("content"):
        pieces.append(tag["content"].strip())

    # 5) 주요 JSON 키 패턴으로 가격 검색
    pattern_kv = r'"((?=[^"]*price)(?![^"]*last)[^"]*)"\s*:\s*([0-9]+(?:\.[0-9]+)?)'
    matches_kv = re.findall(pattern_kv, html, flags=re.IGNORECASE)

    for key, val in matches_kv:
        if int(float(val)) != 0:
            pieces.append(f"{key}: {int(float(val))}")

    # 7) pieces를 state["page_meta"]에 담기
    state["page_meta"] = "\n".join(pieces)

async def fetch_html_tool(state):
    node_log("FETCHING HTML")
    url = state.get("url")
    if not url:
        raise ValueError("fetch_html_tool: state에 'url'이 없습니다.")

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
                html = await resp.read()
            
        state["page"] = [Document(page_content=html, metadata={"source": url})]
        clean_html(state)
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


