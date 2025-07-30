# import os, asyncio, httpx
# from fastapi import FastAPI
# from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
# from moderation_chat.moderation import moderation_chat

# KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:19092")
# CHAT_TOPIC = os.getenv("CHAT_TOPIC", "chat")
# MODERATION_TOPIC = os.getenv("MODERATION_TOPIC", "moderation")
# GROUP_ID = os.getenv("KAFKA_GROUP_ID", "moderation-service")

# async def connect_kafka(app: FastAPI):
#     consumer = AIOKafkaConsumer(
#         CHAT_TOPIC,
#         bootstrap_servers=KAFKA_BOOTSTRAP,
#         group_id=GROUP_ID,
#         auto_offset_reset="latest",
#     )
#     producer = AIOKafkaProducer(bootstrap_servers=KAFKA_BOOTSTRAP)
#     await consumer.start()
#     await producer.start()

#     app.state.kafka_consumer = consumer
#     app.state.kafka_producer = producer

#     asyncio.create_task(moderation_chat(MODERATION_TOPIC, app))

# async def disconnect_kafka(app: FastAPI):
#     await app.state.kafka_consumer.stop()
#     await app.state.kafka_producer.stop()
