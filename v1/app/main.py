#main.py
from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI
from contextlib import asynccontextmanager
from api import generate_post
from moderation_chat.config.kafka_config import connect_kafka, disconnect_kafka

@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect_kafka(app)

    yield

    await disconnect_kafka(app)

def create_app() -> FastAPI:
    from fastapi import FastAPI

    app = FastAPI(
        title="generate_description_server",
        version="0.2.1",
        description="URL to POST(상품 공동구매 주최글 작성 자동화) 서버.",
        lifespan=lifespan)

    app.include_router(generate_post.router)

    @app.get("/")
    def read_root():
        return {"message": "Hello, this is the 14-YG-AI-server. API is running."}

    @app.get("/health")
    def health_check():
        return {"status": "ok"}

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8100)
