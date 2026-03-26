"""Build corpus XML from parsed Article objects using lxml.etree."""

import logging
from pathlib import Path

from lxml import etree

from ..models import Article

logger = logging.getLogger(__name__)


def _set_text(element: etree._Element, value: str | None) -> None:
    """Set element text to *value*, or empty string if None."""
    element.text = value if value is not None else ""


def build_document_element(article: Article) -> etree._Element:
    """Build a <document> XML element from a single Article."""
    doc = etree.Element("document")

    article_el = etree.SubElement(doc, "article")
    _set_text(article_el, article.code)

    bulletin_el = etree.SubElement(doc, "bulletin")
    _set_text(bulletin_el, article.bulletin)

    date_el = etree.SubElement(doc, "date")
    _set_text(date_el, article.date.strftime("%d/%m/%Y") if article.date else None)

    rubrique_el = etree.SubElement(doc, "rubrique")
    _set_text(rubrique_el, article.rubrique)

    titre_el = etree.SubElement(doc, "titre")
    _set_text(titre_el, article.title)

    auteur_el = etree.SubElement(doc, "auteur")
    _set_text(auteur_el, article.author.name if article.author else None)

    texte_el = etree.SubElement(doc, "texte")
    _set_text(texte_el, article.body)

    images_el = etree.SubElement(doc, "images")
    for image in article.images:
        image_el = etree.SubElement(images_el, "image")
        url_el = etree.SubElement(image_el, "urlImage")
        _set_text(url_el, image.url)
        legende_el = etree.SubElement(image_el, "legendeImage")
        _set_text(legende_el, image.legend)

    contact_el = etree.SubElement(doc, "contact")
    _set_text(
        contact_el,
        " | ".join(c.name for c in article.contacts if c.name) or None,
    )

    return doc


class CorpusBuilder:
    """Aggregates Article objects and serialises them to a <corpus> XML tree."""

    def __init__(self) -> None:
        self._root: etree._Element = etree.Element("corpus")

    def add_article(self, article: Article) -> None:
        """Append one Article as a <document> child of the corpus root."""
        doc = build_document_element(article)
        self._root.append(doc)
        logger.debug("Added article %s to corpus", article.code)

    def build(self) -> etree._Element:
        """Return the complete corpus XML element."""
        return self._root

    def write(self, output_path: Path) -> None:
        """Serialise the corpus to *output_path* as indented UTF-8 XML."""
        tree = etree.ElementTree(self._root)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        tree.write(
            str(output_path),
            encoding="utf-8",
            xml_declaration=True,
            pretty_print=True,
        )
        logger.info("Corpus written to %s (%d documents)", output_path, len(self._root))
