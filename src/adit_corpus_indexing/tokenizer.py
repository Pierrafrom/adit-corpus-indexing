"""TD2 — Tokenizer: segment corpus XML into (doc_id, token) pairs."""

import logging
from pathlib import Path

from lxml import etree

logger = logging.getLogger(__name__)


def load_corpus(corpus_path: Path) -> etree._Element:
    """Parse corpus.xml and return the root <corpus> element."""
    # TODO: parse corpus_path with lxml and return root
    raise NotImplementedError


def get_text_fields(document: etree._Element) -> tuple[str, str]:
    """Return (doc_id, text) for a <document> element.

    doc_id is the content of <article>.
    text is the concatenation of <titre> and <texte>.
    """
    # TODO: extract <article>, <titre>, <texte> from document element
    raise NotImplementedError


def tokenize(text: str) -> list[str]:
    """Split a text into lowercase tokens (letters only, no punctuation).

    Returns a list of non-empty token strings.
    """
    # TODO: lowercase, split on non-alphabetic characters, filter empty strings
    raise NotImplementedError


def segmente(corpus_path: Path, output_path: Path) -> None:
    """Segment all titles and texts from corpus.xml into a TSV file.

    Output format (one token per line, tab-separated):
        doc_id\\ttoken

    Args:
        corpus_path: path to corpus.xml produced by TD1.
        output_path: path to write the tokens TSV (e.g. outputs/tokens.tsv).
    """
    # TODO:
    #   1. load_corpus(corpus_path)
    #   2. for each <document>, call get_text_fields() then tokenize()
    #   3. write (doc_id, token) rows to output_path as UTF-8 TSV
    #   4. log total number of tokens written
    raise NotImplementedError
