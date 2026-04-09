from dataclasses import dataclass, field
from datetime import date
from typing import Literal


@dataclass
class Person:
    name: str
    email: str


@dataclass
class Contact:
    name: str
    email: str
    url: str
    phone: str


@dataclass
class Image:
    url: str
    legend: str | None


@dataclass
class Article:
    code: str
    bulletin: str
    date: date | None
    rubrique: str
    title: str
    author: Person | None
    body: str
    images: list[Image]
    contacts: list[Contact] = field(default_factory=list)


@dataclass(frozen=True)
class LemmatizationEntry:
    """A single (word, lemma) pair extracted from the corpus.

    Attributes:
        word:  the lowercase surface form found in the text.
        lemma: the lemma (or stem) assigned by the lemmatizer.
    """

    word: str
    lemma: str


@dataclass
class LemmatizedToken:
    """Per-token output from the combined SpaCy + Snowball lemmatization.

    Produced by :mod:`lemmatisation` for detailed per-token analysis alongside
    the structured vocabulary output of :mod:`lemmatizer`.

    Attributes:
        article_id: identifier of the source document.
        token:      the lowercase surface form found in the text.
        lemma:      the SpaCy lemma.
        stem:       the Snowball stem.
    """

    article_id: str
    token: str
    lemma: str
    stem: str


CorrectionStatus = Literal[
    "entity",  # (a) number / date — kept as-is
    "exact",  # (b) found verbatim in lexicon
    "single_candidate",  # (d) one prefix candidate returned directly
    "best_candidate",  # (e) Levenshtein picks best among multiple
    "not_found",  # (f) no candidate found
]


@dataclass
class CorrectionResult:
    """Outcome of spell-checking one query term.

    Attributes:
        original:   the raw term from the query (after tokenization).
        corrected:  the best matching lexicon word, or None if not found.
        lemma:      the lemma for *corrected*, or None if not found.
        status:     one of the five correction outcomes.
        candidates: all candidates returned by prefix search (may be empty).
        distance:   Levenshtein distance between *original* and *corrected*,
                    or None when status is not ``"best_candidate"``.
    """

    original: str
    corrected: str | None
    lemma: str | None
    status: CorrectionStatus
    candidates: list[str] = field(default_factory=list)
    distance: int | None = None


@dataclass
class ParsedQuery:
    """Structured representation of a natural language query (TD5).

    Produced by :class:`~adit_corpus_indexing.nlp.query_parser.QueryParser`.

    Attributes:
        mots_cles:     lemmatised keywords extracted from the query.
        rubrique:      ADIT rubrique name if explicitly mentioned, else None.
        date_min:      lower date bound (inclusive), as ISO string or None.
        date_max:      upper date bound (inclusive), as ISO string or None.
        operateurs:    logical operators detected (always contains "AND";
                       may also contain "OR" and/or "NOT").
        filtre_images: True → must have images; False → must have none;
                       None → no constraint.
        zone:          "titre" to restrict keyword search to the title field;
                       None means search all zones.
    """

    mots_cles: list[str]
    rubrique: str | None = None
    date_min: str | None = None
    date_max: str | None = None
    operateurs: list[str] = field(default_factory=lambda: ["AND"])
    filtre_images: bool | None = None
    zone: str | None = None


@dataclass
class LemmatizationStats:
    """Descriptive statistics for one lemmatization run.

    Attributes:
        method:           human-readable name of the lemmatizer.
        unique_words:     number of distinct surface forms in the vocabulary.
        unique_lemmas:    number of distinct lemmas produced.
        compression_ratio: unique_lemmas / unique_words — lower means more
                          aggressive grouping (closer to 0 is better for IR).
        top_collisions:   mapping lemma → list[word] for the N lemmas that
                          cover the most distinct surface forms.
    """

    method: str
    unique_words: int
    unique_lemmas: int
    compression_ratio: float
    top_collisions: dict[str, list[str]] = field(default_factory=dict)
