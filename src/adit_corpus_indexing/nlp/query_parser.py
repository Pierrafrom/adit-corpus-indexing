"""TD5 — Natural language query parser for the ADIT corpus.

Transforms a plain French query into a structured :class:`~adit_corpus_indexing.models.ParsedQuery`
that can be used to interrogate the inverted indexes built in TD3.

The parsing pipeline applies five steps in order, each consuming and removing
the text it recognised so that later steps see a progressively cleaner residue:

    1. **Date extraction** — temporal constraints (``date_min``, ``date_max``)
    2. **Rubrique extraction** — ADIT section names (``rubrique``)
    3. **Structural filters** — image presence and search zone
    4. **Operator detection** — AND / OR / NOT (``operateurs``)
    5. **Keyword extraction** — tokenise + stop-word filter + optional spell
       correction / lemmatisation (``mots_cles``)

Typical usage::

    from pathlib import Path
    from adit_corpus_indexing.nlp.query_parser import QueryParser
    from adit_corpus_indexing.nlp.spell_checker import Lexicon, SpellChecker

    lexicon = Lexicon.from_tsv(Path("outputs/td3/lemmes_spacy.tsv"))
    checker = SpellChecker(lexicon)
    parser  = QueryParser(spell_checker=checker)

    pq = parser.parse("Je veux les articles Focus sur les robots depuis 2012")
    print(pq)
    # ParsedQuery(mots_cles=['robot'], rubrique='Focus',
    #             date_min='2012-01-01', date_max=None,
    #             operateurs=['AND'], filtre_images=None, zone=None)
"""

from __future__ import annotations

import logging
import re
from calendar import monthrange
from datetime import date
from typing import Protocol

from ..models import ParsedQuery
from .tokenizer import normalize_elisions, tokenize

logger = logging.getLogger(__name__)


class _CorrectionResult(Protocol):
    """Minimal correction result contract returned by the spell checker."""

    lemma: str | None


class _SpellCheckerLike(Protocol):
    """Minimal spell checker contract used by this module."""

    def correct_term(self, term: str) -> _CorrectionResult: ...


# ---------------------------------------------------------------------------
# French month names → month number
# ---------------------------------------------------------------------------

_MOIS_FR: dict[str, int] = {
    "janvier": 1,
    "février": 2,
    "fevrier": 2,
    "mars": 3,
    "avril": 4,
    "mai": 5,
    "juin": 6,
    "juillet": 7,
    "août": 8,
    "aout": 8,
    "septembre": 9,
    "octobre": 10,
    "novembre": 11,
    "décembre": 12,
    "decembre": 12,
}

# Alternation pattern matching any French month name (longest first to avoid
# partial matches, e.g. "mai" should not shadow "mais").
_MOIS_PAT = "(?:" + "|".join(sorted(_MOIS_FR, key=len, reverse=True)) + ")"

# ---------------------------------------------------------------------------
# Date regexes (tried in order: most specific first)
# ---------------------------------------------------------------------------

# "entre le 3 mars 2013 et le 4 mai 2013"
_RE_FULL_DATE_RANGE = re.compile(
    rf"entre\s+le\s+(\d{{1,2}})\s+({_MOIS_PAT})\s+(\d{{4}})"
    rf"\s+et\s+le\s+(\d{{1,2}})\s+({_MOIS_PAT})\s+(\d{{4}})",
    re.IGNORECASE,
)

# "entre 30/08/2011 et 29/09/2011"
_RE_SLASH_DATE_RANGE = re.compile(
    r"entre\s+(\d{1,2})[/\-](\d{1,2})[/\-](\d{4})"
    r"\s+et\s+(\d{1,2})[/\-](\d{1,2})[/\-](\d{4})",
    re.IGNORECASE,
)

# "entre 2012 et 2013"
_RE_YEAR_RANGE = re.compile(
    r"entre\s+(\d{4})\s+et\s+(\d{4})\b",
    re.IGNORECASE,
)

