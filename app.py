"""TD6 — ADIT Search Engine — Streamlit interface.

Launch::

    uv run streamlit run app.py
    # or with Docker:
    docker compose up
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import streamlit as st

from src.adit_corpus_indexing.search.engine import SearchEngine, SearchResult
from src.adit_corpus_indexing.search.evaluator import Evaluator

# ---------------------------------------------------------------------------
# Paths (relative to project root — works both locally and in Docker)
# ---------------------------------------------------------------------------

_OUTPUTS = Path("outputs/td3")
_INDEXES = _OUTPUTS / "indexes"
_CORPUS = _OUTPUTS / "corpus_final.xml"
_DISPLAY_CORPUS = _OUTPUTS / "corpus_filtered.xml"
_LEXICON = _OUTPUTS / "lemmes_snowball.tsv"
_GROUND_TRUTH = Path("data/ground_truth.json")

# Static-served HTML articles (Streamlit enableStaticServing + COPY data/BULLETINS/ static/)
_STATIC_ARTICLES = Path("static")

# ---------------------------------------------------------------------------
# Demo queries shown when the user presses "Lancer le scénario de démo"
# ---------------------------------------------------------------------------

_DEMO_QUERIES: list[str] = [
    "Je veux les articles de la rubrique Focus publiés en 2013",
    "Articles dont le titre contient le mot robot",
    "Articles avec des images de la rubrique En direct des laboratoires",
    "Articles publiés entre 2012 et 2013 sur l'énergie",
    "Lister tous les articles de la rubrique Horizons Enseignement",
]

# ---------------------------------------------------------------------------
# Cached engine initialisation (loaded once per session)
# ---------------------------------------------------------------------------


@st.cache_resource(show_spinner="Chargement du moteur de recherche…")
def _get_engine() -> SearchEngine:
    return SearchEngine(
        indexes_dir=_INDEXES,
        corpus_path=_CORPUS,
        lexicon_path=_LEXICON,
        display_corpus_path=_DISPLAY_CORPUS if _DISPLAY_CORPUS.exists() else None,
    )


# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------


def _display_results(results: list[SearchResult], keywords: list[str]) -> None:
    if not results:
        st.warning("Aucun résultat trouvé pour cette requête.")
        return

    st.success(f"**{len(results)} résultat(s)** trouvé(s)")
    articles_available = _STATIC_ARTICLES.exists()

    for r in results:
        label = f"📄 [{r.doc_id}] {r.titre or '(titre vide)'}"
        with st.expander(label, expanded=False):
            col1, col2, col3, col4 = st.columns([2, 3, 2, 2])
            col1.metric("Date", r.date or "—")
            col2.metric("Rubrique", r.rubrique or "—")
            col3.metric("Score", f"{r.score:.2f}")
            if articles_available:
                col4.link_button(
                    "📰 Article original",
                    f"/app/static/{r.doc_id}.htm",
                    use_container_width=True,
                )

            snippet = r.snippet
            for kw in keywords:
                if kw:
                    snippet = snippet.replace(kw, f"**{kw}**")
            st.markdown(f"*Extrait :* {snippet}")


def _highlight_metric(value: float, threshold_good: float, threshold_bad: float) -> str:
    if value >= threshold_good:
        return f"🟢 {value:.3f}"
    if value >= threshold_bad:
        return f"🟡 {value:.3f}"
    return f"🔴 {value:.3f}"


# ---------------------------------------------------------------------------
# Main app
# ---------------------------------------------------------------------------


def main() -> None:
    st.set_page_config(
        page_title="ADIT Search Engine — LO17",
        page_icon="🔍",
        layout="wide",
    )

    # ── Header ──────────────────────────────────────────────────────────
    st.title("🔍 Moteur de recherche ADIT")
    st.caption("LO17 — TD6 | Pierre Fromont Boissel | UTC Printemps 2026")
    st.divider()

    engine = _get_engine()

    # ── Sidebar ─────────────────────────────────────────────────────────
    with st.sidebar:
        st.header("⚙️ Options")
        sort_by = st.selectbox(
            "Tri des résultats",
            options=["relevance", "date_asc", "date_desc"],
            format_func=lambda x: {
                "relevance": "📊 Pertinence (score TF-IDF)",
                "date_asc": "📅 Date croissante",
                "date_desc": "📅 Date décroissante",
            }[x],
        )

        st.divider()
        st.header("🎬 Scénario de démo")
        st.write(
            "Cliquez ci-dessous pour exécuter automatiquement "
            "5 requêtes de démonstration et afficher leurs résultats."
        )
        run_demo = st.button("▶ Lancer le scénario de démo", use_container_width=True)

        st.divider()
        st.header("📊 Évaluation")
        run_eval = st.button(
            "📈 Lancer l'évaluation complète", use_container_width=True
        )

        st.divider()
        st.caption(
            "**Corpus** : ~326 articles ADIT (2011–2014)\n\n"
            "**Modèle** : booléen classé (TF-IDF, Snowball)\n\n"
            "**Index** : titre×2 + texte×1"
        )

    # ── Search bar ──────────────────────────────────────────────────────
    st.subheader("Saisir une requête en langage naturel")

    query_input = st.text_input(
        "Requête",
        placeholder="Ex : articles de la rubrique Focus publiés en 2013…",
        label_visibility="collapsed",
    )

    col_search, col_reset = st.columns([1, 5])
    search_clicked = col_search.button("🔍 Rechercher", type="primary")

    # ── Parsed query display ─────────────────────────────────────────────
    if query_input and (search_clicked or query_input):
        pq = engine.parse_query(query_input)
        with st.expander("🔬 Analyse de la requête", expanded=False):
            c1, c2, c3, c4 = st.columns(4)
            c1.write(f"**Mots-clés** : `{pq.mots_cles}`")
            c2.write(f"**Rubrique** : `{pq.rubrique}`")
            c3.write(f"**Dates** : `{pq.date_min}` → `{pq.date_max}`")
            c4.write(
                f"**Opérateurs** : `{pq.operateurs}` | "
                f"**Images** : `{pq.filtre_images}` | "
                f"**Zone** : `{pq.zone}`"
            )

    # ── Search results ───────────────────────────────────────────────────
    if search_clicked and query_input:
        t0 = time.perf_counter()
        results = engine.search(query_input, sort_by=sort_by)
        elapsed_ms = (time.perf_counter() - t0) * 1000.0

        st.write(f"⏱ Temps de réponse : **{elapsed_ms:.1f} ms**")
        pq = engine.parse_query(query_input)
        _display_results(results, pq.mots_cles)

    # ── Demo scenario ────────────────────────────────────────────────────
    if run_demo:
        st.subheader("🎬 Scénario de démonstration")
        for i, demo_query in enumerate(_DEMO_QUERIES, start=1):
            st.markdown(f"---\n**Requête {i}** : *{demo_query}*")
            t0 = time.perf_counter()
            results = engine.search(demo_query, sort_by=sort_by)
            elapsed_ms = (time.perf_counter() - t0) * 1000.0

            pq = engine.parse_query(demo_query)
            with st.expander("Analyse", expanded=False):
                st.write(
                    f"mots-clés={pq.mots_cles}  rubrique={pq.rubrique!r}  "
                    f"dates=[{pq.date_min}, {pq.date_max}]  "
                    f"opérateurs={pq.operateurs}"
                )

            st.write(
                f"⏱ {elapsed_ms:.1f} ms | "
                f"**{len(results)} résultat(s)**"
            )
            _display_results(results, pq.mots_cles)

    # ── Evaluation panel ─────────────────────────────────────────────────
    if run_eval:
        if not _GROUND_TRUTH.exists():
            st.error(f"Fichier ground truth introuvable : `{_GROUND_TRUTH}`")
        else:
            st.subheader("📊 Évaluation expérimentale")
            with st.spinner("Évaluation en cours (100 exécutions par requête)…"):
                evaluator = Evaluator(engine, _GROUND_TRUTH)
                report = evaluator.run()

            # Summary metrics
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Précision macro", f"{report.macro_precision:.3f}")
            col2.metric("Rappel macro", f"{report.macro_recall:.3f}")
            col3.metric("F1 macro", f"{report.macro_f1:.3f}")
            col4.metric("Temps moyen", f"{report.avg_response_ms:.2f} ms")

            # Per-query table
            st.subheader("Résultats par requête")
            table_data = []
            for r in report.results:
                table_data.append(
                    {
                        "Requête": r.query[:60] + ("…" if len(r.query) > 60 else ""),
                        "Précision": _highlight_metric(r.precision, 0.8, 0.5),
                        "Rappel": _highlight_metric(r.recall, 0.8, 0.5),
                        "F1": _highlight_metric(r.f1, 0.8, 0.5),
                        "Résultats": len(r.retrieved_ids),
                        "Pertinents": len(r.relevant_ids),
                        "TP": r.tp,
                        "FP": r.fp,
                        "FN": r.fn,
                        "Temps (ms)": f"{r.avg_response_ms:.2f}",
                    }
                )

            st.dataframe(table_data, use_container_width=True)

            # Export
            if st.button("💾 Télécharger les résultats (JSON)"):
                export = {
                    "macro_precision": report.macro_precision,
                    "macro_recall": report.macro_recall,
                    "macro_f1": report.macro_f1,
                    "avg_response_ms": report.avg_response_ms,
                    "queries": [
                        {
                            "query": r.query,
                            "precision": r.precision,
                            "recall": r.recall,
                            "f1": r.f1,
                            "avg_response_ms": r.avg_response_ms,
                        }
                        for r in report.results
                    ],
                }
                st.download_button(
                    "⬇ JSON",
                    data=json.dumps(export, ensure_ascii=False, indent=2),
                    file_name="evaluation_td6.json",
                    mime="application/json",
                )


if __name__ == "__main__":
    main()
