"""TD6 — Evaluation of search engine quality and performance.

Implements the evaluation protocol from TD6:
* Precision and Recall per query against a ground-truth relevance set.
* Average response time measured over N executions.

Usage::

    evaluator = Evaluator(engine, Path("data/ground_truth.json"))
    results = evaluator.run()
    evaluator.print_report(results)
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path

from .engine import SearchEngine

logger = logging.getLogger(__name__)

_DEFAULT_RUNS = 100  # number of executions for timing measurement


@dataclass
class QueryEvalResult:
    """Evaluation metrics for one query.

    Attributes:
        query:            the natural language query string.
        retrieved_ids:    doc_ids returned by the engine.
        relevant_ids:     doc_ids from the ground truth.
        precision:        |retrieved ∩ relevant| / |retrieved|.
        recall:           |retrieved ∩ relevant| / |relevant|.
        f1:               harmonic mean of precision and recall.
        avg_response_ms:  average response time over ``_DEFAULT_RUNS`` executions.
    """

    query: str
    retrieved_ids: list[int]
    relevant_ids: list[int]
    precision: float
    recall: float
    f1: float
    avg_response_ms: float
    tp: int = field(default=0, repr=False)
    fp: int = field(default=0, repr=False)
    fn: int = field(default=0, repr=False)


@dataclass
class EvaluationReport:
    """Aggregated evaluation report over all queries.

    Attributes:
        results:         per-query evaluation results.
        macro_precision: mean precision across all queries.
        macro_recall:    mean recall across all queries.
        macro_f1:        mean F1 across all queries.
        avg_response_ms: mean response time across all queries.
    """

    results: list[QueryEvalResult]
    macro_precision: float
    macro_recall: float
    macro_f1: float
    avg_response_ms: float


class Evaluator:
    """Runs the TD6 evaluation protocol on a :class:`~.engine.SearchEngine`.

    Args:
        engine:           initialised search engine to evaluate.
        ground_truth_path: path to ``ground_truth.json`` containing
                           ``[{"query": str, "relevant": [int, ...]}]``.
        n_timing_runs:    number of executions per query for timing.
    """

    def __init__(
        self,
        engine: SearchEngine,
        ground_truth_path: Path,
        n_timing_runs: int = _DEFAULT_RUNS,
    ) -> None:
        self._engine = engine
        self._n_runs = n_timing_runs
        self._ground_truth: list[dict[str, object]] = self._load(ground_truth_path)

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def run(self) -> EvaluationReport:
        """Execute all ground-truth queries and return an :class:`EvaluationReport`."""
        results: list[QueryEvalResult] = []
        for entry in self._ground_truth:
            query = str(entry["query"])
            raw_relevant = entry["relevant"]
            assert isinstance(raw_relevant, list)
            relevant = [int(d) for d in raw_relevant]
            result = self._evaluate_query(query, relevant)
            results.append(result)
            logger.info(
                "Evaluated [%s…]: P=%.3f R=%.3f t=%.1fms",
                query[:40],
                result.precision,
                result.recall,
                result.avg_response_ms,
            )

        macro_p = _mean([r.precision for r in results])
        macro_r = _mean([r.recall for r in results])
        macro_f1 = _mean([r.f1 for r in results])
        avg_t = _mean([r.avg_response_ms for r in results])

        return EvaluationReport(
            results=results,
            macro_precision=macro_p,
            macro_recall=macro_r,
            macro_f1=macro_f1,
            avg_response_ms=avg_t,
        )

    @staticmethod
    def print_report(report: EvaluationReport) -> None:
        """Print a formatted evaluation report to stdout."""
        header = f"{'#':<3} {'Requête':<45} {'P':>6} {'R':>6} {'F1':>6} {'ms':>7}"
        print("=" * len(header))
        print("TD6 — Évaluation du moteur de recherche")
        print("=" * len(header))
        print(header)
        print("-" * len(header))
        for i, r in enumerate(report.results, start=1):
            truncated = r.query[:42] + ("…" if len(r.query) > 42 else "")
            print(
                f"{i:<3} {truncated:<45} "
                f"{r.precision:>6.3f} {r.recall:>6.3f} {r.f1:>6.3f} "
                f"{r.avg_response_ms:>7.2f}"
            )
        print("-" * len(header))
        print(
            f"{'Macro-average':<49}"
            f"{report.macro_precision:>6.3f} {report.macro_recall:>6.3f} "
            f"{report.macro_f1:>6.3f} {report.avg_response_ms:>7.2f}"
        )
        print("=" * len(header))
        print(
            f"\nTemps de réponse moyen (sur {_DEFAULT_RUNS} exécutions) : "
            f"{report.avg_response_ms:.2f} ms"
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _evaluate_query(self, query: str, relevant_ids: list[int]) -> QueryEvalResult:
        # ── Timing: run N times, keep mean ───────────────────────────────
        total_ms = 0.0
        results = []
        for _i in range(self._n_runs):
            t0 = time.perf_counter()
            results = self._engine.search(query)
            total_ms += (time.perf_counter() - t0) * 1000.0
        avg_ms = total_ms / self._n_runs

        retrieved = [r.doc_id for r in results]
        retrieved_set = set(retrieved)
        relevant_set = set(relevant_ids)

        tp = len(retrieved_set & relevant_set)
        fp = len(retrieved_set - relevant_set)
        fn = len(relevant_set - retrieved_set)

        precision = tp / len(retrieved_set) if retrieved_set else 0.0
        recall = tp / len(relevant_set) if relevant_set else 0.0
        f1 = (
            2 * precision * recall / (precision + recall)
            if (precision + recall) > 0
            else 0.0
        )

        return QueryEvalResult(
            query=query,
            retrieved_ids=retrieved,
            relevant_ids=relevant_ids,
            precision=precision,
            recall=recall,
            f1=f1,
            avg_response_ms=avg_ms,
            tp=tp,
            fp=fp,
            fn=fn,
        )

    @staticmethod
    def _load(path: Path) -> list[dict[str, object]]:
        with open(path, encoding="utf-8") as f:
            data: object = json.load(f)
        if not isinstance(data, list):
            raise ValueError(
                f"ground_truth.json must be a JSON array, got {type(data)}"
            )
        assert isinstance(data, list)
        return data


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0
