# scsh_local.py
import sys, time, re
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import WebDriverException
from selenium_stealth import stealth

def normalize_url(url: str) -> str:
    # “/vp/”, “/pa/” 등 슬래시 사이의 p를 m으로 바꿔주는 패턴
    pattern = re.compile(r'(?<=/.)p(?=/)|(?<=/)p(?=./)')

    # www → m 서브도메인 교체
    if "://www." in url:
        url = url.replace("://www.", "://m.")

    # 슬래시 사이의 p → m
    url = pattern.sub("m", url)

    return url

def capture_mobile_screenshot(url: str):
    # 저장 경로 설정
    output = "screenshot_local.png"
    
    # 치환 로직 적용
    normalized = normalize_url(url)
    print(f">>> 시도 URL: {normalized}")

    # 크롤링 우회 설정
    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")

    # 모바일 에뮬레이션 (iPhone 12 스펙)
    opts.add_experimental_option("mobileEmulation", {
        "deviceMetrics": {"width":600, "height":1300, "pixelRatio":2.0},
        "userAgent": (
            "Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 "
            "Mobile/15E148 Safari/604.1"
        )
    })

    # undetected_chromedriver가 자동으로 driver를 관리
    service = Service()
    driver  = webdriver.Chrome(service=service, options=opts)

    # stealth fingerprint 제거
    stealth(
        driver,
        languages=["ko-KR","ko"],
        vendor="Google Inc.",
        platform="iPhone",
        webgl_vendor="Intel Inc.",
        renderer="Intel Iris OpenGL Engine",
        fix_hairline=True,
    )

    # 페이지 로드 & 예외 처리
    try:
        driver.get(normalized)
    except WebDriverException as e:
        print(f"[Error] 페이지 로드 실패: {e.msg}")
        driver.quit()
        return
    
    time.sleep(2)  # 렌더링 대기
    driver.save_screenshot(output)
    driver.quit()
    print(f"output: {output}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python scsh.py <URL>")
        sys.exit(1)
    capture_mobile_screenshot(sys.argv[1])
