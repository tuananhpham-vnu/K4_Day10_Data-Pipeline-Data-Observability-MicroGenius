"""Public API for the evaluation package."""

from .metrics import EvaluationBundle, JudgeVerdict, evaluate_pipeline
from .testset import build_test_set

__all__ = [
    "EvaluationBundle",
    "JudgeVerdict",
    "build_test_set",
    "evaluate_pipeline",
]