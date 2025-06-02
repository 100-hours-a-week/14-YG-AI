from api.generate_post import generate_post_run_test
import sys

# traceback을 아예 안 보여주도록 설정
sys.tracebacklimit = 0


if __name__ == "__main__":
    input = {
        # 마프 오메가3
        "url": "https://www.myprotein.co.kr/p/sports-nutrition/essential-omega-3/10529329/",
        # 11번가 옥동자아이스크림
        # "url": "https://www.11st.co.kr/products/pa/5796843123"
        # 11번가 키위
        # "url": "https://www.11st.co.kr/products/5233499372"
        # 쿠팡 사조참치
        # "url": "https://www.coupang.com/vp/products/7038410615?itemId=17397680231&vendorItemId=84567137606",
        # 브랜드.네이버 김치사발면
        # "url": "https://brand.naver.com/nongshim/products/9744402416",
        # 네이버 스마트스토어 몬스터
        # "url": "https://smartstore.naver.com/365mart1/products/7325472185"
        # GS샵 생수
        # "url": "https://www.gsshop.com/prd/prd.gs?prdid=13866536"
        # 오늘의집 수건
        # "url": "https://ohou.se/productions/345755/selling",
        # 지마켓 트레비
        # "url": "https://item.gmarket.co.kr/Item?goodscode=3066886016"
        # 이마트 영양제
        # "url": "https://emart.ssg.com/item/itemView.ssg?itemId=1000686149754&siteNo=6001&salestrNo=6005"
    }
    
    generate_post_run_test(input)
