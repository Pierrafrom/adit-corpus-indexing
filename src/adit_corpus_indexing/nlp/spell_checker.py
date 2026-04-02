"""TD4 — Spell checker for query terms.

Three independent building blocks:

1. **Pure functions** — ``levenshtein_distance``, ``common_prefix_length``,
   ``is_entity``.  No state, trivially testable.

2. **``Lexicon``** — loads a word→lemma TSV (or an inverted-index file) and
   exposes ``prefix_candidates`` using the prefix-search heuristic from the
   course (seuilMin / seuilMax / seuilProximite).

3. **``SpellChecker``** — orchestrates the six-step pipeline from the TD4
   instructions:

   (a) entity → keep as-is
   (b) exact match in lexicon → validate
   (c) absent → prefix_candidates
   (d) one candidate → return directly
   (e) multiple candidates → Levenshtein to break ties
   (f) no candidates → signal failure

Usage::

    from pathlib import Path
    from adit_corpus_indexing.nlp.spell_checker import Lexicon, SpellChecker

    lexicon = Lexicon.from_tsv(Path("tests/fixtures/mini_lexicon.tsv"))
    checker = SpellChecker(lexicon)
    results = checker.process_query("recherche nanotechnolgie 2024")
    for r in results:
        print(r.original, "→", r.corrected, f"[{r.status}]")
"""

from __future__ import annotations

import bisect
import logging
import re
from pathlib import Path

from ..models import CorrectionResult
from .tokenizer import normalize_elisions, tokenize

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Regex patterns for entity detection
# ---------------------------------------------------------------------------

# Matches integers and decimals (e.g. 42, 3.14, 1 000)
_NUMBER_RE = re.compile(r"^\d[\d\s.,]*$")

# Matches dates: dd/mm/yyyy, dd-mm-yyyy, yyyy, mm/yyyy
_DATE_RE = re.compile(r"^(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4}|\d{4}|\d{1,2}[/\-]\d{4})$")

# ---------------------------------------------------------------------------
# Pure functions
# ---------------------------------------------------------------------------


def levenshtein_distance(a: str, b: str) -> int:
    """Compute the Levenshtein (edit) distance between two strings.

    Uses the standard dynamic-programming algorithm in O(|a| × |b|) time and
    O(min(|a|, |b|)) space (single-row optimisation).

    Args:
        a: first string.
        b: second string.

    Returns:
        Minimum number of single-character edits (insertions, deletions,
        substitutions) to transform *a* into *b*.

    Examples:
        >>> levenshtein_distance("kitten", "sitting")
        3
        >>> levenshtein_distance("", "abc")
        3
        >>> levenshtein_distance("abc", "abc")
        0
    """
    # Ensure a is the shorter string to minimise memory use.
    if len(a) > len(b):
        a, b = b, a

    prev = list(range(len(a) + 1))
    for j, cb in enumerate(b, start=1):
        curr = [j] + [0] * len(a)
        for i, ca in enumerate(a, start=1):
            if ca == cb:
                curr[i] = prev[i - 1]
            else:
                curr[i] = 1 + min(prev[i - 1], prev[i], curr[i - 1])
        prev = curr

    return prev[len(a)]


def common_prefix_length(a: str, b: str) -> int:
    """Return the length of the longest common prefix of *a* and *b*.

    Args:
        a: first string.
        b: second string.

    Returns:
        Number of leading characters that are identical in both strings.

    Examples:
        >>> common_prefix_length("nanotechnologie", "nanotechnologic")
        14
        >>> common_prefix_length("abc", "xyz")
        0
        >>> common_prefix_length("", "abc")
        0
    """
    length = 0
    for ca, cb in zip(a, b, strict=False):
        if ca != cb:
            break
        length += 1
    return length


def is_entity(term: str) -> bool:
    """Return True if *term* is a specific entity (number or date).

    Entities are kept as-is during spell checking (step a of the pipeline).

    Args:
        term: a single token from the query (lowercase, letters or digits).

    Returns:
        True if the term looks like a number or a date.

    Examples:
        >>> is_entity("2024")
        True
        >>> is_entity("01/01/2024")
        True
        >>> is_entity("42")
        True
        >>> is_entity("nanotechnologie")
        False
    """
    return bool(_NUMBER_RE.match(term) or _DATE_RE.match(term))


# ---------------------------------------------------------------------------
# Lexicon
# ---------------------------------------------------------------------------


