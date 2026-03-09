"""Tests for adit_corpus_indexing.parser."""

from datetime import date
from pathlib import Path

import pytest
from bs4 import BeautifulSoup, Tag

from adit_corpus_indexing.parser import (
    _email_from_tag,
    _name_from_tag,
    _phone_from_text,
    _url_from_tag,
    load_soup,
    parse_article,
    parse_author,
    parse_body,
    parse_bulletin,
    parse_code,
    parse_contacts,
    parse_date,
    parse_images,
    parse_rubrique,
    parse_title,
)


def _soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "html.parser")


# ---------------------------------------------------------------------------
# load_soup
# ---------------------------------------------------------------------------


def test_load_soup_returns_beautifulsoup(sample_html_path: Path) -> None:
    soup = load_soup(sample_html_path)
    assert isinstance(soup, BeautifulSoup)


def test_load_soup_parses_content(sample_html_path: Path) -> None:
    soup = load_soup(sample_html_path)
    assert soup.find("body") is not None


# ---------------------------------------------------------------------------
# parse_code
# ---------------------------------------------------------------------------


def test_parse_code_returns_code(sample_soup: BeautifulSoup) -> None:
    assert parse_code(sample_soup) == "67068"


def test_parse_code_returns_empty_when_missing(minimal_soup: BeautifulSoup) -> None:
    assert parse_code(minimal_soup) == ""


def test_parse_code_returns_empty_when_no_anchor() -> None:
    soup = _soup('<span class="style15">Code brève :</span>')
    assert parse_code(soup) == ""


# ---------------------------------------------------------------------------
# parse_bulletin
# ---------------------------------------------------------------------------


def test_parse_bulletin_returns_bulletin(sample_soup: BeautifulSoup) -> None:
    assert parse_bulletin(sample_soup) == "BE France 258"


def test_parse_bulletin_returns_empty_when_missing(minimal_soup: BeautifulSoup) -> None:
    assert parse_bulletin(minimal_soup) == ""


# ---------------------------------------------------------------------------
# parse_date
# ---------------------------------------------------------------------------


def test_parse_date_returns_date(sample_soup: BeautifulSoup) -> None:
    result = parse_date(sample_soup)
    assert result == date(2011, 6, 21)


def test_parse_date_returns_none_when_missing(minimal_soup: BeautifulSoup) -> None:
    assert parse_date(minimal_soup) is None


def test_parse_date_returns_none_on_malformed_date() -> None:
    html = """
    <p>
      <span class="style32">BE France 258</span>
      <span class="style42">not-a-date</span>
    </p>
    """
    assert parse_date(_soup(html)) is None


def test_parse_date_returns_none_when_no_style42_in_p() -> None:
    html = '<p><span class="style32">BE France 1</span></p>'
    assert parse_date(_soup(html)) is None


# ---------------------------------------------------------------------------
# parse_rubrique
# ---------------------------------------------------------------------------


def test_parse_rubrique_returns_rubrique(sample_soup: BeautifulSoup) -> None:
    assert parse_rubrique(sample_soup) == "Physique"


def test_parse_rubrique_returns_empty_when_missing(minimal_soup: BeautifulSoup) -> None:
    assert parse_rubrique(minimal_soup) == ""


def test_parse_rubrique_handles_accented_section() -> None:
    html = '<p class="style96"><span class="style42">Énergies renouvelables</span></p>'
    assert parse_rubrique(_soup(html)) == "Énergies renouvelables"


# ---------------------------------------------------------------------------
# parse_title
# ---------------------------------------------------------------------------


def test_parse_title_returns_title(sample_soup: BeautifulSoup) -> None:
    assert "Mathias Fink" in parse_title(sample_soup)


def test_parse_title_returns_empty_when_missing(minimal_soup: BeautifulSoup) -> None:
    assert parse_title(minimal_soup) == ""


def test_parse_title_handles_accented_chars() -> None:
    html = '<span class="style17">Étude sur l\'énergie éolienne</span>'
    assert parse_title(_soup(html)) == "Étude sur l'énergie éolienne"


# ---------------------------------------------------------------------------
# parse_body
# ---------------------------------------------------------------------------


def test_parse_body_returns_text(sample_soup: BeautifulSoup) -> None:
    body = parse_body(sample_soup)
    assert len(body) > 0
    assert "Premier paragraphe" in body


def test_parse_body_joins_paragraphs_with_double_newline(
    sample_soup: BeautifulSoup,
) -> None:
    body = parse_body(sample_soup)
    assert "\n\n" in body


def test_parse_body_returns_empty_when_missing(minimal_soup: BeautifulSoup) -> None:
    assert parse_body(minimal_soup) == ""


def test_parse_body_ignores_non_style95_first_span() -> None:
    html = '<p class="style96"><span class="style42">Not body text</span></p>'
    assert parse_body(_soup(html)) == ""


# ---------------------------------------------------------------------------
# parse_author
# ---------------------------------------------------------------------------


def test_parse_author_returns_person(sample_soup: BeautifulSoup) -> None:
    author = parse_author(sample_soup)
    assert author is not None
    assert author.name == "Jean Dupont"
    assert author.email == "jean.dupont@adit.fr"


def test_parse_author_returns_none_when_missing(minimal_soup: BeautifulSoup) -> None:
    assert parse_author(minimal_soup) is None


def test_parse_author_returns_none_when_no_style95_in_cell() -> None:
    html = """
    <table><tr>
      <td><span class="style28">Rédacteur</span></td>
      <td><span class="style99">No style95 here</span></td>
    </tr></table>
    """
    assert parse_author(_soup(html)) is None


