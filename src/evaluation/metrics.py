from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from statistics import mean
import os
import sys
import types
from typing import Any, Iterable

from pydantic import BaseModel, Field

from core.config import Settings
from core.utils import normalize_whitespace, read_json, write_json
from retrieval.embeddings import MiniLMEmbeddings
from retrieval.index import LocalEmbeddingIndex
from retrieval.llm import build_llm
from retrieval.qa import answer_question


class JudgeVerdict(BaseModel):
    score: int = Field(ge=1, le=5)
    correct: bool
    reasoning: str


@dataclass(frozen=True)
class EvaluationBundle:
    summary: dict[str, Any]
    answers: list[dict[str, Any]]


def _tokenize(text: Any) -> list[str]:
    if text is None:
        return []
    return normalize_whitespace(str(text)).casefold().split()


def _token_f1(reference: str, prediction: str) -> float:
    """Bag-of-words token F1 that preserves duplicate-token counts."""
    ref_tokens = _tokenize(reference)
    pred_tokens = _tokenize(prediction)
    if not ref_tokens or not pred_tokens:
        return 0.0

    overlap = sum((Counter(ref_tokens) & Counter(pred_tokens)).values())
    if overlap == 0:
        return 0.0
    precision = overlap / len(pred_tokens)
    recall = overlap / len(ref_tokens)
    return 2 * precision * recall / (precision + recall)


def _model_dump(model: BaseModel) -> dict[str, Any]:
    """Support both Pydantic v1 and v2."""
    if hasattr(model, "model_dump"):
        return model.model_dump()  # type: ignore[no-any-return, attr-defined]
    return model.dict()


def _coerce_verdict(value: Any) -> JudgeVerdict:
    if isinstance(value, JudgeVerdict):
        return value
    if hasattr(JudgeVerdict, "model_validate"):
        return JudgeVerdict.model_validate(value)  # type: ignore[attr-defined, no-any-return]
    return JudgeVerdict.parse_obj(value)


def _judge_answer(settings: Settings, question: str, reference: str, prediction: str) -> JudgeVerdict:
    prompt = f"""
Evaluate the model answer against the reference answer.

Question: {question}
Reference answer: {reference}
Model answer: {prediction}

Return:
- score from 1 to 5
- correct = true only when the answer is materially correct
- short reasoning
""".strip()
    try:
        llm = build_llm(settings=settings, temperature=0.0).with_structured_output(JudgeVerdict)
        return _coerce_verdict(llm.invoke(prompt))
    except Exception as exc:
        token_f1 = _token_f1(reference, prediction)
        score = 5 if token_f1 >= 0.95 else 3 if token_f1 >= 0.5 else 1
        return JudgeVerdict(
            score=score,
            correct=score >= 3,
            reasoning=(
                "Fallback heuristic judge used because the LLM evaluator was unavailable "
                f"({type(exc).__name__})."
            ),
        )


