from langchain_core.prompts import PromptTemplate
from llm.factory import get_annc_parser_client
from config import PRODUCT_ANNC_PARCER_PROMPT, node_log
from typing import Dict
from pydantic import BaseModel, Field
from langchain_core.output_parsers import JsonOutputParser

# 1) LLM 클라이언트와 프롬프트 준비
llm = get_annc_parser_client()
prompt_template = PromptTemplate.from_template(PRODUCT_ANNC_PARCER_PROMPT)


class Topic(BaseModel):
    product_name: str = Field(
        description="메인 상품의 상세한 상품명(정식 상품명). 무게와 개수가 포함되어있다면 그대로 포함합니다. 부자연스러운 단어들은 자연스럽게 바꿔 작성합니다.",
        example="스윗마토 방울토마토(500g x 2팩)",
    )
    product_lower_name: str = Field(
        description="메인 상품의 명칭과 브랜드와 같이 상품 이름에서 알아야 할 특이사항(무게와 개수가 포함되지 않고, 대중적으로 불리는 이름 및 메인 상품의 브랜드와 같은 식별 가능 정보는 포함).",
        example="스윗마토 방울토마토",
    )
    total_price: int = Field(
        description="메인 상품의 가격(원, 달러 등의 화폐 단위가 붙은 숫자)"
    )
    count: int = Field(description="메인 상품의 개수(개수 단위가 붙은 숫자)")


def product_annc_parser(state: Dict) -> Dict:
    node_log("PRODUCT ANNOUNCEMENT PARSER")
    docs = state["documents"]

    context = "\n\n".join(f"<document>{doc.page_content}</document>" for doc in docs)
    # JsonOutputParser 설정
    parser = JsonOutputParser(pydantic_object=Topic)

    # 1) format_instructions를 먼저 바인딩 (partial)
    prompt_with_instructions = prompt_template.partial(
        format_instructions=parser.get_format_instructions()
    )

    # 2) context를 전달하여 최종 문자열 생성
    formatted_prompt = prompt_with_instructions.format(context=context)

    # 3) LLM 호출
    answer = llm.chat(formatted_prompt)
    text = getattr(answer, "content", answer)
    parsed: Topic = parser.parse(text)

    state["generation"] = parsed
    return state
