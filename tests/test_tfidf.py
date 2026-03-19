"""Tests for TD2 TF-IDF module."""

import math
from pathlib import Path

import pytest

from adit_corpus_indexing.tfidf import compute_idf, compute_tf, compute_tfidf


def _write_tokens(path: Path, rows: list[tuple[str, str]]) -> None:
    """Write (doc_id, token) pairs to a tokens TSV file."""
    path.write_text(
        "\n".join(f"{doc_id}\t{token}" for doc_id, token in rows) + "\n",
        encoding="utf-8",
    )


def _read_tf(path: Path) -> dict[tuple[str, str], float]:
    """Read tf.tsv into a {(doc_id, token): tf} dict."""
    result: dict[tuple[str, str], float] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        doc_id, token, tf = line.split("\t")
        result[(doc_id, token)] = float(tf)
    return result


def _read_idf(path: Path) -> dict[str, float]:
    """Read idf.tsv into a {token: idf} dict."""
    result: dict[str, float] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        token, idf = line.split("\t")
        result[token] = float(idf)
    return result


def _read_tfidf(path: Path) -> dict[tuple[str, str], float]:
    """Read tfidf.tsv into a {(doc_id, token): tfidf} dict."""
    result: dict[tuple[str, str], float] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        doc_id, token, score = line.split("\t")
        result[(doc_id, token)] = float(score)
    return result


class TestComputeTF:
    def test_single_occurrence_gives_one(self, tmp_path: Path) -> None:
        # count=1 → tf = 1 + log10(1) = 1.0
        tokens = tmp_path / "tokens.tsv"
        _write_tokens(tokens, [("1", "chat")])
        out = tmp_path / "tf.tsv"
        compute_tf(tokens, out)
        tf = _read_tf(out)
        assert tf[("1", "chat")] == pytest.approx(1.0)

    def test_two_occurrences_applies_log(self, tmp_path: Path) -> None:
        # count=2 → tf = 1 + log10(2) ≈ 1.301
        tokens = tmp_path / "tokens.tsv"
        _write_tokens(tokens, [("1", "chat"), ("1", "chat")])
        out = tmp_path / "tf.tsv"
        compute_tf(tokens, out)
        tf = _read_tf(out)
        assert tf[("1", "chat")] == pytest.approx(1.0 + math.log10(2), rel=1e-5)

    def test_ten_occurrences_gives_two(self, tmp_path: Path) -> None:
        # count=10 → tf = 1 + log10(10) = 2.0  (the log scale from the course)
        tokens = tmp_path / "tokens.tsv"
        _write_tokens(tokens, [("1", "mot")] * 10)
        out = tmp_path / "tf.tsv"
        compute_tf(tokens, out)
        tf = _read_tf(out)
        assert tf[("1", "mot")] == pytest.approx(2.0)

    def test_different_tokens_each_count_one(self, tmp_path: Path) -> None:
        # Two distinct tokens, 1 occurrence each → tf = 1.0 independently
        tokens = tmp_path / "tokens.tsv"
        _write_tokens(tokens, [("1", "chat"), ("1", "chien")])
        out = tmp_path / "tf.tsv"
        compute_tf(tokens, out)
        tf = _read_tf(out)
        assert tf[("1", "chat")] == pytest.approx(1.0)
        assert tf[("1", "chien")] == pytest.approx(1.0)

    def test_tf_strictly_greater_than_zero_for_any_occurrence(
        self, tmp_path: Path
    ) -> None:
        # 1 + log10(count) > 0 for any count >= 1
        tokens = tmp_path / "tokens.tsv"
        _write_tokens(tokens, [("1", "mot")])
        out = tmp_path / "tf.tsv"
        compute_tf(tokens, out)
        tf = _read_tf(out)
        assert tf[("1", "mot")] > 0.0

    def test_multiple_documents_are_independent(self, tmp_path: Path) -> None:
        # Doc 1: "chat" × 1 → tf=1.0; Doc 2: "chat" × 2 → tf=1+log10(2)
        tokens = tmp_path / "tokens.tsv"
        _write_tokens(
            tokens,
            [("1", "chat"), ("1", "chien"), ("2", "chat"), ("2", "chat")],
        )
        out = tmp_path / "tf.tsv"
        compute_tf(tokens, out)
        tf = _read_tf(out)
        assert tf[("1", "chat")] == pytest.approx(1.0)
        assert tf[("2", "chat")] == pytest.approx(1.0 + math.log10(2), rel=1e-5)

    def test_output_file_is_created(self, tmp_path: Path) -> None:
        tokens = tmp_path / "tokens.tsv"
        _write_tokens(tokens, [("1", "mot")])
        out = tmp_path / "tf.tsv"
        compute_tf(tokens, out)
        assert out.exists()

    def test_empty_tokens_file_produces_empty_output(self, tmp_path: Path) -> None:
        tokens = tmp_path / "tokens.tsv"
        tokens.write_text("", encoding="utf-8")
        out = tmp_path / "tf.tsv"
        compute_tf(tokens, out)
        assert out.read_text(encoding="utf-8") == ""


