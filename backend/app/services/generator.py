"""LLM Generator — DeepSeek API for final answer generation."""

from __future__ import annotations

from openai import AsyncOpenAI

from ..config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL

_client = AsyncOpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)

_SYSTEM_PROMPT = """你是一个专业的RAG知识问答助手。请根据提供的文档片段回答用户问题。

重要规则：
1. 只根据文档内容回答，不要编造信息
2. 如果文档中没有相关信息，请诚实地说"文档中未找到相关信息"
3. 回答时引用具体的文档来源，用 [来源: 文档名, 章节] 的格式标注
4. 回答要简洁、准确、有条理
5. 如果文档内容是中文，请用中文回答"""


async def generate_answer(
    question: str,
    contexts: list[dict],
    history: list[dict] | None = None,
    stream: bool = False,
):
    """Generate answer using DeepSeek with retrieved contexts.

    Args:
        question: User's question
        contexts: Retrieved chunks (with chunk_text, doc_name, header_path)
        history: Previous messages in the conversation
        stream: If True, return an async generator of token strings

    Returns:
        If stream=False: full answer string
        If stream=True: async generator yielding tokens
    """
    # Build context string with source annotations
    context_parts = []
    for i, ctx in enumerate(contexts, 1):
        src = f"[来源{i}] {ctx.get('doc_name', '未知文档')}"
        header = ctx.get("header_path", "")
        if header:
            src += f" > {header}"
        context_parts.append(f"{src}\n{ctx.get('chunk_text', '')}")

    context_str = "\n\n---\n\n".join(context_parts)

    # Build messages
    messages = [{"role": "system", "content": _SYSTEM_PROMPT}]

    # Add conversation history (last 10 messages)
    if history:
        for msg in history[-10:]:
            messages.append({"role": msg.get("role", "user"), "content": msg.get("content", "")})

    # Add current question with context
    messages.append({
        "role": "user",
        "content": f"文档片段：\n{context_str}\n\n用户问题：{question}\n\n请根据上述文档片段回答用户问题。",
    })

    if stream:
        async def _stream():
            response = await _client.chat.completions.create(
                model=DEEPSEEK_MODEL,
                messages=messages,
                temperature=0.3,
                max_tokens=2048,
                stream=True,
            )
            async for chunk in response:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content

        return _stream()

    else:
        response = await _client.chat.completions.create(
            model=DEEPSEEK_MODEL,
            messages=messages,
            temperature=0.3,
            max_tokens=2048,
        )
        return response.choices[0].message.content
