from fastapi import FastAPI
from api import generate_post

app = FastAPI(
    title="generate_description_server",
    version="0.2.1",
    description="URL to POST(상품 공동구매 주최글 작성 자동화) 서버.",
)

app.include_router(generate_post.router)

@app.get("/")
def read_root():
    return {"message": "Hello, this is the 14-YG-AI-server. API is running."}

@app.get("/health")
def health_check():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8100)
