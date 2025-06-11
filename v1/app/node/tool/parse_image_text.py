import os, time, re
import easyocr
from typing import Dict
from config import node_log
from node.tool.proxy_session import ProxySession
from node.tool.crawl_thumbnail import capture_thumbnail

READER = easyocr.Reader(["ko", "en"], gpu=False, verbose=False)

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
    #     print(f"파일 삭제 실패: {e}")

    return text


# 메인 파싱 함수
def parse_image_text(state: Dict) -> Dict:
    node_log("PARSE IMAGE TEXT")
    url = state.get("url")
    if not url:
        print("empty url")
        return {}

    file_path = "img/screenshot.jpg"
    capture_thumbnail(url, file_path)
    
    text = ocr(file_path)
    if text == "":
        print("OCR result is empty")
        return "OCR result is empty. please check image."

    state["page"] = text
    state["page_meta"] = ""
    return state
