# app.py
from fastapi import FastAPI, Header, HTTPException, status, Depends
from pydantic import BaseModel
from typing import Optional
from typing import Optional

from generate_product_announcement import generate_product_announcement

def verify_access_token_cookie(cookie: Optional[str] = Header(None, alias="cookie")):
    if not cookie or not cookie.startswith("AccessToken="):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="유효한 AccessToken 쿠키가 필요합니다."
        )
    # (선택) 토큰 값을 분리해 반환하고 싶다면:
    # token = cookie.split(";", 1)[0].removeprefix("AccessToken=")
    # return token
    return cookie

# 1) 요청 바디 스키마
class Generate_product_announcement_Request(BaseModel):
    url: str


# 2) 응답 데이터 스키마
class Generate_product_announcement_Response(BaseModel):
    title: str
    product_name: str
    total_price: int
    count: int
    summary: str


class APIResponse(BaseModel):
    message: str
    data: Optional[Generate_product_announcement_Response] = None


# 3) FastAPI 인스턴스
app = FastAPI(
    title="상품 상세 설명 생성 API",
    version="0.1.0",
    description="URL을 받아 LangGraph 워크플로우로 상품 상세 설명을 생성합니다.",
)


@app.post(
    "/generation/description",
    response_model=APIResponse,
    summary="상품 상세 설명 생성",
    dependencies=[Depends(verify_access_token_cookie)],
)
def generate_description(req: Generate_product_announcement_Request):
    try:
        result = generate_product_announcement(req.dict())

        payload = result.get("generation", result)

        data = Generate_product_announcement_Response(**payload)

        return APIResponse(message="상품 상세 설명이 생성되었습니다.", data=data)

    except Exception as e:
        print(f"[Error] {e}")
        return APIResponse(
            message="서버에서 오류가 발생했습니다. 잠시 후 다시 시도해주세요.",
            data=None,
        )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app:app", host="0.0.0.0", port=8100)
