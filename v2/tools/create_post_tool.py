# access_token을 활용한 백엔드 API 호출을 통해 공구 게시글 초안 생성 도구
import requests
import json
from typing import Dict, Any
from langchain_core.tools import tool
import logging
from core.session import get_current_access_token

logger = logging.getLogger(__name__)


# tools/create_post_tool.py 수정
@tool
def create_post(url: str) -> str:
    """공구 생성 도구"""

    # access_token = get_current_access_token()

    # if not access_token:
    #     return "❌ 인증 정보가 없습니다. 다시 로그인해 주세요."

    # api_url = "https://moongsan.com/api/group-buys/generation/description"
    # api_url = "https://dev.moongsan.com/api/group-buys/generation/description"
    api_url = "https://dev.moongsan.com/generation/description"

    post_data = {"url": url}

    # 올바른 헤더 설정
    headers = {
        "Content-Type": "application/json; charset=utf-8",
        "Cookie": f"AccessToken=asd",
    }

    try:
        response = requests.post(api_url, json=post_data, headers=headers, timeout=120)
        print(f"response: {response}")
        if response.status_code == 200:
            data = response.json()
            # message 키 제거
            if "message" in data:
                del data["message"]

            # JSON으로 변환
            json_string = json.dumps(data, ensure_ascii=False, indent=4)
            print(json_string)
            wrap_data = f"CREATE_PRODUCT_START\n{json_string}\nCREATE_PRODUCT_END"
            print(wrap_data)

            # 실제 생성된 공구 정보 추출
            # post_data = data.get("data", {})

            #             result_message = f"""✅ 공구 게시글이 성공적으로 생성되었습니다!

            # 📦 **상품명**: {post_data.get('product_name', 'N/A')}
            # 💰 **가격**: {post_data.get('total_price', 0):,}원 (총 {post_data.get('count', 0)}개)
            # 📝 **제목**: {post_data.get('title', 'N/A')}

            # 📋 **상세 설명**:
            # {post_data.get('summary', 'N/A')}

            # 📅 **마감일**: {post_data.get('due_date', 'N/A')}
            # 📦 **픽업일**: {post_data.get('pickup_date', 'N/A')}

            # 🎯 공구 참여를 원하시면 말씀해 주세요!"""

            return wrap_data

        elif response.status_code == 401:
            print("❌ 인증 토큰이 만료되었습니다. 다시 로그인해 주세요.")
            return "❌ 인증 토큰이 만료되었습니다. 다시 로그인해 주세요."
        elif response.status_code == 403:
            print("❌ 이 작업을 수행할 권한이 없습니다.")
            return "❌ 이 작업을 수행할 권한이 없습니다."
        elif response.status_code == 400:
            print("❌ 유효하지 않은 URL 형식입니다. URL을 다시 확인해 주세요.")
            return "❌ 유효하지 않은 URL 형식입니다. URL을 다시 확인해 주세요."
        elif response.status_code == 500:
            print("❌ 서버에서 오류가 발생했습니다. 잠시 후 다시 시도해주세요.")
            return "❌ 서버에서 오류가 발생했습니다. 잠시 후 다시 시도해주세요."
        else:
            print(
                f"❌ 예상치 못한 오류가 발생했습니다. (상태코드: {response.status_code})"
            )
            return f"❌ 예상치 못한 오류가 발생했습니다. (상태코드: {response.status_code})"

    except requests.exceptions.Timeout:
        print(
            "❌ 요청 시간이 초과되었습니다. 네트워크 상태를 확인하고 다시 시도해 주세요."
        )
        return "❌ 요청 시간이 초과되었습니다. 네트워크 상태를 확인하고 다시 시도해 주세요."
    except requests.exceptions.ConnectionError:
        print("❌ 서버에 연결할 수 없습니다. 네트워크 연결을 확인해 주세요.")
        return "❌ 서버에 연결할 수 없습니다. 네트워크 연결을 확인해 주세요."
    except requests.exceptions.RequestException as e:
        print(f"❌ 요청 중 오류가 발생했습니다: {str(e)}")
        return f"❌ 요청 중 오류가 발생했습니다: {str(e)}"
    except json.JSONDecodeError:
        print("❌ 서버 응답을 처리할 수 없습니다. 잠시 후 다시 시도해 주세요.")
        return "❌ 서버 응답을 처리할 수 없습니다. 잠시 후 다시 시도해 주세요."
    except Exception as e:
        print(f"❌ 알 수 없는 오류가 발생했습니다: {str(e)}")
        return f"❌ 알 수 없는 오류가 발생했습니다: {str(e)}"
