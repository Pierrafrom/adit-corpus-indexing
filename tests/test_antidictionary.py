"""Tests for TD2 anti-dictionary module."""

import math
from pathlib import Path

from lxml import etree

from adit_corpus_indexing.antidictionary import (
    AntiDictionary,
    apply_to_corpus,
    build_antidictionary,
    substitue,
)


def _write_idf(path: Path, rows: list[tuple[str, float]]) -> None:
    path.write_text(
        "\n".join(f"{token}\t{idf:.8f}" for token, idf in rows) + "\n",
        encoding="utf-8",
    )


def _read_antidico(path: Path) -> dict[str, str]:
    """Return {token: replacement} from an antidictionary TSV."""
    result: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        parts = line.split("\t", 1)
        result[parts[0]] = parts[1] if len(parts) > 1 else ""
    return result


class TestBuildAntidictionary:
    def test_low_idf_tokens_are_selected(self, tmp_path: Path) -> None:
        idf_path = tmp_path / "idf.tsv"
        _write_idf(idf_path, [("le", 0.0), ("chat", math.log10(3))])
        out = tmp_path / "antidico.tsv"
        build_antidictionary(idf_path, out, threshold=0.5)
        antidico = _read_antidico(out)
        assert "le" in antidico

    def test_mid_idf_tokens_are_excluded_from_default_call(
        self, tmp_path: Path
    ) -> None:
        idf_path = tmp_path / "idf.tsv"
        _write_idf(idf_path, [("le", 0.0), ("biologie", math.log10(10))])
        out = tmp_path / "antidico.tsv"
        build_antidictionary(idf_path, out, threshold=0.5)
        antidico = _read_antidico(out)
        assert "biologie" not in antidico

    def test_low_threshold_boundary_is_inclusive(self, tmp_path: Path) -> None:
        idf_path = tmp_path / "idf.tsv"
        _write_idf(idf_path, [("exact", 0.5)])
        out = tmp_path / "antidico.tsv"
        build_antidictionary(idf_path, out, threshold=0.5)
        antidico = _read_antidico(out)
        assert "exact" in antidico

    def test_replacement_is_empty_string(self, tmp_path: Path) -> None:
        idf_path = tmp_path / "idf.tsv"
        _write_idf(idf_path, [("le", 0.0)])
        out = tmp_path / "antidico.tsv"
        build_antidictionary(idf_path, out, threshold=0.5)
        antidico = _read_antidico(out)
        assert antidico["le"] == ""

    def test_empty_idf_file_produces_empty_antidico(self, tmp_path: Path) -> None:
        idf_path = tmp_path / "idf.tsv"
        idf_path.write_text("", encoding="utf-8")
        out = tmp_path / "antidico.tsv"
        build_antidictionary(idf_path, out, threshold=1.0)
        assert out.read_text(encoding="utf-8") == ""

    def test_output_file_is_created(self, tmp_path: Path) -> None:
        idf_path = tmp_path / "idf.tsv"
        _write_idf(idf_path, [("le", 0.0)])
        out = tmp_path / "antidico.tsv"
        build_antidictionary(idf_path, out, threshold=0.5)
        assert out.exists()

    # --- Tests for the upper (max_threshold) cutoff ---

    def test_max_threshold_removes_hapax(self, tmp_path: Path) -> None:
        # idf = log10(3) ≈ 2.48 → above max_threshold=2.0 → stop word
        idf_path = tmp_path / "idf.tsv"
        _write_idf(idf_path, [("hapax", math.log10(3)), ("commun", 0.1)])
        out = tmp_path / "antidico.tsv"
        build_antidictionary(idf_path, out, threshold=0.5, max_threshold=2.0)
        antidico = _read_antidico(out)
        assert "hapax" in antidico

    def test_max_threshold_keeps_mid_idf_token(self, tmp_path: Path) -> None:
        # idf = 1.0 → between 0.5 and 2.0 → kept
        idf_path = tmp_path / "idf.tsv"
        _write_idf(idf_path, [("milieu", 1.0)])
        out = tmp_path / "antidico.tsv"
        build_antidictionary(idf_path, out, threshold=0.5, max_threshold=2.0)
        antidico = _read_antidico(out)
        assert "milieu" not in antidico

    def test_max_threshold_boundary_is_inclusive(self, tmp_path: Path) -> None:
        # token exactly at max_threshold → excluded
        idf_path = tmp_path / "idf.tsv"
        _write_idf(idf_path, [("limite", 2.0)])
        out = tmp_path / "antidico.tsv"
        build_antidictionary(idf_path, out, threshold=0.5, max_threshold=2.0)
        antidico = _read_antidico(out)
        assert "limite" in antidico

    def test_default_max_threshold_is_disabled(self, tmp_path: Path) -> None:
        # Without max_threshold, very high IDF tokens are kept
        idf_path = tmp_path / "idf.tsv"
        _write_idf(idf_path, [("hapax", 2.5)])
        out = tmp_path / "antidico.tsv"
        build_antidictionary(idf_path, out, threshold=0.5)
        antidico = _read_antidico(out)
        assert "hapax" not in antidico


