"""Pipeline: parse all ADIT HTML bulletins and produce corpus.xml."""

import logging
import os
from collections import defaultdict
from pathlib import Path

from .parser import parse_article
from .xml_builder import CorpusBuilder

logger = logging.getLogger(__name__)

_FIELDS = ("code", "bulletin", "date", "rubrique", "title", "author", "body")


def _field_present(article: object, field: str) -> bool:
    """Return True if the field has a non-empty value."""
    value = getattr(article, field, None)
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    return True


def run(
    bulletins_dir: Path = Path("data"),
    output_path: Path = Path("outputs/corpus.xml"),
) -> None:
    """Parse all .htm files in *bulletins_dir* and write corpus.xml to *output_path*."""
    htm_files = sorted(bulletins_dir.glob("*.htm"))
    sample = int(os.environ.get("SAMPLE_SIZE", "0"))
    if sample > 0:
        htm_files = htm_files[:sample]
        logger.info("Sample mode: processing %d files", sample)
    if not htm_files:
        logger.error("No .htm files found in %s", bulletins_dir)
        return

    logger.info("Found %d bulletin files", len(htm_files))

    builder = CorpusBuilder()
    seen: set[tuple[str, str]] = set()
    stats: dict[str, int] = defaultdict(int)
    total = 0
    duplicates = 0

    for path in htm_files:
        try:
            article = parse_article(path)
        except Exception:
            logger.exception("Failed to parse %s", path)
            continue

        key = (article.bulletin, article.code)
        if key in seen:
            logger.warning(
                "Duplicate article skipped: %s in %s", article.code, path.name
            )
            duplicates += 1
            continue
        seen.add(key)

        builder.add_article(article)
        total += 1

        for field in _FIELDS:
            if _field_present(article, field):
                stats[field] += 1

    builder.write(output_path)

    # Validation report
    sep = "=" * 50
    header = f"{'Field':<12} {'Present':>8} {'Missing':>8} {'Coverage':>10}"
    logger.info(sep)
    logger.info(
        "Corpus report — %d articles written (%d duplicates skipped)", total, duplicates
    )
    logger.info(sep)
    logger.info(header)
    logger.info("-" * len(header))
    for field in _FIELDS:
        present = stats[field]
        missing = total - present
        pct = (present / total * 100) if total else 0.0
        logger.info("%-12s %8d %8d %9.1f%%", field, present, missing, pct)
    logger.info(sep)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO, format="%(levelname)s %(name)s: %(message)s"
    )
    run()