class Lexicon:
    """Word→lemma mapping with prefix-search support.

    Internally keeps the vocabulary as a **sorted list** so that
    ``prefix_candidates`` can use ``bisect`` (O(log N)) to jump to the first
    candidate and then iterate linearly until the prefix no longer matches —
    O(log N + k) instead of O(N).

    Args:
        entries: mapping from surface word to its lemma.
    """

    def __init__(self, entries: dict[str, str]) -> None:
        self._word_to_lemma: dict[str, str] = entries
        # Sorted list of words for binary-search prefix lookup.
        self._sorted_words: list[str] = sorted(entries)

    # ------------------------------------------------------------------
    # Class-level constructors
    # ------------------------------------------------------------------

    @classmethod
    def from_tsv(cls, path: Path) -> Lexicon:
        """Load a two-column ``word<TAB>lemma`` TSV file.

        Suitable for the mini test lexicon and for ``lemmes_spacy.tsv`` /
        ``lemmes_snowball.tsv`` produced by the TD3 pipeline.

        Args:
            path: path to a UTF-8 tab-separated file with no header.

        Returns:
            A :class:`Lexicon` instance populated from *path*.
        """
        entries: dict[str, str] = {}
        with open(path, encoding="utf-8") as f:
            for lineno, raw in enumerate(f, start=1):
                line = raw.rstrip("\n")
                if not line:
                    continue
                parts = line.split("\t", 1)
                if len(parts) != 2:
                    logger.warning(
                        "Lexicon.from_tsv: malformed line %d in %s — skipped",
                        lineno,
                        path,
                    )
                    continue
                word, lemma = parts
                entries[word.strip()] = lemma.strip()
        logger.info("Lexicon.from_tsv: %d entries loaded from %s", len(entries), path)
        return cls(entries)

    @classmethod
    def from_index(cls, path: Path) -> Lexicon:
        """Build a lexicon from an inverted-index TSV (first column = term).

        The lemma is set to the term itself (the index does not store lemmas).
        Useful to load the full corpus vocabulary directly from
        ``index_texte.tsv`` or ``index_titre_texte.tsv``.

        Args:
            path: path to a TSV index file produced by :class:`InvertedIndexBuilder`.

        Returns:
            A :class:`Lexicon` instance where every term maps to itself.
        """
        entries: dict[str, str] = {}
        with open(path, encoding="utf-8") as f:
            for lineno, raw in enumerate(f, start=1):
                line = raw.rstrip("\n")
                if not line:
                    continue
                term = line.split("\t", 1)[0].strip()
                if not term:
                    logger.warning(
                        "Lexicon.from_index: empty term on line %d in %s — skipped",
                        lineno,
                        path,
                    )
                    continue
                entries[term] = term
        logger.info("Lexicon.from_index: %d terms loaded from %s", len(entries), path)
        return cls(entries)

    # ------------------------------------------------------------------
    # Membership and lemma lookup
    # ------------------------------------------------------------------

    def __contains__(self, word: object) -> bool:
        """Return True if *word* is in the lexicon."""
        return word in self._word_to_lemma

    def __len__(self) -> int:
        """Return the number of entries in the lexicon."""
        return len(self._word_to_lemma)

    def get_lemma(self, word: str) -> str | None:
        """Return the lemma for *word*, or None if absent.

        Args:
            word: a surface form to look up.

        Returns:
            The associated lemma, or None.
        """
        return self._word_to_lemma.get(word)

    # ------------------------------------------------------------------
    # Prefix-based candidate search
    # ------------------------------------------------------------------

    def prefix_candidates(
        self,
        word: str,
        seuil_min: int = 3,
        seuil_max: int = 6,
        seuil_proximite: int = 3,
    ) -> list[str]:
        """Return lexicon words that share a common prefix with *word*.

        This is the heuristic described in the TD4 instructions to reduce the
        candidate space before applying Levenshtein.

        Algorithm:
            1. If ``len(word) < seuil_min`` → return [] (word too short to
               guess reliably).
            2. Build ``query_prefix = word[:min(len(word), seuil_max)]``.
            3. Use binary search to jump to the first lexicon entry whose
               leading characters could match.
            4. Collect all entries *c* such that
               ``common_prefix_length(word, c) >= seuil_proximite``.

        Args:
            word:             the (possibly misspelled) query term.
            seuil_min:        minimum word length to attempt prefix search.
            seuil_max:        maximum prefix length compared against lexicon words.
            seuil_proximite:  minimum common-prefix length for a word to qualify
                              as a candidate.

        Returns:
            List of candidate lexicon words (may be empty).
        """
        if len(word) < seuil_min:
            logger.debug(
                "prefix_candidates: '%s' shorter than seuil_min=%d → []",
                word,
                seuil_min,
            )
            return []

        # The search prefix: the first seuil_proximite characters guide the
        # binary search entry point; we compare up to seuil_max characters.
        search_prefix = word[:seuil_proximite]

        # Jump to the first word that could start with search_prefix.
        start_idx = bisect.bisect_left(self._sorted_words, search_prefix)

        candidates: list[str] = []
        for candidate in self._sorted_words[start_idx:]:
            cpl = common_prefix_length(word, candidate)
            if cpl < seuil_proximite:
                # Since the list is sorted, once the prefix no longer matches
                # at position seuil_proximite, no further entries will match.
                break
            candidates.append(candidate)

        logger.debug(
            "prefix_candidates('%s', min=%d, max=%d, prox=%d): %d candidate(s)",
            word,
            seuil_min,
            seuil_max,
            seuil_proximite,
            len(candidates),
        )
        return candidates


