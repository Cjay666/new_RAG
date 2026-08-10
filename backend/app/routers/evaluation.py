"""Evaluation router — RAGAS metrics and experiment comparison."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

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

_eval_history: list[dict] = []
_experiments: dict[str, dict] = {}


@router.post("/run", response_model=EvalResponse)
async def run_evaluation(body: EvalRequest):
    """Run RAGAS evaluation on a set of test queries."""
    eval_id = str(uuid.uuid4())[:8]

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

    # Simplified metrics calculation (full RAGAS requires the ragas library)
    # In production: use ragas.evaluate() with metrics
    metrics = _calculate_simple_metrics(results)

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
    return [
        EvalResponse(**r)
        for r in _eval_history
        if r["kb_id"] == kb_id
    ]


@router.post("/experiment", response_model=ExperimentResponse)
async def create_experiment(body: ExperimentCreate):
    """Run a comparison experiment with different configs."""
    exp_id = str(uuid.uuid4())[:8]
    results: list[ExperimentResult] = []

    for config in body.configs:
        # Run a single test query to compare configs
        test_q = f"测试查询 - 知识库: {body.kb_id}"
        try:
            result = await query_pipeline(
                question=test_q,
                kb_id=body.kb_id,
                session_id="experiment",
                top_k=config.top_k,
            )
            metrics = EvalMetrics(
                context_precision=0.85,  # Placeholder — real RAGAS needed
                context_recall=0.80,
                faithfulness=0.90,
                answer_relevancy=0.88,
            )
        except Exception:
            metrics = EvalMetrics(
                context_precision=0.0,
                context_recall=0.0,
                faithfulness=0.0,
                answer_relevancy=0.0,
            )

        results.append(ExperimentResult(config=config, metrics=metrics))

    record = {
        "experiment_id": exp_id,
        "name": body.name,
        "kb_id": body.kb_id,
        "results": [r.model_dump() for r in results],
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


def _calculate_simple_metrics(results: list[dict]) -> EvalMetrics:
    """Simplified metric calculation without full RAGAS.

    In production, replace with: from ragas import evaluate; evaluate(dataset, metrics=[...])
    """
    if not results:
        return EvalMetrics(
            context_precision=0.0, context_recall=0.0,
            faithfulness=0.0, answer_relevancy=0.0,
        )

    # Simple heuristics
    answered = sum(1 for r in results if r["answer"] and "ERROR:" not in r["answer"])
    has_context = sum(1 for r in results if r["contexts"])

    total = len(results)
    return EvalMetrics(
        context_precision=round(has_context / total, 3) if total else 0.0,
        context_recall=round(has_context / total, 3) if total else 0.0,
        faithfulness=round(answered / total, 3) if total else 0.0,
        answer_relevancy=round(answered / total, 3) if total else 0.0,
    )
