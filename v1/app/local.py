from config import RECURSION_LIMIT
from langchain_core.runnables import RunnableConfig
from langchain_teddynote.messages import random_uuid
from graph import app
from graph_output import invoke_graph, invoke_graph_clean, invoke_graph_json_test
import sys

# traceback을 아예 안 보여주도록 설정
sys.tracebacklimit = 0


def local_test(inputs: dict):
    """
    딕셔너리 형태의 inputs를 받아 LangGraph 워크플로우를 실행합니다.
    예시) main({"url": "https://...product_page..."})
    """
    # 1) RunnableConfig 생성
    config = RunnableConfig(
        recursion_limit=RECURSION_LIMIT, configurable={"thread_id": random_uuid()}
    )
    # 2) 그래프 실행
    # invoke_graph(app, inputs, config, node_names=["product_desc_gen"])
    # invoke_graph_clean(app, inputs, config, node_names=["product_desc_gen"])
    invoke_graph_json_test(app, inputs, config, node_names=["product_desc_gen"])


# 아래 코드는 스크립트로 직접 실행할 때, 기본 URL을 넣어주는 예시입니다.
if __name__ == "__main__":
    # 디폴트 테스트 URL 혹은 JSON 파싱 등을 여기에 넣어두셔도 되고
    test_inputs = {
        # 마프 오메가3
        # "url": "https://www.myprotein.co.kr/p/sports-nutrition/essential-omega-3/10529329/",
        # 11번가 키위
        # "url": "https://www.11st.co.kr/products/5233499372"
        # 쿠팡 사조참치
        "url": "https://www.coupang.com/vp/products/7038410615?itemId=17397680231&vendorItemId=84567137606",
        # 브랜드.네이버 김치사발면
        # "url": "https://brand.naver.com/nongshim/products/9744402416",
        # 네이버 스마트스토어 몬스터
        # "url": "https://smartstore.naver.com/365mart1/products/7325472185"
        # GS샵 생수
        # "url": "https://www.gsshop.com/prd/prd.gs?prdid=13866536&lseq=390802-7&gsid=ECmain-AU390802-AU390802-7&dseq=7&svcid=pc&bnclick=main-mrcm_mainMrcmA_PopularCateItemUirm&rank=7"
        # 오늘의집 수건
        # "url": "https://ohou.se/productions/345755/selling",
        # 지마켓 트레비
        # "url": "https://item.gmarket.co.kr/Item?goodscode=3066886016"
        # 이마트 영양제
        # "url": "https://emart.ssg.com/item/itemView.ssg?itemId=1000686149754&siteNo=6001&salestrNo=6005"
    }
    local_test(test_inputs)
