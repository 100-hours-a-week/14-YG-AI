from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional
from api.security.access_token_handler import verify_access_token_cookie
from config import RECURSION_LIMIT
from langchain_core.runnables import RunnableConfig
from langchain_teddynote.messages import random_uuid
from graph.graph import app
from graph.graph_output import invoke_graph_json


def generate_post_run(input: dict):
    config = RunnableConfig(
        recursion_limit=RECURSION_LIMIT, configurable={"thread_id": random_uuid()}
    )

    return invoke_graph_json(app, input, config, node_names=["product_desc_gen"])


# 1) 요청 바디 스키마
class Generate_Post_Request(BaseModel):
    url: str


# 2) 응답 데이터 스키마
class Generate_Post_Response(BaseModel):
    title: str
    product_name: str
    total_price: int
    count: int
    summary: str


class APIResponse(BaseModel):
    message: str
    data: Optional[Generate_Post_Response] = None

router = APIRouter()

@router.post(
    "/generation/description",
    response_model=APIResponse,
    summary="공구 주최글 생성",
    dependencies=[Depends(verify_access_token_cookie)],
)
def generate_post(req: Generate_Post_Request):
    try:
        result = generate_post_run(req.dict())

        payload = result.get("generation", result)

        data = Generate_Post_Response(**payload)

        return APIResponse(message="상품 상세 설명이 생성되었습니다.", data=data)

    except Exception as e:
        print(f"[Error] {e}")
        return APIResponse(
            message="서버에서 오류가 발생했습니다. 잠시 후 다시 시도해주세요.",
            data=None,
        )