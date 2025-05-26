import re, json, logging
from bs4 import BeautifulSoup
from langchain_core.documents import Document
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium_stealth import stealth
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import WebDriverException
from typing import Dict, Any
from config import node_log
from node.tool.proxy_session import ProxySession

logger = logging.getLogger(__name__)


def clean_html(state: Dict[str, Any]) -> Dict[str, Any]:
    # 1) 원본 HTML 가져오기
    html = (
        state["page"][0].page_content
        if isinstance(state["page"], list) and hasattr(state["page"][0], "page_content")
        else state["page"]
    )

    # 2) BeautifulSoup으로 태그 제거 & 순수 텍스트 저장
    soup = BeautifulSoup(html, "html.parser")
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
    matches_kv = re.findall(pattern_kv, html, flags=re.IGNORECASE)

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


def fetch_with_selenium(url: str, timeout: int = 15, proxy: str = "") -> str:
    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--ignore-certificate-errors")
    opts.set_capability("acceptInsecureCerts", True)

    if proxy:
        opts.add_argument(f"--proxy-server={proxy}")

    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=opts)
    except WebDriverException as e:
        raise RuntimeError(f"Chrome 드라이버 실행 실패: {e}")

    try:
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
        return html

    finally:
        driver.quit()


def fetch_html_tool(state: Dict[str, Any]) -> Dict[str, Any]:
    node_log("FETCHING HTML")
    url = state.get("url")
    if not url:
        raise ValueError("fetch_html_tool: state에 'url'이 없습니다.")

    proxy_session = ProxySession()
    session = proxy_session.session
    proxy = proxy_session.proxy

    # 전체 HTML 가져오기
    try:
        resp = session.get(url, timeout=(10, 120))  # connect 10s, read 60s
        resp.raise_for_status()
        resp.encoding = resp.apparent_encoding     
        html = resp.text
    except Exception as e:
        node_log(f"requests failed ({e}), falling back to Selenium")
        opts = Options()
        opts.add_argument("--headless")
        opts.add_argument(f"--proxy-server={proxy}")
        driver = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()), options=opts
        )
        driver.get(url)
        html = driver.page_source
        driver.quit()

    if not html or is_blocked(html):
        node_log("FETCH_HTML: BLOCKED OR EMPTY")
        state["page"] = []
        state["page_meta"] = []  
        return state

    state["page"] = [Document(page_content=html, metadata={"source": url})]

    clean_html(state)

    return state

