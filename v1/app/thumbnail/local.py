import os
import requests
from bs4 import BeautifulSoup
import urllib3
from urllib.parse import urljoin, urlparse
from proxy_factory import ProxySession
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
    
urllib3.disable_warnings()

def capture_full_page_thumbnail(url, dest_dir='img'):
    os.makedirs(dest_dir, exist_ok=True)

    savefilename = 'thumbnail.png'
    output_path = 'img/' + savefilename

    options = Options()
    options.add_argument('--headless=new')
    options.add_experimental_option(
        "mobileEmulation",
        {
            "deviceMetrics": {"width": 1100, "height": 1100, "pixelRatio": 2.0},
            "userAgent": (
                "Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) "
                "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 "
                "Mobile/15E148 Safari/604.1"
            ),
        },
    )

    driver = webdriver.Chrome(options=options)
    try:
        driver.get(url)
        # 1) 웹폰트 주입
        inject_js = r"""
            var link = document.createElement('link');
            link.href = 'https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;700&display=swap';
            link.rel = 'stylesheet';
            document.head.appendChild(link);
            var style = document.createElement('style');
            style.innerHTML = "body, * { font-family: 'Noto Sans KR', sans-serif !important; }";
            document.head.appendChild(style);
        """
        driver.execute_script(inject_js)
        driver.execute_async_script("""
            const callback = arguments[arguments.length - 1];
            document.fonts.ready.then(() => callback());
        """)

        # 2) 스크린샷 캡처
        driver.save_screenshot(output_path)
    finally:
        driver.quit()


if __name__ == '__main__':
    page = "http://www.tcgshop.co.kr/goods_detail.php?goodsIdx=117733"
    
    capture_full_page_thumbnail(page)
