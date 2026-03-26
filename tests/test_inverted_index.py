"""Tests for TD3 — InvertedIndexBuilder (create_inverse_file module)."""

from __future__ import annotations

from pathlib import Path

from adit_corpus_indexing.indexing.create_inverse_file import InvertedIndexBuilder

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _write_corpus(
    path: Path,
    docs: list[tuple[str, str, str, str, str]],
) -> None:
    """Write a corpus XML with (article_id, titre, texte, rubrique, date) tuples."""
    lines = ["<?xml version='1.0' encoding='utf-8'?>", "<corpus>"]
    for article_id, titre, texte, rubrique, date in docs:
        parts = [
            "  <document>",
            f"    <article>{article_id}</article>",
        ]
        if titre:
            parts.append(f"    <titre>{titre}</titre>")
        if texte:
            parts.append(f"    <texte>{texte}</texte>")
        if rubrique:
            parts.append(f"    <rubrique>{rubrique}</rubrique>")
        if date:
            parts.append(f"    <date>{date}</date>")
        parts.append("  </document>")
        lines.extend(parts)
    lines.append("</corpus>")
    path.write_text("\n".join(lines), encoding="utf-8")


def _read_index(path: Path) -> dict[str, str]:
    """Read an index TSV into a {term: postings_string} dict."""
    result: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line:
            continue
        parts = line.split("\t", 1)
        result[parts[0]] = parts[1] if len(parts) > 1 else ""
    return result


# ---------------------------------------------------------------------------
# build_text_index
# ---------------------------------------------------------------------------


class TestBuildTextIndex:
    def test_single_doc_single_token_has_freq_one(self, tmp_path: Path) -> None:
        corpus = tmp_path / "corpus.xml"
        _write_corpus(corpus, [("1", "chat", "", "", "")])
        builder = InvertedIndexBuilder(corpus)
        out = tmp_path / "index.tsv"
        builder.build_text_index("titre", out)
        index = _read_index(out)
        assert "chat" in index
        assert index["chat"] == "1:1"

    def test_repeated_token_increments_frequency(self, tmp_path: Path) -> None:
        corpus = tmp_path / "corpus.xml"
        _write_corpus(corpus, [("1", "chat chat chat", "", "", "")])
        builder = InvertedIndexBuilder(corpus)
        out = tmp_path / "index.tsv"
        builder.build_text_index("titre", out)
        index = _read_index(out)
        assert index["chat"] == "1:3"

    def test_token_in_multiple_docs_has_multiple_postings(self, tmp_path: Path) -> None:
        corpus = tmp_path / "corpus.xml"
        _write_corpus(
            corpus,
            [("1", "chat", "", "", ""), ("2", "chat chien", "", "", "")],
        )
        builder = InvertedIndexBuilder(corpus)
        out = tmp_path / "index.tsv"
        builder.build_text_index("titre", out)
        index = _read_index(out)
        assert "1:1" in index["chat"]
        assert "2:1" in index["chat"]

    def test_terms_are_sorted_alphabetically(self, tmp_path: Path) -> None:
        corpus = tmp_path / "corpus.xml"
        _write_corpus(corpus, [("1", "zèbre amour chat", "", "", "")])
        builder = InvertedIndexBuilder(corpus)
        out = tmp_path / "index.tsv"
        builder.build_text_index("titre", out)
        terms = list(_read_index(out).keys())
        assert terms == sorted(terms)

    def test_absent_field_is_skipped_silently(self, tmp_path: Path) -> None:
        corpus = tmp_path / "corpus.xml"
        # Doc 1 has no <texte>
        corpus.write_text(
            "<corpus><document><article>1</article><titre>chat</titre></document></corpus>",
            encoding="utf-8",
        )
        builder = InvertedIndexBuilder(corpus)
        out = tmp_path / "index.tsv"
        count = builder.build_text_index("texte", out)
        assert count == 0
        assert out.read_text(encoding="utf-8") == ""

    def test_returns_number_of_distinct_terms(self, tmp_path: Path) -> None:
        corpus = tmp_path / "corpus.xml"
        _write_corpus(corpus, [("1", "chat chien oiseau", "", "", "")])
        builder = InvertedIndexBuilder(corpus)
        out = tmp_path / "index.tsv"
        count = builder.build_text_index("titre", out)
        assert count == 3

    def test_document_without_article_id_skipped(self, tmp_path: Path) -> None:
        corpus = tmp_path / "corpus.xml"
        corpus.write_text(
            "<corpus><document><titre>chat</titre></document></corpus>",
            encoding="utf-8",
        )
        builder = InvertedIndexBuilder(corpus)
        out = tmp_path / "index.tsv"
        count = builder.build_text_index("titre", out)
        assert count == 0

    def test_real_mini_corpus(self, mini_corpus_path: Path, tmp_path: Path) -> None:
        builder = InvertedIndexBuilder(mini_corpus_path)
        out = tmp_path / "index.tsv"
        count = builder.build_text_index("titre", out)
        assert count > 0
        index = _read_index(out)
        # "le" appears in at least one document
        assert any("le" in term for term in index)


