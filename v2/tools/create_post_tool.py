import requests
import json
from typing import Dict, Any
from langchain_core.tools import tool


@tool
def create_post(url: str) -> str:
    """공구 생성 (승인 필요 없음, 워크플로우에서 처리)"""

    # API 엔드포인트 설정
    api_url = "https://dev.moongsan.com/api/group-buys/generation/description"

    # 요청 데이터 구성
    post_data = {"url": url}

    # 헤더 설정
    headers = {"Content-Type": "application/json;charset=UTF-8"}

    try:
        # API 호출
        response = requests.post(
            api_url, json=post_data, headers=headers, timeout=30  # 30초 타임아웃
        )

        # 응답 처리
        if response.status_code == 200:
            data = response.json()
            product_info = data.get("data", {})

            # 성공 메시지 포맷팅
            result_message = f"""✅ 공구 게시글 초안이 작성되었습니다! AI가 작성한 초안은 틀릴 수 있습니다. 꼭 확인하시고 다음 과정을 진행해주세요!

📦 **상품 정보**
- 상품명: {product_info.get('product_name', 'N/A')}
- 간단명: {product_info.get('product_lower_name', 'N/A')}
- 가격: {product_info.get('total_price', 0):,}원
- 수량: {product_info.get('count', 0)}개

📝 **AI 생성 설명**
{product_info.get('summary', '설명을 생성하지 못했습니다.')}

---
⚠️ 생성된 내용을 검토하신 후 필요시 수정해 주세요."""

            return result_message

        elif response.status_code == 400:
            return "❌ 유효하지 않은 URL 형식입니다. URL을 다시 확인해 주세요."

        elif response.status_code == 401:
            return "❌ 인증 정보가 유효하지 않습니다. 로그인 상태를 확인해 주세요."

        elif response.status_code == 500:
            return "❌ 서버에서 오류가 발생했습니다. 잠시 후 다시 시도해주세요."

        else:
            return f"❌ 예상치 못한 오류가 발생했습니다. (상태코드: {response.status_code})"

    except requests.exceptions.Timeout:
        return "❌ 요청 시간이 초과되었습니다. 네트워크 상태를 확인하고 다시 시도해 주세요."

    except requests.exceptions.ConnectionError:
        return "❌ 서버에 연결할 수 없습니다. 네트워크 연결을 확인해 주세요."

    except requests.exceptions.RequestException as e:
        return f"❌ 요청 중 오류가 발생했습니다: {str(e)}"

    except json.JSONDecodeError:
        return "❌ 서버 응답을 처리할 수 없습니다. 잠시 후 다시 시도해 주세요."

    except Exception as e:
        return f"❌ 알 수 없는 오류가 발생했습니다: {str(e)}"
