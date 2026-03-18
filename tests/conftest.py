"""Shared pytest fixtures for adit_corpus_indexing tests."""

from datetime import date
from pathlib import Path

import pytest
from bs4 import BeautifulSoup

from adit_corpus_indexing.models import Article, Contact, Image, Person

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture()
def mini_corpus_path() -> Path:
    """Path to the small 3-document corpus XML fixture for TD2 tests."""
    return FIXTURES_DIR / "mini_corpus.xml"


@pytest.fixture()
def sample_html_path() -> Path:
    """Path to the complete sample bulletin HTML fixture."""
    return FIXTURES_DIR / "sample_article.html"


@pytest.fixture()
def minimal_html_path() -> Path:
    """Path to the minimal (almost empty) bulletin HTML fixture."""
    return FIXTURES_DIR / "minimal_article.html"


@pytest.fixture()
def sample_soup(sample_html_path: Path) -> BeautifulSoup:
    """BeautifulSoup object for the complete sample fixture."""
    return BeautifulSoup(sample_html_path.read_bytes(), "html.parser")


@pytest.fixture()
def minimal_soup(minimal_html_path: Path) -> BeautifulSoup:
    """BeautifulSoup object for the minimal fixture (all fields absent)."""
    return BeautifulSoup(minimal_html_path.read_bytes(), "html.parser")


@pytest.fixture()
def sample_article() -> Article:
    """A fully populated Article for xml_builder tests."""
    return Article(
        code="67068",
        bulletin="BE France 258",
        date=date(2011, 6, 21),
        rubrique="Physique",
        title="Mathias Fink, un bel exemple de chercheur qui innove",
        author=Person(name="Jean Dupont", email="jean.dupont@adit.fr"),
        body="Premier paragraphe.\n\nDeuxième paragraphe.",
        images=[Image(url="images/photo.jpg", legend="Photo de test")],
        contacts=[
            Contact(
                name="Institut Langevin",
                email="contact@langevin.fr",
                url="http://www.institut-langevin.fr",
                phone="01 23 45 67 89",
            )
        ],
    )


@pytest.fixture()
def minimal_article() -> Article:
    """An Article with all optional fields absent."""
    return Article(
        code="",
        bulletin="",
        date=None,
        rubrique="",
        title="",
        author=None,
        body="",
        images=[],
        contacts=[],
    )