class TestComputeIDF:
    def test_token_in_all_documents_has_zero_idf(self, tmp_path: Path) -> None:
        # log10(2/2) = log10(1) = 0
        tokens = tmp_path / "tokens.tsv"
        _write_tokens(tokens, [("1", "le"), ("2", "le")])
        out = tmp_path / "idf.tsv"
        compute_idf(tokens, out)
        idf = _read_idf(out)
        assert idf["le"] == pytest.approx(0.0)

    def test_token_in_one_of_two_documents(self, tmp_path: Path) -> None:
        # log10(2/1) = log10(2) ≈ 0.301
        tokens = tmp_path / "tokens.tsv"
        _write_tokens(tokens, [("1", "chat"), ("2", "chien")])
        out = tmp_path / "idf.tsv"
        compute_idf(tokens, out)
        idf = _read_idf(out)
        assert idf["chat"] == pytest.approx(math.log10(2), rel=1e-5)
        assert idf["chien"] == pytest.approx(math.log10(2), rel=1e-5)

    def test_idf_formula_log10_n_over_df(self, tmp_path: Path) -> None:
        # N=3 docs, "chat" in 1 doc → idf = log10(3/1)
        tokens = tmp_path / "tokens.tsv"
        _write_tokens(
            tokens,
            [("1", "chat"), ("2", "chien"), ("3", "oiseau")],
        )
        out = tmp_path / "idf.tsv"
        compute_idf(tokens, out)
        idf = _read_idf(out)
        assert idf["chat"] == pytest.approx(math.log10(3), rel=1e-5)

    def test_duplicate_token_in_same_doc_counted_once(self, tmp_path: Path) -> None:
        # "chat" appears twice in doc 1 but df("chat") = 1
        tokens = tmp_path / "tokens.tsv"
        _write_tokens(tokens, [("1", "chat"), ("1", "chat"), ("2", "chien")])
        out = tmp_path / "idf.tsv"
        compute_idf(tokens, out)
        idf = _read_idf(out)
        assert idf["chat"] == pytest.approx(math.log10(2), rel=1e-5)

    def test_sorted_by_ascending_idf(self, tmp_path: Path) -> None:
        # "le" in all docs → idf=0; "rare" in 1 doc → higher idf
        tokens = tmp_path / "tokens.tsv"
        _write_tokens(
            tokens,
            [("1", "le"), ("2", "le"), ("3", "le"), ("1", "rare")],
        )
        out = tmp_path / "idf.tsv"
        compute_idf(tokens, out)
        idf = _read_idf(out)
        assert idf["le"] < idf["rare"]

    def test_empty_tokens_file_produces_empty_output(self, tmp_path: Path) -> None:
        tokens = tmp_path / "tokens.tsv"
        tokens.write_text("", encoding="utf-8")
        out = tmp_path / "idf.tsv"
        compute_idf(tokens, out)
        assert out.read_text(encoding="utf-8") == ""


