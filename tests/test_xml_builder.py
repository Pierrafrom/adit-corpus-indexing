"""Tests for adit_corpus_indexing.xml_builder."""

from datetime import date
from pathlib import Path

import pytest
from lxml import etree

from adit_corpus_indexing.models import Article, Contact, Person
from adit_corpus_indexing.io.xml_builder import CorpusBuilder, build_document_element

# ---------------------------------------------------------------------------
# build_document_element
# ---------------------------------------------------------------------------


def test_build_document_element_returns_element(sample_article: Article) -> None:
    doc = build_document_element(sample_article)
    assert isinstance(doc, etree._Element)
    assert doc.tag == "document"


def test_build_document_element_has_required_children(sample_article: Article) -> None:
    doc = build_document_element(sample_article)
    tags = {child.tag for child in doc}
    for required in (
        "article",
        "bulletin",
        "date",
        "rubrique",
        "titre",
        "auteur",
        "texte",
    ):
        assert required in tags


def test_build_document_element_sets_code(sample_article: Article) -> None:
    doc = build_document_element(sample_article)
    assert doc.findtext("article") == "67068"


def test_build_document_element_sets_bulletin(sample_article: Article) -> None:
    doc = build_document_element(sample_article)
    assert doc.findtext("bulletin") == "BE France 258"


def test_build_document_element_sets_date(sample_article: Article) -> None:
    doc = build_document_element(sample_article)
    assert doc.findtext("date") == "21/06/2011"


def test_build_document_element_sets_rubrique(sample_article: Article) -> None:
    doc = build_document_element(sample_article)
    assert doc.findtext("rubrique") == "Physique"


def test_build_document_element_sets_titre(sample_article: Article) -> None:
    doc = build_document_element(sample_article)
    assert "Mathias Fink" in (doc.findtext("titre") or "")


def test_build_document_element_sets_auteur(sample_article: Article) -> None:
    doc = build_document_element(sample_article)
    assert doc.findtext("auteur") == "Jean Dupont"


def test_build_document_element_sets_texte(sample_article: Article) -> None:
    doc = build_document_element(sample_article)
    assert "paragraphe" in (doc.findtext("texte") or "")


def test_build_document_element_images_element(sample_article: Article) -> None:
    doc = build_document_element(sample_article)
    images_el = doc.find("images")
    assert images_el is not None
    assert len(images_el) == 1
    assert images_el[0].findtext("urlImage") == "images/photo.jpg"
    assert images_el[0].findtext("legendeImage") == "Photo de test"


def test_build_document_element_no_images(minimal_article: Article) -> None:
    doc = build_document_element(minimal_article)
    images_el = doc.find("images")
    assert images_el is not None
    assert len(images_el) == 0


def test_build_document_element_none_date_gives_empty(minimal_article: Article) -> None:
    doc = build_document_element(minimal_article)
    assert doc.findtext("date") == ""


def test_build_document_element_none_author_gives_empty(
    minimal_article: Article,
) -> None:
    doc = build_document_element(minimal_article)
    assert doc.findtext("auteur") == ""


def test_build_document_element_contacts_joined(sample_article: Article) -> None:
    doc = build_document_element(sample_article)
    contact_text = doc.findtext("contact") or ""
    assert "Institut Langevin" in contact_text


def test_build_document_element_no_contacts_gives_empty(
    minimal_article: Article,
) -> None:
    doc = build_document_element(minimal_article)
    assert doc.findtext("contact") == ""


# ---------------------------------------------------------------------------
# CorpusBuilder
# ---------------------------------------------------------------------------


def test_corpus_builder_build_returns_element(sample_article: Article) -> None:
    builder = CorpusBuilder()
    builder.add_article(sample_article)
    root = builder.build()
    assert root.tag == "corpus"


def test_corpus_builder_add_article_increases_count(sample_article: Article) -> None:
    builder = CorpusBuilder()
    builder.add_article(sample_article)
    builder.add_article(sample_article)
    assert len(builder.build()) == 2


def test_corpus_builder_empty_corpus_has_no_children() -> None:
    builder = CorpusBuilder()
    assert len(builder.build()) == 0


def test_corpus_builder_write_creates_file(
    sample_article: Article, tmp_path: Path
) -> None:
    builder = CorpusBuilder()
    builder.add_article(sample_article)
    out = tmp_path / "corpus.xml"
    builder.write(out)
    assert out.exists()
    assert out.stat().st_size > 0


def test_corpus_builder_write_produces_valid_xml(
    sample_article: Article, tmp_path: Path
) -> None:
    builder = CorpusBuilder()
    builder.add_article(sample_article)
    out = tmp_path / "corpus.xml"
    builder.write(out)
    tree = etree.parse(str(out))
    root = tree.getroot()
    assert root.tag == "corpus"
    assert len(root) == 1


def test_corpus_builder_write_creates_parent_dirs(
    sample_article: Article, tmp_path: Path
) -> None:
    builder = CorpusBuilder()
    builder.add_article(sample_article)
    out = tmp_path / "nested" / "deep" / "corpus.xml"
    builder.write(out)
    assert out.exists()


def test_corpus_builder_write_utf8_encoding(
    tmp_path: Path,
) -> None:
    article = Article(
        code="1",
        bulletin="BE Test 1",
        date=date(2023, 1, 1),
        rubrique="Énergie",
        title="Titre avec accents : éàü",
        author=Person(name="André Müller", email=""),
        body="Corps avec des caractères spéciaux : éàü.",
        images=[],
        contacts=[],
    )
    builder = CorpusBuilder()
    builder.add_article(article)
    out = tmp_path / "corpus.xml"
    builder.write(out)
    content = out.read_text(encoding="utf-8")
    assert "Énergie" in content
    assert "André Müller" in content


def test_corpus_builder_multiple_articles(tmp_path: Path) -> None:
    articles = [
        Article(
            code=str(i),
            bulletin=f"BE Test {i}",
            date=None,
            rubrique="",
            title=f"Article {i}",
            author=None,
            body="",
            images=[],
            contacts=[],
        )
        for i in range(5)
    ]
    builder = CorpusBuilder()
    for a in articles:
        builder.add_article(a)
    out = tmp_path / "corpus.xml"
    builder.write(out)
    tree = etree.parse(str(out))
    assert len(tree.getroot()) == 5


@pytest.mark.parametrize("contact_count", [0, 1, 3])
def test_build_document_element_contact_count(contact_count: int) -> None:
    contacts = [
        Contact(name=f"Contact {i}", email="", url="", phone="")
        for i in range(contact_count)
    ]
    article = Article(
        code="x",
        bulletin="",
        date=None,
        rubrique="",
        title="",
        author=None,
        body="",
        images=[],
        contacts=contacts,
    )
    doc = build_document_element(article)
    contact_text = doc.findtext("contact") or ""
    if contact_count == 0:
        assert contact_text == ""
    else:
        assert contact_text != ""
