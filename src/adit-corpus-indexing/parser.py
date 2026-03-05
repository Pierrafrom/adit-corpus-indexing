"""Parseur pour les bulletins HTML du corpus ADIT."""

import re
from datetime import date
from pathlib import Path

from bs4 import BeautifulSoup, Tag

from .models import Article, Contact, Person

_ENCODING = "utf-8"


# ---------------------------------------------------------------------------
# Chargement
# ---------------------------------------------------------------------------


def load_soup(path: Path) -> BeautifulSoup:
    return BeautifulSoup(path.read_bytes(), "html.parser")


# ---------------------------------------------------------------------------
# Champs simples
# ---------------------------------------------------------------------------


def parse_code(soup: BeautifulSoup) -> str:
    """Code brève ADIT (ex. "67068") — section bas-droite, style15 + <a>."""
    for span in soup.find_all("span", class_="style15"):
        if "Code" in span.get_text():
            a_tag = span.find_next("a")
            if isinstance(a_tag, Tag):
                return a_tag.get_text(strip=True)
    return ""


def parse_bulletin(soup: BeautifulSoup) -> str:
    """Numéro de bulletin (ex. "BE France 258") — style32."""
    tag = soup.find("span", class_="style32")
    return tag.get_text(strip=True) if isinstance(tag, Tag) else ""


def parse_date(soup: BeautifulSoup) -> date | None:
    """Date de l'article — style42 dans le même <p> que style32."""
    style32 = soup.find("span", class_="style32")
    if not isinstance(style32, Tag):
        return None
    p_tag = style32.find_parent("p")
    if not isinstance(p_tag, Tag):
        return None
    style42 = p_tag.find("span", class_="style42")
    if not isinstance(style42, Tag):
        return None
    raw = style42.get_text(strip=True)  # "21/06/2011"
    try:
        day, month, year = int(raw[:2]), int(raw[3:5]), int(raw[6:])
        return date(year, month, day)
    except (ValueError, IndexError):
        return None


def parse_rubrique(soup: BeautifulSoup) -> str:
    """Rubrique — premier span.style42 dans un p.style96."""
    for p in soup.find_all("p", class_="style96"):
        span = p.find("span", class_="style42")
        if isinstance(span, Tag):
            return span.get_text(strip=True)
    return ""


def parse_title(soup: BeautifulSoup) -> str:
    """Titre de l'article — style17 (unique par fichier)."""
    tag = soup.find("span", class_="style17")
    return tag.get_text(strip=True) if isinstance(tag, Tag) else ""


def parse_body(soup: BeautifulSoup) -> str:
    """Corps de l'article — p.style96 dont le premier enfant est span.style95."""
    paragraphs: list[str] = []
    for p in soup.find_all("p", class_="style96"):
        first_span = p.find("span")
        if isinstance(first_span, Tag) and "style95" in first_span.get("class", []):
            text = p.get_text(separator="\n", strip=True)
            if text:
                paragraphs.append(text)
    return "\n\n".join(paragraphs)


# ---------------------------------------------------------------------------
# Helpers d'extraction (email / url / phone / name) pour Person et Contact
# ---------------------------------------------------------------------------

_RE_EMAIL_LABEL = re.compile(r"\s*-?\s*email\s*:\s*\S+", re.IGNORECASE)
_RE_URL_INLINE = re.compile(r"\s*-?\s*https?://\S+", re.IGNORECASE)
_RE_SITE_LABEL = re.compile(r"\s*-?\s*Site\s+Internet\s*:\s*\S+", re.IGNORECASE)
_RE_PHONE_LABEL = re.compile(
    r"\s*-?\s*t[eé]l(?:[eé]phone)?\s*:\s*[\d\s\+\-\(\)\.]{4,}", re.IGNORECASE
)


