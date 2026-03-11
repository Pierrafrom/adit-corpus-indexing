"""TD2 — Pipeline: orchestrate tokenization, TF-IDF, anti-dictionary, filtering."""

import logging
from pathlib import Path

from .antidictionary import apply_to_corpus, build_antidictionary
from .tfidf import compute_idf, compute_tf, compute_tfidf
from .tokenizer import segmente

logger = logging.getLogger(__name__)

# Tokens with idf <= IDF_THRESHOLD are treated as stop words.
# Adjust after inspecting the idf.tsv distribution.
IDF_THRESHOLD = 0.5  # TODO: tune this value based on corpus analysis


def run(
    corpus_path: Path = Path("outputs/corpus.xml"),
    output_dir: Path = Path("outputs"),
) -> None:
    """Run the full TD2 pipeline.

    Steps:
        1. segmente         → tokens.tsv
        2. compute_tf       → tf.tsv
        3. compute_idf      → idf.tsv
        4. compute_tfidf    → tfidf.tsv
        5. build_antidictionary → antidictionary.tsv
        6. apply_to_corpus  → corpus_filtered.xml

    Args:
        corpus_path: path to corpus.xml produced by the TD1 pipeline.
        output_dir:  directory where all intermediate and final files are written.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    tokens_path = output_dir / "tokens.tsv"
    tf_path = output_dir / "tf.tsv"
    idf_path = output_dir / "idf.tsv"
    tfidf_path = output_dir / "tfidf.tsv"
    antidico_path = output_dir / "antidictionary.tsv"
    filtered_path = output_dir / "corpus_filtered.xml"

    logger.info("Step 1/6 — segmentation")
    segmente(corpus_path, tokens_path)

    logger.info("Step 2/6 — TF computation")
    compute_tf(tokens_path, tf_path)

    logger.info("Step 3/6 — IDF computation")
    compute_idf(tokens_path, idf_path)

    logger.info("Step 4/6 — TF-IDF computation")
    compute_tfidf(tf_path, idf_path, tfidf_path)

    logger.info("Step 5/6 — building anti-dictionary (threshold=%.3f)", IDF_THRESHOLD)
    build_antidictionary(idf_path, antidico_path, threshold=IDF_THRESHOLD)

    logger.info("Step 6/6 — generating filtered corpus")
    apply_to_corpus(corpus_path, antidico_path, filtered_path)

    logger.info("TD2 pipeline complete — filtered corpus: %s", filtered_path)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO, format="%(levelname)s %(name)s: %(message)s"
    )
    run()