# "date d'après le 2 juillet 2012" / "après le 3 mars 2013"
_RE_AFTER_FULL_DATE = re.compile(
    rf"(?:(?:date\s+d['\u2019])?(?:après|apres|depuis))\s+le\s+"
    rf"(\d{{1,2}})\s+({_MOIS_PAT})\s+(\d{{4}})",
    re.IGNORECASE,
)

# "après janvier 2014" / "depuis mars 2013"
_RE_AFTER_MONTH_YEAR = re.compile(
    rf"(?:après|apres|depuis)\s+({_MOIS_PAT})\s+(\d{{4}})",
    re.IGNORECASE,
)

# "(datés) à partir de 2012"
_RE_FROM_YEAR = re.compile(
    r"(?:dat[ée]e?s?\s+)?(?:à\s+partir\s+de|a\s+partir\s+de)\s+(\d{4})\b",
    re.IGNORECASE,
)

# "après 2014" / "depuis 2011"
_RE_AFTER_YEAR = re.compile(
    r"(?:après|apres|depuis)\s+(\d{4})\b",
    re.IGNORECASE,
)

# "avant 2013" / "jusqu'en 2013"
_RE_BEFORE_YEAR = re.compile(
    r"(?:avant|jusqu['\u2019]en|jusqu\s+en)\s+(\d{4})\b",
    re.IGNORECASE,
)

# "du 1 décembre 2012" — single specific date starting with "du"
_RE_DU_DATE = re.compile(
    rf"du\s+(\d{{1,2}})\s+({_MOIS_PAT})\s+(\d{{4}})",
    re.IGNORECASE,
)

# "au mois de juin 2013" / "du mois de juin 2013"
_RE_MONTH_LABEL_YEAR = re.compile(
    rf"(?:au\s+mois\s+de|du\s+mois\s+de)\s+({_MOIS_PAT})\s+(\d{{4}})",
    re.IGNORECASE,
)

# "en février 2010" / "en décembre 2012"
_RE_MONTH_YEAR = re.compile(
    rf"(?:en|de)\s+({_MOIS_PAT})\s+(\d{{4}})",
    re.IGNORECASE,
)

# "en 2014" / "de 2013" / "de l'année 2013"
_RE_YEAR_ONLY = re.compile(
    r"(?:de\s+l['\u2019]ann[eé]e|de\s+l\s+ann[eé]e|en|de)\s+(\d{4})\b",
    re.IGNORECASE,
)

