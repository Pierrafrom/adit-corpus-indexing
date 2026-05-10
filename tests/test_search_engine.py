"""Tests for TD6 — SearchEngine, IndexLoader, CorpusReader.

Tests use the real TD3 outputs when available (integration tests),
and fall back to lightweight fixtures for unit tests.

Index-dependent tests are skipped if outputs/td3/ is not present
(e.g. in a fresh CI environment without the pre-generated files).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from adit_corpus_indexing.search.index_loader import load_set_index, load_text_index

# ---------------------------------------------------------------------------
# Fixtures availability guard
# ---------------------------------------------------------------------------

_TD3 = Path("outputs/td3")
_INDEXES = _TD3 / "indexes"
_CORPUS = _TD3 / "corpus_final.xml"
_LEXICON = _TD3 / "lemmes_snowball.tsv"
_GT = Path("data/ground_truth.json")

requires_td3 = pytest.mark.skipif(
    not _INDEXES.exists() or not _CORPUS.exists(),
    reason="outputs/td3/ not available",
)


# ---------------------------------------------------------------------------
# IndexLoader — unit tests using temp files
# ---------------------------------------------------------------------------


class TestLoadTextIndex:
    def test_basic_parse(self, tmp_path: Path) -> None:
        tsv = tmp_path / "idx.tsv"
        tsv.write_text("robot\t67383:5.00 68883:7.00\n", encoding="utf-8")
        idx = load_text_index(tsv)
        assert "robot" in idx
        assert idx["robot"][67383] == pytest.approx(5.0)
        assert idx["robot"][68883] == pytest.approx(7.0)

    def test_empty_lines_skipped(self, tmp_path: Path) -> None:
        tsv = tmp_path / "idx.tsv"
        tsv.write_text("robot\t67383:1.0\n\ndrон\t99:2.0\n", encoding="utf-8")
        idx = load_text_index(tsv)
        assert len(idx) == 2

    def test_malformed_line_skipped(self, tmp_path: Path) -> None:
        tsv = tmp_path / "idx.tsv"
        tsv.write_text("badline\nrobot\t67383:1.0\n", encoding="utf-8")
        idx = load_text_index(tsv)
        assert "robot" in idx
        assert "badline" not in idx


class TestLoadSetIndex:
    def test_basic_parse(self, tmp_path: Path) -> None:
        tsv = tmp_path / "idx.tsv"
        tsv.write_text("focus\t67068 67383 67553\n", encoding="utf-8")
        idx = load_set_index(tsv)
        assert "focus" in idx
        assert idx["focus"] == {67068, 67383, 67553}

    def test_multiple_keys(self, tmp_path: Path) -> None:
        tsv = tmp_path / "idx.tsv"
        tsv.write_text("focus\t67068\nevénement\t67392 67561\n", encoding="utf-8")
        idx = load_set_index(tsv)
        assert len(idx) == 2
        assert 67392 in idx["evénement"]


# ---------------------------------------------------------------------------
# CorpusReader — unit tests using a minimal XML fixture
# ---------------------------------------------------------------------------


_MINI_XML = """\
<?xml version='1.0' encoding='UTF-8'?>
<corpus>
  <document>
    <article>100</article>
    <date>21/06/2011</date>
    <rubrique>Focus</rubrique>
    <titre>physique ondes</titre>
    <auteur>Alice</auteur>
    <texte>cnrs ondés acoust imageur</texte>
    <images><image><urlImage>img.jpg</urlImage></image></images>
  </document>
  <document>
    <article>200</article>
    <date>15/03/2012</date>
    <rubrique>Evénement</rubrique>
    <titre>robot industri</titre>
    <auteur>Bob</auteur>
    <texte>robot automatis usine industri</texte>
    <images/>
  </document>