# ---------------------------------------------------------------------------
# build_combined_index
# ---------------------------------------------------------------------------


class TestBuildCombinedIndex:
    def test_weight_is_applied(self, tmp_path: Path) -> None:
        corpus = tmp_path / "corpus.xml"
        _write_corpus(corpus, [("1", "chat", "chat", "", "")])
        builder = InvertedIndexBuilder(corpus)
        out = tmp_path / "combined.tsv"
        builder.build_combined_index(
            ["titre", "texte"],
            out,
            weights={"titre": 2.0, "texte": 1.0},
        )
        index = _read_index(out)
        assert "chat" in index
        # "chat" appears once in titre (×2) + once in texte (×1) → score 3.0
        assert "1:3.00" in index["chat"]

    def test_default_weight_is_one(self, tmp_path: Path) -> None:
        corpus = tmp_path / "corpus.xml"
        _write_corpus(corpus, [("1", "chat", "", "", "")])
        builder = InvertedIndexBuilder(corpus)
        out = tmp_path / "combined.tsv"
        builder.build_combined_index(["titre"], out)
        index = _read_index(out)
        assert "1:1.00" in index["chat"]

    def test_returns_distinct_term_count(self, tmp_path: Path) -> None:
        corpus = tmp_path / "corpus.xml"
        _write_corpus(corpus, [("1", "chat chien", "chat oiseau", "", "")])
        builder = InvertedIndexBuilder(corpus)
        out = tmp_path / "combined.tsv"
        count = builder.build_combined_index(["titre", "texte"], out)
        # "chat", "chien", "oiseau" → 3 distinct terms
        assert count == 3


# ---------------------------------------------------------------------------
# build_facet_index
# ---------------------------------------------------------------------------


class TestBuildFacetIndex:
    def test_single_rubrique(self, tmp_path: Path) -> None:
        corpus = tmp_path / "corpus.xml"
        _write_corpus(corpus, [("1", "", "", "Physique", "")])
        builder = InvertedIndexBuilder(corpus)
        out = tmp_path / "rubrique.tsv"
        builder.build_facet_index("rubrique", out)
        index = _read_index(out)
        assert "physique" in index
        assert "1" in index["physique"]

    def test_multiple_docs_same_rubrique(self, tmp_path: Path) -> None:
        corpus = tmp_path / "corpus.xml"
        _write_corpus(
            corpus,
            [("1", "", "", "Chimie", ""), ("2", "", "", "Chimie", "")],
        )
        builder = InvertedIndexBuilder(corpus)
        out = tmp_path / "rubrique.tsv"
        builder.build_facet_index("rubrique", out)
        index = _read_index(out)
        assert "1" in index["chimie"] and "2" in index["chimie"]

    def test_facet_value_lowercased(self, tmp_path: Path) -> None:
        corpus = tmp_path / "corpus.xml"
        _write_corpus(corpus, [("1", "", "", "BIOLOGIE", "")])
        builder = InvertedIndexBuilder(corpus)
        out = tmp_path / "rubrique.tsv"
        builder.build_facet_index("rubrique", out)
        index = _read_index(out)
        assert "biologie" in index
        assert "BIOLOGIE" not in index

    def test_absent_field_yields_empty_index(self, tmp_path: Path) -> None:
        corpus = tmp_path / "corpus.xml"
        corpus.write_text(
            "<corpus><document><article>1</article></document></corpus>",
            encoding="utf-8",
        )
        builder = InvertedIndexBuilder(corpus)
        out = tmp_path / "rubrique.tsv"
        count = builder.build_facet_index("rubrique", out)
        assert count == 0

    def test_returns_number_of_distinct_facets(self, tmp_path: Path) -> None:
        corpus = tmp_path / "corpus.xml"
        _write_corpus(
            corpus,
            [("1", "", "", "Physique", ""), ("2", "", "", "Chimie", "")],
        )
        builder = InvertedIndexBuilder(corpus)
        out = tmp_path / "rubrique.tsv"
        count = builder.build_facet_index("rubrique", out)
        assert count == 2


