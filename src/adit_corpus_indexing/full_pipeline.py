"""Full pipeline: TD1 (HTML → corpus.xml) then TD2 (TF-IDF → corpus_filtered.xml)."""

import logging
from pathlib import Path

from .td1_pipeline import run as run_td1
from .td2_pipeline import run as run_td2

logger = logging.getLogger(__name__)


def run(
    bulletins_dir: Path = Path("data/BULLETINS"),
    output_dir: Path = Path("outputs"),
) -> None:
    """Run TD1 then TD2 end-to-end.

    Args:
        bulletins_dir: directory containing the raw ADIT .htm files.
        output_dir:    directory where all generated files are written.
    """
    corpus_path = output_dir / "corpus.xml"

    logger.info("=== TD1 — HTML parsing ===")
    run_td1(bulletins_dir=bulletins_dir, output_path=corpus_path)

    logger.info("=== TD2 — TF-IDF & anti-dictionary ===")
    run_td2(corpus_path=corpus_path, output_dir=output_dir)

    filtered = output_dir / "corpus_filtered.xml"
    logger.info("Full pipeline complete — final corpus: %s", filtered)


def main() -> None:
    """Entry point for the ``adit-pipeline`` console script."""
    logging.basicConfig(
        level=logging.INFO, format="%(levelname)s %(name)s: %(message)s"
    )
    run()


if __name__ == "__main__":
    main()
