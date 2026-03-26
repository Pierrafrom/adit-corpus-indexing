"""Tests for TD3 — lemmatizer module.

Coverage targets:
- SnowballLemmatizer  : lemmatize(), extract_vocabulary(), extract_from_corpus()
- SpacyLemmatizer     : lemmatize(), extract_vocabulary(), extract_from_corpus()
- LemmatizationComparator: _load_table(), _compute_stats(), stats(), best_method()
- lemmatize_corpus_tokens()
- apply_lemmatization_to_corpus()

SpaCy tests are skipped when ``fr_core_news_sm`` is not installed.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from adit_corpus_indexing.lemmatizer import (
    LemmatizationComparator,
    SnowballLemmatizer,
    SpacyLemmatizer,
    apply_lemmatization_to_corpus,
    lemmatize_corpus_tokens,
)
from adit_corpus_indexing.models import LemmatizationEntry, LemmatizationStats

FIXTURES_DIR = Path(__file__).parent / "fixtures"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_corpus(path: Path, docs: list[tuple[str, str, str]]) -> None:
    """Write a minimal corpus XML with (article_id, titre, texte) triples."""
    lines = ["<?xml version='1.0' encoding='utf-8'?>", "<corpus>"]
    for article_id, titre, texte in docs:
        lines += [
            "  <document>",
            f"    <article>{article_id}</article>",
            f"    <titre>{titre}</titre>",
            f"    <texte>{texte}</texte>",
            "  </document>",
        ]
    lines.append("</corpus>")
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_lemma_tsv(path: Path, entries: list[tuple[str, str]]) -> None:
    """Write a two-column word\tlemma TSV."""
    path.write_text(
        "\n".join(f"{w}\t{lem}" for w, lem in entries) + "\n",
        encoding="utf-8",
    )


def _write_antidico(path: Path, stop_lemmas: list[str]) -> None:
    """Write an antidictionary TSV (lemma → empty replacement)."""
    path.write_text(
        "\n".join(f"{lem}\t" for lem in stop_lemmas) + "\n",
        encoding="utf-8",
    )


def _spacy_available() -> bool:
    try:
        import spacy  # noqa: F401

        spacy.load("fr_core_news_sm")
        return True
    except Exception:
        return False


requires_spacy = pytest.mark.skipif(
    not _spacy_available(),
    reason="fr_core_news_sm not installed — skipping SpaCy tests",
)


# ---------------------------------------------------------------------------
# SnowballLemmatizer
# ---------------------------------------------------------------------------


class TestSnowballLemmatizer:
    def test_lemmatize_returns_string(self) -> None:
        lem = SnowballLemmatizer()
        result = lem.lemmatize("mangeait")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_lemmatize_lowercase_output(self) -> None:
        lem = SnowballLemmatizer()
        assert lem.lemmatize("INFORMATIQUE") == lem.lemmatize("informatique")

    def test_lemmatize_same_root_words_share_stem(self) -> None:
        # "manger" and "mangeait" should produce the same Snowball stem.
        lem = SnowballLemmatizer()
        assert lem.lemmatize("manger") == lem.lemmatize("mangeait")

    def test_name_is_snowball(self) -> None:
        assert SnowballLemmatizer().name == "snowball"

    def test_extract_vocabulary_returns_entries(self, tmp_path: Path) -> None:
        corpus = tmp_path / "corpus.xml"
        _write_corpus(corpus, [("1", "chat mange souris", "chien court vite")])
        lem = SnowballLemmatizer()
        entries = lem.extract_vocabulary(corpus)
        assert len(entries) > 0
        assert all(isinstance(e, LemmatizationEntry) for e in entries)

    def test_extract_vocabulary_one_entry_per_unique_word(self, tmp_path: Path) -> None:
        # "chat" appears in both titre and texte — only one entry expected.
        corpus = tmp_path / "corpus.xml"
        _write_corpus(corpus, [("1", "chat rouge", "chat bleu")])
        lem = SnowballLemmatizer()
        entries = lem.extract_vocabulary(corpus)
        words = [e.word for e in entries]
        assert len(words) == len(set(words))

    def test_extract_vocabulary_sorted_alphabetically(self, tmp_path: Path) -> None:
        corpus = tmp_path / "corpus.xml"
        _write_corpus(corpus, [("1", "zèbre amour chat", "")])
        lem = SnowballLemmatizer()
        entries = lem.extract_vocabulary(corpus)
        words = [e.word for e in entries]
        assert words == sorted(words)

    def test_extract_from_corpus_writes_tsv(self, tmp_path: Path) -> None:
        corpus = tmp_path / "corpus.xml"
        _write_corpus(corpus, [("1", "chat mange", "chien court")])
        out = tmp_path / "lemmes.tsv"
        SnowballLemmatizer().extract_from_corpus(corpus, out)
        assert out.exists()
        lines = out.read_text(encoding="utf-8").splitlines()
        assert all("\t" in line for line in lines if line)

    def test_extract_from_corpus_two_columns(self, tmp_path: Path) -> None:
        corpus = tmp_path / "corpus.xml"
        _write_corpus(corpus, [("1", "chat", "")])
        out = tmp_path / "lemmes.tsv"
        SnowballLemmatizer().extract_from_corpus(corpus, out)
        for line in out.read_text(encoding="utf-8").splitlines():
            if line:
                assert len(line.split("\t")) == 2

    def test_empty_corpus_produces_empty_tsv(self, tmp_path: Path) -> None:
        corpus = tmp_path / "corpus.xml"
        corpus.write_text("<corpus></corpus>", encoding="utf-8")
        out = tmp_path / "lemmes.tsv"
        SnowballLemmatizer().extract_from_corpus(corpus, out)
        assert out.read_text(encoding="utf-8") == ""


# ---------------------------------------------------------------------------
# SpaCy lemmatizer
# ---------------------------------------------------------------------------


class TestSpacyLemmatizer:
    @requires_spacy
    def test_lemmatize_returns_string(self) -> None:
        lem = SpacyLemmatizer()
        result = lem.lemmatize("mangeait")
        assert isinstance(result, str)
        assert len(result) > 0

    @requires_spacy
    def test_lemmatize_lowercase_output(self) -> None:
        lem = SpacyLemmatizer()
        assert lem.lemmatize("chat") == lem.lemmatize("chat")
        assert lem.lemmatize("chat") == lem.lemmatize("chat").lower()

    @requires_spacy
    def test_lemmatize_verb_form(self) -> None:
        # "mangeait" should lemmatize to "manger"
        lem = SpacyLemmatizer()
        result = lem.lemmatize("mangeait")
        assert result == "manger"

    @requires_spacy
    def test_name_is_spacy(self) -> None:
        assert SpacyLemmatizer().name == "spacy"

    @requires_spacy
    def test_extract_vocabulary_returns_entries(self, tmp_path: Path) -> None:
        corpus = tmp_path / "corpus.xml"
        _write_corpus(corpus, [("1", "chat mange souris", "chien court vite")])
        lem = SpacyLemmatizer()
        entries = lem.extract_vocabulary(corpus)
        assert len(entries) > 0

    @requires_spacy
    def test_extract_vocabulary_uses_batch_and_matches_single(
        self, tmp_path: Path
    ) -> None:
        """Batch result from extract_vocabulary must match single-word lemmatize()."""
        corpus = tmp_path / "corpus.xml"
        _write_corpus(corpus, [("1", "chat chien", "")])
        lem = SpacyLemmatizer()
        entries = {e.word: e.lemma for e in lem.extract_vocabulary(corpus)}
        for word, lemma in entries.items():
            assert lemma == lem.lemmatize(word)

    @requires_spacy
    def test_extract_from_corpus_writes_tsv(self, tmp_path: Path) -> None:
        corpus = tmp_path / "corpus.xml"
        _write_corpus(corpus, [("1", "chat mange", "")])
        out = tmp_path / "lemmes_spacy.tsv"
        SpacyLemmatizer().extract_from_corpus(corpus, out)
        assert out.exists()
        lines = [ln for ln in out.read_text(encoding="utf-8").splitlines() if ln]
        assert len(lines) > 0
        assert all(len(ln.split("\t")) == 2 for ln in lines)


# ---------------------------------------------------------------------------
# LemmatizationComparator
# ---------------------------------------------------------------------------


class TestLemmatizationComparator:
    def _make_tsvs(
        self,
        tmp_path: Path,
        spacy_entries: list[tuple[str, str]],
        snowball_entries: list[tuple[str, str]],
    ) -> tuple[Path, Path]:
        spacy_tsv = tmp_path / "spacy.tsv"
        snow_tsv = tmp_path / "snowball.tsv"
        _write_lemma_tsv(spacy_tsv, spacy_entries)
        _write_lemma_tsv(snow_tsv, snowball_entries)
        return spacy_tsv, snow_tsv

    def test_load_table_reads_entries(self, tmp_path: Path) -> None:
        tsv = tmp_path / "t.tsv"
        _write_lemma_tsv(tsv, [("chat", "chat"), ("mangeait", "manger")])
        table = LemmatizationComparator._load_table(tsv)
        assert table["chat"] == "chat"
        assert table["mangeait"] == "manger"

    def test_load_table_skips_blank_lines(self, tmp_path: Path) -> None:
        tsv = tmp_path / "t.tsv"
        tsv.write_text("chat\tchat\n\nchien\tchien\n", encoding="utf-8")
        table = LemmatizationComparator._load_table(tsv)
        assert len(table) == 2

    def test_compute_stats_unique_words(self, tmp_path: Path) -> None:
        spacy, snow = self._make_tsvs(
            tmp_path,
            [("a", "x"), ("b", "x"), ("c", "y")],
            [("a", "a"), ("b", "b"), ("c", "c")],
        )
        comp = LemmatizationComparator(spacy, snow)
        sp_stats, _ = comp.stats()
        assert sp_stats.unique_words == 3

    def test_compute_stats_unique_lemmas(self, tmp_path: Path) -> None:
        # "a" and "b" both map to "x" → 2 unique lemmas ("x", "y")
        spacy, snow = self._make_tsvs(
            tmp_path,
            [("a", "x"), ("b", "x"), ("c", "y")],
            [("a", "a"), ("b", "b"), ("c", "c")],
        )
        comp = LemmatizationComparator(spacy, snow)
        sp_stats, _ = comp.stats()
        assert sp_stats.unique_lemmas == 2

    def test_compute_stats_compression_ratio(self, tmp_path: Path) -> None:
        spacy, snow = self._make_tsvs(
            tmp_path,
            [("a", "x"), ("b", "x"), ("c", "y")],
            [("a", "a"), ("b", "b"), ("c", "c")],
        )
        comp = LemmatizationComparator(spacy, snow)
        sp_stats, snow_stats = comp.stats()
        # spaCy: 2 unique lemmas / 3 words ≈ 0.667
        assert sp_stats.compression_ratio == pytest.approx(2 / 3)
        # Snowball (identity): 3/3 = 1.0
        assert snow_stats.compression_ratio == pytest.approx(1.0)

    def test_compute_stats_top_collisions(self, tmp_path: Path) -> None:
        spacy, snow = self._make_tsvs(
            tmp_path,
            [("a", "x"), ("b", "x"), ("c", "x")],
            [("a", "a"), ("b", "b"), ("c", "c")],
        )
        comp = LemmatizationComparator(spacy, snow, top_n=1)
        sp_stats, _ = comp.stats()
        assert "x" in sp_stats.top_collisions
        assert set(sp_stats.top_collisions["x"]) == {"a", "b", "c"}

    def test_best_method_lower_compression_wins(self, tmp_path: Path) -> None:
        # spaCy groups aggressively (low ratio) → should win
        spacy, snow = self._make_tsvs(
            tmp_path,
            [("a", "x"), ("b", "x"), ("c", "y")],  # ratio = 2/3
            [("a", "a"), ("b", "b"), ("c", "c")],  # ratio = 3/3 = 1.0
        )
        comp = LemmatizationComparator(spacy, snow)
        assert comp.best_method() == "spacy"

    def test_best_method_tiebreak_favours_spacy(self, tmp_path: Path) -> None:
        # Both methods produce identical ratios → SpaCy wins.
        entries = [("a", "x"), ("b", "y"), ("c", "z")]
        spacy, snow = self._make_tsvs(tmp_path, entries, entries)
        comp = LemmatizationComparator(spacy, snow)
        assert comp.best_method() == "spacy"

    def test_print_report_smoke(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        spacy, snow = self._make_tsvs(
            tmp_path,
            [("chat", "chat"), ("chats", "chat")],
            [("chat", "chat"), ("chats", "chat")],
        )
        comp = LemmatizationComparator(spacy, snow)
        comp.print_report()  # Must not raise
        output = capsys.readouterr().out
        assert "RECOMMENDATION" in output

    def test_stats_returns_two_stats_objects(self, tmp_path: Path) -> None:
        spacy, snow = self._make_tsvs(tmp_path, [("a", "b")], [("a", "a")])
        comp = LemmatizationComparator(spacy, snow)
        result = comp.stats()
        assert len(result) == 2
        assert all(isinstance(s, LemmatizationStats) for s in result)


# ---------------------------------------------------------------------------
# lemmatize_corpus_tokens
# ---------------------------------------------------------------------------


class TestLemmatizeCorpusTokens:
    def test_produces_doc_id_lemma_pairs(self, tmp_path: Path) -> None:
        corpus = tmp_path / "corpus.xml"
        _write_corpus(corpus, [("42", "chat mange", "")])
        tsv = tmp_path / "lemmes.tsv"
        _write_lemma_tsv(tsv, [("chat", "chat"), ("mange", "manger")])
        out = tmp_path / "tokens_lem.tsv"
        lemmatize_corpus_tokens(corpus, tsv, out)

        lines = [ln for ln in out.read_text(encoding="utf-8").splitlines() if ln]
        assert len(lines) == 2  # two tokens
        for line in lines:
            doc_id, lemma = line.split("\t")
            assert doc_id == "42"
            assert lemma in ("chat", "manger")

    def test_unknown_words_fall_back_to_surface_form(self, tmp_path: Path) -> None:
        corpus = tmp_path / "corpus.xml"
        _write_corpus(corpus, [("1", "inconnu", "")])
        tsv = tmp_path / "lemmes.tsv"
        _write_lemma_tsv(tsv, [("chat", "chat")])  # "inconnu" not in mapping
        out = tmp_path / "tokens_lem.tsv"
        lemmatize_corpus_tokens(corpus, tsv, out)

        lines = [ln for ln in out.read_text(encoding="utf-8").splitlines() if ln]
        assert lines[0].split("\t")[1] == "inconnu"

    def test_multiple_documents(self, tmp_path: Path) -> None:
        corpus = tmp_path / "corpus.xml"
        _write_corpus(corpus, [("1", "chat", ""), ("2", "chien", "")])
        tsv = tmp_path / "lemmes.tsv"
        _write_lemma_tsv(tsv, [("chat", "chat"), ("chien", "chien")])
        out = tmp_path / "tokens_lem.tsv"
        lemmatize_corpus_tokens(corpus, tsv, out)
        lines = [ln for ln in out.read_text(encoding="utf-8").splitlines() if ln]
        doc_ids = {ln.split("\t")[0] for ln in lines}
        assert doc_ids == {"1", "2"}

    def test_empty_corpus_produces_empty_file(self, tmp_path: Path) -> None:
        corpus = tmp_path / "corpus.xml"
        corpus.write_text("<corpus></corpus>", encoding="utf-8")
        tsv = tmp_path / "lemmes.tsv"
        tsv.write_text("", encoding="utf-8")
        out = tmp_path / "tokens_lem.tsv"
        lemmatize_corpus_tokens(corpus, tsv, out)
        assert out.read_text(encoding="utf-8") == ""


# ---------------------------------------------------------------------------
# apply_lemmatization_to_corpus
# ---------------------------------------------------------------------------


class TestApplyLemmatizationToCorpus:
    def test_produces_valid_xml(self, tmp_path: Path) -> None:
        from lxml import etree

        corpus = tmp_path / "corpus.xml"
        _write_corpus(corpus, [("1", "chat mange", "chien court")])
        tsv = tmp_path / "lemmes.tsv"
        _write_lemma_tsv(
            tsv,
            [
                ("chat", "chat"),
                ("mange", "manger"),
                ("chien", "chien"),
                ("court", "courir"),
            ],
        )
        anti = tmp_path / "anti.tsv"
        _write_antidico(anti, [])
        out = tmp_path / "corpus_final.xml"
        apply_lemmatization_to_corpus(corpus, tsv, anti, out)
        tree = etree.parse(str(out))
        assert tree.getroot().tag == "corpus"

    def test_stop_lemmas_are_removed(self, tmp_path: Path) -> None:
        corpus = tmp_path / "corpus.xml"
        _write_corpus(corpus, [("1", "chat mange chien", "")])
        tsv = tmp_path / "lemmes.tsv"
        _write_lemma_tsv(
            tsv, [("chat", "chat"), ("mange", "manger"), ("chien", "chien")]
        )
        anti = tmp_path / "anti.tsv"
        _write_antidico(anti, ["manger"])  # "mange" → "manger" → removed
        out = tmp_path / "corpus_final.xml"
        apply_lemmatization_to_corpus(corpus, tsv, anti, out)

        from lxml import etree

        root = etree.parse(str(out)).getroot()
        titre_text = root.find(".//titre")
        assert titre_text is not None
        words = (titre_text.text or "").split()
        assert "manger" not in words

    def test_unknown_words_are_kept(self, tmp_path: Path) -> None:
        corpus = tmp_path / "corpus.xml"
        _write_corpus(corpus, [("1", "inconnu", "")])
        tsv = tmp_path / "lemmes.tsv"
        tsv.write_text("", encoding="utf-8")  # empty mapping
        anti = tmp_path / "anti.tsv"
        _write_antidico(anti, [])
        out = tmp_path / "corpus_final.xml"
        apply_lemmatization_to_corpus(corpus, tsv, anti, out)

        from lxml import etree

        root = etree.parse(str(out)).getroot()
        titre_el = root.find(".//titre")
        assert titre_el is not None
        assert "inconnu" in (titre_el.text or "")

    def test_output_preserves_non_text_fields(self, tmp_path: Path) -> None:
        """Fields like <rubrique> and <date> must survive unchanged."""
        from lxml import etree

        corpus = tmp_path / "corpus.xml"
        lines = [
            "<?xml version='1.0' encoding='utf-8'?>",
            "<corpus><document>",
            "<article>1</article>",
            "<date>01/06/2013</date>",
            "<rubrique>Physique</rubrique>",
            "<titre>chat</titre>",
            "<texte>chien</texte>",
            "</document></corpus>",
        ]
        corpus.write_text("\n".join(lines), encoding="utf-8")
        tsv = tmp_path / "lemmes.tsv"
        _write_lemma_tsv(tsv, [("chat", "chat"), ("chien", "chien")])
        anti = tmp_path / "anti.tsv"
        _write_antidico(anti, [])
        out = tmp_path / "corpus_final.xml"
        apply_lemmatization_to_corpus(corpus, tsv, anti, out)
        root = etree.parse(str(out)).getroot()
        assert root.find(".//rubrique").text == "Physique"  # type: ignore[union-attr]
        assert root.find(".//date").text == "01/06/2013"  # type: ignore[union-attr]
