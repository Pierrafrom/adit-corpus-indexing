"""TD2 — Anti-dictionary: identify stop words and apply substitutions."""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def build_antidictionary(idf_path: Path, output_path: Path, threshold: float) -> None:
    """Select stop-word tokens based on their IDF score.

    Tokens with idf <= threshold are considered non-informative (stop words).
    Low IDF means the token appears in almost every document.

    Output format (tab-separated, two columns):
        token\\t
    (empty substitution means "delete this token")

    Args:
        idf_path:   path to idf TSV produced by compute_idf().
        output_path: path to write the antidictionary TSV.
        threshold:  idf cutoff — tokens at or below this value are stop words.
    """
    # TODO:
    #   1. read idf_path
    #   2. select rows where idf <= threshold
    #   3. write (token, "") rows to output_path as UTF-8 TSV
    #   4. log how many stop words were selected
    raise NotImplementedError


def substitue(text: str, substitutions_path: Path) -> str:
    """Replace or delete tokens in *text* according to a substitution file.

    The substitution file is a two-column TSV:
        token\\treplacement
    An empty replacement string means the token is deleted.
    Matching is case-insensitive; word boundaries are respected.

    Args:
        text:               input text to filter.
        substitutions_path: path to the substitution TSV file.

    Returns:
        Filtered text with stop words removed and extra whitespace collapsed.
    """
    # TODO:
    #   1. load substitution file into a dict {token: replacement}
    #   2. split text into tokens (same logic as tokenizer.tokenize)
    #   3. for each token: if in substitutions dict, replace (or drop if "")
    #   4. rejoin remaining tokens and collapse whitespace
    raise NotImplementedError


def apply_to_corpus(
    corpus_path: Path,
    substitutions_path: Path,
    output_path: Path,
) -> None:
    """Produce a filtered corpus XML with stop words removed from all text fields.

    Applies substitue() to every <titre> and <texte> element in corpus.xml.

    Args:
        corpus_path:        path to the original corpus.xml.
        substitutions_path: path to the antidictionary TSV.
        output_path:        path to write the filtered corpus XML.
    """
    # TODO:
    #   1. parse corpus_path with lxml
    #   2. for each <document>, apply substitue() to <titre> and <texte> text
    #   3. write the modified tree to output_path (UTF-8, pretty_print=True)
    raise NotImplementedError