# ---------------------------------------------------------------------------
# build_date_index
# ---------------------------------------------------------------------------


class TestBuildDateIndex:
    def test_extracts_month_year(self, tmp_path: Path) -> None:
        corpus = tmp_path / "corpus.xml"
        _write_corpus(corpus, [("1", "", "", "", "15/06/2013")])
        builder = InvertedIndexBuilder(corpus)
        out = tmp_path / "date.tsv"
        builder.build_date_index(out)
        index = _read_index(out)
        assert "06/2013" in index
        assert "1" in index["06/2013"]

    def test_multiple_docs_same_month(self, tmp_path: Path) -> None:
        corpus = tmp_path / "corpus.xml"
        _write_corpus(
            corpus,
            [("1", "", "", "", "01/03/2012"), ("2", "", "", "", "15/03/2012")],
        )
        builder = InvertedIndexBuilder(corpus)
        out = tmp_path / "date.tsv"
        builder.build_date_index(out)
        index = _read_index(out)
        assert "1" in index["03/2012"] and "2" in index["03/2012"]

    def test_distinct_months_get_separate_entries(self, tmp_path: Path) -> None:
        corpus = tmp_path / "corpus.xml"
        _write_corpus(
            corpus,
            [("1", "", "", "", "01/01/2012"), ("2", "", "", "", "01/02/2012")],
        )
        builder = InvertedIndexBuilder(corpus)
        out = tmp_path / "date.tsv"
        count = builder.build_date_index(out)
        assert count == 2

    def test_malformed_date_is_skipped(self, tmp_path: Path) -> None:
        corpus = tmp_path / "corpus.xml"
        _write_corpus(corpus, [("1", "", "", "", "2013-06-15")])
        builder = InvertedIndexBuilder(corpus)
        out = tmp_path / "date.tsv"
        count = builder.build_date_index(out)
        assert count == 0

    def test_missing_date_field_skipped(self, tmp_path: Path) -> None:
        corpus = tmp_path / "corpus.xml"
        corpus.write_text(
            "<corpus><document><article>1</article></document></corpus>",
            encoding="utf-8",
        )
        builder = InvertedIndexBuilder(corpus)
        out = tmp_path / "date.tsv"
        count = builder.build_date_index(out)
        assert count == 0

    def test_dates_sorted_in_output(self, tmp_path: Path) -> None:
        corpus = tmp_path / "corpus.xml"
        _write_corpus(
            corpus,
            [
                ("3", "", "", "", "01/12/2014"),
                ("1", "", "", "", "01/01/2011"),
                ("2", "", "", "", "01/06/2013"),
            ],
        )
        builder = InvertedIndexBuilder(corpus)
        out = tmp_path / "date.tsv"
        builder.build_date_index(out)
        periods = list(_read_index(out).keys())
        assert periods == sorted(periods)

    def test_real_mini_corpus(self, mini_corpus_path: Path, tmp_path: Path) -> None:
        builder = InvertedIndexBuilder(mini_corpus_path)
        out = tmp_path / "date.tsv"
        count = builder.build_date_index(out)
        assert count > 0


# ---------------------------------------------------------------------------
# Output file creation
# ---------------------------------------------------------------------------


class TestOutputFileCreation:
    def test_creates_parent_directories(self, tmp_path: Path) -> None:
        corpus = tmp_path / "corpus.xml"
        _write_corpus(corpus, [("1", "chat", "", "", "")])
        builder = InvertedIndexBuilder(corpus)
        deep_path = tmp_path / "a" / "b" / "c" / "index.tsv"
        builder.build_text_index("titre", deep_path)
        assert deep_path.exists()
