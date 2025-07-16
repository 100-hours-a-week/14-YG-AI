import json
from fastapi import FastAPI
from typing import Optional, Tuple
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from moderation_chat.schema.kafka_schema import ChatEvent, ModerationEvent
from moderation_chat.config.vLLM_config import call_llm
from pydantic import ValidationError

CATEGORY_MAP = {
    "S1": "증오",
    "S2": "괴롭힘",
    "S3": "성적 콘텐츠",
    "S4": "범죄",
    "S5": "아동 성착취",
    "S6": "자살 및 자해",
    "S7": "잘못된 정보",
}

def parse_llm_result(res: str) -> Tuple[bool, Optional[str]]:
    text = res.strip()
    if text == "<SAFE>":
        return True, "None"
    for code, description in CATEGORY_MAP.items():
        if text.startswith(f"<UNSAFE-{code}>"):
            return False, description
    return False, "알 수 없음"


async def moderation_chat(MODERATION_TOPIC:str, app: FastAPI):
    consumer: AIOKafkaConsumer = app.state.kafka_consumer
    producer: AIOKafkaProducer = app.state.kafka_producer

    async for msg in consumer:
        raw = msg.value.decode('utf-8')
        print(f"Received: {raw}")
        try:
            event = ChatEvent.model_validate_json(raw) 
        except ValidationError as exc:
            print("스키마 검증 실패:", exc.json())
            continue

        try:
            llm_res = await call_llm(event.content)
        except Exception as e:
            print(f"LLM 호출 실패: {e}")
            continue

        is_safe, reason = parse_llm_result(llm_res)

        payload_model = ModerationEvent(
            room_id=event.room_id,
            message_id=msg.offset,
            is_safe=is_safe,
            reason=reason
        )

        out_payload = payload_model.dict(by_alias=True)

        await producer.send_and_wait(
            MODERATION_TOPIC,
            json.dumps(out_payload).encode('utf-8')
        )
        print(f"Sent: {out_payload}")