# ---------------------------------------------------------------------------
# SpellChecker
# ---------------------------------------------------------------------------


class SpellChecker:
    """Six-step query spell checker following the TD4 specification.

    Steps per term:
        (a) Entity (number / date) → keep as-is.
        (b) Exact match in lexicon → validate.
        (c) Not found → run prefix search.
        (d) One candidate → return it.
        (e) Multiple candidates → pick closest by Levenshtein.
        (f) No candidates → report failure.

    Args:
        lexicon:          the :class:`Lexicon` to search against.
        seuil_min:        forwarded to :meth:`Lexicon.prefix_candidates`.
        seuil_max:        forwarded to :meth:`Lexicon.prefix_candidates`.
        seuil_proximite:  forwarded to :meth:`Lexicon.prefix_candidates`.
    """

    def __init__(
        self,
        lexicon: Lexicon,
        seuil_min: int = 3,
        seuil_max: int = 6,
        seuil_proximite: int = 3,
    ) -> None:
        self._lexicon = lexicon
        self._seuil_min = seuil_min
        self._seuil_max = seuil_max
        self._seuil_proximite = seuil_proximite

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def correct_term(self, term: str) -> CorrectionResult:
        """Apply the six-step pipeline to a single query term.

        Args:
            term: a single lowercase token from the query.

        Returns:
            A :class:`CorrectionResult` describing the outcome.
        """
        # (a) Entity check — numbers, dates
        if is_entity(term):
            logger.debug("correct_term('%s'): entity → kept as-is", term)
            return CorrectionResult(
                original=term,
                corrected=term,
                lemma=term,
                status="entity",
            )

        # (b) Exact match in lexicon
        if term in self._lexicon:
            lemma = self._lexicon.get_lemma(term)
            logger.debug("correct_term('%s'): exact match → lemma='%s'", term, lemma)
            return CorrectionResult(
                original=term,
                corrected=term,
                lemma=lemma,
                status="exact",
            )

        # (c) Prefix search for candidates
        candidates = self._lexicon.prefix_candidates(
            term,
            seuil_min=self._seuil_min,
            seuil_max=self._seuil_max,
            seuil_proximite=self._seuil_proximite,
        )

        # (f) No candidates found
        if not candidates:
            logger.info("correct_term('%s'): no candidates found", term)
            return CorrectionResult(
                original=term,
                corrected=None,
                lemma=None,
                status="not_found",
                candidates=[],
            )

        # (d) Exactly one candidate
        if len(candidates) == 1:
            best = candidates[0]
            lemma = self._lexicon.get_lemma(best)
            logger.debug(
                "correct_term('%s'): single candidate '%s' → lemma='%s'",
                term,
                best,
                lemma,
            )
            return CorrectionResult(
                original=term,
                corrected=best,
                lemma=lemma,
                status="single_candidate",
                candidates=candidates,
            )

        # (e) Multiple candidates — Levenshtein to break the tie
        best, best_dist = self._closest_by_levenshtein(term, candidates)
        lemma = self._lexicon.get_lemma(best)
        logger.debug(
            "correct_term('%s'): %d candidates, best='%s' (dist=%d) → lemma='%s'",
            term,
            len(candidates),
            best,
            best_dist,
            lemma,
        )
        return CorrectionResult(
            original=term,
            corrected=best,
            lemma=lemma,
            status="best_candidate",
            candidates=candidates,
            distance=best_dist,
        )

    def process_query(self, query: str) -> list[CorrectionResult]:
        """Tokenize *query* and correct each term.

        Applies the same tokenization as the TD2 pipeline (elision removal +
        letter-only splitting + lowercasing) so that the corrected lemmas are
        consistent with the inverted indexes.

        Args:
            query: raw query string typed by the user.

        Returns:
            One :class:`CorrectionResult` per token extracted from the query.
        """
        normalized = normalize_elisions(query)
        tokens = tokenize(normalized)
        if not tokens:
            logger.info("process_query: no tokens extracted from query '%s'", query)
            return []

        results = [self.correct_term(t) for t in tokens]
        logger.info(
            "process_query: %d tokens processed from query '%s'", len(results), query
        )
        return results

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _closest_by_levenshtein(word: str, candidates: list[str]) -> tuple[str, int]:
        """Return the candidate with the smallest Levenshtein distance to *word*.

        Ties are broken by lexicographic order (first alphabetically wins).

        Args:
            word:       the original query term.
            candidates: non-empty list of candidate words.

        Returns:
            ``(best_candidate, distance)`` tuple.
        """
        best = candidates[0]
        best_dist = levenshtein_distance(word, best)
        for candidate in candidates[1:]:
            dist = levenshtein_distance(word, candidate)
            if dist < best_dist or (dist == best_dist and candidate < best):
                best = candidate
                best_dist = dist
        return best, best_dist