def _json_safe(value: Any) -> Any:
    """Convert common metric-library outputs into JSON-serializable values."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    if hasattr(value, "item"):
        try:
            return value.item()
        except (TypeError, ValueError):
            pass
    if hasattr(value, "to_dict"):
        try:
            return _json_safe(value.to_dict())
        except (TypeError, ValueError):
            pass
    return str(value)


def _run_ragas(settings: Settings, answers: list[dict[str, Any]]) -> dict[str, Any]:
    if os.getenv("RUN_RAGAS", "").lower() not in {"1", "true", "yes"}:
        return {"skipped": "Set RUN_RAGAS=1 to enable the slower Ragas pass."}
    if not answers:
        return {"skipped": "No evaluation samples were available for Ragas."}

    try:
        # Keep optional dependencies lazy: importing this module should still
        # work when Ragas/datasets are intentionally not installed.
        from datasets import Dataset

        if "langchain_community.chat_models.vertexai" not in sys.modules:
            shim = types.ModuleType("langchain_community.chat_models.vertexai")
            shim.ChatVertexAI = type("ChatVertexAI", (), {})
            sys.modules["langchain_community.chat_models.vertexai"] = shim

        from ragas import evaluate
        from ragas.metrics import answer_relevancy, context_precision, context_recall, faithfulness

        dataset = Dataset.from_dict(
            {
                "question": [item["question"] for item in answers],
                "answer": [item["answer"] for item in answers],
                "ground_truth": [item["ground_truth"] for item in answers],
                "contexts": [item["retrieved_contexts"] for item in answers],
            }
        )
        result = evaluate(
            dataset,
            metrics=[answer_relevancy, context_precision, context_recall, faithfulness],
            llm=build_llm(settings=settings, temperature=0.0),
            embeddings=MiniLMEmbeddings(settings.embedding_model),
        )
        return _json_safe(dict(result))
    except Exception as exc:  # pragma: no cover - depends on optional integrations
        return {"error": f"Ragas evaluation failed: {exc}"}


def _validate_test_set(test_set: Any) -> list[dict[str, Any]]:
    if not isinstance(test_set, list):
        raise ValueError("The test-set JSON must contain a list of examples.")

    required = {
        "id",
        "question_type",
        "question",
        "ground_truth",
        "ground_truth_doc_ids",
    }
    validated: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    for position, item in enumerate(test_set):
        if not isinstance(item, dict):
            raise ValueError(f"Test-set item at position {position} must be an object.")
        missing = sorted(required - item.keys())
        if missing:
            raise ValueError(
                f"Test-set item at position {position} is missing fields: {', '.join(missing)}."
            )

        item_id = str(item["id"])
        if item_id in seen_ids:
            raise ValueError(f"Duplicate test-set id: {item_id}")
        seen_ids.add(item_id)

        doc_ids = item["ground_truth_doc_ids"]
        if not isinstance(doc_ids, (list, tuple, set)) or not doc_ids:
            raise ValueError(
                f"Test-set item {item_id!r} must have a non-empty ground_truth_doc_ids list."
            )
        validated.append(item)

    return validated


def _retrieval_hit(expected_ids: Iterable[Any], retrieved_ids: Iterable[Any]) -> bool:
    expected = {str(doc_id) for doc_id in expected_ids}
    return any(str(doc_id) in expected for doc_id in retrieved_ids)


def _average(values: Iterable[float]) -> float:
    values_list = list(values)
    return mean(values_list) if values_list else 0.0


def _summary_by_question_type(answers: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for item in answers:
        grouped.setdefault(str(item["question_type"]), []).append(item)

    return {
        question_type: {
            "samples": len(items),
            "retrieval_hit_rate": _average(
                1.0 if item["retrieval_hit"] else 0.0 for item in items
            ),
            "mean_token_f1": _average(item["token_f1"] for item in items),
            "judge_accuracy": _average(
                1.0 if item["judge"]["correct"] else 0.0 for item in items
            ),
            "mean_judge_score": _average(float(item["judge"]["score"]) for item in items),
        }
        for question_type, items in sorted(grouped.items())
    }


def evaluate_pipeline(
    settings: Settings,
    index: LocalEmbeddingIndex,
    test_set_path,
    metrics_output_path,
    answers_output_path,
) -> EvaluationBundle:
    """Run the QA pipeline over a test set and persist aggregate/detail metrics."""
    test_set = _validate_test_set(read_json(test_set_path))
    answers: list[dict[str, Any]] = []

    for item in test_set:
        question = str(item["question"])
        ground_truth = str(item["ground_truth"])
        result = answer_question(question, settings=settings, index=index)

        answer = str(result.answer)
        retrieved_doc_ids = list(result.retrieved_doc_ids or [])
        retrieved_contexts = [str(context) for context in (result.retrieved_contexts or [])]
        judge = _judge_answer(settings, question, ground_truth, answer)

        answers.append(
            {
                "id": str(item["id"]),
                "question_type": str(item["question_type"]),
                "question": question,
                "ground_truth": ground_truth,
                "ground_truth_doc_ids": [str(doc_id) for doc_id in item["ground_truth_doc_ids"]],
                "answer": answer,
                "retrieved_doc_ids": [str(doc_id) for doc_id in retrieved_doc_ids],
                "retrieved_contexts": retrieved_contexts,
                "retrieval_hit": _retrieval_hit(item["ground_truth_doc_ids"], retrieved_doc_ids),
                "token_f1": _token_f1(ground_truth, answer),
                "judge": _model_dump(judge),
            }
        )

    summary: dict[str, Any] = {
        "samples": len(answers),
        "retrieval_hit_rate": _average(
            1.0 if item["retrieval_hit"] else 0.0 for item in answers
        ),
        "mean_token_f1": _average(item["token_f1"] for item in answers),
        "judge_accuracy": _average(
            1.0 if item["judge"]["correct"] else 0.0 for item in answers
        ),
        "mean_judge_score": _average(float(item["judge"]["score"]) for item in answers),
    }
    summary["ragas"] = _run_ragas(settings, answers)

    summary = _json_safe(summary)
    answers = _json_safe(answers)
    bundle = EvaluationBundle(summary=summary, answers=answers)
    write_json(metrics_output_path, summary)
    write_json(answers_output_path, answers)
    return bundle