# ---------------------------------------------------------------------------
# parse_contacts
# ---------------------------------------------------------------------------


def test_parse_contacts_returns_contacts(sample_soup: BeautifulSoup) -> None:
    contacts = parse_contacts(sample_soup)
    assert len(contacts) >= 1
    names = [c.name for c in contacts]
    assert any("Institut Langevin" in n for n in names)


def test_parse_contacts_returns_empty_when_missing(minimal_soup: BeautifulSoup) -> None:
    assert parse_contacts(minimal_soup) == []


def test_parse_contacts_extracts_email() -> None:
    html = """
    <table><tr>
      <td><span class="style28">Pour en savoir plus</span></td>
      <td>
        <p class="style44">
          <span class="style85">Org
            <a href="mailto:org@example.com">org@example.com</a></span>
        </p>
      </td>
    </tr></table>
    """
    contacts = parse_contacts(_soup(html))
    assert len(contacts) == 1
    assert contacts[0].email == "org@example.com"


def test_parse_contacts_filters_empty_contacts() -> None:
    html = """
    <table><tr>
      <td><span class="style28">Pour en savoir plus</span></td>
      <td>
        <p class="style44"><span class="style85">   </span></p>
      </td>
    </tr></table>
    """
    assert parse_contacts(_soup(html)) == []


# ---------------------------------------------------------------------------
# parse_images
# ---------------------------------------------------------------------------


def test_parse_images_returns_urls(sample_soup: BeautifulSoup) -> None:
    images = parse_images(sample_soup)
    assert len(images) == 1
    assert "photo_mathias_fink.jpg" in images[0]


def test_parse_images_excludes_clear_gif(sample_soup: BeautifulSoup) -> None:
    images = parse_images(sample_soup)
    assert not any("_clear.gif" in url for url in images)


def test_parse_images_excludes_resources(sample_soup: BeautifulSoup) -> None:
    images = parse_images(sample_soup)
    assert not any("Resources/" in url for url in images)


def test_parse_images_returns_empty_when_no_sidebar(
    minimal_soup: BeautifulSoup,
) -> None:
    assert parse_images(minimal_soup) == []


# ---------------------------------------------------------------------------
# parse_article (integration)
# ---------------------------------------------------------------------------


def test_parse_article_returns_article(sample_html_path: Path) -> None:
    from adit_corpus_indexing.models import Article

    article = parse_article(sample_html_path)
    assert isinstance(article, Article)
    assert article.code == "67068"
    assert article.bulletin == "BE France 258"
    assert article.date == date(2011, 6, 21)


def test_parse_article_does_not_crash_on_minimal(minimal_html_path: Path) -> None:
    article = parse_article(minimal_html_path)
    assert article.code == ""
    assert article.date is None
    assert article.contacts == []


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def test_email_from_tag_finds_mailto() -> None:
    parent = _soup('<span><a href="mailto:test@example.com">test</a></span>')
    span = parent.find("span")
    assert isinstance(span, Tag)
    assert _email_from_tag(span) == "test@example.com"


def test_email_from_tag_finds_text_pattern() -> None:
    soup = _soup("<span>Contact - email : user@domain.fr</span>")
    span = soup.find("span")
    assert isinstance(span, Tag)
    assert _email_from_tag(span) == "user@domain.fr"


def test_email_from_tag_returns_empty_when_absent() -> None:
    soup = _soup("<span>No email here</span>")
    span = soup.find("span")
    assert isinstance(span, Tag)
    assert _email_from_tag(span) == ""


def test_url_from_tag_finds_http_href() -> None:
    soup = _soup('<span><a href="http://example.com">link</a></span>')
    span = soup.find("span")
    assert isinstance(span, Tag)
    assert _url_from_tag(span) == "http://example.com"


def test_url_from_tag_finds_site_internet_pattern() -> None:
    soup = _soup("<span>Site Internet : www.example.com</span>")
    span = soup.find("span")
    assert isinstance(span, Tag)
    url = _url_from_tag(span)
    assert "example.com" in url


def test_url_from_tag_returns_empty_when_absent() -> None:
    soup = _soup("<span>No URL here</span>")
    span = soup.find("span")
    assert isinstance(span, Tag)
    assert _url_from_tag(span) == ""


def test_phone_from_text_finds_tel_pattern() -> None:
    assert _phone_from_text("Tél : 01 23 45 67 89") == "01 23 45 67 89"


def test_phone_from_text_finds_telephone_pattern() -> None:
    assert _phone_from_text("Téléphone : +33 1 23 45 67 89") == "+33 1 23 45 67 89"


def test_phone_from_text_returns_empty_when_absent() -> None:
    assert _phone_from_text("No phone here") == ""


def test_name_from_tag_strips_email() -> None:
    soup = _soup("<span>Jean Dupont - email : jean@adit.fr</span>")
    span = soup.find("span")
    assert isinstance(span, Tag)
    name = _name_from_tag(span)
    assert "email" not in name.lower()
    assert "Jean Dupont" in name


def test_name_from_tag_handles_empty_string() -> None:
    soup = _soup("<span></span>")
    span = soup.find("span")
    assert isinstance(span, Tag)
    assert _name_from_tag(span) == ""


@pytest.mark.parametrize(
    "text,expected",
    [
        ("Tél : 01 23 45 67 89", "01 23 45 67 89"),
        ("tel: 0033612345678", "0033612345678"),
        ("", ""),
    ],
)
def test_phone_from_text_parametrized(text: str, expected: str) -> None:
    assert _phone_from_text(text) == expected
