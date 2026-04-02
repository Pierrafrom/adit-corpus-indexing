"""TD4 — Interactive spell-checker pipeline.

Workflow
--------
1. Load a lexicon (mini test fixture or full corpus lemma TSV).
2. Instantiate a :class:`SpellChecker` with configurable hyperparameters.
3. Accept queries from stdin in a REPL loop.
4. For each query, tokenize → lemmatize → correct each term → display results.

Two lexicon modes
-----------------
``--mini``  (default when no path is given)
    Loads ``tests/fixtures/mini_lexicon.tsv`` — a hand-crafted ~25-word
    vocabulary for rapid algorithm validation.

``--lexicon <path>``
    Loads a full ``word<TAB>lemma`` TSV (e.g. ``outputs/td3/lemmes_spacy.tsv``
    produced by the TD3 pipeline) for production use.

``--index <path>``
    Loads an inverted-index file (first column = term) when no lemma mapping
    is available.  The lemma is set to the term itself.

Hyperparameters (with sensible defaults)
-----------------------------------------
``--seuil-min``      minimum word length to attempt prefix search (default 3).
``--seuil-max``      maximum prefix length compared (default 6).
``--seuil-proximite`` minimum shared prefix length for candidacy (default 3).

Usage
-----
::

    uv run td4                                       # mini lexicon, default params
    uv run td4 --lexicon outputs/td3/lemmes_spacy.tsv
    uv run td4 --index outputs/td3/indexes/index_texte.tsv --seuil-proximite 4
    uv run td4 --help
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from ..models import CorrectionResult
from ..nlp.spell_checker import Lexicon, SpellChecker

logger = logging.getLogger(__name__)

# Default mini lexicon relative to this file (works when installed via `uv`).
_MINI_LEXICON = (
    Path(__file__).parent.parent.parent.parent  # project root
    / "tests"
    / "fixtures"
    / "mini_lexicon.tsv"
)

# Status symbols for compact display
_STATUS_ICON: dict[str, str] = {
    "entity":           "🔢",
    "exact":            "✓",
    "single_candidate": "→",
    "best_candidate":   "~",
    "not_found":        "✗",
}

_STATUS_LABEL: dict[str, str] = {
    "entity":           "entité conservée",
    "exact":            "trouvé dans le lexique",
    "single_candidate": "candidat unique (préfixe)",
    "best_candidate":   "meilleur candidat (Levenshtein)",
    "not_found":        "introuvable",
}


# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------


def _format_result(result: CorrectionResult) -> str:
    """Format a single CorrectionResult for terminal display."""
    icon = _STATUS_ICON.get(result.status, "?")
    label = _STATUS_LABEL.get(result.status, result.status)

    if result.status == "entity":
        return f"  {icon} {result.original!r:25s}  [{label}]"

    if result.status == "exact":
        lemma_info = (
            f" (lemme: {result.lemma})" if result.lemma != result.corrected else ""
        )
        return f"  {icon} {result.original!r:25s}  [{label}]{lemma_info}"

    if result.status in ("single_candidate", "best_candidate"):
        dist_info = (
            f", distance={result.distance}" if result.distance is not None else ""
        )
        candidates_info = (
            f", candidats: {result.candidates}" if len(result.candidates) > 1 else ""
        )
        return (
            f"  {icon} {result.original!r:25s}  [{label}]\n"
            f"      → correction: {result.corrected!r}"
            f" (lemme: {result.lemma}){dist_info}{candidates_info}"
        )

    # not_found
    return f"  {icon} {result.original!r:25s}  [{label}]"


def _print_query_results(query: str, results: list[CorrectionResult]) -> None:
    """Print the full correction report for one query."""
    sep = "─" * 60
    print(f"\n{sep}")
    print(f"  Requête : {query!r}")
    print(sep)

    if not results:
        print("  (aucun terme extrait)")
        print(sep)
        return

    corrected_terms: list[str] = []
    for r in results:
        print(_format_result(r))
        if r.corrected is not None:
            # Use the lemma for the normalized query; fall back to corrected form.
            corrected_terms.append(r.lemma if r.lemma else r.corrected)

    print(sep)
    if corrected_terms:
        print(f"  Requête normalisée : {' '.join(corrected_terms)}")
    else:
        print("  Requête normalisée : (aucun terme valide)")
    print(sep + "\n")


# ---------------------------------------------------------------------------
# Pipeline entry point
# ---------------------------------------------------------------------------


def run(
    lexicon_path: Path | None = None,
    index_path: Path | None = None,
    seuil_min: int = 3,
    seuil_max: int = 6,
    seuil_proximite: int = 3,
    interactive: bool = True,
) -> SpellChecker:
    """Load lexicon and return a ready-to-use :class:`SpellChecker`.

    When *interactive* is True, enters a REPL loop reading queries from stdin.
    When False, returns the checker without entering the loop (useful for
    programmatic use and testing).

    Args:
        lexicon_path:    path to a ``word<TAB>lemma`` TSV, or None to use mini.
        index_path:      path to an inverted-index TSV (alternative to lexicon).
        seuil_min:       minimum word length for prefix search.
        seuil_max:       maximum prefix length compared.
        seuil_proximite: minimum shared prefix length for candidacy.
        interactive:     if True, run the REPL loop.

    Returns:
        The configured :class:`SpellChecker` instance.
    """
    # --- Load lexicon ---
    if index_path is not None:
        print(f"Chargement du lexique depuis l'index : {index_path}")
        lexicon = Lexicon.from_index(index_path)
    elif lexicon_path is not None:
        print(f"Chargement du lexique : {lexicon_path}")
        lexicon = Lexicon.from_tsv(lexicon_path)
    else:
        print(f"Chargement du lexique de test : {_MINI_LEXICON}")
        lexicon = Lexicon.from_tsv(_MINI_LEXICON)

    print(f"  {len(lexicon)} entrées chargées.")
    print(
        f"  Hyperparamètres : seuilMin={seuil_min}, "
        f"seuilMax={seuil_max}, seuilProximite={seuil_proximite}\n"
    )

    checker = SpellChecker(
        lexicon,
        seuil_min=seuil_min,
        seuil_max=seuil_max,
        seuil_proximite=seuil_proximite,
    )

    if not interactive:
        return checker

    # --- REPL loop ---
    print(
        "Correcteur orthographique prêt. "
        "Tapez une requête (ou 'quitter' pour sortir).\n"
    )
    while True:
        try:
            query = input("Requête > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nAu revoir.")
            break

        if not query:
            continue
        if query.lower() in ("quitter", "quit", "exit", "q"):
            print("Au revoir.")
            break

        results = checker.process_query(query)
        _print_query_results(query, results)

    return checker


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="td4",
        description="TD4 — Correcteur orthographique de requêtes (LO17)",
    )
    source = parser.add_mutually_exclusive_group()
    source.add_argument(
        "--lexicon",
        metavar="PATH",
        type=Path,
        help="Chemin vers un TSV word→lemme (ex: outputs/td3/lemmes_spacy.tsv)",
    )
    source.add_argument(
        "--index",
        metavar="PATH",
        type=Path,
        help="Chemin vers un fichier index inversé (1ère colonne = terme)",
    )
    parser.add_argument(
        "--seuil-min",
        type=int,
        default=3,
        metavar="N",
        help="Longueur minimale du terme pour la recherche par préfixe (défaut: 3)",
    )
    parser.add_argument(
        "--seuil-max",
        type=int,
        default=6,
        metavar="N",
        help="Longueur maximale du préfixe comparé (défaut: 6)",
    )
    parser.add_argument(
        "--seuil-proximite",
        type=int,
        default=3,
        metavar="N",
        help="Longueur minimale du préfixe commun pour être candidat (défaut: 3)",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Activer les logs DEBUG",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    """CLI entry point registered in pyproject.toml as ``td4``."""
    args = _parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,
    )

    run(
        lexicon_path=args.lexicon,
        index_path=args.index,
        seuil_min=args.seuil_min,
        seuil_max=args.seuil_max,
        seuil_proximite=args.seuil_proximite,
        interactive=True,
    )


if __name__ == "__main__":
    main()
