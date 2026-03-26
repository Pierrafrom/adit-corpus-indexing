"""TD3 — Full pipeline: lemmatisation, anti-dictionary refinement, and indexation.

The pipeline runs in three sections matching the lab instructions:

**Section 1 — Lemmatisation du corpus filtré**

1. ``SpacyLemmatizer``   → ``lemmes_spacy.tsv``
2. ``SnowballLemmatizer``→ ``lemmes_snowball.tsv``
3. Comparative report printed to stdout; best method selected automatically.

**Section 2 — Affinage de l'anti-dictionnaire**

4. Lemmatize corpus tokens  → ``tokens_lemmatized.tsv``
5. TF-IDF on lemmas         → ``tf_lemmatized.tsv``, ``idf_lemmatized.tsv``,
                               ``tfidf_lemmatized.tsv``
6. Refined anti-dictionary  → ``antidictionary_v2.tsv``
7. Apply lemmatisation + filtering → ``corpus_final.xml``

**Section 3 — Création des fichiers inverses**

8. Build per-field inverted indexes → ``outputs/indexes/``

   - ``index_titre.tsv``       — titre (term-frequency)
   - ``index_texte.tsv``       — texte (term-frequency)
   - ``index_titre_texte.tsv`` — titre × 2 + texte × 1 (combined weighted)
   - ``index_rubrique.tsv``    — rubrique (facet)
   - ``index_auteur.tsv``      — auteur (facet)
   - ``index_bulletin.tsv``    — bulletin (facet)
   - ``index_date.tsv``        — date grouped by mm/yyyy (facet)

The input is ``corpus_filtered.xml`` produced by the TD2 pipeline.
The final deliverable is ``corpus_final.xml`` and the ``indexes/`` directory.
"""

import logging
from pathlib import Path

from ..nlp.antidictionary import build_antidictionary
from ..indexing.create_inverse_file import InvertedIndexBuilder
from ..nlp.lemmatizer import (
    LemmatizationComparator,
    SnowballLemmatizer,
    SpacyLemmatizer,
    apply_lemmatization_to_corpus,
    lemmatize_corpus_tokens,
)
from ..indexing.tfidf import compute_idf, compute_tf, compute_tfidf

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Threshold constants
# ---------------------------------------------------------------------------

# Lower IDF cutoff for the *lemmatised* vocabulary:
# lemmas with idf ≤ LEMMA_IDF_THRESHOLD appear in ≥ 10^(−threshold) × N docs
# and are considered stop-lemmas to exclude from the final index.
# After TD2 filtering, the remaining tokens are mostly content words; a
# threshold of 0.5 (≥31 % of docs) is kept for consistency with TD2.
# Inspect ``idf_lemmatized.tsv`` and lower this if too many content lemmas are
# excluded.
LEMMA_IDF_THRESHOLD: float = 0.5

# Upper IDF cutoff — disabled (hapax retention) to maximise recall at this stage.
LEMMA_MAX_IDF_THRESHOLD: float = float("inf")


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------


