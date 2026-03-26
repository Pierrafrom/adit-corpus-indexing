"""TD2 — Tokenizer: segment corpus XML into (doc_id, token) pairs."""

import logging
import re
from pathlib import Path

from lxml import etree

logger = logging.getLogger(__name__)

# Matches sequences of Unicode letters (ASCII + accented Latin-1 supplement).
_WORD_RE = re.compile(r"[a-zA-ZÀ-ÿ]+")

# French elision prefixes: l', d', j', m', t', s', c', n', qu'
# The apostrophe can be a straight quote (') or a typographic one (')
_ELISION_RE = re.compile(r"\b(qu|[ldjmtscn])['\u2019]", re.IGNORECASE)


def normalize_elisions(text: str) -> str:
    """Remove French elision prefixes before tokenization.

    Strips clitic forms like ``l'``, ``d'``, ``j'``, ``m'``, ``t'``, ``s'``,
    ``c'``, ``n'``, and ``qu'`` (both straight and typographic apostrophes) so
    that ``l'innovation`` is tokenized as ``innovation`` rather than ``l`` +
    ``innovation``.

    Args:
        text: raw text, possibly containing French elisions.

    Returns:
        Text with elision prefixes removed.
    """
    return _ELISION_RE.sub("", text)


def load_corpus(corpus_path: Path) -> etree._Element:
    """Parse corpus.xml and return the root <corpus> element.

    Args:
        corpus_path: path to a corpus XML file produced by the TD1 pipeline.

    Returns:
        The root <corpus> lxml element.
    """
    tree = etree.parse(str(corpus_path))
    return tree.getroot()


def get_text_fields(document: etree._Element) -> tuple[str, str]:
    """Return (doc_id, text) for a <document> element.

    doc_id is the content of <article> (article number).
    text is the concatenation of <titre> and <texte>, separated by a space.
    Missing or empty elements contribute an empty string.

    Args:
        document: a <document> lxml element from the corpus.

    Returns:
        A (doc_id, text) tuple — both strings, never None.
    """
    article_el = document.find("article")
    titre_el = document.find("titre")
    texte_el = document.find("texte")

    doc_id = (article_el.text or "").strip() if article_el is not None else ""
    titre = (titre_el.text or "").strip() if titre_el is not None else ""
    texte = (texte_el.text or "").strip() if texte_el is not None else ""

    text = normalize_elisions(f"{titre} {texte}".strip())
    return doc_id, text


def tokenize(text: str) -> list[str]:
    """Split a text into lowercase tokens (letters only, no punctuation).

    Sequences of Unicode letters (ASCII + accented Latin-1) are extracted.
    Numbers and punctuation are treated as separators and discarded.

    Args:
        text: raw text to tokenize.

    Returns:
        List of lowercase token strings — may be empty.
    """
    return _WORD_RE.findall(text.lower())


def segmente(corpus_path: Path, output_path: Path) -> None:
    """Segment all titles and texts from corpus.xml into a TSV file.

    Output format (one token per line, tab-separated, no header):
        doc_id\\ttoken

    Args:
        corpus_path: path to corpus.xml produced by TD1.
        output_path: path to write the tokens TSV (e.g. outputs/tokens.tsv).
    """
    root = load_corpus(corpus_path)
    rows: list[str] = []

    for document in root.findall("document"):
        doc_id, text = get_text_fields(document)
        if not doc_id:
            logger.warning("segmente: <document> has no <article> id — skipping")
            continue
        for token in tokenize(text):
            rows.append(f"{doc_id}\t{token}")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(rows))
        if rows:
            f.write("\n")

    logger.info("segmente: wrote %d tokens → %s", len(rows), output_path)
