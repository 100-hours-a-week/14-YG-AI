import os
import requests
from bs4 import BeautifulSoup
import urllib3
from urllib.parse import urljoin, urlparse
from proxy_factory import ProxySession

urllib3.disable_warnings()

def filter_largest_image_urls(image_urls):
    def extract_size(u):
        # '/' 단위로 뗀 후, 'ex'로 끝나고 'x'가 있는 단위에서 앞 숫자만 뽑아 int로 반환, 없으면 0.
        for seg in urlparse(u).path.split('/'):
            if seg.endswith('ex') and 'x' in seg:
                try:
                    return int(seg.split('x', 1)[0])
                except ValueError:
                    pass
        return 0

    largest_image_url = image_urls[0]
    largest_image_size = -1
    for u in image_urls:
        size = extract_size(u)

        if size >= largest_image_size:
            largest_image_url = u

    return largest_image_url

def fetch_coupang_image_urls(page_url, session, selector='img'):
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

    filtered = filter_largest_image_urls(image_urls)

    return filtered

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
        image_urls = fetch_coupang_image_urls(url, session)

        try:
            download_image(image_urls, dest_dir, session)
        except Exception as e:
            print(f"[ERROR] 다운로드 실패 ({image_urls}): {e}")
    except Exception as e:
        print(f"[ERROR] 페이지 로드 실패: {e}")

if __name__ == '__main__':
    page = 'https://www.coupang.com/vp/products/4590016491?itemId=1053867&vendorItemId=3000994741'

    crawl_and_save(page)
