import os, re, requests
from bs4 import BeautifulSoup
import urllib3
from urllib.parse import urljoin, urlparse
from proxy_factory import ProxySession

urllib3.disable_warnings()

def fetch_image_urls(page_url, session):
    regex = re.compile(r"<img\b[^>]*src=['\"]([^'\"]+)['\"]", re.IGNORECASE)

    with session.get(page_url, stream=True) as resp:
        resp.raise_for_status()
        buffer = ""
        for chunk in resp.iter_content(chunk_size=1024, decode_unicode=True):
            buffer += chunk
            m = regex.search(buffer)
            if m:
                return m.group(1)
        return None

def download_image(img_url, dest_dir, session):
    savefilename = 'thumbnail.jpg'
    parsed = urlparse(img_url)
    filename = os.path.basename(parsed.path)
    if not filename:
        return

    dest_path = os.path.join(dest_dir, savefilename)
    # 스트리밍 모드로 요청
    with session.get(img_url, stream=True) as resp:
        resp.raise_for_status()
        with open(dest_path, 'wb') as file:
            for chunk in resp.iter_content(chunk_size=8192):
                if chunk:
                    file.write(chunk)
    print(f"[DOWNLOADED] {filename} as {savefilename}")

def crawl_and_save(url, dest_dir='img'):
    os.makedirs(dest_dir, exist_ok=True)

    ps = ProxySession()
    session = ps.session

    print(f"[FETCHING PAGE] {url}")
    try:
        image_url = fetch_image_urls(url, session)

        try:
            download_image(image_url, dest_dir, session)
        except Exception as e:
            print(f"[ERROR] 다운로드 실패 ({image_url}): {e}")
    except Exception as e:
        print(f"[ERROR] 페이지 로드 실패: {e}")

if __name__ == '__main__':
    page = "https://www.myprotein.co.kr/p/sports-nutrition/daily-multivitamin-tablets/10530076/"

    crawl_and_save(page)
