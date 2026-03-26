"""TD3 — Inverted index construction.

An *inverted index* maps each term (lemma, date, rubrique, …) to the list of
documents in which it appears, along with the frequency of occurrence.

This module exposes :class:`InvertedIndexBuilder`, an object that parses the
lemmatized corpus once at construction and then offers four specialised
build methods:

- :meth:`~InvertedIndexBuilder.build_text_index` — term-frequency index for
  free-text fields (``titre``, ``texte``).
- :meth:`~InvertedIndexBuilder.build_combined_index` — weighted combination of
  multiple text fields.
- :meth:`~InvertedIndexBuilder.build_facet_index` — facet index for categorical
  fields (``rubrique``, ``auteur``, ``bulletin``).
- :meth:`~InvertedIndexBuilder.build_date_index` — facet index for dates,
  grouped by ``mm/yyyy``.

Output format
-------------
Text / combined indexes (one line per term)::

    term<TAB>article_id:freq article_id:freq …

Facet / date indexes (one line per facet value)::

    value<TAB>article_id article_id …

All files are UTF-8 encoded, tab-separated, no header line.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from collections.abc import Iterator
from pathlib import Path

from lxml import etree

from .tokenizer import tokenize as _tokenize

logger = logging.getLogger(__name__)


class InvertedIndexBuilder:
    """Build inverted-index files from a lemmatized corpus XML.

    The corpus is parsed once at construction; all build methods reuse the
    same in-memory element tree.

    Args:
        corpus_path: path to the final lemmatized corpus XML
                     (``corpus_final.xml`` produced by the TD3 pipeline).

    Example::

        builder = InvertedIndexBuilder(Path("outputs/corpus_final.xml"))
        builder.build_text_index("titre", Path("outputs/indexes/index_titre.tsv"))
        builder.build_combined_index(
            ["titre", "texte"],
            Path("outputs/indexes/index_titre_texte.tsv"),
            weights={"titre": 2.0, "texte": 1.0},
        )
        builder.build_facet_index(
            "rubrique", Path("outputs/indexes/index_rubrique.tsv")
        )
        builder.build_date_index(Path("outputs/indexes/index_date.tsv"))
    """

    def __init__(self, corpus_path: Path) -> None:
        tree = etree.parse(str(corpus_path))
        self._root = tree.getroot()
        self._documents = self._root.findall("document")
        logger.info(
            "InvertedIndexBuilder: loaded %d documents from %s",
            len(self._documents),
            corpus_path,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _iter_documents(self) -> Iterator[tuple[str, etree._Element]]:
        """Yield ``(article_id, document_element)`` pairs, skipping invalid docs."""
        for doc in self._documents:
            article = doc.find("article")
            if article is None or not article.text:
                logger.warning(
                    "InvertedIndexBuilder: document without article ID — skipped"
                )
                continue
            yield article.text.strip(), doc

    @staticmethod
    def _write_text_index(index: dict[str, dict[str, int]], path: Path) -> None:
        """Write a term-frequency posting list to *path*."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            for term in sorted(index):
                postings = " ".join(
                    f"{aid}:{freq}" for aid, freq in sorted(index[term].items())
                )
                f.write(f"{term}\t{postings}\n")

    @staticmethod
    def _write_float_index(index: dict[str, dict[str, float]], path: Path) -> None:
        """Write a weighted posting list to *path*."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            for term in sorted(index):
                postings = " ".join(
                    f"{aid}:{score:.2f}" for aid, score in sorted(index[term].items())
                )
                f.write(f"{term}\t{postings}\n")

    @staticmethod
    def _write_facet_index(index: dict[str, list[str]], path: Path) -> None:
        """Write a facet posting list to *path*."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            for key in sorted(index):
                docs = " ".join(index[key])
                f.write(f"{key}\t{docs}\n")

    # ------------------------------------------------------------------
    # Public build methods
    # ------------------------------------------------------------------

    def build_text_index(self, field: str, output_path: Path) -> int:
        """Build a term-frequency inverted index for a text field.

        Tokenizes the content of ``<field>`` in every document and counts
        occurrences per ``article_id``.

        Output line format::

            term<TAB>article_id:freq article_id:freq …

        Args:
            field:       XML tag name (e.g. ``"titre"``, ``"texte"``).
            output_path: path to write the index TSV.

        Returns:
            Number of distinct terms indexed.
        """
        index: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

        for article_id, doc in self._iter_documents():
            el = doc.find(field)
            if el is None or not el.text:
                logger.debug(
                    "build_text_index('%s'): field absent for article %s",
                    field,
                    article_id,
                )
                continue
            for token in _tokenize(el.text):
                index[token][article_id] += 1

        self._write_text_index(index, output_path)
        logger.info(
            "build_text_index('%s'): %d terms, %d docs → %s",
            field,
            len(index),
            len(self._documents),
            output_path,
        )
        return len(index)

    def build_combined_index(
        self,
        fields: list[str],
        output_path: Path,
        weights: dict[str, float] | None = None,
    ) -> int:
        """Build a weighted combined inverted index for multiple fields.

        Each field's token counts are multiplied by its weight before
        accumulation.  This allows boosting precise fields (e.g. ``titre``)
        over broader ones (e.g. ``texte``).

        Output line format::

            term<TAB>article_id:score article_id:score …

        Args:
            fields:      list of XML tag names to combine.
            output_path: path to write the index TSV.
            weights:     ``{field: float}`` weight map.
                         Defaults to 1.0 for every field.

        Returns:
            Number of distinct terms indexed.
        """
        _weights = weights if weights is not None else {f: 1.0 for f in fields}
        index: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))

        for article_id, doc in self._iter_documents():
            for field in fields:
                el = doc.find(field)
                if el is None or not el.text:
                    continue
                w = _weights.get(field, 1.0)
                for token in _tokenize(el.text):
                    index[token][article_id] += w

        self._write_float_index(index, output_path)
        logger.info(
            "build_combined_index(%s, weights=%s): %d terms → %s",
            fields,
            _weights,
            len(index),
            output_path,
        )
        return len(index)

    def build_facet_index(self, field: str, output_path: Path) -> int:
        """Build a facet index for a categorical field.

        The entire field value is used as the facet key (lowercased and
        stripped).  Suitable for fields like ``rubrique``, ``auteur``, and
        ``bulletin``.

        Output line format::

            value<TAB>article_id article_id …

        Args:
            field:       XML tag name (e.g. ``"rubrique"``, ``"auteur"``).
            output_path: path to write the index TSV.

        Returns:
            Number of distinct facet values.
        """
        index: dict[str, list[str]] = defaultdict(list)

        for article_id, doc in self._iter_documents():
            el = doc.find(field)
            if el is None or not el.text:
                logger.debug(
                    "build_facet_index('%s'): field absent for article %s",
                    field,
                    article_id,
                )
                continue
            key = el.text.strip().lower()
            if key:
                index[key].append(article_id)

        self._write_facet_index(index, output_path)
        logger.info(
            "build_facet_index('%s'): %d distinct values → %s",
            field,
            len(index),
            output_path,
        )
        return len(index)

    def build_date_index(self, output_path: Path) -> int:
        """Build a date facet index grouped by ``mm/yyyy``.

        Parses ``<date>`` fields in ``dd/mm/yyyy`` format and indexes articles
        under their ``mm/yyyy`` key.

        Output line format::

            mm/yyyy<TAB>article_id article_id …

        Args:
            output_path: path to write the index TSV.

        Returns:
            Number of distinct ``mm/yyyy`` periods.
        """
        index: dict[str, list[str]] = defaultdict(list)

        for article_id, doc in self._iter_documents():
            date_el = doc.find("date")
            if date_el is None or not date_el.text:
                continue
            date_text = date_el.text.strip()
            parts = date_text.split("/")
            if len(parts) == 3:
                mm_yyyy = f"{parts[1]}/{parts[2]}"
                index[mm_yyyy].append(article_id)
            else:
                logger.warning(
                    "build_date_index: malformed date '%s' for article %s — skipped",
                    date_text,
                    article_id,
                )

        self._write_facet_index(index, output_path)
        logger.info(
            "build_date_index: %d distinct periods → %s",
            len(index),
            output_path,
        )
        return len(index)
