"""Index file loading utilities.

Two index formats produced by TD3:

* **Text index** (titre, texte, titre_texte): ``token\\tdoc_id:score ...``
  Scores are floats (TF-IDF weighted, titre×2 + texte×1 for the combined index).

* **Set index** (rubrique, date, auteur, bulletin): ``key\\tdoc_id doc_id ...``
  No scores — just a set of document identifiers per key.
"""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def load_text_index(path: Path) -> dict[str, dict[int, float]]:
    """Load a text index TSV into a token → {doc_id: score} mapping."""
    index: dict[str, dict[int, float]] = {}
    with open(path, encoding="utf-8") as f:
        for lineno, raw in enumerate(f, start=1):
            line = raw.rstrip("\n")
            if not line:
                continue
            parts = line.split("\t", 1)
            if len(parts) != 2:
                logger.warning("load_text_index: malformed line %d in %s", lineno, path)
                continue
            token, postings_str = parts
            postings: dict[int, float] = {}
            for entry in postings_str.split():
                try:
                    doc_str, score_str = entry.split(":", 1)
                    postings[int(doc_str)] = float(score_str)
                except ValueError:
                    logger.warning(
                        "load_text_index: bad posting %r at line %d", entry, lineno
                    )
            index[token] = postings
    logger.info("load_text_index: %d tokens from %s", len(index), path.name)
    return index


def load_set_index(path: Path) -> dict[str, set[int]]:
    """Load a set index TSV into a key → set[doc_id] mapping."""
    index: dict[str, set[int]] = {}
    with open(path, encoding="utf-8") as f:
        for lineno, raw in enumerate(f, start=1):
            line = raw.rstrip("\n")
            if not line:
                continue
            parts = line.split("\t", 1)
            if len(parts) != 2:
                logger.warning("load_set_index: malformed line %d in %s", lineno, path)
                continue
            key, docs_str = parts
            doc_ids: set[int] = set()
            for d in docs_str.split():
                try:
                    doc_ids.add(int(d))
                except ValueError:
                    logger.warning(
                        "load_set_index: bad doc_id %r at line %d", d, lineno
                    )
            index[key] = doc_ids
    logger.info("load_set_index: %d keys from %s", len(index), path.name)
    return index
