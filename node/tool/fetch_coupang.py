import os
import time
from dotenv import load_dotenv
import warnings
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup
from config import node_log
from requests.packages.urllib3.exceptions import InsecureRequestWarning
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import random

# SSL 인증서 경고 무시
warnings.filterwarnings("ignore", category=InsecureRequestWarning)

# ─── .env 로드 및 proxy 설정 ─────────────────────────
load_dotenv()
proxy_list = [
    os.getenv("PROXY1"),
    os.getenv("PROXY2")
]
proxy = random.choice(proxy_list)
user_agent = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 " \
    "(KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36"

if not proxy:
    raise RuntimeError("PROXY 환경변수 설정 필요")

# ─── 세션 생성: proxy, headers, retry/backoff ─────────
session = requests.Session()
session.proxies.update({"http": proxy, "https": proxy})
session.verify = False
session.headers.update(
    {
        "User-Agent": user_agent,
        "Accept-Encoding": "gzip, deflate, br",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ko-KR,ko;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Referer": "https://www.coupang.com/",
    }
)
retry = Retry(
    total=1,
    backoff_factor=0.3,
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["GET", "HEAD"],
)
adapter = HTTPAdapter(max_retries=retry)
session.mount("https://", adapter)
session.mount("http://", adapter)


def fetch_coupang_tool(state):
    node_log("FETCHING COUPANG HTML")
    url = state.get("url")
    if not url:
        raise ValueError("fetch_coupang_tool: state에 'url'이 없습니다.")

    # 전체 HTML 가져오기
    try:
        time.sleep(random.uniform(0.5, 0.8))
        resp = session.get(url, timeout=(10, 120))  # connect 10s, read 60s
        resp.raise_for_status()
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

    # 3) BeautifulSoup으로 전체 HTML 파싱
    soup = BeautifulSoup(html, "html.parser")

    # 4) 필요한 메타·가격 정보 추출, 필요한 정보 추가 가능
    pieces = []
    # 메타 제목
    if tag := soup.select_one('meta[property="og:title"]'):
        pieces.append(tag.get("content", "").strip())
    # 메타 설명
    if tag := soup.select_one('meta[property="og:description"]'):
        pieces.append(tag.get("content", "").strip())
    # 본문 가격
    if price_tag := soup.select_one("span.total-price strong"):
        pieces.append(price_tag.get_text(strip=True))

    result = "\n".join(pieces)
    # print(result)
    state["page"] = result
    state["page_meta"] = ""
    return state
