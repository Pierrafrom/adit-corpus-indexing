"""Full pipeline: TD1 → TD2 → TD3 (HTML to inverted indexes end-to-end)."""

import logging
from pathlib import Path

from .td1_pipeline import run as run_td1
from .td2_pipeline import run as run_td2
from .td3_pipeline import run as run_td3

logger = logging.getLogger(__name__)


def run(
    bulletins_dir: Path = Path("data/BULLETINS"),
    output_dir: Path = Path("outputs"),
) -> None:
    """Run TD1, TD2, and TD3 end-to-end.

    Steps:
        1. TD1 — parse HTML bulletins → ``corpus.xml``
        2. TD2 — TF-IDF + anti-dictionary → ``corpus_filtered.xml``
        3. TD3 — lemmatisation + indexation → ``corpus_final.xml`` + ``indexes/``

    Args:
        bulletins_dir: directory containing the raw ADIT ``.htm`` files.
        output_dir:    directory where all generated files are written.
    """
    corpus_path = output_dir / "td1/corpus.xml"
    filtered_path = output_dir / "td2/corpus_filtered.xml"

    logger.info("=== TD1 — HTML parsing ===")
    run_td1(bulletins_dir=bulletins_dir, output_path=corpus_path)

    logger.info("=== TD2 — TF-IDF & anti-dictionary ===")
    run_td2(corpus_path=corpus_path, output_dir=output_dir / "td2")

    logger.info("=== TD3 — Lemmatisation & indexation ===")
    run_td3(filtered_corpus_path=filtered_path, output_dir=output_dir / "td3")

    final = output_dir / "td3/corpus_final.xml"
    indexes = output_dir / "td3/indexes"
    logger.info(
        "Full pipeline complete — final corpus: %s, indexes: %s", final, indexes
    )


def main() -> None:
    """Entry point for the ``adit-pipeline`` console script."""
    logging.basicConfig(
        level=logging.INFO, format="%(levelname)s %(name)s: %(message)s"
    )
    run()


if __name__ == "__main__":
    main()
