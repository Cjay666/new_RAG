"""Query rewriting — HyDE, Step Back, Dehydration/Disambiguation."""

from __future__ import annotations

import json

import httpx

from ..config import LOCAL_LLM_MODEL, OLLAMA_BASE_URL

# ── Prompts ──────────────────────────────────────────────

_HYDE_PROMPT = """你是一个知识助手。根据用户的问题，写一份简短的回答（200-300字）。这份回答将被用于检索相关文档。

用户问题：{question}

请直接写出回答，不要加"好的"、"根据"等开头语。"""

_STEP_BACK_PROMPT = """你是一个问题分析器。面对用户提出的复杂问题，你需要：
1. 回退到更抽象的原理层面
2. 将复杂问题拆分为2-4个独立的原子子问题
3. 每个子问题应该可以独立回答

用户问题：{question}

请返回JSON格式：
{{"principle": "回退后的原理问题", "sub_questions": ["子问题1", "子问题2", ...]}}"""

_DEHYDRATE_PROMPT = """你是一个查询优化器。你的任务是清理用户问题，使其更适合搜索引擎检索。

规则：
1. 消歧：将"他"、"它"、"那个"、"这个"等代词替换为具体的实体名词（需要参考对话历史）
2. 脱水：去掉"请问"、"帮我看看"、"能不能"等礼貌用语和口语化表达
3. 保留核心问题意图，不要添加额外信息

对话历史：{history}
用户原始问题：{question}

请只返回处理后的干净查询句子，不要加任何解释。"""


# ── API ──────────────────────────────────────────────────

async def decompose_question(question: str) -> list[str]:
    """Decompose complex/compound questions into sub-questions.

    - Compound questions (multiple ？): simple split by ？
    - Complex single questions: LLM-based step_back decomposition
    """
    # Detect compound: split by ？/?, keep parts with ≥2 chars
    parts = []
    for p in question.replace("?", "？").split("？"):
        p = p.strip()
        if p and len(p) >= 2:
            parts.append(p + "？")

    if len(parts) >= 2:
        return parts

    # Fall back to LLM-based decomposition
    return await step_back_decompose(question)


async def hyde_generate(question: str) -> str:
    """Generate a hypothetical answer for the question."""
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            f"{OLLAMA_BASE_URL}/api/generate",
            json={
                "model": LOCAL_LLM_MODEL,
                "prompt": _HYDE_PROMPT.format(question=question),
                "stream": False,
                "options": {"temperature": 0.7, "num_predict": 400},
            },
        )
        resp.raise_for_status()
        return resp.json()["response"].strip()


async def step_back_decompose(question: str) -> list[str]:
    """Decompose a complex question into atomic sub-questions.

    Returns both the principle question and sub-questions merged.
    """
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            f"{OLLAMA_BASE_URL}/api/generate",
            json={
                "model": LOCAL_LLM_MODEL,
                "prompt": _STEP_BACK_PROMPT.format(question=question),
                "stream": False,
                "options": {"temperature": 0.3, "num_predict": 500},
            },
        )
        resp.raise_for_status()
        raw = resp.json()["response"].strip()

    try:
        if "```" in raw:
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        data = json.loads(raw)
        queries = [data.get("principle", "")]
        queries.extend(data.get("sub_questions", []))
        return [q for q in queries if q]
    except (json.JSONDecodeError, KeyError):
        return [question]


async def dehydrate(question: str, history: list[str] | None = None) -> str:
    """Remove ambiguity and filler from a query."""
    history_str = "\n".join(history[-6:]) if history else "无历史"
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{OLLAMA_BASE_URL}/api/generate",
            json={
                "model": LOCAL_LLM_MODEL,
                "prompt": _DEHYDRATE_PROMPT.format(history=history_str, question=question),
                "stream": False,
                "options": {"temperature": 0.2, "num_predict": 200},
            },
        )
        resp.raise_for_status()
        return resp.json()["response"].strip()
