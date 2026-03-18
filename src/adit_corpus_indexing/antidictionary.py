"""TD2 — Anti-dictionary: identify stop words and apply substitutions."""

import logging
import re
from pathlib import Path

from lxml import etree

from .tokenizer import _WORD_RE, normalize_elisions

logger = logging.getLogger(__name__)

# Matches any character that is not a letter (ASCII + accented Latin-1) or whitespace.
# Used to strip orphaned punctuation (commas, quotes, guillemets…) after word filtering.
_PUNCT_RE = re.compile(r"[^a-zA-ZÀ-ÿ\s]")


def build_antidictionary(
    idf_path: Path,
    output_path: Path,
    threshold: float,
    max_threshold: float = float("inf"),
) -> None:
    """Select stop-word tokens based on their IDF score using two thresholds.

    Two-threshold selection (Zipf's law, as per course):

    * Tokens with idf <= threshold are too *common* — they appear in almost
      every document and carry no discriminating power (e.g. "le", "de").
    * Tokens with idf >= max_threshold are too *rare* — they appear in so few
      documents that they are statistically non-representative (e.g. hapaxes,
      typos).  Pass float("inf") (the default) to disable this filter.

    Tokens whose IDF falls strictly between the two thresholds are kept.

    Output format (tab-separated, two columns, no header):
        token\\t
    (empty substitution means "delete this token")

    Args:
        idf_path:       path to idf TSV produced by compute_idf().
        output_path:    path to write the antidictionary TSV.
        threshold:      lower IDF cutoff — tokens at or below are stop words.
        max_threshold:  upper IDF cutoff — tokens at or above are stop words.
                        Default: float("inf") (no upper cutoff applied).
    """
    stop_words: list[str] = []

    with open(idf_path, encoding="utf-8") as f:
        for lineno, raw in enumerate(f, start=1):
            line = raw.rstrip("\n")
            if not line:
                continue
            parts = line.split("\t", 1)
            if len(parts) != 2:
                logger.warning(
                    "build_antidictionary: malformed line %d in %s — skipped",
                    lineno,
                    idf_path,
                )
                continue
            token, idf_val = parts
            idf = float(idf_val)
            if idf <= threshold or idf >= max_threshold:
                stop_words.append(token)

    with open(output_path, "w", encoding="utf-8") as f:
        for token in stop_words:
            f.write(f"{token}\t\n")

    logger.info(
        "build_antidictionary: %d stop words "
        "(low_threshold=%.3f, high_threshold=%s) → %s",
        len(stop_words),
        threshold,
        f"{max_threshold:.3f}" if max_threshold != float("inf") else "∞",
        output_path,
    )


def _load_substitutions(substitutions_path: Path) -> dict[str, str]:
    """Load a substitution TSV into a {lowercase_token: replacement} dict."""
    subs: dict[str, str] = {}
    with open(substitutions_path, encoding="utf-8") as f:
        for raw in f:
            line = raw.rstrip("\n")
            if not line:
                continue
            parts = line.split("\t", 1)
            token = parts[0].lower()
            replacement = parts[1] if len(parts) > 1 else ""
            subs[token] = replacement
    return subs


class AntiDictionary:
    """Stop-word substitution table loaded once from a TSV file.

    Loading the TSV on every call to ``substitue()`` is wasteful when
    filtering an entire corpus: ``apply_to_corpus`` would re-read the same
    file for every ``<titre>`` and ``<texte>`` element.  This class loads
    the table once at construction and exposes an ``apply()`` method that
    can be called as many times as needed.

    Usage::

        anti = AntiDictionary(path)
        for text in texts:
            filtered = anti.apply(text)
    """

    def __init__(self, path: Path) -> None:
        """Load the substitution table from *path*.

        Args:
            path: path to the antidictionary TSV produced by
                  :func:`build_antidictionary`.
        """
        self._subs = _load_substitutions(path)

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def apply(self, text: str) -> str:
        """Filter *text* by replacing or deleting stop words.

        Steps applied in order:

        1. Normalise French elisions (``l'`` → ``''``, etc.).
        2. Replace each word token with its substitution (empty = delete).
        3. Strip orphaned punctuation characters (guillemets, commas…).
        4. Collapse runs of whitespace and strip leading/trailing spaces.

        Args:
            text: raw text to filter.

        Returns:
            Filtered text containing only content words separated by spaces.
        """
        text = normalize_elisions(text)

        def _replace(match: re.Match[str]) -> str:
            word = match.group(0)
            return self._subs.get(word.lower(), word)

        result = _WORD_RE.sub(_replace, text)
        result = _PUNCT_RE.sub(" ", result)
        return re.sub(r"\s+", " ", result).strip()

    def __len__(self) -> int:
        """Return the number of entries in the substitution table."""
        return len(self._subs)

    def __contains__(self, token: object) -> bool:
        """Return True if *token* (case-insensitive) is in the table."""
        return str(token).lower() in self._subs


def substitue(text: str, substitutions_path: Path) -> str:
    """Replace or delete tokens in *text* according to a substitution file.

    Convenience wrapper around :class:`AntiDictionary` for one-shot use.
    When filtering many texts, prefer instantiating ``AntiDictionary`` once
    and calling :meth:`~AntiDictionary.apply` repeatedly.

    Args:
        text:               input text to filter.
        substitutions_path: path to the substitution TSV file.

    Returns:
        Filtered text with stop words removed and extra whitespace collapsed.
    """
    return AntiDictionary(substitutions_path).apply(text)


def apply_to_corpus(
    corpus_path: Path,
    substitutions_path: Path,
    output_path: Path,
) -> None:
    """Produce a filtered corpus XML with stop words removed from all text fields.

    Applies :class:`AntiDictionary` to every <titre> and <texte> element in
    corpus.xml.  The substitution table is loaded once for the entire corpus.

    Args:
        corpus_path:        path to the original corpus.xml.
        substitutions_path: path to the antidictionary TSV.
        output_path:        path to write the filtered corpus XML.
    """
    anti = AntiDictionary(substitutions_path)
    tree = etree.parse(str(corpus_path))
    root = tree.getroot()

    fields_filtered = 0
    for document in root.findall("document"):
        for tag in ("titre", "texte"):
            el = document.find(tag)
            if el is not None and el.text:
                el.text = anti.apply(el.text)
                fields_filtered += 1

    tree.write(
        str(output_path),
        encoding="utf-8",
        xml_declaration=True,
        pretty_print=True,
    )
    logger.info(
        "apply_to_corpus: filtered %d text fields → %s",
        fields_filtered,
        output_path,
    )
