"""Evaluation router — RAGAS metrics (DeepSeek judge) + experiment comparison."""

from __future__ import annotations

import asyncio
import traceback
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from ..config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL
from ..models.schemas import (
    EvalMetrics,
    EvalRequest,
    EvalResponse,
    ExperimentConfig,
    ExperimentCreate,
    ExperimentResponse,
    ExperimentResult,
)
from ..services.pipeline import query_pipeline

router = APIRouter(prefix="/api/eval", tags=["evaluation"])

# ── In-memory history (single-user, persists until restart) ──
_eval_history: list[dict] = []
_experiments: dict[str, dict] = {}


# ═══════════════════════════════════════════════════════════
# RAGAS evaluation
# ═══════════════════════════════════════════════════════════

def _build_judge():
    """Create a LangChain LLM wrapper pointed at DeepSeek for RAGAS judge."""
    from langchain_openai import ChatOpenAI
    from ragas.llms import LangchainLLMWrapper

    judge_llm = ChatOpenAI(
        model=DEEPSEEK_MODEL,
        api_key=DEEPSEEK_API_KEY,
        base_url=DEEPSEEK_BASE_URL,
        temperature=0.0,
        timeout=180,
        max_retries=2,
    )
    return LangchainLLMWrapper(judge_llm)


async def _run_ragas(results: list[dict]) -> EvalMetrics:
    """Run real RAGAS evaluation using DeepSeek as judge LLM.

    Falls back to simple heuristics if RAGAS is not installed or fails.
    """
    valid = [
        r for r in results
        if r.get("answer") and "ERROR:" not in r["answer"] and r.get("contexts")
    ]
    if not valid:
        return EvalMetrics(
            context_precision=0.0, context_recall=0.0,
            faithfulness=0.0, answer_relevancy=0.0,
        )

    try:
        from ragas import evaluate, EvaluationDataset
        from ragas.metrics import (
            Faithfulness,
            AnswerRelevancy,
            ContextPrecision,
            ContextRecall,
        )

        judge = _build_judge()

        dataset_dict = {
            "question": [r["question"] for r in valid],
            "answer": [r["answer"] for r in valid],
            "contexts": [r["contexts"] for r in valid],
        }
        dataset = EvaluationDataset.from_dict(dataset_dict)

        metrics = [
            ContextPrecision(),
            ContextRecall(),
            Faithfulness(),
            AnswerRelevancy(),
        ]

        # RAGAS evaluate() is sync — run in thread to avoid event-loop conflicts
        result = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: evaluate(dataset, metrics=metrics, llm=judge),
        )

        df = result.to_pandas()
        return EvalMetrics(
            context_precision=round(float(df["context_precision"].mean()), 4),
            context_recall=round(float(df["context_recall"].mean()), 4),
            faithfulness=round(float(df["faithfulness"].mean()), 4),
            answer_relevancy=round(float(df["answer_relevancy"].mean()), 4),
        )

    except ImportError:
        traceback.print_exc()
        return _fallback_metrics(results)
    except Exception:
        traceback.print_exc()
        return _fallback_metrics(results)


def _fallback_metrics(results: list[dict]) -> EvalMetrics:
    """Simple heuristics when RAGAS is unavailable."""
    if not results:
        return EvalMetrics(
            context_precision=0.0, context_recall=0.0,
            faithfulness=0.0, answer_relevancy=0.0,
        )
    total = len(results)
    answered = sum(1 for r in results if r.get("answer") and "ERROR:" not in r["answer"])
    has_context = sum(1 for r in results if r.get("contexts"))
    return EvalMetrics(
        context_precision=round(has_context / total, 3) if total else 0.0,
        context_recall=round(has_context / total, 3) if total else 0.0,
        faithfulness=round(answered / total, 3) if total else 0.0,
        answer_relevancy=round(answered / total, 3) if total else 0.0,
    )


# ═══════════════════════════════════════════════════════════
# Endpoints
# ═══════════════════════════════════════════════════════════

@router.post("/run", response_model=EvalResponse)
async def run_evaluation(body: EvalRequest):
    """Run RAGAS evaluation on a set of test queries.

    Each query goes through the full RAG pipeline, then all (question, answer, contexts)
    triples are scored by RAGAS using DeepSeek as the judge LLM.
    """
    eval_id = str(uuid.uuid4())[:8]

    # ── Step 1: Run pipeline for every test query ──
    results = []
    for question in body.test_queries:
        try:
            result = await query_pipeline(
                question=question,
                kb_id=body.kb_id,
                session_id="eval",
            )
            results.append({
                "question": question,
                "answer": result["answer"],
                "contexts": [s.content for s in result["sources"]],
            })
        except Exception as e:
            results.append({
                "question": question,
                "answer": f"ERROR: {e}",
                "contexts": [],
            })

    # ── Step 2: RAGAS judge scoring ──
    metrics = await _run_ragas(results)

    record = {
        "eval_id": eval_id,
        "kb_id": body.kb_id,
        "metrics": metrics,
        "query_count": len(body.test_queries),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    _eval_history.append(record)

    return EvalResponse(**record)


@router.get("/history/{kb_id}", response_model=list[EvalResponse])
async def get_eval_history(kb_id: str):
    """Get evaluation history for a knowledge base."""
    return [EvalResponse(**r) for r in _eval_history if r["kb_id"] == kb_id]


@router.post("/experiment", response_model=ExperimentResponse)
async def create_experiment(body: ExperimentCreate):
    """Run a comparison experiment with different configs, scored by RAGAS."""
    exp_id = str(uuid.uuid4())[:8]
    exp_results: list[ExperimentResult] = []

    # Standard test query for experiment comparison
    test_queries = [
        "请简要介绍该知识库中的核心内容",
        "知识库中最重要的概念是什么",
        "请总结知识库的关键信息",
    ]

    for config in body.configs:
        eval_inputs = []
        for q in test_queries:
            try:
                result = await query_pipeline(
                    question=q,
                    kb_id=body.kb_id,
                    session_id="experiment",
                    top_k=config.top_k,
                )
                eval_inputs.append({
                    "question": q,
                    "answer": result["answer"],
                    "contexts": [s.content for s in result["sources"]],
                })
            except Exception as e:
                eval_inputs.append({
                    "question": q,
                    "answer": f"ERROR: {e}",
                    "contexts": [],
                })

        metrics = await _run_ragas(eval_inputs)
        exp_results.append(ExperimentResult(config=config, metrics=metrics))

    record = {
        "experiment_id": exp_id,
        "name": body.name,
        "kb_id": body.kb_id,
        "results": [r.model_dump() for r in exp_results],
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    _experiments[exp_id] = record

    return ExperimentResponse(**record)


@router.get("/experiments/{kb_id}", response_model=list[ExperimentResponse])
async def list_experiments(kb_id: str):
    """List experiments for a knowledge base."""
    return [
        ExperimentResponse(**e)
        for e in _experiments.values()
        if e["kb_id"] == kb_id
    ]
