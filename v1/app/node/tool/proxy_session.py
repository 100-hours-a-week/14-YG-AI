import os
import random
import requests
from dotenv import load_dotenv
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from urllib.parse import urlparse
from config import node_log

load_dotenv()

proxy_list = list(
    filter(None, [os.getenv("PROXY1"), os.getenv("PROXY2")])
)

class ProxySession:
    def __init__(self):
        if not proxy_list:
            raise RuntimeError("PROXY 환경변수 설정 필요")

        self._proxy = random.choice(proxy_list)
        node_log(f"SET PROXY: {self.getProxyName()}")

        user_agent = (
            "Mozilla/5.0 (X11; Linux x86_64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/91.0.4472.114 Safari/537.36"
        )
        default_headers = {
            "User-Agent": user_agent,
            "Accept-Encoding": "gzip, deflate",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "ko-KR,ko;q=0.9",
            "Connection": "keep-alive",
        } 

        self._session = requests.Session()
        self._session.proxies.update({"http": self._proxy, "https": self._proxy})
        self._session.verify = False
        self._session.headers.update(default_headers)

        retry_strategy = Retry(
            total=1,
            backoff_factor=0.3,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "HEAD"],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self._session.mount("https://", adapter)
        self._session.mount("http://", adapter)

    def getProxyName(self):
        parsed = urlparse(self._proxy)
        user_info = parsed.username or ""

        try:
            return user_info.split('zone-')[1].split('-country')[0]
        except (IndexError, AttributeError):
            return "CANNOT PARSE PROXY NAME"

    @property
    def session(self) -> requests.Session:
        """requests.Session 객체 반환"""
        return self._session

    @property
    def proxy(self) -> str:
        """현재 세션에서 사용된 프록시 반환"""
        return self._proxy
