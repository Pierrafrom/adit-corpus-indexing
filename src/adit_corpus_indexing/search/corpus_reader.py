"""CorpusReader: loads corpus_final.xml and provides document metadata.

Usage::

    reader = CorpusReader(
        Path("outputs/td3/corpus_final.xml"),
        display_corpus_path=Path("outputs/td3/corpus_filtered.xml"),
    )
    meta = reader.get(67068)
    if meta:
        print(meta.titre, meta.date, meta.rubrique)
        print(meta.original_texte)  # original (non-lemmatised) body text
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from lxml import etree

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DocumentMeta:
    """Metadata and text content for one document.

    Attributes:
        doc_id:        numeric article identifier (``<article>`` element).
        titre:         lemmatized title text.
        date:          publication date as ``dd/mm/yyyy``.
        rubrique:      section name (original capitalisation from XML).
        auteur:        author name or empty string.
        texte:         lemmatized body text (used for keyword position finding).
        has_images:    True when the document contains at least one ``<image>``.
        original_texte: original (non-lemmatised) body text for display; equals
                       ``texte`` when no display corpus is loaded.
    """

    doc_id: int
    titre: str
    date: str
    rubrique: str
    auteur: str
    texte: str
    has_images: bool
    original_texte: str = field(default="")


def _text(el: etree._Element | None) -> str:
    if el is None:
        return ""
    return (el.text or "").strip()


class CorpusReader:
    """Loads corpus_final.xml once and exposes per-document metadata.

    All documents are held in memory (~6 MB XML parsed into ~326 dicts).
    Call :meth:`get` to retrieve a single document or use the set helpers
    to bulk-filter by image presence.
    """

    def __init__(
        self,
        corpus_path: Path,
        display_corpus_path: Path | None = None,
    ) -> None:
        self._docs: dict[int, DocumentMeta] = {}
        self._with_images: set[int] = set()
        self._without_images: set[int] = set()
        display_texts: dict[int, str] = {}
        if display_corpus_path is not None and display_corpus_path.exists():
            display_texts = self._load_display_texts(display_corpus_path)
            logger.info(
                "CorpusReader: display corpus loaded (%d texts)", len(display_texts)
            )
        self._load(corpus_path, display_texts)

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def get(self, doc_id: int) -> DocumentMeta | None:
        """Return metadata for *doc_id*, or None if not found."""
        return self._docs.get(doc_id)

    def all_ids(self) -> set[int]:
        """Return all document identifiers in the corpus."""
        return set(self._docs.keys())

    def ids_with_images(self) -> set[int]:
        """Return doc_ids for documents that contain at least one image."""
        return self._with_images.copy()

    def ids_without_images(self) -> set[int]:
        """Return doc_ids for documents that contain no images."""
        return self._without_images.copy()

    def __len__(self) -> int:
        return len(self._docs)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _load(self, path: Path, display_texts: dict[int, str]) -> None:
        tree = etree.parse(str(path))
        root = tree.getroot()
        for doc_el in root.findall("document"):
            article_el = doc_el.find("article")
            if article_el is None or not article_el.text:
                continue
            try:
                doc_id = int(article_el.text.strip())
            except ValueError:
                continue

            has_images = self._has_images(doc_el)
            lemmatized_texte = _text(doc_el.find("texte"))
            meta = DocumentMeta(
                doc_id=doc_id,
                titre=_text(doc_el.find("titre")),
                date=_text(doc_el.find("date")),
                rubrique=_text(doc_el.find("rubrique")),
                auteur=_text(doc_el.find("auteur")),
                texte=lemmatized_texte,
                has_images=has_images,
                original_texte=display_texts.get(doc_id, lemmatized_texte),
            )
            self._docs[doc_id] = meta
            if has_images:
                self._with_images.add(doc_id)
            else:
                self._without_images.add(doc_id)

        logger.info(
            "CorpusReader: %d documents loaded (%d with images)",
            len(self._docs),
            len(self._with_images),
        )

    @staticmethod
    def _load_display_texts(path: Path) -> dict[int, str]:
        """Parse *path* (corpus_filtered.xml) and return {doc_id: original_texte}."""
        result: dict[int, str] = {}
        tree = etree.parse(str(path))
        for doc_el in tree.getroot().findall("document"):
            article_el = doc_el.find("article")
            if article_el is None or not article_el.text:
                continue
            try:
                doc_id = int(article_el.text.strip())
            except ValueError:
                continue
            result[doc_id] = _text(doc_el.find("texte"))
        return result

    @staticmethod
    def _has_images(doc_el: etree._Element) -> bool:
        images_el = doc_el.find("images")
        if images_el is None:
            return False
        return images_el.find("image") is not None
