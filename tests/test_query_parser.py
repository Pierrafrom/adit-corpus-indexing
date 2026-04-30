"""Tests for TD5 — QueryParser.

Each test class targets one extraction step.  Tests use QueryParser without a
spell_checker so they don't require the full lexicon / SpaCy model.
"""

from __future__ import annotations

from adit_corpus_indexing.models import ParsedQuery
from adit_corpus_indexing.nlp.query_parser import (
    QueryParser,
    _extract_dates,
    _extract_filters,
    _extract_keywords,
    _extract_operators,
    _extract_rubrique,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def parse(query: str) -> ParsedQuery:
    return QueryParser().parse(query)


# ---------------------------------------------------------------------------
# Step 1 — Date extraction
# ---------------------------------------------------------------------------


class TestExtractDates:
    def test_year_only_en(self) -> None:
        dmin, dmax, _ = _extract_dates("Je veux les articles en 2014")
        assert dmin == "2014-01-01"
        assert dmax == "2014-12-31"

    def test_year_only_de(self) -> None:
        dmin, dmax, _ = _extract_dates("les articles de 2011 sur l'enseignement")
        assert dmin == "2011-01-01"
        assert dmax == "2011-12-31"

    def test_year_only_de_lannee(self) -> None:
        dmin, dmax, _ = _extract_dates("articles de l'année 2013")
        assert dmin == "2013-01-01"
        assert dmax == "2013-12-31"

    def test_year_range(self) -> None:
        dmin, dmax, _ = _extract_dates("écrits entre 2010 et 2011")
        assert dmin == "2010-01-01"
        assert dmax == "2011-12-31"

    def test_year_range_removes_standalone_month(self) -> None:
        """'mais pas au mois de juin' is consumed so 'juin' won't reach keywords."""
        dmin, dmax, residual = _extract_dates(
            "bulletins écrits entre 2012 et 2013 mais pas au mois de juin"
        )
        assert dmin == "2012-01-01"
        assert dmax == "2013-12-31"
        assert "juin" not in residual

    def test_full_date_range(self) -> None:
        dmin, dmax, _ = _extract_dates("parus entre le 3 mars 2013 et le 4 mai 2013")
        assert dmin == "2013-03-03"
        assert dmax == "2013-05-04"

    def test_slash_date_range(self) -> None:
        dmin, dmax, _ = _extract_dates("publiés entre 30/08/2011 et 29/09/2011")
        assert dmin == "2011-08-30"
        assert dmax == "2011-09-29"

    def test_after_month_year(self) -> None:
        dmin, dmax, _ = _extract_dates("écrits après janvier 2014")
        assert dmin == "2014-01-01"
        assert dmax is None

    def test_after_full_date(self) -> None:
        dmin, dmax, _ = _extract_dates("date d'après le 2 juillet 2012")
        assert dmin == "2012-07-02"
        assert dmax is None

    def test_from_year(self) -> None:
        dmin, dmax, _ = _extract_dates("datés à partir de 2012")
        assert dmin == "2012-01-01"
        assert dmax is None

    def test_a_partir_de(self) -> None:
        dmin, dmax, _ = _extract_dates("à partir de 2013")
        assert dmin == "2013-01-01"
        assert dmax is None

    def test_before_year(self) -> None:
        dmin, dmax, _ = _extract_dates("avant 2013")
        assert dmin is None
        assert dmax == "2013-12-31"

    def test_month_label_year(self) -> None:
        dmin, dmax, _ = _extract_dates("publiés au mois de novembre 2011")
        assert dmin == "2011-11-01"
        assert dmax == "2011-11-30"

    def test_month_year_en(self) -> None:
        dmin, dmax, _ = _extract_dates("publiés en Février 2010")
        assert dmin == "2010-02-01"
        assert dmax == "2010-02-28"

    def test_month_year_december(self) -> None:
        dmin, dmax, _ = _extract_dates("écrits en Décembre 2012")
        assert dmin == "2012-12-01"
        assert dmax == "2012-12-31"

    def test_no_date(self) -> None:
        dmin, dmax, residual = _extract_dates("articles sur les robots")
        assert dmin is None
        assert dmax is None
        assert residual == "articles sur les robots"

    def test_residual_cleaned(self) -> None:
        _, _, residual = _extract_dates("articles de 2013 sur les drones")
        assert "2013" not in residual
        assert "drones" in residual


# ---------------------------------------------------------------------------
# Step 2 — Rubrique extraction
# ---------------------------------------------------------------------------


class TestExtractRubrique:
    def test_focus(self) -> None:
        rub, _ = _extract_rubrique("articles de la rubrique Focus")
        assert rub == "Focus"

    def test_horizons_enseignement(self) -> None:
        rub, _ = _extract_rubrique("rubrique Horizons Enseignement")
        assert rub == "Horizons Enseignement"

    def test_en_direct_des_laboratoires(self) -> None:
        rub, _ = _extract_rubrique("la rubrique en direct des laboratoires")
        assert rub == "En direct des laboratoires"

    def test_actualites_innovations(self) -> None:
        rub, _ = _extract_rubrique("dont la rubrique est Actualités Innovations")
        assert rub == "Actualités Innovations"

    def test_evenement(self) -> None:
        rub, _ = _extract_rubrique("articles de la rubrique Evénement")
        assert rub == "Evénement"

    def test_a_lire(self) -> None:
        rub, _ = _extract_rubrique("rubrique A lire")
        assert rub == "A lire"

    def test_no_rubrique(self) -> None:
        rub, _ = _extract_rubrique("articles sur les robots")
        assert rub is None

    def test_rubrique_removed_from_text(self) -> None:
        _, residual = _extract_rubrique("articles rubrique Focus sur les drones")
        assert "focus" not in residual.lower()
        assert "drones" in residual

    def test_focus_case_insensitive(self) -> None:
        rub, _ = _extract_rubrique("rubrique FOCUS")
        assert rub == "Focus"


# ---------------------------------------------------------------------------
# Step 3 — Filter extraction
# ---------------------------------------------------------------------------


class TestExtractFilters:
    def test_avec_images(self) -> None:
        fi, zone, _ = _extract_filters("articles avec des images")
        assert fi is True
        assert zone is None

    def test_avec_une_image(self) -> None:
        fi, zone, _ = _extract_filters("Articles contenant une image.")
        assert fi is True

    def test_sans_image(self) -> None:
        fi, zone, _ = _extract_filters("je veux les articles sans image")
        assert fi is False

    def test_no_image_filter(self) -> None:
        fi, zone, _ = _extract_filters("articles sur les robots")
        assert fi is None

    def test_zone_titre(self) -> None:
        fi, zone, residual = _extract_filters("dont le titre contient le mot chimie")
        assert zone == "titre"
        assert "chimie" in residual

    def test_zone_titre_evoque(self) -> None:
        _, zone, _ = _extract_filters("dont le titre évoque la recherche")
        assert zone == "titre"

    def test_no_zone(self) -> None:
        _, zone, _ = _extract_filters("articles sur les robots")
        assert zone is None

    def test_image_and_zone(self) -> None:
        fi, zone, _ = _extract_filters(
            "avec des images dont le titre contient le mot croissance"
        )
        assert fi is True
        assert zone == "titre"


# ---------------------------------------------------------------------------
# Step 4 — Operator detection
# ---------------------------------------------------------------------------


class TestExtractOperators:
    def test_default_and(self) -> None:
        ops, _ = _extract_operators("articles sur les robots")
        assert ops == ["AND"]

    def test_or(self) -> None:
        ops, _ = _extract_operators("airbus ou le projet Taxibot")
        assert "OR" in ops
        assert "AND" in ops

    def test_not_mais_pas(self) -> None:
        ops, _ = _extract_operators("CNRS mais pas Centrale")
        assert "NOT" in ops

    def test_not_et_non(self) -> None:
        ops, _ = _extract_operators("systèmes embarqués et non la robotique")
        assert "NOT" in ops

    def test_or_and_not(self) -> None:
        ops, _ = _extract_operators("CNRS ou grandes écoles mais pas Centrale")
        assert "AND" in ops
        assert "OR" in ops
        assert "NOT" in ops

    def test_or_removed_from_residual(self) -> None:
        _, residual = _extract_operators("airbus ou taxibot")
        assert "ou" not in residual.lower()

    def test_not_removed_from_residual(self) -> None:
        _, residual = _extract_operators("robots mais pas drones")
        assert "mais pas" not in residual.lower()

    def test_not_ne_pas(self) -> None:
        ops, _ = _extract_operators("qui ne parlent pas d'ingénieurs")
        assert "NOT" in ops

    def test_not_ne_verb_pas_full_query(self) -> None:
        pq = parse(
            "Articles dont la rubrique est Horizon Enseignement"
            " mais qui ne parlent pas d'ingénieurs."
        )
        assert "NOT" in pq.operateurs
        assert pq.rubrique == "Horizons Enseignement"


# ---------------------------------------------------------------------------
# Step 5 — Keyword extraction
# ---------------------------------------------------------------------------


class TestExtractKeywords:
    def test_basic(self) -> None:
        kws = _extract_keywords("articles sur les robots", None)
        assert "robots" in kws

    def test_stop_words_removed(self) -> None:
        kws = _extract_keywords("je voudrais les articles sur les drones", None)
        assert "je" not in kws
        assert "les" not in kws
        assert "drones" in kws

    def test_elision_handled(self) -> None:
        kws = _extract_keywords("articles sur l'innovation", None)
        assert "innovation" in kws

    def test_short_tokens_removed(self) -> None:
        kws = _extract_keywords("articles sur d", None)
        assert "d" not in kws

    def test_dedup(self) -> None:
        kws = _extract_keywords("robot robot robot", None)
        assert kws.count("robot") == 1

    def test_empty_residual(self) -> None:
        kws = _extract_keywords("je voudrais les articles", None)
        assert kws == []


# ---------------------------------------------------------------------------
# Full pipeline (QueryParser.parse) — annexe examples
# ---------------------------------------------------------------------------


class TestQueryParserFull:
    def test_horizons_enseignement_with_keyword(self) -> None:
        pq = parse(
            "Afficher la liste des articles qui parlent des systèmes embarqués"
            " dans la rubrique Horizons Enseignement."
        )
        assert pq.rubrique == "Horizons Enseignement"
        assert (
            "embarqués" in pq.mots_cles
            or "embarque" in pq.mots_cles
            or any("embarqu" in kw for kw in pq.mots_cles)
        )

    def test_or_query(self) -> None:
        pq = parse(
            "Je voudrais les articles qui parlent d'airbus ou du projet Taxibot."
        )
        assert "OR" in pq.operateurs
        assert "airbus" in pq.mots_cles

    def test_date_with_rubrique(self) -> None:
        pq = parse(
            "Je veux les articles de 2014 et de la rubrique Focus"
            " et parlant de la santé."
        )
        assert pq.date_min == "2014-01-01"
        assert pq.date_max == "2014-12-31"
        assert pq.rubrique == "Focus"
        assert "santé" in pq.mots_cles or "sante" in pq.mots_cles

    def test_full_date_range_query(self) -> None:
        pq = parse(
            "Quels sont les articles parus entre le 3 mars 2013 et le 4 mai 2013"
            " évoquant les Etats-Unis ?"
        )
        assert pq.date_min == "2013-03-03"
        assert pq.date_max == "2013-05-04"

    def test_rubrique_en_direct(self) -> None:
        pq = parse("Afficher les articles de la rubrique en direct des laboratoires.")
        assert pq.rubrique == "En direct des laboratoires"

    def test_image_and_zone_titre(self) -> None:
        pq = parse(
            "Je voudrais les articles avec des images"
            " dont le titre contient le mot croissance."
        )
        assert pq.filtre_images is True
        assert pq.zone == "titre"
        assert "croissance" in pq.mots_cles

    def test_sans_image(self) -> None:
        pq = parse("Je veux les articles sans image.")
        assert pq.filtre_images is False

    def test_zone_titre_only(self) -> None:
        pq = parse("je voudrais les articles dont le titre contient le mot chimie.")
        assert pq.zone == "titre"
        assert "chimie" in pq.mots_cles

    def test_not_operator(self) -> None:
        pq = parse(
            "Liste des articles qui parlent soit du CNRS, soit des grandes écoles,"
            " mais pas de Centrale Paris."
        )
        assert "NOT" in pq.operateurs

    def test_year_range_no_june(self) -> None:
        pq = parse(
            "Je voudrais tous les bulletins écrits entre 2012 et 2013"
            " mais pas au mois de juin."
        )
        assert pq.date_min == "2012-01-01"
        assert pq.date_max == "2013-12-31"
        assert "NOT" in pq.operateurs
        assert "juin" not in pq.mots_cles

    def test_after_date_query(self) -> None:
        pq = parse(
            "J'aimerais un article qui parle de biologie"
            " et qui date d'après le 2 juillet 2012 ?"
        )
        assert pq.date_min == "2012-07-02"
        assert pq.date_max is None
        assert "biologie" in pq.mots_cles

    def test_month_year_query(self) -> None:
        pq = parse(
            "quels sont les articles publiés au mois de novembre 2011"
            " portant sur de la recherche."
        )
        assert pq.date_min == "2011-11-01"
        assert pq.date_max == "2011-11-30"
        assert "recherche" in pq.mots_cles

    def test_actualites_innovations_with_date(self) -> None:
        pq = parse(
            "Je voudrais les articles qui datent du 1 décembre 2012"
            " et dont la rubrique est Actualités Innovations."
        )
        assert pq.rubrique == "Actualités Innovations"
        assert pq.date_min == "2012-12-01"
        assert pq.date_max == "2012-12-01"

    def test_no_metadata_query(self) -> None:
        pq = parse("Je voudrais les articles qui parlent du tennis.")
        assert pq.rubrique is None
        assert pq.date_min is None
        assert pq.date_max is None
        assert pq.filtre_images is None
        assert pq.zone is None
        assert "tennis" in pq.mots_cles

    def test_operateurs_always_contains_and(self) -> None:
        pq = parse("Je voudrais les articles sur la Lune.")
        assert "AND" in pq.operateurs

    def test_from_year_query(self) -> None:
        pq = parse(
            "Chercher les articles dans le domaine industriel"
            " et datés à partir de 2012."
        )
        assert pq.date_min == "2012-01-01"
        assert pq.date_max is None

    def test_focus_with_images(self) -> None:
        pq = parse(
            "Lister tous les articles dont la rubrique est Focus et qui ont des images."
        )
        assert pq.rubrique == "Focus"
        assert pq.filtre_images is True

    def test_slash_date_range(self) -> None:
        pq = parse(
            "je veux les articles de la rubrique Focus"
            " et publiés entre 30/08/2011 et 29/09/2011."
        )
        assert pq.rubrique == "Focus"
        assert pq.date_min == "2011-08-30"
        assert pq.date_max == "2011-09-29"

    def test_or_with_rubriques(self) -> None:
        pq = parse(
            "Tous les articles dont la rubrique est En direct des laboratoires"
            " ou Focus et qui évoquent la médecine."
        )
        # First rubrique found: "En direct des laboratoires"
        assert pq.rubrique == "En direct des laboratoires"
        assert "OR" in pq.operateurs
