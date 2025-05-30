import os
import requests
from bs4 import BeautifulSoup
import urllib3
from urllib.parse import urljoin, urlparse
from proxy_factory import ProxySession

urllib3.disable_warnings()

def fetch_naver_image_url(page_url, session, selector='img'):
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

def download_image(img_url, dest_dir, session):
    savefilename = 'thumbnail.jpg'
    parsed = urlparse(img_url)
    filename = os.path.basename(parsed.path)
    if not filename:
        return

    dest_path = os.path.join(dest_dir, savefilename)
    # 이미 다운받은 파일 스킵
    # if os.path.exists(dest_path):
    #     print(f"[SKIP] {filename} already exists.")
    #     return

    # 스트리밍 모드로 요청
    with session.get(img_url, stream=True) as r:
        r.raise_for_status()
        with open(dest_path, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
    print(f"[DOWNLOADED] {filename} as {savefilename}")

def crawl_and_save(url, dest_dir='img'):
    os.makedirs(dest_dir, exist_ok=True)

    ps = ProxySession()
    session = ps.session

    print(f"[FETCHING PAGE] {url}")
    try:
        img_url = fetch_naver_image_url(url, session)

        try:
            download_image(img_url, dest_dir, session)
        except Exception as e:
            print(f"[ERROR] 다운로드 실패 ({img_url}): {e}")
    except Exception as e:
        print(f"[ERROR] 페이지 로드 실패: {e}")

if __name__ == '__main__':
    page = 'https://brand.naver.com/nongshim/products/9744402416'

    crawl_and_save(page)
