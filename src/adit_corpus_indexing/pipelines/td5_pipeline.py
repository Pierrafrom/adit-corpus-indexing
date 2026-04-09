"""TD5 pipeline — Query processing demo.

Runs the :class:`~adit_corpus_indexing.nlp.query_parser.QueryParser` on the
example queries from the TD5 annexe and prints the structured output.

Usage::

    uv run td5                          # process all annexe examples
    uv run td5 "ma requête en français" # process a single query
"""

from __future__ import annotations

import logging
import sys

from ..nlp.query_parser import QueryParser

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Example queries from the TD5 annexe
# ---------------------------------------------------------------------------

_ANNEXE_QUERIES: list[str] = [
    "Afficher la liste des articles qui parlent des systèmes embarqués dans la rubrique Horizons Enseignement.",
    "Je voudrais les articles qui parlent d'airbus ou du projet Taxibot.",
    "Je voudrais les articles qui parlent du tennis.",
    "Je voudrais les articles traitant de la Lune.",
    "Quels sont les articles parus entre le 3 mars 2013 et le 4 mai 2013 évoquant les Etats-Unis ?",
    "Afficher les articles de la rubrique en direct des laboratoires.",
    "Je veux les articles de la rubrique Focus parlant d'innovation.",
    "Je cherche les recherches sur l'aéronotique.",
    "Quels sont les articles parlant de la Russie ou du Japon ?",
    "Je voudrais les articles de 2011 sur l'enseignement.",
    "Je voudrais les articles dont le titre contient le mot chimie.",
    "Je veux les articles de 2014 et de la rubrique Focus et parlant de la santé.",
    "Je souhaite les rubriques des articles parlant de nutrition ou de vins.",
    "quels sont les articles publiés au mois de novembre 2011 portant sur de la recherche.",
    "Je voudrais les articles avec des images dont le titre contient le mot croissance.",
    "J'aimerais la liste des articles écrits après janvier 2014 et qui parlent d'informatique ou de télécommunications.",
    "Je veux les articles de 2012 qui parlent de l'écologie en France.",
    "Liste des articles qui parlent soit du CNRS, soit des grandes écoles, mais pas de Centrale Paris.",
    "J'aimerais un article qui parle de biologie et qui date d'après le 2 juillet 2012 ?",
    "je voudrais les articles dont le titre contient le mot europe.",
    "Je cherche les articles provenant de la rubrique en direct des laboratoires.",
    "Je voudrais les articles qui datent du 1 décembre 2012 et dont la rubrique est Actualités Innovations.",
    "Articles contenant une image.",
    "Je veux les articles sans image.",
    "quels articles portent à la fois sur les nanotechnologies et les microsatélites.",
    "Lister tous les articles dont la rubrique est Focus et qui ont des images.",
    "Articles dont la rubrique est Horizon Enseignement mais qui ne parlent pas d'ingénieurs.",
    "Tous les articles dont la rubrique est En direct des laboratoires ou Focus et qui évoquent la médecine.",
    "Je voudrais tous les bulletins écrits entre 2012 et 2013 mais pas au mois de juin.",
    "je veux les articles de la rubrique Focus et publiés entre 30/08/2011 et 29/09/2011.",
    "Listezmo les articles qui parlent de 3D et qui sont écrits entre 2010 et 2011.",
    "Chercher les articles dans le domaine industriel et datés à partir de 2012.",
    "Rechercher tous les articles sur le CNRS et l'innovation à partir de 2013.",
]


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------


def _format_query_result(query: str, index: int) -> str:
    """Parse one query and return a formatted string."""
    parser = QueryParser()
    pq = parser.parse(query)
    lines = [
        f"[{index:02d}] {query}",
        f"     mots_cles    : {pq.mots_cles}",
        f"     rubrique     : {pq.rubrique!r}",
        f"     date_min     : {pq.date_min!r}",
        f"     date_max     : {pq.date_max!r}",
        f"     operateurs   : {pq.operateurs}",
        f"     filtre_images: {pq.filtre_images}",
        f"     zone         : {pq.zone!r}",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Run the TD5 query parsing pipeline."""
    logging.basicConfig(
        level=logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )

    if len(sys.argv) > 1:
        # Single query passed on the command line
        query = " ".join(sys.argv[1:])
        print(_format_query_result(query, 0))
    else:
        # Process all annexe examples
        print("=" * 72)
        print("TD5 — Traitement des Requêtes : exemples de l'annexe")
        print("=" * 72)
        for i, query in enumerate(_ANNEXE_QUERIES, start=1):
            print(_format_query_result(query, i))
            print()
