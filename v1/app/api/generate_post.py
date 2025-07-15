from fastapi import APIRouter, Depends, status, HTTPException
from pydantic import BaseModel
from typing import Optional
from api.security.access_token_handler import verify_access_token_cookie
from config import RECURSION_LIMIT
from langchain_core.runnables import RunnableConfig
from langchain_teddynote.messages import random_uuid
from graph.graph import app
from graph.graph_output import invoke_graph_json

class GeneratePostRequest(BaseModel):
    url: str

class GeneratePostResponse(BaseModel):
    upload_image_key: str
    title: str
    product_name: str
    total_price: int
    count: int
    summary: str
    due_date: str
    pickup_date: str
    

class APIResponse(BaseModel):
    message: str
    data: Optional[GeneratePostResponse] = None


router = APIRouter()

@router.post(
    "/generation/description",
    response_model=APIResponse,
    summary="공구 주최글 생성",
    dependencies=[Depends(verify_access_token_cookie)],
)
async def generate_post(req: GeneratePostRequest):
    try:
        result = await run_generate_post(req.dict())

        payload = result.get("generation", result)
        data = GeneratePostResponse(**payload)
        return APIResponse(message="상품 상세 설명이 생성되었습니다.", data=data)

    except Exception as e:
        print(f"[Error] {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="서버에서 오류가 발생했습니다. 잠시 후 다시 시도해주세요."
        )


async def run_generate_post(input: dict):
    config = RunnableConfig(
        recursion_limit=RECURSION_LIMIT, configurable={"thread_id": random_uuid()}
    )

    return await invoke_graph_json(app, input, config, node_names=["product_post_gen"])