def run(
    filtered_corpus_path: Path = Path("outputs/td2/corpus_filtered.xml"),
    output_dir: Path = Path("outputs/td3"),
) -> None:
    """Run the complete TD3 pipeline.

    Args:
        filtered_corpus_path: ``corpus_filtered.xml`` produced by the TD2 pipeline.
        output_dir:           directory where all intermediate and final files
                              are written.

    Raises:
        FileNotFoundError: if *filtered_corpus_path* does not exist.
    """
    if not filtered_corpus_path.exists():
        raise FileNotFoundError(
            f"TD3 requires corpus_filtered.xml — not found at {filtered_corpus_path}. "
            "Run the TD2 pipeline first."
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    index_dir = output_dir / "indexes"
    index_dir.mkdir(exist_ok=True)

    # ── Intermediate file paths ──────────────────────────────────────────────
    spacy_tsv = output_dir / "lemmes_spacy.tsv"
    snowball_tsv = output_dir / "lemmes_snowball.tsv"
    tokens_lemmatized = output_dir / "tokens_lemmatized.tsv"
    tf_lemmatized = output_dir / "tf_lemmatized.tsv"
    idf_lemmatized = output_dir / "idf_lemmatized.tsv"
    tfidf_lemmatized = output_dir / "tfidf_lemmatized.tsv"
    antidico_v2 = output_dir / "antidictionary_v2.tsv"
    corpus_final = output_dir / "corpus_final.xml"

    # ════════════════════════════════════════════════════════════════════════
    # Section 1 — Lemmatisation
    # ════════════════════════════════════════════════════════════════════════

    logger.info("Step 1/8 — SpaCy lemmatisation")
    SpacyLemmatizer().extract_from_corpus(filtered_corpus_path, spacy_tsv)

    logger.info("Step 2/8 — Snowball stemming")
    SnowballLemmatizer().extract_from_corpus(filtered_corpus_path, snowball_tsv)

    logger.info("Step 3/8 — Comparative analysis")
    comparator = LemmatizationComparator(spacy_tsv, snowball_tsv)
    comparator.print_report()
    best_method = comparator.best_method()
    best_tsv = spacy_tsv if best_method == "spacy" else snowball_tsv
    logger.info("Best method: '%s' → using %s", best_method, best_tsv.name)

    # ════════════════════════════════════════════════════════════════════════
    # Section 2 — Anti-dictionary refinement
    # ════════════════════════════════════════════════════════════════════════

    logger.info("Step 4/8 — Lemmatise corpus tokens")
    lemmatize_corpus_tokens(filtered_corpus_path, best_tsv, tokens_lemmatized)

    logger.info("Step 5/8 — TF-IDF on lemmatised tokens")
    compute_tf(tokens_lemmatized, tf_lemmatized)
    compute_idf(tokens_lemmatized, idf_lemmatized)
    compute_tfidf(tf_lemmatized, idf_lemmatized, tfidf_lemmatized)

    logger.info(
        "Step 6/8 — Refined anti-dictionary on lemmas (low=%.3f, high=%s)",
        LEMMA_IDF_THRESHOLD,
        f"{LEMMA_MAX_IDF_THRESHOLD:.3f}"
        if LEMMA_MAX_IDF_THRESHOLD != float("inf")
        else "∞",
    )
    build_antidictionary(
        idf_lemmatized,
        antidico_v2,
        threshold=LEMMA_IDF_THRESHOLD,
        max_threshold=LEMMA_MAX_IDF_THRESHOLD,
    )

    logger.info("Step 7/8 — Apply lemmatisation + second filter → corpus_final.xml")
    apply_lemmatization_to_corpus(
        filtered_corpus_path, best_tsv, antidico_v2, corpus_final
    )

    # ════════════════════════════════════════════════════════════════════════
    # Section 3 — Inverted indexes
    # ════════════════════════════════════════════════════════════════════════

    logger.info("Step 8/8 — Building inverted indexes from %s", corpus_final)
    builder = InvertedIndexBuilder(corpus_final)

    # Text indexes
    n_titre = builder.build_text_index("titre", index_dir / "index_titre.tsv")
    n_texte = builder.build_text_index("texte", index_dir / "index_texte.tsv")

    # Combined weighted index: titre × 2 + texte × 1
    builder.build_combined_index(
        ["titre", "texte"],
        index_dir / "index_titre_texte.tsv",
        weights={"titre": 2.0, "texte": 1.0},
    )

    # Facet indexes
    builder.build_facet_index("rubrique", index_dir / "index_rubrique.tsv")
    builder.build_facet_index("auteur", index_dir / "index_auteur.tsv")
    builder.build_facet_index("bulletin", index_dir / "index_bulletin.tsv")

    # Date facet
    builder.build_date_index(index_dir / "index_date.tsv")

    logger.info(
        "TD3 pipeline complete — %d titre terms, %d texte terms — indexes in %s",
        n_titre,
        n_texte,
        index_dir,
    )


# ---------------------------------------------------------------------------
# Entry points
# ---------------------------------------------------------------------------


def main() -> None:
    """Entry point for the ``td3`` console script."""
    logging.basicConfig(
        level=logging.INFO, format="%(levelname)s %(name)s: %(message)s"
    )
    run()


if __name__ == "__main__":
    main()
