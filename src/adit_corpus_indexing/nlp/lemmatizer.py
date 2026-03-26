"""TD3 — Lemmatisation du corpus filtré.

Deux approches sont comparées sur le même corpus :

- ``SpacyLemmatizer``    : lemmatisation linguistique via fr_core_news_sm.
- ``SnowballLemmatizer`` : racinisation par règles (stemmer de Porter adapté
  au français, fourni par NLTK).

Chaque classe produit un fichier TSV à deux colonnes (sans en-tête) :

    mot<TAB>lemme_ou_racine

La classe ``LemmatizationComparator`` charge les deux TSV et calcule des
statistiques comparatives pour choisir la meilleure méthode.

Deux fonctions de haut niveau permettent d'utiliser le vocabulaire produit
pour transformer le corpus XML :

- :func:`lemmatize_corpus_tokens` : produit un TSV ``doc_id\\tlemma`` pour le
  calcul TF-IDF sur les lemmes.
- :func:`apply_lemmatization_to_corpus` : applique la lemmatisation et le
  second anti-dictionnaire pour produire ``corpus_final.xml``.

Utilisation typique::

    spacy_lem = SpacyLemmatizer()
    spacy_lem.extract_from_corpus(filtered_xml, outputs / "lemmes_spacy.tsv")

    snow_lem = SnowballLemmatizer()
    snow_lem.extract_from_corpus(filtered_xml, outputs / "lemmes_snowball.tsv")

    comp = LemmatizationComparator(
        outputs / "lemmes_spacy.tsv",
        outputs / "lemmes_snowball.tsv",
    )
    comp.print_report()
    best_tsv = outputs / f"lemmes_{comp.best_method()}.tsv"

    lemmatize_corpus_tokens(filtered_xml, best_tsv, outputs / "tokens_lemmatized.tsv")
    apply_lemmatization_to_corpus(
        filtered_xml, best_tsv, outputs / "antidictionary_v2.tsv",
        outputs / "corpus_final.xml",
    )
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from collections import defaultdict
from pathlib import Path

from lxml import etree

from ..models import LemmatizationEntry, LemmatizationStats
from .tokenizer import tokenize as _tokenize

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


def _load_lemma_map(tsv_path: Path) -> dict[str, str]:
    """Read a two-column lemma TSV into a ``{word: lemma}`` dict.

    Skips blank lines and logs a warning for malformed rows.

    Args:
        tsv_path: path to a TSV produced by :meth:`BaseLemmatizer.extract_from_corpus`.

    Returns:
        Mapping from surface word to its lemma / stem.
    """
    mapping: dict[str, str] = {}
    with open(tsv_path, encoding="utf-8") as f:
        for lineno, raw in enumerate(f, start=1):
            line = raw.rstrip("\n")
            if not line:
                continue
            parts = line.split("\t", 1)
            if len(parts) != 2:
                logger.warning(
                    "_load_lemma_map: malformed line %d in %s — skipped",
                    lineno,
                    tsv_path,
                )
                continue
            mapping[parts[0]] = parts[1]
    return mapping


def _collect_unique_words(corpus_path: Path) -> list[str]:
    """Return a sorted list of unique tokens from <titre> and <texte> elements.

    Args:
        corpus_path: path to a corpus XML file.

    Returns:
        Sorted list of unique lowercase word strings.
    """
    root = etree.parse(str(corpus_path)).getroot()
    words: set[str] = set()
    for document in root.findall("document"):
        for tag in ("titre", "texte"):
            el = document.find(tag)
            if el is not None and el.text:
                words.update(_tokenize(el.text))
    return sorted(words)


# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------


class BaseLemmatizer(ABC):
    """Common interface for all lemmatizers used in TD3.

    Subclasses must implement :meth:`lemmatize`.  The corpus-level extraction
    logic (:meth:`extract_vocabulary` and :meth:`extract_from_corpus`) is
    provided here and relies on :meth:`lemmatize` for each token.

    :class:`SpacyLemmatizer` overrides :meth:`extract_vocabulary` to exploit
    SpaCy's batch ``nlp.pipe()`` for better throughput.
    """

    # ------------------------------------------------------------------
    # Abstract interface
    # ------------------------------------------------------------------

    @property
    @abstractmethod
    def name(self) -> str:
        """Short, human-readable identifier for this lemmatizer."""
        ...

    @abstractmethod
    def lemmatize(self, word: str) -> str:
        """Return the lemma (or stem) of a single lowercase word.

        Args:
            word: a single, already-lowercased token (no punctuation).

        Returns:
            The canonical form of *word* according to this lemmatizer.
        """
        ...

    # ------------------------------------------------------------------
    # Shared corpus-level logic
    # ------------------------------------------------------------------

    def extract_vocabulary(self, corpus_path: Path) -> list[LemmatizationEntry]:
        """Collect all unique tokens from the filtered corpus and lemmatize them.

        Reads every ``<titre>`` and ``<texte>`` element in *corpus_path*,
        tokenizes the concatenated text, deduplicates at the vocabulary level,
        then applies :meth:`lemmatize` to each unique word.

        :class:`SpacyLemmatizer` overrides this method to use batch processing.

        Args:
            corpus_path: path to the filtered corpus XML.

        Returns:
            Sorted list of :class:`LemmatizationEntry` — one per unique word.
        """
        unique_words = _collect_unique_words(corpus_path)
        entries = [
            LemmatizationEntry(word=w, lemma=self.lemmatize(w)) for w in unique_words
        ]
        logger.info(
            "%s.extract_vocabulary: %d unique words lemmatized", self.name, len(entries)
        )
        return entries

    def extract_from_corpus(self, corpus_path: Path, output_path: Path) -> None:
        """Lemmatize the corpus vocabulary and write results to a TSV file.

        Output format — two columns, tab-separated, no header, UTF-8::

            word<TAB>lemma

        One row per unique word found in the corpus.  Rows are sorted
        alphabetically by *word* for reproducibility.

        Args:
            corpus_path: path to the filtered corpus XML.
            output_path: path to write the two-column TSV.
        """
        entries = self.extract_vocabulary(corpus_path)
        with open(output_path, "w", encoding="utf-8") as f:
            for entry in entries:
                f.write(f"{entry.word}\t{entry.lemma}\n")
        logger.info(
            "%s.extract_from_corpus: %d entries → %s",
            self.name,
            len(entries),
            output_path,
        )


# ---------------------------------------------------------------------------
# SpaCy implementation
# ---------------------------------------------------------------------------


class SpacyLemmatizer(BaseLemmatizer):
    """Lemmatizer backed by the SpaCy ``fr_core_news_sm`` French model.

    The SpaCy pipeline is loaded once at construction.  Components not needed
    for lemmatisation (NER, sentence segmenter) are disabled to reduce overhead.
    Batch processing via ``nlp.pipe()`` is used in :meth:`extract_vocabulary`
    to vectorise inference across the full vocabulary.

    Requires::

        uv add spacy
        uv run python -m spacy download fr_core_news_sm

    Args:
        model: SpaCy model identifier.  Defaults to ``"fr_core_news_sm"``.
    """

    def __init__(self, model: str = "fr_core_news_sm") -> None:
        import spacy  # local import — heavy dependency, lazy-loaded

        nlp = spacy.load(model)
        # Disable components not required for lemmatisation to save memory/time.
        for pipe_name in ("ner", "senter", "parser"):
            if nlp.has_pipe(pipe_name):
                nlp.disable_pipe(pipe_name)
        self._nlp = nlp
        logger.info("SpacyLemmatizer: loaded model '%s'", model)

    @property
    def name(self) -> str:
        """Return ``"spacy"``."""
        return "spacy"

    def lemmatize(self, word: str) -> str:
        """Return the SpaCy lemma for a single word.

        Processes *word* as a single-token document through the loaded
        SpaCy pipeline and returns ``token.lemma_``.

        Args:
            word: a single lowercase token.

        Returns:
            The SpaCy lemma string, lowercased.
        """
        doc = self._nlp(word)
        return doc[0].lemma_.lower() if len(doc) > 0 else word

    def extract_vocabulary(self, corpus_path: Path) -> list[LemmatizationEntry]:
        """Collect unique tokens and batch-lemmatize them with SpaCy.

        Uses ``nlp.pipe()`` (batch size 256) for efficient vectorised inference
        rather than calling ``nlp()`` once per token.

        Args:
            corpus_path: path to the filtered corpus XML.

        Returns:
            Sorted list of :class:`LemmatizationEntry`.
        """
        unique_words = _collect_unique_words(corpus_path)
        entries: list[LemmatizationEntry] = []

        for word, doc in zip(
            unique_words,
            self._nlp.pipe(unique_words, batch_size=256),
            strict=False,
        ):
            lemma = doc[0].lemma_.lower() if len(doc) > 0 else word
            entries.append(LemmatizationEntry(word=word, lemma=lemma))

        logger.info(
            "SpacyLemmatizer.extract_vocabulary: %d unique words lemmatized",
            len(entries),
        )
        return entries


# ---------------------------------------------------------------------------
# Snowball (NLTK) implementation
# ---------------------------------------------------------------------------


class SnowballLemmatizer(BaseLemmatizer):
    """Lemmatizer backed by the NLTK Snowball stemmer for French.

    Snowball is a rule-based stemmer adapted from Porter for several
    European languages.  It returns a *stem* (truncated root), not a true
    linguistic lemma, but it requires no pre-trained model.

    Requires::

        uv add nltk

    Args:
        language: language passed to ``nltk.stem.SnowballStemmer``.
                  Defaults to ``"french"``.
    """

    def __init__(self, language: str = "french") -> None:
        from nltk.stem.snowball import SnowballStemmer  # type: ignore[import-untyped]

        self._stemmer = SnowballStemmer(language)
        logger.info("SnowballLemmatizer: loaded stemmer for language '%s'", language)

    @property
    def name(self) -> str:
        """Return ``"snowball"``."""
        return "snowball"

    def lemmatize(self, word: str) -> str:
        """Return the Snowball stem of *word*.

        Args:
            word: a single lowercase token.

        Returns:
            The Snowball stem string.
        """
        return str(self._stemmer.stem(word))


# ---------------------------------------------------------------------------
# Comparative analysis
# ---------------------------------------------------------------------------


class LemmatizationComparator:
    """Load two lemmatization TSVs and produce a comparative statistics report.

    Args:
        spacy_path:    path to the TSV produced by :class:`SpacyLemmatizer`.
        snowball_path: path to the TSV produced by :class:`SnowballLemmatizer`.
        top_n:         number of high-collision lemmas to include in the report.
    """

    def __init__(
        self,
        spacy_path: Path,
        snowball_path: Path,
        top_n: int = 10,
    ) -> None:
        self._spacy_path = spacy_path
        self._snowball_path = snowball_path
        self._top_n = top_n
        self._spacy_table = self._load_table(spacy_path)
        self._snowball_table = self._load_table(snowball_path)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _load_table(path: Path) -> dict[str, str]:
        """Read a two-column TSV into a ``{word: lemma}`` dictionary.

        Skips blank lines and logs a warning for malformed rows.

        Args:
            path: path to a TSV produced by :meth:`BaseLemmatizer.extract_from_corpus`.

        Returns:
            Mapping from surface word to its lemma/stem.
        """
        return _load_lemma_map(path)

    def _compute_stats(self, table: dict[str, str], method: str) -> LemmatizationStats:
        """Compute descriptive statistics for one lemmatization table.

        Statistics computed:

        - ``unique_words``      = len(table)
        - ``unique_lemmas``     = len(set(table.values()))
        - ``compression_ratio`` = unique_lemmas / unique_words
        - ``top_collisions``    = top-N lemmas covering the most surface forms

        Args:
            table:  ``{word: lemma}`` mapping for one lemmatizer.
            method: human-readable method name (stored in the stats object).

        Returns:
            A populated :class:`LemmatizationStats` instance.
        """
        unique_words = len(table)
        unique_lemmas = len(set(table.values()))
        compression_ratio = unique_lemmas / unique_words if unique_words > 0 else 1.0

        # Group surface forms by lemma to find high-collision entries.
        lemma_to_words: dict[str, list[str]] = defaultdict(list)
        for word, lemma in table.items():
            lemma_to_words[lemma].append(word)

        sorted_collisions = sorted(
            lemma_to_words.items(),
            key=lambda kv: len(kv[1]),
            reverse=True,
        )
        top_collisions = {
            lemma: words for lemma, words in sorted_collisions[: self._top_n]
        }

        return LemmatizationStats(
            method=method,
            unique_words=unique_words,
            unique_lemmas=unique_lemmas,
            compression_ratio=compression_ratio,
            top_collisions=top_collisions,
        )

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def stats(self) -> tuple[LemmatizationStats, LemmatizationStats]:
        """Return ``(spacy_stats, snowball_stats)`` computed from loaded tables.

        Returns:
            A tuple of two :class:`LemmatizationStats` instances.
        """
        spacy_stats = self._compute_stats(self._spacy_table, "spacy")
        snowball_stats = self._compute_stats(self._snowball_table, "snowball")
        return spacy_stats, snowball_stats

    def print_report(self) -> None:
        """Print a human-readable comparison report to stdout.

        The report includes, for each method:

        - unique words, unique lemmas, compression ratio
        - the top-N collision examples

        Concludes with a recommendation from :meth:`best_method`.
        """
        spacy_s, snow_s = self.stats()
        sep = "─" * 60

        print(f"\n{sep}")
        print("LEMMATIZATION COMPARATIVE REPORT")
        print(sep)

        for stat in (spacy_s, snow_s):
            print(f"\n  Method           : {stat.method.upper()}")
            print(f"  Unique words     : {stat.unique_words:,}")
            print(f"  Unique lemmas    : {stat.unique_lemmas:,}")
            print(f"  Compression ratio: {stat.compression_ratio:.4f}")
            print(
                f"  Grouping factor  : {stat.unique_words / stat.unique_lemmas:.2f}x"
                if stat.unique_lemmas > 0
                else "  Grouping factor  : N/A"
            )
            print(f"\n  Top-{self._top_n} collisions (lemma → surface forms):")
            for lemma, words in list(stat.top_collisions.items())[:5]:
                sample = ", ".join(words[:6])
                if len(words) > 6:
                    sample += f" … (+{len(words) - 6})"
                print(f"    {lemma!r:20s} ← {sample}")

        best = self.best_method()
        print(f"\n{sep}")
        print(
            f"  RECOMMENDATION: use '{best}' "
            f"(lower compression ratio → better grouping for IR)."
        )
        print(sep + "\n")

    def best_method(self) -> str:
        """Return the name of the recommended lemmatizer.

        Selection criterion: the method with the **lower compression ratio**
        groups more surface forms under the same lemma — better recall for IR.
        Ties are broken in favour of SpaCy (linguistic quality).

        Returns:
            ``"spacy"`` or ``"snowball"``.
        """
        spacy_s, snow_s = self.stats()
        if snow_s.compression_ratio < spacy_s.compression_ratio:
            return "snowball"
        return "spacy"  # SpaCy wins on tie (linguistic quality preferred)


# ---------------------------------------------------------------------------
# Corpus-level transformation helpers
# ---------------------------------------------------------------------------


def lemmatize_corpus_tokens(
    corpus_path: Path,
    lemma_tsv_path: Path,
    output_path: Path,
) -> None:
    """Tokenize a corpus and map each token to its lemma.

    Reads the ``word → lemma`` mapping from *lemma_tsv_path* and produces a
    tokens TSV where each line is ``doc_id\\tlemma``, ready to be fed into the
    TF-IDF functions from :mod:`tfidf`.  Words absent from the mapping fall
    back to their surface form.

    Args:
        corpus_path:    path to the filtered corpus XML (from TD2).
        lemma_tsv_path: two-column TSV produced by
                        :meth:`BaseLemmatizer.extract_from_corpus`.
        output_path:    path to write the lemmatized tokens TSV.
    """
    lemma_map = _load_lemma_map(lemma_tsv_path)
    root = etree.parse(str(corpus_path)).getroot()

    rows: list[str] = []
    for document in root.findall("document"):
        article_el = document.find("article")
        if article_el is None or not article_el.text:
            logger.warning(
                "lemmatize_corpus_tokens: document without article ID — skipped"
            )
            continue
        doc_id = article_el.text.strip()

        parts: list[str] = []
        for tag in ("titre", "texte"):
            el = document.find(tag)
            if el is not None and el.text:
                parts.append(el.text)

        for token in _tokenize(" ".join(parts)):
            lemma = lemma_map.get(token, token)
            rows.append(f"{doc_id}\t{lemma}")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(rows))
        if rows:
            f.write("\n")

    logger.info(
        "lemmatize_corpus_tokens: %d (doc_id, lemma) pairs → %s",
        len(rows),
        output_path,
    )


def apply_lemmatization_to_corpus(
    corpus_path: Path,
    lemma_tsv_path: Path,
    antidictionary_path: Path,
    output_path: Path,
) -> None:
    """Apply lemmatization and refined filtering to produce ``corpus_final.xml``.

    For each ``<titre>`` and ``<texte>`` element:

    1. Tokenize the text.
    2. Map each token to its lemma (fallback to surface form if absent).
    3. Remove lemmas present in the refined anti-dictionary.
    4. Replace element text with space-joined filtered lemmas.

    Args:
        corpus_path:         filtered corpus XML from TD2 (``corpus_filtered.xml``).
        lemma_tsv_path:      word→lemma TSV produced by a :class:`BaseLemmatizer`.
        antidictionary_path: lemma stop-word TSV produced by
                             :func:`antidictionary.build_antidictionary` on
                             lemmatized tokens.
        output_path:         path to write the final lemmatized corpus XML
                             (``corpus_final.xml``).
    """
    from .antidictionary import AntiDictionary

    lemma_map = _load_lemma_map(lemma_tsv_path)
    anti = AntiDictionary(antidictionary_path)

    tree = etree.parse(str(corpus_path))
    root = tree.getroot()

    fields_processed = 0
    for document in root.findall("document"):
        for tag in ("titre", "texte"):
            el = document.find(tag)
            if el is None or not el.text:
                continue
            tokens = _tokenize(el.text)
            lemmas = [lemma_map.get(t, t) for t in tokens]
            filtered = [lem for lem in lemmas if lem not in anti]
            el.text = " ".join(filtered)
            fields_processed += 1

    tree.write(
        str(output_path),
        encoding="utf-8",
        xml_declaration=True,
        pretty_print=True,
    )
    logger.info(
        "apply_lemmatization_to_corpus: %d fields processed → %s",
        fields_processed,
        output_path,
    )