</corpus>
"""


@pytest.fixture()
def mini_corpus(tmp_path: Path) -> Path:
    p = tmp_path / "corpus.xml"
    p.write_text(_MINI_XML, encoding="utf-8")
    return p


class TestCorpusReader:
    def test_loads_documents(self, mini_corpus: Path) -> None:
        from adit_corpus_indexing.search.corpus_reader import CorpusReader

        reader = CorpusReader(mini_corpus)
        assert len(reader) == 2

    def test_get_existing(self, mini_corpus: Path) -> None:
        from adit_corpus_indexing.search.corpus_reader import CorpusReader

        reader = CorpusReader(mini_corpus)
        meta = reader.get(100)
        assert meta is not None
        assert meta.rubrique == "Focus"
        assert meta.date == "21/06/2011"
        assert meta.has_images is True

    def test_get_missing(self, mini_corpus: Path) -> None:
        from adit_corpus_indexing.search.corpus_reader import CorpusReader

        reader = CorpusReader(mini_corpus)
        assert reader.get(999) is None

    def test_image_sets(self, mini_corpus: Path) -> None:
        from adit_corpus_indexing.search.corpus_reader import CorpusReader

        reader = CorpusReader(mini_corpus)
        assert 100 in reader.ids_with_images()
        assert 200 in reader.ids_without_images()

    def test_all_ids(self, mini_corpus: Path) -> None:
        from adit_corpus_indexing.search.corpus_reader import CorpusReader

        reader = CorpusReader(mini_corpus)
        assert reader.all_ids() == {100, 200}


# ---------------------------------------------------------------------------
# SearchEngine — unit tests with minimal in-memory indexes
# ---------------------------------------------------------------------------


@pytest.fixture()
def mini_engine(mini_corpus: Path, tmp_path: Path) -> object:
    """SearchEngine built from tiny in-memory fixtures."""
    from adit_corpus_indexing.search.engine import SearchEngine

    indexes_dir = tmp_path / "indexes"
    indexes_dir.mkdir()

    # Combined text index (titre_texte)
    (indexes_dir / "index_titre_texte.tsv").write_text(
        "robot\t200:5.00\nphysiqu\t100:3.00\n", encoding="utf-8"
    )
    (indexes_dir / "index_titre.tsv").write_text(
        "robot\t200:1\nphysiqu\t100:1\n", encoding="utf-8"
    )
    (indexes_dir / "index_rubrique.tsv").write_text(
        "focus\t100\nevénement\t200\n", encoding="utf-8"
    )
    (indexes_dir / "index_date.tsv").write_text(
        "06/2011\t100\n03/2012\t200\n", encoding="utf-8"
    )

    return SearchEngine(indexes_dir=indexes_dir, corpus_path=mini_corpus)


class TestSearchEngine:
    def test_keyword_search(self, mini_engine: object) -> None:
        from adit_corpus_indexing.search.engine import SearchEngine

        engine: SearchEngine = mini_engine  # type: ignore[assignment]
        # Use exact lemma form (no spell checker in mini_engine)
        results = engine.search("articles sur le robot")
        assert len(results) == 1
        assert results[0].doc_id == 200

    def test_rubrique_filter(self, mini_engine: object) -> None:
        from adit_corpus_indexing.search.engine import SearchEngine

        engine: SearchEngine = mini_engine  # type: ignore[assignment]
        results = engine.search("articles de la rubrique Focus")
        assert len(results) == 1
        assert results[0].doc_id == 100

    def test_image_filter(self, mini_engine: object) -> None:
        from adit_corpus_indexing.search.engine import SearchEngine

        engine: SearchEngine = mini_engine  # type: ignore[assignment]
        results = engine.search("articles avec des images")
        assert all(r.doc_id in {100} for r in results)

    def test_no_results(self, mini_engine: object) -> None:
        from adit_corpus_indexing.search.engine import SearchEngine

        engine: SearchEngine = mini_engine  # type: ignore[assignment]
        results = engine.search("articles sur les nanotechnologies")
        assert results == []

    def test_date_filter(self, mini_engine: object) -> None:
        from adit_corpus_indexing.search.engine import SearchEngine

        engine: SearchEngine = mini_engine  # type: ignore[assignment]
        results = engine.search("articles publiés en 2011")
        assert all(r.doc_id == 100 for r in results)

    def test_sort_by_relevance(self, mini_engine: object) -> None:
        from adit_corpus_indexing.search.engine import SearchEngine

        engine: SearchEngine = mini_engine  # type: ignore[assignment]
        # Both docs match as we search for nothing specific with no filter
        # Force a rubrique to get a single result and verify sort key exists
        results = engine.search("articles de la rubrique Focus", sort_by="relevance")
        # result has score 0 (no keywords) — just check it doesn't crash
        assert isinstance(results, list)

    def test_sort_by_date_asc(self, mini_engine: object) -> None:
        from adit_corpus_indexing.search.engine import SearchEngine

        engine: SearchEngine = mini_engine  # type: ignore[assignment]
        results = engine.search("articles publiés en 2011", sort_by="date_asc")
        assert isinstance(results, list)

    def test_parse_query_returns_parsed_query(self, mini_engine: object) -> None:
        from adit_corpus_indexing.models import ParsedQuery
        from adit_corpus_indexing.search.engine import SearchEngine

        engine: SearchEngine = mini_engine  # type: ignore[assignment]
        pq = engine.parse_query("articles de la rubrique Focus en 2012")
        assert isinstance(pq, ParsedQuery)
        assert pq.rubrique == "Focus"
        assert pq.date_min == "2012-01-01"


# ---------------------------------------------------------------------------
# Integration tests — use real TD3 outputs
# ---------------------------------------------------------------------------


class TestSearchEngineIntegration:
    @requires_td3
    def test_engine_loads(self) -> None:
        from adit_corpus_indexing.search.engine import SearchEngine

        engine = SearchEngine(
            indexes_dir=_INDEXES,
            corpus_path=_CORPUS,
            lexicon_path=_LEXICON,
        )
        assert engine is not None

    @requires_td3
    def test_focus_query_returns_results(self) -> None:
        from adit_corpus_indexing.search.engine import SearchEngine

        engine = SearchEngine(
            indexes_dir=_INDEXES,
            corpus_path=_CORPUS,
            lexicon_path=_LEXICON,
        )
        results = engine.search("Je veux les articles de la rubrique Focus")
        assert len(results) > 0

    @requires_td3
    def test_focus_query_all_in_focus(self) -> None:
        from adit_corpus_indexing.search.engine import SearchEngine

        engine = SearchEngine(
            indexes_dir=_INDEXES,
            corpus_path=_CORPUS,
            lexicon_path=_LEXICON,
        )
        results = engine.search("Je veux les articles de la rubrique Focus")
        doc_ids = {r.doc_id for r in results}
        expected = {
            67068,
            67383,
            67553,
            67554,
            67555,
            67794,
            67795,
            67937,
            67938,
            67939,
        }
        assert expected.issubset(doc_ids)

    @requires_td3
    def test_image_filter_only_with_images(self) -> None:
        from adit_corpus_indexing.search.engine import SearchEngine

        engine = SearchEngine(
            indexes_dir=_INDEXES,
            corpus_path=_CORPUS,
            lexicon_path=_LEXICON,
        )
        results = engine.search("articles avec des images")
        for r in results:
            meta = engine._corpus.get(r.doc_id)
            assert meta is not None
            assert meta.has_images is True

    @requires_td3
    def test_date_january_2012(self) -> None:
        from adit_corpus_indexing.search.engine import SearchEngine

        engine = SearchEngine(
            indexes_dir=_INDEXES,
            corpus_path=_CORPUS,
            lexicon_path=_LEXICON,
        )
        results = engine.search("articles publiés au mois de janvier 2012")
        doc_ids = {r.doc_id for r in results}
        expected = {68881, 68882, 68883, 68884, 68885, 68886, 68887, 68888, 68889}
        assert expected == doc_ids

    @requires_td3
    def test_evaluator_runs(self) -> None:
        from adit_corpus_indexing.search.engine import SearchEngine
        from adit_corpus_indexing.search.evaluator import Evaluator

        if not _GT.exists():
            pytest.skip("ground_truth.json not found")

        engine = SearchEngine(
            indexes_dir=_INDEXES,
            corpus_path=_CORPUS,
            lexicon_path=_LEXICON,
        )
        evaluator = Evaluator(engine, _GT, n_timing_runs=1)
        report = evaluator.run()
        assert len(report.results) == 10
        assert 0.0 <= report.macro_precision <= 1.0
        assert 0.0 <= report.macro_recall <= 1.0
