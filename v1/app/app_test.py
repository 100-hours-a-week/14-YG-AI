# app.py
from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.responses import JSONResponse
from typing import Optional

from generate_product_announcement import generate_product_announcement_test


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
    description="입력된 URL의 상품 페이지를 스크랩 및 분석하여 상세 설명을 생성합니다.",
)
def generate_description(req: Generate_product_announcement_Request):
    try:
        result = generate_product_announcement_test(req.dict())

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