def _email_from_tag(tag: Tag) -> str:
    """Email depuis <a href="mailto:..."> ou pattern 'email : ...' dans le texte."""
    for a in tag.find_all("a"):
        href = str(a.get("href", ""))
        if href.startswith("mailto:"):
            return href[7:]
    m = re.search(r"email\s*:\s*(\S+)", tag.get_text(), re.IGNORECASE)
    return m.group(1) if m else ""


def _url_from_tag(tag: Tag) -> str:
    """URL depuis <a href="http..."> ou 'Site Internet : www...' dans le texte."""
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
    """Numéro de téléphone depuis un pattern 'tel : ...' dans le texte."""
    m = re.search(r"t[eé]l(?:[eé]phone)?\s*:\s*([\d\s\+\-\(\)\.]{4,})", text, re.IGNORECASE)
    return m.group(1).strip() if m else ""


def _name_from_tag(tag: Tag) -> str:
    """Nom d'un contact : texte brut duquel on a retiré email, url, téléphone."""
    text = tag.get_text(" ", strip=True)
    text = _RE_EMAIL_LABEL.sub("", text)
    text = _RE_URL_INLINE.sub("", text)
    text = _RE_SITE_LABEL.sub("", text)
    text = _RE_PHONE_LABEL.sub("", text)
    parts = [p.strip(" -:/") for p in text.split(" - ")]
    return " - ".join(p for p in parts if p)


def _contact_from_span(span: Tag) -> Contact:
    return Contact(
        name=_name_from_tag(span),
        email=_email_from_tag(span),
        url=_url_from_tag(span),
        phone=_phone_from_text(span.get_text()),
    )


# ---------------------------------------------------------------------------
# Champs nécessitant une navigation dans le tableau (label → cellule voisine)
# ---------------------------------------------------------------------------


def _find_sibling_cell(soup: BeautifulSoup, label: str) -> Tag | None:
    """Trouve le <td> voisin du <td> contenant le span.style28 dont le texte
    correspond à *label*."""
    for span in soup.find_all("span", class_="style28"):
        if label in span.get_text():
            td = span.find_parent("td")
            if isinstance(td, Tag):
                next_td = td.find_next_sibling("td")
                if isinstance(next_td, Tag):
                    return next_td
    return None


def parse_author(soup: BeautifulSoup) -> Person | None:
    """Auteur — extrait nom et email depuis la cellule voisine du label 'Rédacteur'."""
    td = _find_sibling_cell(soup, "Rédacteur")
    if not isinstance(td, Tag):
        return None
    span = td.find("span", class_="style95")
    if not isinstance(span, Tag):
        return None
    text = span.get_text(" ", strip=True)
    # supprime le préfixe "ADIT - "
    text = re.sub(r"^ADIT\s*-\s*", "", text, flags=re.IGNORECASE)
    # extrait email
    email = _email_from_tag(span)
    # supprime la partie " - email : ..."
    name = _RE_EMAIL_LABEL.sub("", text).strip(" -")
    return Person(name=name, email=email)


def parse_contacts(soup: BeautifulSoup) -> list[Contact]:
    """Contacts — tous les p.style44 > span.style85 dans la cellule voisine du label."""
    td = _find_sibling_cell(soup, "Pour en savoir plus")
    if not isinstance(td, Tag):
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


def parse_images(soup: BeautifulSoup) -> list[str]:
    """URLs des images de la colonne gauche (sidebar td.FWExtra),
    sans les spacers _clear.gif."""
    sidebar = soup.find("td", class_="FWExtra")
    if not isinstance(sidebar, Tag):
        return []
    return [
        str(img["src"])
        for img in sidebar.find_all("img")
        if "_clear.gif" not in str(img.get("src", ""))
        and "Resources/" not in str(img.get("src", ""))
    ]


# ---------------------------------------------------------------------------
# Point d'entrée principal
# ---------------------------------------------------------------------------


def parse_article(path: Path) -> Article:
    """Parse un fichier bulletin HTM et retourne un Article."""
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