# Standalone "au mois de juin" (no year) — remove from text to avoid polluting
# keywords with month names after year-range extraction.
_RE_STANDALONE_MONTH = re.compile(
    rf"(?:au\s+mois\s+de|du\s+mois\s+de)\s+({_MOIS_PAT})(?!\s+\d{{4}})\b",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# ADIT rubriques
# ---------------------------------------------------------------------------

_RUBRIQUES: list[tuple[str, list[str]]] = [
    ("En direct des laboratoires", ["en direct des laboratoires"]),
    ("Horizons Enseignement", ["horizons enseignement"]),
    (
        "Actualités Innovations",
        [
            "actualités innovations",
            "actualité innovations",
            "actualités innovation",
            "actualité innovation",
        ],
    ),
    ("Focus", ["focus"]),
    ("A lire", ["a lire", "à lire"]),
    ("Evénement", ["événement", "evénement", "evenement", "évènement"]),
]

# Build compiled patterns sorted by alias length (longest first).
# Each pattern optionally consumes common preceding rubrique context such as
# "dans la rubrique", "de la rubrique est", "rubrique", etc.
_RUBRIQUE_PATTERNS: list[tuple[str, re.Pattern[str]]] = []
for _canonical, _aliases in _RUBRIQUES:
    for _alias in _aliases:
        _pat = re.compile(
            r"(?:"
            r"(?:de\s+(?:la\s+)?|dans\s+(?:la\s+)?|à\s+(?:la\s+)?|"
            r"sur\s+(?:la\s+)?|dont\s+(?:la\s+)?|provenant\s+de\s+(?:la\s+)?)?"
            r"rubrique\s+(?:est\s+)?)?" + re.escape(_alias),
            re.IGNORECASE,
        )
        _RUBRIQUE_PATTERNS.append((_canonical, _pat))

_RUBRIQUE_PATTERNS.sort(key=lambda x: -len(x[1].pattern))

# ---------------------------------------------------------------------------
# Structural filters
# ---------------------------------------------------------------------------

_RE_AVEC_IMAGES = re.compile(
    r"\b(?:"
    r"avec\s+(?:des?\s+)?images?|"
    r"contenant\s+(?:une?\s+)?images?|"
    r"possédant\s+(?:des?\s+)?images?|"
    r"(?:ont|ayant)\s+(?:des?\s+)?images?|"
    r"qui\s+ont\s+(?:des?\s+)?images?"
    r")\b",
    re.IGNORECASE,
)
_RE_SANS_IMAGES = re.compile(r"\bsans\s+images?\b", re.IGNORECASE)

# "dont le titre contient le mot X" / "dans le titre" / "dont le titre évoque"
_RE_ZONE_TITRE = re.compile(
    r"\b(?:"
    r"dont\s+le\s+titre\s+(?:contient|contiennent|évoque|évoquent|inclut|"
    r"comporte|comprend)?\s*(?:le\s+mot\s+)?|"
    r"dans\s+le\s+titre\s*|"
    r"le\s+titre\s+(?:contient|évoque|inclut)\s*(?:le\s+mot\s+)?|"
    r"titre\s+(?:contient|évoque|inclut)\s*(?:le\s+mot\s+)?"
    r")\b",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Logical operators
# ---------------------------------------------------------------------------

_RE_NOT = re.compile(
    r"\b(?:mais\s+pas|non\s+pas|et\s+non(?:\s+pas)?|sans)\b",
    re.IGNORECASE,
)
_RE_OR = re.compile(r"\bou\b", re.IGNORECASE)

# ---------------------------------------------------------------------------
# Stop words for keyword extraction (query framing words)
# ---------------------------------------------------------------------------

_STOP_WORDS: frozenset[str] = frozenset(
    {
        # Pronouns
        "je",
        "tu",
        "il",
        "elle",
        "nous",
        "vous",
        "ils",
        "elles",
        "on",
        "me",
        "te",
        "se",
        "lui",
        "y",
        # Articles & determiners
        "le",
        "la",
        "les",
        "un",
        "une",
        "des",
        "du",
        "ce",
        "cet",
        "cette",
        "ces",
        "mon",
        "ton",
        "son",
        "ma",
        "ta",
        "sa",
        "nos",
        "vos",
        "leur",
        "leurs",
        # Prepositions
        "de",
        "d",
        "a",
        "au",
        "aux",
        "sur",
        "dans",
        "par",
        "pour",
        "avec",
        "sous",
        "vers",
        "entre",
        "contre",
        "depuis",
        "apres",
        "avant",
        "jusque",
        # Conjunctions / relative pronouns
        "et",
        "mais",
        "ou",
        "que",
        "qui",
        "quoi",
        "dont",
        "quels",
        "quelles",
        "quel",
        "quelle",
        # Query framing verbs
        "afficher",
        "lister",
        "liste",
        "donner",
        "retourner",
        "trouver",
        "chercher",
        "rechercher",
        "vouloir",
        "veux",
        "voudrais",
        "voulez",
        "souhaiter",
        "souhaite",
        "souhaitez",
        "souhaitons",
        "aimer",
        "aimerais",
        # Query framing nouns
        "article",
        "articles",
        "bulletin",
        "bulletins",
        "mot",
        "mots",
        "terme",
        "termes",
        "sujet",
        "domaine",
        # Topic verbs (infinitives and conjugated)
        "parler",
        "parlent",
        "parle",
        "parlant",
        "traiter",
        "traitent",
        "traite",
        "traitant",
        "porter",
        "portent",
        "porte",
        "portant",
        "contenir",
        "contiennent",
        "contient",
        "contenant",
        "evoquer",
        "evoquent",
        "evoque",
        "evoquant",
        "mentionner",
        "mentionnent",
        "mentionne",
        "mentionnant",
        "concerner",
        "concernent",
        "concerne",
        "concernant",
        "incluant",
        "lier",
        "datent",
        "dater",
        # Participials (unaccented forms after tokenisation)
        "publie",
        "publies",
        "ecrit",
        "ecrits",
        "date",
        "dates",
        "paru",
        "parus",
        # Miscellaneous
        "tous",
        "tout",
        "toutes",
        "toute",
        "soit",
        "soient",
        "donc",
        "ainsi",
        "aussi",
        "pas",
        "non",
        "ni",
        "quand",
        "comment",
        "pourquoi",
        "lesquels",
        "lesquelles",
        "alors",
        # Single letters left over from elision removal
        "s",
        "t",
        "n",
        "m",
        "c",
        "l",
        "j",
        "qu",
        "en",
    }
)

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _remove_span(text: str, m: re.Match[str]) -> str:
    """Replace a matched span with a single space and normalise whitespace."""
    return " ".join((text[: m.start()] + " " + text[m.end() :]).split())


def _parse_month(name: str) -> int:
    """Return the month number for a French month name (case-insensitive)."""
    return _MOIS_FR[name.lower()]


def _last_day(year: int, month: int) -> int:
    """Return the last calendar day of the given month."""
    return monthrange(year, month)[1]


def _fmt(d: date) -> str:
    """Format a :class:`datetime.date` as an ISO string ``YYYY-MM-DD``."""
    return d.isoformat()


# ---------------------------------------------------------------------------
# Step 1 — Date extraction
# ---------------------------------------------------------------------------


def _extract_dates(text: str) -> tuple[str | None, str | None, str]:
    """Extract the first date constraint found, return (date_min, date_max, residual).

    Patterns are tried from most specific to least specific.
    Date bounds are returned as ISO strings (``YYYY-MM-DD``).
    """
    # ── "entre le 3 mars 2013 et le 4 mai 2013" ──────────────────────────
    m = _RE_FULL_DATE_RANGE.search(text)
    if m:
        d1, mo1, yr1, d2, mo2, yr2 = m.groups()
        dmin = _fmt(date(int(yr1), _parse_month(mo1), int(d1)))
        dmax = _fmt(date(int(yr2), _parse_month(mo2), int(d2)))
        return dmin, dmax, _remove_span(text, m)

    # ── "entre 30/08/2011 et 29/09/2011" ─────────────────────────────────
    m = _RE_SLASH_DATE_RANGE.search(text)
    if m:
        d1, mo1, yr1, d2, mo2, yr2 = m.groups()
        dmin = _fmt(date(int(yr1), int(mo1), int(d1)))
        dmax = _fmt(date(int(yr2), int(mo2), int(d2)))
        return dmin, dmax, _remove_span(text, m)

    # ── "entre 2012 et 2013" ──────────────────────────────────────────────
    m = _RE_YEAR_RANGE.search(text)
    if m:
        yr1, yr2 = int(m.group(1)), int(m.group(2))
        dmin = _fmt(date(yr1, 1, 1))
        dmax = _fmt(date(yr2, 12, 31))
        text = _remove_span(text, m)
        # Also remove any standalone month clause left over
        # (e.g. "mais pas au mois de juin")
        text = _RE_STANDALONE_MONTH.sub(" ", text)
        return dmin, dmax, " ".join(text.split())

    # ── "après le 2 juillet 2012" / "date d'après le …" ──────────────────
    m = _RE_AFTER_FULL_DATE.search(text)
    if m:
        day, month, year = int(m.group(1)), _parse_month(m.group(2)), int(m.group(3))
        dmin = _fmt(date(year, month, day))
        return dmin, None, _remove_span(text, m)

    # ── "après janvier 2014" ──────────────────────────────────────────────
    m = _RE_AFTER_MONTH_YEAR.search(text)
    if m:
        month, year = _parse_month(m.group(1)), int(m.group(2))
        dmin = _fmt(date(year, month, 1))
        return dmin, None, _remove_span(text, m)

    # ── "à partir de 2012" ───────────────────────────────────────────────
    m = _RE_FROM_YEAR.search(text)
    if m:
        dmin = _fmt(date(int(m.group(1)), 1, 1))
        return dmin, None, _remove_span(text, m)

    # ── "après 2014" ─────────────────────────────────────────────────────
    m = _RE_AFTER_YEAR.search(text)
    if m:
        dmin = _fmt(date(int(m.group(1)), 1, 1))
        return dmin, None, _remove_span(text, m)

    # ── "avant 2013" / "jusqu'en 2013" ───────────────────────────────────
    m = _RE_BEFORE_YEAR.search(text)
    if m:
        dmax = _fmt(date(int(m.group(1)), 12, 31))
        return None, dmax, _remove_span(text, m)

    # ── "du 1 décembre 2012" ─────────────────────────────────────────────
    m = _RE_DU_DATE.search(text)
    if m:
        day, month, year = int(m.group(1)), _parse_month(m.group(2)), int(m.group(3))
        d = _fmt(date(year, month, day))
        return d, d, _remove_span(text, m)

    # ── "au mois de novembre 2011" ────────────────────────────────────────
    m = _RE_MONTH_LABEL_YEAR.search(text)
    if m:
        month, year = _parse_month(m.group(1)), int(m.group(2))
        dmin = _fmt(date(year, month, 1))
        dmax = _fmt(date(year, month, _last_day(year, month)))
        return dmin, dmax, _remove_span(text, m)

    # ── "en février 2010" / "en décembre 2012" ───────────────────────────
    m = _RE_MONTH_YEAR.search(text)
    if m:
        month, year = _parse_month(m.group(1)), int(m.group(2))
        dmin = _fmt(date(year, month, 1))
        dmax = _fmt(date(year, month, _last_day(year, month)))
        return dmin, dmax, _remove_span(text, m)

    # ── "en 2014" / "de 2013" / "de l'année 2013" ────────────────────────
    m = _RE_YEAR_ONLY.search(text)
    if m:
        year = int(m.group(1))
        dmin = _fmt(date(year, 1, 1))
        dmax = _fmt(date(year, 12, 31))
        return dmin, dmax, _remove_span(text, m)

    return None, None, text


# ---------------------------------------------------------------------------
# Step 2 — Rubrique extraction
# ---------------------------------------------------------------------------


def _extract_rubrique(text: str) -> tuple[str | None, str]:
    """Return the first ADIT rubrique name found and the residual text."""
    for canonical, pattern in _RUBRIQUE_PATTERNS:
        m = pattern.search(text)
        if m:
            logger.debug(
                "_extract_rubrique: found %r at %d-%d", canonical, m.start(), m.end()
            )
            return canonical, _remove_span(text, m)
    return None, text


# ---------------------------------------------------------------------------
# Step 3 — Structural filters
# ---------------------------------------------------------------------------


def _extract_filters(text: str) -> tuple[bool | None, str | None, str]:
    """Return (filtre_images, zone, residual_text).

    ``filtre_images``:  True → with images, False → without, None → no constraint.
    ``zone``:           "titre" → search in title only, None → all zones.
    """
    filtre_images: bool | None = None
    zone: str | None = None

    # "sans images" must be checked before _RE_NOT so "sans" is consumed here.
    m = _RE_SANS_IMAGES.search(text)
    if m:
        filtre_images = False
        text = _remove_span(text, m)
    else:
        m = _RE_AVEC_IMAGES.search(text)
        if m:
            filtre_images = True
            text = _remove_span(text, m)

    m = _RE_ZONE_TITRE.search(text)
    if m:
        zone = "titre"
        text = _remove_span(text, m)

    return filtre_images, zone, text


# ---------------------------------------------------------------------------
# Step 4 — Operator detection
# ---------------------------------------------------------------------------


def _extract_operators(text: str) -> tuple[list[str], str]:
    """Detect AND / OR / NOT operators; always returns at least ["AND"]."""
    operateurs: list[str] = ["AND"]

    if _RE_NOT.search(text):
        operateurs.append("NOT")
        text = _RE_NOT.sub(" ", text)

    if _RE_OR.search(text):
        operateurs.append("OR")
        text = _RE_OR.sub(" ", text)

    return operateurs, " ".join(text.split())


# ---------------------------------------------------------------------------
# Step 5 — Keyword extraction
# ---------------------------------------------------------------------------


def _extract_keywords(
    text: str,
    spell_checker: _SpellCheckerLike | None,
) -> list[str]:
    """Tokenise, filter stop words, and optionally spell-correct the residual.

    Args:
        text:          residual query text after all metadata extraction.
        spell_checker: optional :class:`~adit_corpus_indexing.nlp.spell_checker.SpellChecker`
                       instance.  When provided, each token is corrected and
                       the corresponding lemma is returned.

    Returns:
        List of lowercase keyword strings (deduplicated, order preserved).
    """
    normalised = normalize_elisions(text)
    tokens = [t for t in tokenize(normalised) if t not in _STOP_WORDS and len(t) > 1]

    if not tokens:
        return []

    if spell_checker is None:
        return _dedup(tokens)

    # Spell-correct each token and keep only the lemma.
    # The index stores lemmas, so only a lemma can produce a match.
    # Tokens whose lemma cannot be resolved (not_found) are silently dropped:
    # keeping the raw surface form would be useless against a lemma index.
    keywords: list[str] = []
    for token in tokens:
        result = spell_checker.correct_term(token)
        if result.lemma is not None:
            keywords.append(result.lemma)
        # not_found or corrected-without-lemma → drop: unresolvable against the index

    return _dedup(keywords)


def _dedup(seq: list[str]) -> list[str]:
    """Remove duplicates while preserving order."""
    seen: set[str] = set()
    out: list[str] = []
    for item in seq:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


class QueryParser:
    """Parse a natural language French query into a :class:`~adit_corpus_indexing.models.ParsedQuery`.

    Args:
        spell_checker: optional :class:`~adit_corpus_indexing.nlp.spell_checker.SpellChecker`
                       to correct and lemmatise keywords.  When *None*, keywords
                       are returned as raw lowercase tokens.

    Example::

        parser = QueryParser()
        pq = parser.parse("Je voudrais les articles Focus sur les drones en 2014")
        # ParsedQuery(mots_cles=['drones'], rubrique='Focus',
        #             date_min='2014-01-01', date_max='2014-12-31', ...)
    """

    def __init__(self, spell_checker: _SpellCheckerLike | None = None) -> None:
        self._spell_checker = spell_checker

    def parse(self, query: str) -> ParsedQuery:
        """Parse *query* and return a structured :class:`~adit_corpus_indexing.models.ParsedQuery`.

        Args:
            query: raw natural language query typed by the user.

        Returns:
            A :class:`~adit_corpus_indexing.models.ParsedQuery` instance.
        """
        text = query.strip()
        logger.debug("parse: input=%r", text)

        # Each step mutates `text` by removing what it recognised.
        date_min, date_max, text = _extract_dates(text)
        logger.debug(
            "parse: after dates → date_min=%r date_max=%r residual=%r",
            date_min,
            date_max,
            text,
        )

        rubrique, text = _extract_rubrique(text)
        logger.debug("parse: after rubrique → rubrique=%r residual=%r", rubrique, text)

        filtre_images, zone, text = _extract_filters(text)
        logger.debug(
            "parse: after filters → filtre_images=%r zone=%r residual=%r",
            filtre_images,
            zone,
            text,
        )

        operateurs, text = _extract_operators(text)
        logger.debug(
            "parse: after operators → operateurs=%r residual=%r", operateurs, text
        )

        mots_cles = _extract_keywords(text, self._spell_checker)
        logger.debug("parse: mots_cles=%r", mots_cles)

        result = ParsedQuery(
            mots_cles=mots_cles,
            rubrique=rubrique,
            date_min=date_min,
            date_max=date_max,
            operateurs=operateurs,
            filtre_images=filtre_images,
            zone=zone,
        )
        logger.info("parse: %r → %r", query, result)
        return result