class TestSubstitue:
    def _write_antidico(self, path: Path, entries: dict[str, str]) -> None:
        path.write_text(
            "\n".join(f"{token}\t{repl}" for token, repl in entries.items()) + "\n",
            encoding="utf-8",
        )

    def test_stop_word_is_removed(self, tmp_path: Path) -> None:
        antidico = tmp_path / "antidico.tsv"
        self._write_antidico(antidico, {"le": "", "la": ""})
        result = substitue("Le chat mange la souris", antidico)
        words = result.split()
        assert "le" not in words
        assert "Le" not in words
        assert "la" not in words

    def test_non_stop_word_is_preserved(self, tmp_path: Path) -> None:
        antidico = tmp_path / "antidico.tsv"
        self._write_antidico(antidico, {"le": ""})
        result = substitue("Le chat mange", antidico)
        assert "chat" in result
        assert "mange" in result

    def test_matching_is_case_insensitive(self, tmp_path: Path) -> None:
        antidico = tmp_path / "antidico.tsv"
        self._write_antidico(antidico, {"le": ""})
        result = substitue("LE chat", antidico)
        assert "LE" not in result
        assert "chat" in result

    def test_token_replaced_with_non_empty_string(self, tmp_path: Path) -> None:
        antidico = tmp_path / "antidico.tsv"
        self._write_antidico(antidico, {"chat": "félin"})
        result = substitue("Le chat dorme", antidico)
        assert "félin" in result
        assert "chat" not in result

    def test_whitespace_collapsed_after_removal(self, tmp_path: Path) -> None:
        antidico = tmp_path / "antidico.tsv"
        self._write_antidico(antidico, {"le": "", "la": "", "un": ""})
        result = substitue("le chat et la souris et un chien", antidico)
        assert "  " not in result

    def test_empty_text_returns_empty(self, tmp_path: Path) -> None:
        antidico = tmp_path / "antidico.tsv"
        self._write_antidico(antidico, {"le": ""})
        assert substitue("", antidico) == ""

    def test_all_tokens_removed_returns_empty(self, tmp_path: Path) -> None:
        antidico = tmp_path / "antidico.tsv"
        self._write_antidico(antidico, {"le": "", "chat": ""})
        result = substitue("le chat", antidico)
        assert result == ""

    def test_french_accents_handled(self, tmp_path: Path) -> None:
        antidico = tmp_path / "antidico.tsv"
        self._write_antidico(antidico, {"à": ""})
        result = substitue("aller à Paris", antidico)
        assert "à" not in result
        assert "Paris" in result


class TestApplyToCorpus:
    def _write_corpus(self, path: Path, documents: list[dict[str, str]]) -> None:
        root = etree.Element("corpus")
        for doc_data in documents:
            doc = etree.SubElement(root, "document")
            for tag, text in doc_data.items():
                el = etree.SubElement(doc, tag)
                el.text = text
        tree = etree.ElementTree(root)
        tree.write(str(path), encoding="utf-8", xml_declaration=True, pretty_print=True)

    def test_output_file_is_created(self, tmp_path: Path) -> None:
        corpus = tmp_path / "corpus.xml"
        self._write_corpus(
            corpus, [{"article": "1", "titre": "Test", "texte": "Corps"}]
        )
        antidico = tmp_path / "antidico.tsv"
        antidico.write_text("", encoding="utf-8")
        out = tmp_path / "corpus_filtered.xml"
        apply_to_corpus(corpus, antidico, out)
        assert out.exists()

    def test_stop_words_removed_from_titre(self, tmp_path: Path) -> None:
        corpus = tmp_path / "corpus.xml"
        self._write_corpus(
            corpus,
            [{"article": "1", "titre": "Le chat mange la souris", "texte": "Rien"}],
        )
        antidico = tmp_path / "antidico.tsv"
        antidico.write_text("le\t\nla\t\n", encoding="utf-8")
        out = tmp_path / "corpus_filtered.xml"
        apply_to_corpus(corpus, antidico, out)
        tree = etree.parse(str(out))
        titre = tree.find(".//titre")
        assert titre is not None
        titre_words = (titre.text or "").lower().split()
        assert "le" not in titre_words
        assert "la" not in titre_words
        assert "chat" in titre_words

    def test_stop_words_removed_from_texte(self, tmp_path: Path) -> None:
        corpus = tmp_path / "corpus.xml"
        self._write_corpus(
            corpus,
            [{"article": "1", "titre": "Titre", "texte": "Un chien court vite"}],
        )
        antidico = tmp_path / "antidico.tsv"
        antidico.write_text("un\t\n", encoding="utf-8")
        out = tmp_path / "corpus_filtered.xml"
        apply_to_corpus(corpus, antidico, out)
        tree = etree.parse(str(out))
        texte = tree.find(".//texte")
        assert texte is not None
        texte_words = (texte.text or "").lower().split()
        assert "un" not in texte_words
        assert "chien" in texte_words

    def test_other_fields_are_not_modified(self, tmp_path: Path) -> None:
        corpus = tmp_path / "corpus.xml"
        self._write_corpus(
            corpus,
            [
                {
                    "article": "1",
                    "bulletin": "BE France 1",
                    "titre": "Le test",
                    "texte": "Le corps",
                }
            ],
        )
        antidico = tmp_path / "antidico.tsv"
        antidico.write_text("le\t\n", encoding="utf-8")
        out = tmp_path / "corpus_filtered.xml"
        apply_to_corpus(corpus, antidico, out)
        tree = etree.parse(str(out))
        bulletin = tree.find(".//bulletin")
        assert bulletin is not None
        assert bulletin.text == "BE France 1"

    def test_document_count_is_preserved(
        self, mini_corpus_path: Path, tmp_path: Path
    ) -> None:
        antidico = tmp_path / "antidico.tsv"
        antidico.write_text("le\t\nla\t\nun\t\n", encoding="utf-8")
        out = tmp_path / "corpus_filtered.xml"
        apply_to_corpus(mini_corpus_path, antidico, out)
        tree = etree.parse(str(out))
        assert len(tree.findall(".//document")) == 3

    def test_full_pipeline_integration(
        self, mini_corpus_path: Path, tmp_path: Path
    ) -> None:
        """segmente → tf → idf → build_antidictionary → apply_to_corpus."""
        from adit_corpus_indexing.antidictionary import (
            apply_to_corpus,
            build_antidictionary,
        )
        from adit_corpus_indexing.tfidf import compute_idf, compute_tf
        from adit_corpus_indexing.tokenizer import segmente

        tokens = tmp_path / "tokens.tsv"
        tf = tmp_path / "tf.tsv"
        idf = tmp_path / "idf.tsv"
        antidico = tmp_path / "antidico.tsv"
        filtered = tmp_path / "corpus_filtered.xml"

        segmente(mini_corpus_path, tokens)
        compute_tf(tokens, tf)
        compute_idf(tokens, idf)
        # Very high threshold → all tokens become stop words
        build_antidictionary(idf, antidico, threshold=99.0)
        apply_to_corpus(mini_corpus_path, antidico, filtered)

        assert filtered.exists()
        tree = etree.parse(str(filtered))
        # With threshold=99, everything is filtered out
        for titre in tree.findall(".//titre"):
            assert (titre.text or "").strip() == ""


