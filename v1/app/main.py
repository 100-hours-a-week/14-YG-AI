from fastapi import FastAPI
from pydantic import BaseModel
from typing import Optional

from api import generate_description

app = FastAPI(
    title="generate_description_server",
    version="0.2.1",
    description="URL을 받아 LangGraph 워크플로우로 상품 상세 설명을 생성합니다.",
)

app.include_router(generate_description.router)

@app.get("/")
def read_root():
    return {"message": "Hello, this is the 14-YG-AI-server. API is running."}

@app.get("/health")
def health_check():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8100)
