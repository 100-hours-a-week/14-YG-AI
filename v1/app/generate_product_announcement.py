from config import RECURSION_LIMIT
from langchain_core.runnables import RunnableConfig
from langchain_teddynote.messages import random_uuid
from graph import app
from graph_output import invoke_graph_json_test
from graph_output import invoke_graph_json


from config import RECURSION_LIMIT


def generate_product_announcement(inputs: dict):
    """
    딕셔너리 형태의 inputs를 받아 LangGraph 워크플로우를 실행합니다.
    예시) main({"url": "https://...product_page..."})
    """
    # 1) RunnableConfig 생성
    config = RunnableConfig(
        recursion_limit=RECURSION_LIMIT, configurable={"thread_id": random_uuid()}
    )

    return invoke_graph_json(app, inputs, config, node_names=["product_desc_gen"])

