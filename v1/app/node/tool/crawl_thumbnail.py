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

import aiohttp
import asyncio

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

async def download_thumbnail(img_url, proxy):
    savefilename = 'thumbnail.jpg'
    parsed = urlparse(img_url)
    filename = os.path.basename(parsed.path)
    if not filename:
        return

    dest_path = os.path.join('img', savefilename)

    connector = aiohttp.TCPConnector(ssl=False)

    async with aiohttp.ClientSession(connector=connector) as client:
        async with client.get(img_url, proxy=proxy) as resp:
            resp.raise_for_status()
            data = await resp.read()

            with open(dest_path, 'wb') as f:
                f.write(data)

    return dest_path


def capture_thumbnail(url, output_path = 'img/thumbnail.jpg'):
    os.makedirs('img', exist_ok=True)

    options = Options()
    options.add_argument('--headless')
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")

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
        driver.get_screenshot_as_file(output_path)

        return output_path

    finally:
        driver.quit()

async def crawl_and_save(url: str, session, proxy):
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
                    download_thumbnail_path = await download_thumbnail(thumbnail_url, proxy)
                    return download_thumbnail_path
                except Exception as e:
                    print(f"[ERROR] 다운로드 실패 ({thumbnail_url}): {e}")
                    return e
            except Exception as e:
                print(f"[ERROR] 페이지 로드 실패: {e}")
                return e

    download_thumbnail_path = capture_thumbnail(url)

    return download_thumbnail_path

async def upload_thumbnail(download_thumbnail_path: str):
    presigned_url = get_presigned_url()

    file_path = os.getcwd() + '/' + download_thumbnail_path

    with open(file_path, 'rb') as f:
        file_bytes = f.read()

    connector = aiohttp.TCPConnector(ssl=False)

    async with aiohttp.ClientSession(connector=connector) as session:
        try:
            async with session.put(
                presigned_url.get('url'),
                data=file_bytes,
                headers={'Content-Type': 'image'}
            ) as resp:
                resp.raise_for_status()
                return presigned_url.get('key')
        except aiohttp.ClientResponseError as e:
            body = await resp.text()
            print(f"[ERROR] Upload failed: {e}\nResponse body: {body}")
            return e

async def crawl_thumbnail(url: str, session, proxy):
    download_thumbnail_path = await crawl_and_save(url, session, proxy)
    
    upload_image_key = await upload_thumbnail(download_thumbnail_path)

    return upload_image_key