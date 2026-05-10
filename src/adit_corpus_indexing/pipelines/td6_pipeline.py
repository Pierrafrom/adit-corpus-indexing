"""TD6 pipeline — Search engine evaluation.

Loads the inverted indexes and corpus built in TD3, initialises the
:class:`~adit_corpus_indexing.search.engine.SearchEngine`, runs the
10-query ground-truth evaluation, and prints a summary report.

Usage::

    uv run td6                          # full evaluation
    uv run td6 "ma requête en français" # single query demo
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from ..search.engine import SearchEngine
from ..search.evaluator import Evaluator

logger = logging.getLogger(__name__)

_OUTPUTS = Path("outputs/td3")
_INDEXES = _OUTPUTS / "indexes"
_CORPUS = _OUTPUTS / "corpus_final.xml"
_LEXICON = _OUTPUTS / "lemmes_snowball.tsv"
_GROUND_TRUTH = Path("data/ground_truth.json")


def _build_engine() -> SearchEngine:
    return SearchEngine(
        indexes_dir=_INDEXES,
        corpus_path=_CORPUS,
        lexicon_path=_LEXICON,
    )


def _run_single_query(query: str) -> None:
    print(f"\nRequête : {query}")
    print("-" * 60)
    engine = _build_engine()
    pq = engine.parse_query(query)
    print(f"Analyse : {pq}")
    results = engine.search(query)
    if not results:
        print("Aucun résultat trouvé.")
        return
    print(f"{len(results)} résultat(s) :\n")
    for i, r in enumerate(results[:10], start=1):
        header = f"  [{i:2d}] doc={r.doc_id}  score={r.score:.2f}  {r.date}"
        print(f"{header}  [{r.rubrique}]")
        print(f"       Titre   : {r.titre[:80]}")
        print(f"       Extrait : {r.snippet[:120]}")
        print()


def _run_evaluation() -> None:
    engine = _build_engine()

    if not _GROUND_TRUTH.exists():
        logger.error("Ground truth not found at %s", _GROUND_TRUTH)
        sys.exit(1)

    evaluator = Evaluator(engine, _GROUND_TRUTH)
    report = evaluator.run()
    Evaluator.print_report(report)


def main() -> None:
    """Entry point for ``uv run td6``."""
    logging.basicConfig(
        level=logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )

    if len(sys.argv) > 1:
        query = " ".join(sys.argv[1:])
        _run_single_query(query)
    else:
        _run_evaluation()
