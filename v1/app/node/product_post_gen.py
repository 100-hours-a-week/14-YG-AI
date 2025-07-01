from langchain_core.prompts import PromptTemplate
from llm.factory import get_desc_gen_client, get_title_gen_client
from config import PRODUCT_DESC_GEN_PROMPT, PRODUCT_TITLE_GEN_PROMPT, node_log
from typing import Dict
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import asyncio

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
    state["generation"]["due_date"] = generate_due_date()
    state["generation"]["pickup_date"] = generate_pickup_date()

    return {"generation": state["generation"]}

async def generate_describe(state: Dict) -> str:
    prompt = desc_prompt_template.format(context=state["web_search"])
    desc = await llm.async_generate(prompt)
    
    return desc

async def generate_title(state: Dict) -> str:
    prompt = title_prompt_template.format(
        context=state["generation"],
        product_lower_name=state["generation"]["product_lower_name"],
    )
    
    title = await llm.async_generate(prompt)

    return title

# async def generate_date(state: Dict) -> str:

def generate_pickup_date():
    now = datetime.now(ZoneInfo("Asia/Seoul"))
    floored_minute = (now.minute // 30) * 30
    floored = now.replace(minute=floored_minute, second=0, microsecond=0)
    due_datetime = floored + timedelta(days=9)

    return due_datetime.strftime("%Y-%m-%dT%H:%M")

def generate_due_date():
    now = datetime.now(ZoneInfo("Asia/Seoul"))
    floored_minute = (now.minute // 30) * 30
    floored = now.replace(minute=floored_minute, second=0, microsecond=0)
    due_datetime = floored + timedelta(days=7)

    return due_datetime.strftime("%Y-%m-%dT%H:%M")