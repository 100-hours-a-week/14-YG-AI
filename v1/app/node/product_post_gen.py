from langchain_core.prompts import PromptTemplate
from llm.factory import get_desc_gen_client, get_title_gen_client
from config import PRODUCT_DESC_GEN_PROMPT, PRODUCT_TITLE_GEN_PROMPT, node_log
from typing import Dict

import asyncio

# 1) LLM 클라이언트와 프롬프트 준비
llm = get_desc_gen_client()
desc_prompt_template = PromptTemplate.from_template(PRODUCT_DESC_GEN_PROMPT)
title_prompt_template = PromptTemplate.from_template(PRODUCT_TITLE_GEN_PROMPT)


async def product_post_gen(state: Dict) -> Dict:
    node_log("GENERATE POST")

    desc_task = asyncio.create_task(generate_describe(state))
    title_task = asyncio.create_task(generate_title(state))

    desc_res, title_res = await asyncio.gather(desc_task, title_task)

    state["generation"]["summary"] = desc_res
    state["generation"]["title"] = title_res

    return {"generation": state["generation"]}

async def generate_describe(state: Dict) -> str:
    docs = state["web_search"]
    context = "\n\n".join(
        f"<document><content>{doc.page_content}</content></document>"
        for doc in docs
    )

    prompt = desc_prompt_template.format(context=context)
    desc = await llm.async_generate(prompt)
    
    return desc

async def generate_title(state: Dict) -> str:
    prompt = title_prompt_template.format(
        context=state["generation"],
        product_lower_name=state["generation"]["product_lower_name"],
    )
    
    title = await llm.async_generate(prompt)

    return title