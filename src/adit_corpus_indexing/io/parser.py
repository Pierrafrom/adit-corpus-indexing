"""Parser for ADIT HTML bulletin files."""

import logging
import re
from datetime import date
from pathlib import Path

from bs4 import BeautifulSoup, Tag

from ..models import Article, Contact, Image, Person

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------


def load_soup(path: Path) -> BeautifulSoup:
    """Load an HTML file and return a BeautifulSoup object."""
    return BeautifulSoup(path.read_bytes(), "html.parser")


# ---------------------------------------------------------------------------
# Simple fields
# ---------------------------------------------------------------------------


def parse_code(soup: BeautifulSoup) -> str:
    """Article code (e.g. "67068") — bottom-right section, style15 + <a>."""
    for span in soup.find_all("span", class_="style15"):
        if "Code" in span.get_text():
            a_tag = span.find_next("a")
            if isinstance(a_tag, Tag):
                return a_tag.get_text(strip=True)
    logger.warning("Missing article code")
    return ""


def parse_bulletin(soup: BeautifulSoup) -> str:
    """Bulletin identifier (e.g. "BE France 258") — style32."""
    tag = soup.find("span", class_="style32")
    if not isinstance(tag, Tag):
        logger.warning("Missing bulletin number (style32 not found)")
        return ""
    return tag.get_text(strip=True)


def parse_date(soup: BeautifulSoup) -> date | None:
    """Article date — style42 in the same <p> as style32."""
    style32 = soup.find("span", class_="style32")
    if not isinstance(style32, Tag):
        logger.warning("Missing date: style32 anchor not found")
        return None
    p_tag = style32.find_parent("p")
    if not isinstance(p_tag, Tag):
        logger.warning("Missing date: style32 has no parent <p>")
        return None
    style42 = p_tag.find("span", class_="style42")
    if not isinstance(style42, Tag):
        logger.warning("Missing date: style42 not found in parent <p>")
        return None
    raw = style42.get_text(strip=True)
    try:
        parts = raw.split("/")
        day, month, year = int(parts[0]), int(parts[1]), int(parts[2])
        return date(year, month, day)
    except (ValueError, IndexError):
        logger.warning("Unparseable date value: %r", raw)
        return None


def parse_rubrique(soup: BeautifulSoup) -> str:
    """Section name — first span.style42 inside a p.style96."""
    for p in soup.find_all("p", class_="style96"):
        span = p.find("span", class_="style42")
        if isinstance(span, Tag):
            return span.get_text(strip=True)
    logger.warning("Missing rubrique (no style42 in style96)")
    return ""


def parse_title(soup: BeautifulSoup) -> str:
    """Article title — style17 (unique per file)."""
    tag = soup.find("span", class_="style17")
    if not isinstance(tag, Tag):
        logger.warning("Missing title (style17 not found)")
        return ""
    return tag.get_text(strip=True)


def parse_body(soup: BeautifulSoup) -> str:
    """Article body — p.style96 paragraphs whose first child is span.style95."""
    paragraphs: list[str] = []
    for p in soup.find_all("p", class_="style96"):
        first_span = p.find("span")
        if isinstance(first_span, Tag) and "style95" in first_span.get("class", []):
            text = p.get_text(separator="\n", strip=True)
            if text:
                paragraphs.append(text)
    if not paragraphs:
        logger.warning("Empty article body")
    return "\n\n".join(paragraphs)


# ---------------------------------------------------------------------------
# Extraction helpers (email / url / phone / name) for Person and Contact
# ---------------------------------------------------------------------------

_RE_EMAIL_LABEL = re.compile(r"\s*-?\s*email\s*:\s*\S+", re.IGNORECASE)
_RE_URL_INLINE = re.compile(r"\s*-?\s*https?://\S+", re.IGNORECASE)
_RE_SITE_LABEL = re.compile(r"\s*-?\s*Site\s+Internet\s*:\s*\S+", re.IGNORECASE)
_RE_PHONE_LABEL = re.compile(
    r"\s*-?\s*t[eé]l(?:[eé]phone)?\s*:\s*[\d\s\+\-\(\)\.]{4,}", re.IGNORECASE
)


def _email_from_tag(tag: Tag) -> str:
    """Email from <a href="mailto:..."> or 'email : ...' pattern in text."""
    for a in tag.find_all("a"):
        href = str(a.get("href", ""))
        if href.startswith("mailto:"):
            return href[7:]
    m = re.search(r"email\s*:\s*(\S+)", tag.get_text(), re.IGNORECASE)
    return m.group(1) if m else ""


def _url_from_tag(tag: Tag) -> str:
    """URL from <a href="http..."> or 'Site Internet : www...' in text."""
    for a in tag.find_all("a"):
        href = str(a.get("href", ""))
        if href.startswith("http") and not href.startswith("mailto:"):
            return href
    m_url = re.search(r"https?://\S+", tag.get_text(), re.IGNORECASE)
    if m_url:
        return m_url.group(0).rstrip("/ ")
    m_site = re.search(r"Site\s+Internet\s*:\s*(\S+)", tag.get_text(), re.IGNORECASE)
    if m_site:
        raw = m_site.group(1).strip("/ ")
        return raw if raw.startswith("http") else f"http://{raw}"
    return ""