class TestComputeTFIDF:
    def test_score_equals_tf_times_idf(self, tmp_path: Path) -> None:
        # compute_tfidf is a pure multiplication — tf and idf values come from files
        tf_path = tmp_path / "tf.tsv"
        idf_path = tmp_path / "idf.tsv"
        tf_path.write_text("1\tchat\t1.30103000\n", encoding="utf-8")
        idf_path.write_text(f"chat\t{math.log10(2):.8f}\n", encoding="utf-8")
        out = tmp_path / "tfidf.tsv"
        compute_tfidf(tf_path, idf_path, out)
        scores = _read_tfidf(out)
        assert scores[("1", "chat")] == pytest.approx(1.30103 * math.log10(2), rel=1e-5)

    def test_token_not_in_idf_gets_zero_score(self, tmp_path: Path) -> None:
        tf_path = tmp_path / "tf.tsv"
        idf_path = tmp_path / "idf.tsv"
        tf_path.write_text("1\tunknown\t1.00000000\n", encoding="utf-8")
        idf_path.write_text("chat\t0.30103000\n", encoding="utf-8")
        out = tmp_path / "tfidf.tsv"
        compute_tfidf(tf_path, idf_path, out)
        scores = _read_tfidf(out)
        assert scores[("1", "unknown")] == pytest.approx(0.0)

    def test_zero_idf_gives_zero_tfidf(self, tmp_path: Path) -> None:
        tf_path = tmp_path / "tf.tsv"
        idf_path = tmp_path / "idf.tsv"
        tf_path.write_text("1\tle\t1.00000000\n", encoding="utf-8")
        idf_path.write_text("le\t0.00000000\n", encoding="utf-8")
        out = tmp_path / "tfidf.tsv"
        compute_tfidf(tf_path, idf_path, out)
        scores = _read_tfidf(out)
        assert scores[("1", "le")] == pytest.approx(0.0)

    def test_output_has_same_row_count_as_tf(self, tmp_path: Path) -> None:
        tf_path = tmp_path / "tf.tsv"
        idf_path = tmp_path / "idf.tsv"
        tf_path.write_text(
            "1\tchat\t1.00000000\n1\tchien\t1.00000000\n", encoding="utf-8"
        )
        idf_path.write_text(
            f"chat\t{math.log10(2):.8f}\nchien\t{math.log10(2):.8f}\n",
            encoding="utf-8",
        )
        out = tmp_path / "tfidf.tsv"
        compute_tfidf(tf_path, idf_path, out)
        scores = _read_tfidf(out)
        assert len(scores) == 2

    def test_pipeline_integration(self, mini_corpus_path: Path, tmp_path: Path) -> None:
        """Full pipeline: segmente → tf → idf → tfidf."""
        from adit_corpus_indexing.tokenizer import segmente

        tokens_path = tmp_path / "tokens.tsv"
        tf_path = tmp_path / "tf.tsv"
        idf_path = tmp_path / "idf.tsv"
        tfidf_path = tmp_path / "tfidf.tsv"

        segmente(mini_corpus_path, tokens_path)
        compute_tf(tokens_path, tf_path)
        compute_idf(tokens_path, idf_path)
        compute_tfidf(tf_path, idf_path, tfidf_path)

        scores = _read_tfidf(tfidf_path)
        # All tf-idf scores are non-negative (tf ≥ 1 when present, idf ≥ 0)
        for score in scores.values():
            assert score >= 0.0
        # Tokens with idf=0 yield tfidf=0 regardless of tf
        idf = _read_idf(idf_path)
        zero_idf_tokens = {t for t, v in idf.items() if v == pytest.approx(0.0)}
        for (_doc, token), score in scores.items():
            if token in zero_idf_tokens:
                assert score == pytest.approx(0.0)
