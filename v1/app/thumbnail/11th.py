import os, re, requests
from bs4 import BeautifulSoup
import urllib3
from urllib.parse import urljoin, urlparse
from proxy_factory import ProxySession

urllib3.disable_warnings()

def extract_11th_img_size(u):
    # /resize/{W}x{H}/' 형태에서 'W'(Width) 만 뽑아 int로 반환, 없으면 0.
    pattern = re.compile(r"/resize/(\d+)x(\d+)/")
    m = pattern.search(urlparse(u).path)
    if m:
        try:
            return int(m.group(1))
        except ValueError:
            pass
    return -1

def filter_largest_img_url(image_urls):
    largest_image_url = image_urls[0]
    largest_image_size = -1
    for u in image_urls:
        size = extract_11th_img_size(u)

        if size >= largest_image_size:
            largest_image_url = u
            largest_image_size = size

    return largest_image_url

def fetch_image_urls(page_url, session, selector='img'):
    resp = session.get(page_url)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, 'html.parser')
    image_urls = []
    for img in soup.select(selector):
        src = img.get('src')
        if not src:
            continue
        
        if 'cdn.011st.com/11dims/resize' in src:
            img_url = urljoin(page_url, src)
            image_urls.append(img_url)

    filtered = filter_largest_img_url(image_urls)

    return filtered

def download_image(img_url, dest_dir, session):
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
    page = "https://www.11st.co.kr/products/8087653567?trTypeCd=03&trCtgrNo=2142534"

    crawl_and_save(page)
