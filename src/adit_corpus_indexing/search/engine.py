"""TD6 — Boolean ranked search engine.

Integrates TD5 query parsing with the TD3 inverted indexes to implement a
complete French-language search engine over the ADIT corpus.

Search model
------------
* **Keywords** are looked up in the combined ``index_titre_texte.tsv`` (or
  ``index_titre.tsv`` when ``zone="titre"``).  The posting scores are TF-IDF
  floats (title field weighted ×2).
* **AND** (default): intersect posting lists, cumulate scores.
* **OR**: union posting lists, cumulate scores.
* **Rubrique / date / image filters** always apply as strict AND constraints
  on top of the keyword results.
* When *no keywords* are given, the filter sets alone form the result set
  (score = 0 for all documents).

Rubrique normalisation
----------------------
The query parser returns canonical names (e.g. "Horizons Enseignement") that
must be mapped to one or more keys present in ``index_rubrique.tsv`` (e.g.
"horizon enseignement", "horizons enseignement", …).  ``_RUBRIQUE_INDEX_KEYS``
drives this mapping.

Usage::

    engine = SearchEngine(
        indexes_dir=Path("outputs/td3/indexes"),
        corpus_path=Path("outputs/td3/corpus_final.xml"),
        lexicon_path=Path("outputs/td3/lemmes_snowball.tsv"),
    )
    results = engine.search("Je voudrais les articles Focus sur les robots")
    for r in results:
        print(r.doc_id, r.score, r.titre)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from ..models import ParsedQuery
from ..nlp.query_parser import QueryParser
from ..nlp.spell_checker import Lexicon, SpellChecker
from .corpus_reader import CorpusReader, DocumentMeta
from .index_loader import load_set_index, load_text_index

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Rubrique canonical name → index keys
# ---------------------------------------------------------------------------

_RUBRIQUE_INDEX_KEYS: dict[str, list[str]] = {
    "Focus": ["focus"],
    "Horizons Enseignement": [
        "horizons enseignement",
        "horizon enseignement",
        "horizons formation enseignement",
        "horizon formation",
    ],
    "Actualités Innovations": [
        "actualités innovations",
        "actualités innovation",
        "actualité innovation",
        "actualité-innovation",
    ],
    "En direct des laboratoires": [
        "en direct des laboratoires",
        "en direct des labos",
    ],
    "Evénement": ["evénement"],
    "A lire": ["a lire"],
}

# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

_SNIPPET_WINDOW = 200


@dataclass
class SearchResult:
    """One document returned by :class:`SearchEngine`.

    Attributes:
        doc_id:   numeric ADIT article identifier.
        score:    cumulative TF-IDF relevance score (higher = more relevant).
        titre:    lemmatized title from ``corpus_final.xml``.
        date:     publication date as ``dd/mm/yyyy``.
        rubrique: section name.
        snippet:  context excerpt (~200 chars) around the first keyword hit.
    """

    doc_id: int
    score: float
    titre: str
    date: str
    rubrique: str
    snippet: str


# ---------------------------------------------------------------------------
# SearchEngine
# ---------------------------------------------------------------------------


class SearchEngine:
    """Boolean ranked search engine over the ADIT inverted indexes.

    Args:
        indexes_dir:  directory containing the ``index_*.tsv`` files from TD3.
        corpus_path:  path to ``corpus_final.xml`` (for snippets and metadata).
        lexicon_path: path to ``lemmes_snowball.tsv`` used by the spell checker
                      to map query terms to their Snowball stems (= index keys).
                      When *None*, keywords are used as-is (no lemmatisation).
    """

    def __init__(
        self,
        indexes_dir: Path,
        corpus_path: Path,
        lexicon_path: Path | None = None,
    ) -> None:
        self._corpus = CorpusReader(corpus_path)

        # Load indexes
        self._main_index = load_text_index(indexes_dir / "index_titre_texte.tsv")
        self._title_index = load_text_index(indexes_dir / "index_titre.tsv")
        self._rubrique_index = load_set_index(indexes_dir / "index_rubrique.tsv")
        self._date_index = load_set_index(indexes_dir / "index_date.tsv")

        # Build query parser (with spell checking if lexicon provided)
        spell_checker = None
        if lexicon_path is not None and lexicon_path.exists():
            lexicon = Lexicon.from_tsv(lexicon_path)
            spell_checker = SpellChecker(lexicon)
            logger.info("SearchEngine: spell checker loaded from %s", lexicon_path.name)
        else:
            logger.info("SearchEngine: no spell checker (raw tokens used)")

        self._parser = QueryParser(spell_checker=spell_checker)
        logger.info("SearchEngine: ready")

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def search(
        self,
        query: str,
        sort_by: str = "relevance",
    ) -> list[SearchResult]:
        """Parse *query* and return ranked documents.

        Args:
            query:   natural language query in French.
            sort_by: ``"relevance"`` (default, descending score),
                     ``"date_asc"`` (oldest first),
                     ``"date_desc"`` (newest first).

        Returns:
            List of :class:`SearchResult` objects, sorted as requested.
        """
        pq = self._parser.parse(query)
        logger.debug("search: parsed=%r", pq)
        return self._execute(pq, sort_by)

    def parse_query(self, query: str) -> ParsedQuery:
        """Return the structured :class:`~adit_corpus_indexing.models.ParsedQuery`
        for *query* without executing the search.  Useful for debugging."""
        return self._parser.parse(query)

    # ------------------------------------------------------------------
    # Core execution
    # ------------------------------------------------------------------

    def _execute(
        self, pq: ParsedQuery, sort_by: str = "relevance"
    ) -> list[SearchResult]:
        # ── Step 1: keyword scoring ──────────────────────────────────────
        keyword_scores: dict[int, float] = {}
        if pq.mots_cles:
            keyword_scores = self._search_keywords(pq.mots_cles, pq.operateurs, pq.zone)

        # ── Step 2: filter sets ──────────────────────────────────────────
        rubrique_docs: set[int] | None = None
        if pq.rubrique:
            rubrique_docs = self._get_rubrique_docs(pq.rubrique)

        date_docs: set[int] | None = None
        if pq.date_min is not None or pq.date_max is not None:
            date_docs = self._get_date_docs(pq.date_min, pq.date_max)

        image_docs: set[int] | None = None
        if pq.filtre_images is True:
            image_docs = self._corpus.ids_with_images()
        elif pq.filtre_images is False:
            image_docs = self._corpus.ids_without_images()

        # ── Step 3: combine ──────────────────────────────────────────────
        result_ids: set[int] | None = (
            set(keyword_scores.keys()) if keyword_scores else None
        )

        for filter_set in (rubrique_docs, date_docs, image_docs):
            if filter_set is None:
                continue
            result_ids = filter_set if result_ids is None else result_ids & filter_set

        if result_ids is None:
            return []

        # ── Step 4: build result objects ─────────────────────────────────
        results: list[SearchResult] = []
        for doc_id in result_ids:
            meta = self._corpus.get(doc_id)
            if meta is None:
                continue
            score = keyword_scores.get(doc_id, 0.0)
            snippet = self._extract_snippet(meta, pq.mots_cles)
            results.append(
                SearchResult(
                    doc_id=doc_id,
                    score=score,
                    titre=meta.titre,
                    date=meta.date,
                    rubrique=meta.rubrique,
                    snippet=snippet,
                )
            )

        return self._sort_results(results, sort_by)

    # ------------------------------------------------------------------
    # Keyword search helpers
    # ------------------------------------------------------------------

    def _search_keywords(
        self,
        keywords: list[str],
        operateurs: list[str],
        zone: str | None,
    ) -> dict[int, float]:
        """Return {doc_id: cumulative_score} for the keyword combination."""
        text_index = self._title_index if zone == "titre" else self._main_index

        posting_lists: list[dict[int, float]] = []
        for kw in keywords:
            if kw in text_index:
                posting_lists.append(text_index[kw])
            else:
                logger.debug("_search_keywords: %r not in index", kw)

        if not posting_lists:
            return {}

        if "OR" in operateurs:
            combined: dict[int, float] = {}
            for pl in posting_lists:
                for doc_id, score in pl.items():
                    combined[doc_id] = combined.get(doc_id, 0.0) + score
            return combined

        # AND: intersect, then sum scores for common docs
        common = set(posting_lists[0].keys())
        for pl in posting_lists[1:]:
            common &= pl.keys()

        if not common:
            return {}

        return {
            doc_id: sum(pl.get(doc_id, 0.0) for pl in posting_lists)
            for doc_id in common
        }

    # ------------------------------------------------------------------
    # Filter helpers
    # ------------------------------------------------------------------

    def _get_rubrique_docs(self, rubrique: str) -> set[int]:
        keys = _RUBRIQUE_INDEX_KEYS.get(rubrique, [rubrique.lower()])
        result: set[int] = set()
        for key in keys:
            result |= self._rubrique_index.get(key, set())
        logger.debug("_get_rubrique_docs(%r): %d docs", rubrique, len(result))
        return result

    def _get_date_docs(
        self, date_min: str | None, date_max: str | None
    ) -> set[int]:
        """Return doc_ids whose publication month falls within [date_min, date_max].

        The date index uses ``MM/YYYY`` keys; date bounds are ``YYYY-MM-DD`` ISO
        strings.  Filtering is month-granular: a document from 2013-03-15 matches
        any bound that includes March 2013.
        """
        min_ym: tuple[int, int] | None = None
        max_ym: tuple[int, int] | None = None
        if date_min:
            parts = date_min.split("-")
            min_ym = (int(parts[0]), int(parts[1]))
        if date_max:
            parts = date_max.split("-")
            max_ym = (int(parts[0]), int(parts[1]))

        result: set[int] = set()
        for key, doc_ids in self._date_index.items():
            try:
                mm_str, yyyy_str = key.split("/")
                key_ym = (int(yyyy_str), int(mm_str))
            except ValueError:
                continue
            if min_ym is not None and key_ym < min_ym:
                continue
            if max_ym is not None and key_ym > max_ym:
                continue
            result |= doc_ids

        logger.debug(
            "_get_date_docs([%s, %s]): %d docs", date_min, date_max, len(result)
        )
        return result

    # ------------------------------------------------------------------
    # Snippet extraction
    # ------------------------------------------------------------------

    def _extract_snippet(self, meta: DocumentMeta, keywords: list[str]) -> str:
        """Return a ~200-char context window around the first keyword hit."""
        text = meta.texte
        if not text:
            return meta.titre[:_SNIPPET_WINDOW]

        text_lower = text.lower()
        best_pos = len(text)
        for kw in keywords:
            pos = text_lower.find(kw)
            if 0 <= pos < best_pos:
                best_pos = pos

        if best_pos == len(text):
            # No keyword found: return start of text
            return (
                (text[:_SNIPPET_WINDOW] + "…") if len(text) > _SNIPPET_WINDOW else text
            )

        half = _SNIPPET_WINDOW // 2
        start = max(0, best_pos - half)
        end = min(len(text), start + _SNIPPET_WINDOW)
        snippet = text[start:end]
        if start > 0:
            snippet = "…" + snippet
        if end < len(text):
            snippet = snippet + "…"
        return snippet

    # ------------------------------------------------------------------
    # Sorting
    # ------------------------------------------------------------------

    @staticmethod
    def _sort_results(results: list[SearchResult], sort_by: str) -> list[SearchResult]:
        if sort_by == "date_asc":
            return sorted(results, key=lambda r: _date_sort_key(r.date))
        if sort_by == "date_desc":
            return sorted(results, key=lambda r: _date_sort_key(r.date), reverse=True)
        # Default: sort by score descending
        return sorted(results, key=lambda r: r.score, reverse=True)


def _date_sort_key(date_str: str) -> tuple[int, int, int]:
    """Parse ``dd/mm/yyyy`` into a sortable tuple (yyyy, mm, dd)."""
    try:
        parts = date_str.split("/")
        return (int(parts[2]), int(parts[1]), int(parts[0]))
    except (IndexError, ValueError):
        return (0, 0, 0)