class TestAntiDictionary:
    def _write_antidico(self, path: Path, entries: dict[str, str]) -> None:
        path.write_text(
            "\n".join(f"{token}\t{repl}" for token, repl in entries.items()) + "\n",
            encoding="utf-8",
        )

    def test_len_reflects_entry_count(self, tmp_path: Path) -> None:
        antidico = tmp_path / "antidico.tsv"
        self._write_antidico(antidico, {"le": "", "la": "", "un": ""})
        assert len(AntiDictionary(antidico)) == 3

    def test_contains_stop_word(self, tmp_path: Path) -> None:
        antidico = tmp_path / "antidico.tsv"
        self._write_antidico(antidico, {"le": ""})
        anti = AntiDictionary(antidico)
        assert "le" in anti
        assert "Le" in anti  # case-insensitive

    def test_does_not_contain_unknown_token(self, tmp_path: Path) -> None:
        antidico = tmp_path / "antidico.tsv"
        self._write_antidico(antidico, {"le": ""})
        assert "chat" not in AntiDictionary(antidico)

    def test_apply_removes_stop_word(self, tmp_path: Path) -> None:
        antidico = tmp_path / "antidico.tsv"
        self._write_antidico(antidico, {"le": ""})
        result = AntiDictionary(antidico).apply("Le chat dort")
        assert "le" not in result.lower()
        assert "chat" in result

    def test_apply_strips_double_quotes(self, tmp_path: Path) -> None:
        antidico = tmp_path / "antidico.tsv"
        self._write_antidico(antidico, {"le": ""})
        result = AntiDictionary(antidico).apply('"Le chat"')
        assert '"' not in result
        assert "chat" in result

    def test_apply_strips_guillemets(self, tmp_path: Path) -> None:
        antidico = tmp_path / "antidico.tsv"
        antidico.write_text("", encoding="utf-8")
        result = AntiDictionary(antidico).apply("«Paris»")
        assert "«" not in result
        assert "»" not in result
        assert "Paris" in result

    def test_apply_strips_orphaned_comma(self, tmp_path: Path) -> None:
        antidico = tmp_path / "antidico.tsv"
        self._write_antidico(antidico, {"le": ""})
        result = AntiDictionary(antidico).apply("chat , souris")
        assert "," not in result
        assert "chat" in result

    def test_apply_is_reusable(self, tmp_path: Path) -> None:
        antidico = tmp_path / "antidico.tsv"
        self._write_antidico(antidico, {"le": ""})
        anti = AntiDictionary(antidico)
        r1 = anti.apply("le chat")
        r2 = anti.apply("le chien")
        assert "chat" in r1 and "le" not in r1
        assert "chien" in r2 and "le" not in r2