def _phone_from_text(text: str) -> str:
    """Phone number from a 'tel : ...' pattern in text."""
    m = re.search(
        r"t[eé]l(?:[eé]phone)?\s*:\s*([\d\s\+\-\(\)\.]{4,})", text, re.IGNORECASE
    )
    return m.group(1).strip() if m else ""


def _name_from_tag(tag: Tag) -> str:
    """Contact name: raw text with email, url, and phone stripped out."""
    text = tag.get_text(" ", strip=True)
    text = _RE_EMAIL_LABEL.sub("", text)
    text = _RE_URL_INLINE.sub("", text)
    text = _RE_SITE_LABEL.sub("", text)
    text = _RE_PHONE_LABEL.sub("", text)
    parts = [p.strip(" -:/") for p in text.split(" - ")]
    return " - ".join(p for p in parts if p)


def _contact_from_span(span: Tag) -> Contact:
    """Build a Contact from a span element."""
    return Contact(
        name=_name_from_tag(span),
        email=_email_from_tag(span),
        url=_url_from_tag(span),
        phone=_phone_from_text(span.get_text()),
    )


# ---------------------------------------------------------------------------
# Fields requiring table navigation (label → neighbouring cell)
# ---------------------------------------------------------------------------


def _find_sibling_cell(soup: BeautifulSoup, label: str) -> Tag | None:
    """Find the <td> neighbouring the <td> whose span.style28 matches *label*."""
    for span in soup.find_all("span", class_="style28"):
        if label in span.get_text():
            td = span.find_parent("td")
            if isinstance(td, Tag):
                next_td = td.find_next_sibling("td")
                if isinstance(next_td, Tag):
                    return next_td
    return None


def parse_author(soup: BeautifulSoup) -> Person | None:
    """Author — name and email from the cell next to the 'Rédacteur' label."""
    td = _find_sibling_cell(soup, "Rédacteur")
    if not isinstance(td, Tag):
        logger.warning("Missing author: 'Rédacteur' label not found")
        return None
    span = td.find("span", class_="style95")
    if not isinstance(span, Tag):
        logger.warning("Missing author: style95 span not found in author cell")
        return None
    text = span.get_text(" ", strip=True)
    text = re.sub(r"^ADIT\s*-\s*", "", text, flags=re.IGNORECASE)
    email = _email_from_tag(span)
    name = _RE_EMAIL_LABEL.sub("", text).strip(" -")
    return Person(name=name, email=email)


def parse_contacts(soup: BeautifulSoup) -> list[Contact]:
    """Contacts — all p.style44 > span.style85 in the cell next to the label."""
    td = _find_sibling_cell(soup, "Pour en savoir plus")
    if not isinstance(td, Tag):
        logger.warning("Missing contacts: 'Pour en savoir plus' label not found")
        return []
    contacts: list[Contact] = []
    for p in td.find_all("p", class_="style44"):
        if not isinstance(p, Tag):
            continue
        span = p.find("span", class_="style85")
        if not isinstance(span, Tag):
            continue
        contact = _contact_from_span(span)
        if contact.name or contact.email or contact.url:
            contacts.append(contact)
    return contacts


# ---------------------------------------------------------------------------
# Images
# ---------------------------------------------------------------------------


def parse_images(soup: BeautifulSoup) -> list[Image]:
    """Article images with captions from centered div blocks in the article body."""
    images: list[Image] = []

    def _has_text_align(s: str | None) -> bool:
        return s is not None and "text-align" in s

    for div in soup.find_all("div", style=_has_text_align):
        img = div.find("img")
        if not isinstance(img, Tag):
            continue
        src = str(img.get("src", ""))
        if "_clear.gif" in src or "/Resources" in src:
            continue
        legend_span = div.find("span", class_="style21")
        legend = (
            legend_span.get_text(strip=True) if isinstance(legend_span, Tag) else None
        )
        images.append(Image(url=src, legend=legend))
    return images


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


class ArticleParser:
    """Parses a single ADIT bulletin HTML file into an Article."""

    def parse(self, path: Path) -> Article:
        """Parse an HTML bulletin file and return an Article."""
        soup = load_soup(path)
        return Article(
            code=parse_code(soup),
            bulletin=parse_bulletin(soup),
            date=parse_date(soup),
            rubrique=parse_rubrique(soup),
            title=parse_title(soup),
            author=parse_author(soup),
            body=parse_body(soup),
            images=parse_images(soup),
            contacts=parse_contacts(soup),
        )


def parse_article(path: Path) -> Article:
    """Parse an HTML bulletin file and return an Article."""
    return ArticleParser().parse(path)
