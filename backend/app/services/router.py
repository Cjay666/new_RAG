"""Query Router — classify user question and decide rewriting strategy."""

from __future__ import annotations

import json

import httpx

from ..config import LOCAL_LLM_MODEL, OLLAMA_BASE_URL

_ROUTER_PROMPT = """你是一个查询路由分析器。分析用户的问题，判断它属于哪一类，应该走什么改写策略。

分类标准：
- "direct": 问题清晰、语义完整、指代明确，可以直接检索
- "dehydrate": 包含模糊代词(他/它/那个/这个)、废话/礼貌用语，需要消歧+脱水
- "step_back": 需要多步推理、比较分析、综合判断的复杂问题
- "hyde": 短问题、专业冷门领域、在文档中可能有多种表述方式的问题

输入：
用户问题：{question}
对话历史：{history}

请只返回JSON格式：
{{"category": "direct|dehydrate|step_back|hyde", "reason": "简短理由"}}

注意：可以选择多个类别，用逗号分隔，例如："dehydrate,hyde"
如果问题混合了多种特征，返回多个类别。"""


async def route_query(question: str, history: list[str] | None = None) -> list[str]:
    """Analyze the question and return which rewriting strategies to apply.

    Returns a list of strategy names: ["direct"] | ["dehydrate"] | ["hyde", "step_back"] | etc.
    """
    history_str = "\n".join(history[-5:]) if history else "无历史对话"

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{OLLAMA_BASE_URL}/api/generate",
            json={
                "model": LOCAL_LLM_MODEL,
                "prompt": _ROUTER_PROMPT.format(question=question, history=history_str),
                "stream": False,
                "options": {"temperature": 0.1, "num_predict": 150},
            },
        )
        resp.raise_for_status()
        raw = resp.json()["response"].strip()

    # Extract JSON from response
    try:
        # Handle possible markdown code fences
        if "```" in raw:
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        data = json.loads(raw)
        categories = [s.strip() for s in data["category"].split(",")]
    except (json.JSONDecodeError, KeyError):
        categories = ["direct"]

    # Normalize
    valid = {"direct", "dehydrate", "step_back", "hyde"}
    strategies = [c for c in categories if c in valid]
    if not strategies:
        strategies = ["direct"]

    return strategies
