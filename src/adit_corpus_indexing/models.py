from dataclasses import dataclass, field
from datetime import date


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
