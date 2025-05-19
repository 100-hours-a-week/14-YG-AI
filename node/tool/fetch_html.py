# node/tool/fetch_html.py

import re
import json
from bs4 import BeautifulSoup
from langchain_core.documents import Document
import requests, logging
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium_stealth import stealth
from webdriver_manager.chrome import ChromeDriverManager
from typing import Dict, Any
from config import node_log

logger = logging.getLogger(__name__)


def clean_html(state: Dict[str, Any]) -> Dict[str, Any]:
    # 1) 원본 HTML 가져오기
    raw_html = (
        state["page"][0].page_content
        if isinstance(state["page"], list) and hasattr(state["page"][0], "page_content")
        else state["page"]
    )

    # 2) BeautifulSoup으로 태그 제거 & 순수 텍스트 저장
    soup = BeautifulSoup(raw_html, "html.parser")
    state["page"] = soup.get_text(separator="\n", strip=True)

    pieces: list[str] = []

    # 3) <title>, meta.description, og:description, og:title
    if soup.title and soup.title.string:
        pieces.append(soup.title.string.strip())
    for sel in ("meta[name='description']", "meta[property='og:description']"):
        tag = soup.select_one(sel)
        if tag and tag.has_attr("content"):
            pieces.append(tag["content"].strip())
    tag = soup.select_one("meta[property='og:title']")
    if tag and tag.has_attr("content"):
        pieces.append(tag["content"].strip())

    # 4) script#data 내부 JSON 페이로드 (견본)
    data_tag = soup.select_one("script#data")
    if data_tag and data_tag.string:
        try:
            obj = json.loads(data_tag.string)
            for key in ("prdNo", "price", "content_category"):
                if key in obj:
                    pieces.append(f"{key}: {obj[key]}")
        except json.JSONDecodeError:
            pass

    # 5) 주요 JSON 키 패턴으로 가격 검색
    pattern_kv = r'"((?=[^"]*price)(?![^"]*last)[^"]*)"\s*:\s*([0-9]+(?:\.[0-9]+)?)'
    matches_kv = re.findall(pattern_kv, raw_html, flags=re.IGNORECASE)

    for key, val in matches_kv:
        if int(float(val)) != 0:
            pieces.append(f"{key}: {int(float(val))}")

    # 7) pieces를 state["page_meta"]에 담기
    state["page_meta"] = "\n".join(pieces)


def is_blocked(content: str) -> bool:
    if not content or len(content) < 200:
        return True
    text = BeautifulSoup(content, "html.parser").get_text().lower()
    for kw in ["captcha", "robot", "blocked", "access denied", "too many requests"]:
        if kw in text:
            return True
    return False


def fetch_with_selenium(url: str, timeout: int = 15) -> str:
    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--ignore-certificate-errors")
    opts.set_capability("acceptInsecureCerts", True)

    # 드라이버 실행
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=opts)

    stealth(
        driver,
        languages=["ko-KR", "ko"],
        vendor="Google Inc.",
        platform="iPhone",
        webgl_vendor="Intel Inc.",
        renderer="Intel Iris OpenGL Engine",
        fix_hairline=True,
    )

    driver.execute_cdp_cmd(
        "Page.addScriptToEvaluateOnNewDocument",
        {
            "source": "window.alert = ()=>{}; window.confirm = ()=>true; window.prompt = ()=>null;"
        },
    )

    driver.get(url)
    html = driver.page_source
    driver.quit()
    return html


def fetch_html_tool(state: Dict[str, Any]) -> Dict[str, Any]:
    node_log("FETCHING AND CLEANING HTML")
    url = state.get("url")
    if not url:
        raise ValueError("fetch_html_tool: state에 'url'이 없습니다.")

    html_str = ""
    try:
        # requests 타임아웃을 조금 늘릴 수도 있습니다.
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        resp.encoding = resp.apparent_encoding
        candidate = resp.text

        text_len = len(BeautifulSoup(candidate, "html.parser").get_text().strip())
        if is_blocked(candidate) or text_len < 300:
            node_log("STATIC fetch insufficient or blocked, using Selenium fallback")
            html_str = fetch_with_selenium(url)
        else:
            html_str = candidate

    except requests.exceptions.ReadTimeout as e:
        logger.info(f"requests timeout ({e}), switching to Selenium")
        html_str = fetch_with_selenium(url)
    except Exception as e:
        logger.info(f"requests fetch failed ({e}), switching to Selenium")
        html_str = fetch_with_selenium(url)

    if not html_str or is_blocked(html_str):
        # raise RuntimeError(f"fetch_html 실패 (blocked or empty): {url}")
        # html 가져오기 실패시 이미지 텍스트 파서로 넘기기
        node_log("FETCH_HTML: BLOCKED OR EMPTY")
        state["page"] = ""
        return state

    state["page"] = [Document(page_content=html_str, metadata={"source": url})]

    clean_html(state)

    return state
