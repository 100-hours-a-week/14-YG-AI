import os
import requests
from bs4 import BeautifulSoup
import urllib3
from urllib.parse import urljoin, urlparse
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
import warnings

from auth.get_presigned_url import get_presigned_url


urllib3.disable_warnings()

warnings.filterwarnings(
        "ignore",
        message="name used for saved screenshot does not match file type"
    )

def extract_coupang_thumbnail_size(u):
    for seg in urlparse(u).path.split('/'):
        if seg.endswith('ex') and 'x' in seg:
            try:
                return int(seg.split('x', 1)[0])
            except ValueError:
                pass
    return -1

def filter_largest_thumbnail_url(image_urls):
    largest_image_url = image_urls[0]
    largest_image_size = -1
    for u in image_urls:
        size = extract_coupang_thumbnail_size(u)

        if size >= largest_image_size:
            largest_image_url = u
            largest_image_size = size

    return largest_image_url

def fetch_coupang_thumbnail_url(page_url, session, selector='img'):
    resp = session.get(page_url)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, 'html.parser')
    image_urls = []
    for img in soup.select(selector):
        src = img.get('src')
        if not src:
            continue
        
        if 'thumbnail' in src:
            img_url = urljoin(page_url, src)
            image_urls.append(img_url)

    largest_thumbnail_url = filter_largest_thumbnail_url(image_urls)

    return largest_thumbnail_url

def fetch_naver_thumbnail_url(page_url, session, selector='img'):
    resp = session.get(page_url)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, 'html.parser')
    img_url = None
    for img in soup.select(selector):
        src = img.get('src')
        if not src:
            continue

        if any(ext in src for ext in ['png', 'jpg', 'jpeg']):
            img_url = urljoin(page_url, src)    

    return img_url

def download_thumbnail(img_url, dest_dir, session):
    savefilename = 'thumbnail.jpg'
    parsed = urlparse(img_url)
    filename = os.path.basename(parsed.path)
    if not filename:
        return

    dest_path = os.path.join(dest_dir, savefilename)

    # 스트리밍 모드로 요청
    with session.get(img_url, stream=True) as r:
        r.raise_for_status()
        with open(dest_path, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)

    return dest_path 


def capture_thumbnail(url):
    os.makedirs('img', exist_ok=True)

    savefilename = 'thumbnail.jpg'
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
        # 한글 폰트 js로 주입
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


        driver.get_screenshot_as_file(output_path)

        return output_path

    finally:
        driver.quit()


def crawl_and_save(url: str, session: str):
    os.makedirs('img', exist_ok=True)

    domain_handlers = {
        'naver': fetch_naver_thumbnail_url,
        'coupang': fetch_coupang_thumbnail_url,
    }

    for key, handler in domain_handlers.items():
        if key in url:
            try:
                thumbnail_url = handler(url, session)
                try:
                    return download_thumbnail(thumbnail_url, 'img', session)
                except Exception as e:
                    print(f"[ERROR] 다운로드 실패 ({thumbnail_url}): {e}")
                    return e
            except Exception as e:
                print(f"[ERROR] 페이지 로드 실패: {e}")
                return e

    return capture_thumbnail(url)

def upload_thumbnail(file_path: str):
    presigned_url = get_presigned_url()

    file_path = os.getcwd() + '/' + file_path

    with open(file_path, 'rb') as f:
        files = {'file': (file_path, f, 'image')}

        resp = requests.put(presigned_url.get('url'), data=f, headers={'Content-Type': 'image'})
    try:
        resp.raise_for_status()
        return presigned_url.get('key')
    except requests.HTTPError as e:
        print(f"[ERROR] Upload failed: {e}\nResponse body: {resp.text}")
        return e
