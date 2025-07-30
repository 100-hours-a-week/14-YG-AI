# import os, asyncio, httpx

# VLLM_ENDPOINT = os.getenv("VLLM_ENDPOINT", "http://34.47.77.77:8200/v1/chat/completions")

# async def call_llm(message: str) -> str:
#     payload = {
#         "model": "local",
#         "messages": [
#             {
#                 "role": "system", 
#                 "content": (
#                     "0. 반드시 유해할 확률이 98% 이상인 메시지만 UNSAFE 하다고 응답하세요."
#                     "1. 입력의 길이가 1이라면 항상 SAFE를 출력하세요."
#                     "2. 입력이 전부 초성일 때는 항상 SAFE를 출력하세요."
#                 )
#             },
#             {
#                 "role": "user", 
#                 "content": message
#             }
#         ],
#         "temperature": 0.0
#     }
#     async with httpx.AsyncClient(timeout=30.0) as client:
#         resp = await client.post(VLLM_ENDPOINT, json=payload)
#         resp.raise_for_status()
#         data = resp.json()
#         return data["choices"][0]["message"]["content"].strip()