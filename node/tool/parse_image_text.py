import os
import sys
import time
import re
import warnings
from typing import Dict
import easyocr
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import UnexpectedAlertPresentException
from webdriver_manager.chrome import ChromeDriverManager
from selenium_stealth import stealth
from urllib.parse import urlparse, urlunparse
from config import node_log

import torch
import platform

# EasyOCR 경고 무시(gpu 사용가능인데 cpu 실행으로 인한 경고)
warnings.filterwarnings("ignore")


# EasyOCR 리더 인스턴스 생성 (한글+영어)
# READER = easyocr.Reader(["ko", "en"], gpu=False)
def init_easyocr_reader(langs: list) -> easyocr.Reader:
    """
    런타임에서 CUDA / MPS 지원 여부를 검사해서
    GPU 사용이 가능한 경우에만 EasyOCR에 gpu=True 플래그를 넘깁니다.
    """
    if torch.cuda.is_available():
        # print("✅ CUDA GPU detected → EasyOCR on GPU")
        use_gpu = True
    elif platform.system() == "Darwin" and torch.backends.mps.is_available():
        # 현재 EasyOCR는 MPS를 공식 지원하지 않으므로
        # MPS에서는 fallback으로 CPU를 사용하도록 처리합니다.
        # print("⚠️ Apple MPS detected, but EasyOCR only supports CUDA → using CPU")
        use_gpu = False
    else:
        # print("⚠️ No GPU detected → using CPU")
        use_gpu = False

    return easyocr.Reader(langs, gpu=use_gpu, verbose=False)


# 실제 Reader 생성
READER = init_easyocr_reader(["ko", "en"])


# URL 정규화 함수
def normalize_url(url: str) -> str:
    pattern = re.compile(r"(?<=/.)p(?=/)|(?<=/)p(?=./)")
    if "://www." in url:
        url = url.replace("://www.", "://m.")
    return pattern.sub("m", url)


# OCR 수행 (EasyOCR 사용)
def ocr(image_path: str) -> str:
    if not os.path.exists(image_path):
        print(f"not valid image file path: {image_path}")
        return ""
    results = READER.readtext(image_path)
    text = " ".join([res[1] for res in results])
    text = re.sub(r"\s+", " ", text).strip()

    # try:
    #     os.remove(image_path)
    # except OSError as e:
    #     print(f"⚠️ 파일 삭제 실패: {e}")

    return text


# 메인 파싱 함수
def parse_image_text(state: Dict) -> Dict:
    node_log("PARSE IMAGE TEXT")
    url = state.get("url")
    if not url:
        print("empty url")
        return {}

    screenshot_file = "./img/screenshot.png"
    normalized = normalize_url(url)

    # ─── 도메인별 뷰포트 너비 맵 ───────────────────────────
    domain_widths = {
        "coupang": (600, 1300),
        "gmarket": (1300, 600),
    }

    # 기본 뷰포트
    width, height = 1300, 1300

    host = urlparse(normalized).netloc.lower()

    for domain, (w, h) in domain_widths.items():
        if domain in host:
            width, height = w, h
            break
    # ───────────────────────────────────────────────────────

    # Selenium WebDriver 설정
    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_experimental_option(
        "mobileEmulation",
        {
            "deviceMetrics": {"width": width, "height": height, "pixelRatio": 2.0},
            "userAgent": (
                "Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) "
                "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 "
                "Mobile/15E148 Safari/604.1"
            ),
        },
    )

    opts.add_argument("--ignore-certificate-errors")
    opts.set_capability("acceptInsecureCerts", True)

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=opts)

    # stealth 설정
    stealth(
        driver,
        languages=["ko-KR", "ko"],
        vendor="Google Inc.",
        platform="iPhone",
        webgl_vendor="Intel Inc.",
        renderer="Intel Iris OpenGL Engine",
        fix_hairline=True,
    )

    # alert override: 팝업 방지 스크립트 추가
    driver.execute_cdp_cmd(
        "Page.addScriptToEvaluateOnNewDocument",
        {
            "source": "window.alert = ()=>{}; window.confirm = ()=>true; window.prompt = ()=>null;"
        },
    )

    # 페이지 로드 및 스크린샷 시도
    try:
        driver.get(normalized)
        time.sleep(2)
        driver.save_screenshot(screenshot_file)
    except UnexpectedAlertPresentException:
        # alert 발생 시 닫고 재시도
        try:
            alert = driver.switch_to.alert
            alert.dismiss()
        except Exception as e:
            print(e)
            return "alert error"

        time.sleep(1)
        driver.save_screenshot(screenshot_file)
    finally:
        driver.quit()

    # OCR 및 상태 업데이트
    text = ocr(screenshot_file)
    if text == "":
        print("OCR result is empty")
        return "OCR result is empty. please check image."

    state["page"] = text
    state["page_meta"] = ""
    return state
