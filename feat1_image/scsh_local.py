# scsh_local.py
import sys, time, re
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import WebDriverException
from selenium_stealth import stealth
from urllib.parse import urlparse, urlunparse

def normalize_url(url: str) -> str:
    pattern = re.compile(r'(?<=/.)p(?=/)|(?<=/)p(?=./)')
    if "://www." in url:
        url = url.replace("://www.", "://m.")
    return pattern.sub("m", url)

def capture_mobile_screenshot(url: str):
    output = "screenshot.png"
    normalized = normalize_url(url)
    print(f">>> 시도 URL: {normalized}")

    # ─── 도메인별 뷰포트 너비 맵 ───────────────────────────
    # 원하는 도메인을 키로, 너비(px)를 값으로 추가하세요.
    domain_widths = {
        "naver": 1300,
        "example": 800
    }
    # 기본 모바일 뷰포트
    width, height = 600, 1300

    host = urlparse(normalized).netloc.lower()

    for domain, w in domain_widths.items():
        if domain in host:
            width = w
            break
    # ───────────────────────────────────────────────────────

    # 크롤링 우회 설정
    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")

    # 모바일 에뮬레이션
    opts.add_experimental_option("mobileEmulation", {
        "deviceMetrics": {"width": width, "height": height, "pixelRatio":2.0},
        "userAgent": (
            "Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 "
            "Mobile/15E148 Safari/604.1"
        )
    })

    service = Service()
    driver = webdriver.Chrome(service=service, options=opts)
    stealth(
        driver,
        languages=["ko-KR","ko"],
        vendor="Google Inc.",
        platform="iPhone",
        webgl_vendor="Intel Inc.",
        renderer="Intel Iris OpenGL Engine",
        fix_hairline=True,
    )

    try:
        driver.get(normalized)
    except WebDriverException as e:
        print(f"[Error] 페이지 로드 실패: {e.msg}")
        driver.quit()
        return

    time.sleep(2)
    driver.save_screenshot(output)
    driver.quit()
    print(f"output: {output}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python scsh_local.py <URL>")
        sys.exit(1)
    capture_mobile_screenshot(sys.argv[1])
