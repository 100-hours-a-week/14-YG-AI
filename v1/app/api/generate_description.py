from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional

from generate_product_announcement import generate_product_announcement
from api.security.access_token_handler import verify_access_token_cookie

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

router = APIRouter()

@router.post(
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