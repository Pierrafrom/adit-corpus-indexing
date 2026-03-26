"""Tests for TD2 tokenizer module."""

from pathlib import Path

import pytest
from lxml import etree

from adit_corpus_indexing.nlp.tokenizer import (
    get_text_fields,
    load_corpus,
    normalize_elisions,
    segmente,
    tokenize,
)


class TestNormalizeElisions:
    def test_l_apostrophe_removed(self) -> None:
        assert normalize_elisions("l'innovation") == "innovation"

    def test_d_apostrophe_removed(self) -> None:
        assert normalize_elisions("d'abord") == "abord"

    def test_j_apostrophe_removed(self) -> None:
        assert normalize_elisions("j'aime") == "aime"

    def test_qu_apostrophe_removed(self) -> None:
        assert normalize_elisions("qu'il") == "il"

    def test_multiple_elisions_in_sentence(self) -> None:
        # "d'aujourd'hui" → "aujourd'hui" (internal d' in compound word kept)
        result = normalize_elisions("l'innovation d'aujourd'hui")
        assert "l'innovation" not in result  # l' prefix stripped
        assert "d'aujourd" not in result  # leading d' stripped
        assert "innovation" in result
        assert "aujourd" in result

    def test_uppercase_elision_removed(self) -> None:
        assert normalize_elisions("L'innovation") == "innovation"

    def test_typographic_apostrophe_removed(self) -> None:
        # Unicode RIGHT SINGLE QUOTATION MARK U+2019
        assert normalize_elisions("l\u2019innovation") == "innovation"

    def test_no_elision_unchanged(self) -> None:
        assert normalize_elisions("bonjour monde") == "bonjour monde"

    def test_empty_string(self) -> None:
        assert normalize_elisions("") == ""

    def test_tokenize_after_normalize_has_no_single_l(self) -> None:
        tokens = tokenize(normalize_elisions("l'innovation"))
        assert "l" not in tokens
        assert "innovation" in tokens

    def test_s_apostrophe_removed(self) -> None:
        assert normalize_elisions("s'il") == "il"

    def test_c_apostrophe_removed(self) -> None:
        assert normalize_elisions("c'est") == "est"


class TestTokenize:
    def test_basic_words(self) -> None:
        assert tokenize("Hello World") == ["hello", "world"]

    def test_lowercases(self) -> None:
        assert tokenize("CHAT Chien") == ["chat", "chien"]

    def test_punctuation_is_separator(self) -> None:
        assert tokenize("bonjour, monde!") == ["bonjour", "monde"]

    def test_numbers_are_stripped(self) -> None:
        assert tokenize("abc123def") == ["abc", "def"]

    def test_numbers_only(self) -> None:
        assert tokenize("12345") == []

    def test_empty_string(self) -> None:
        assert tokenize("") == []

    def test_french_accents(self) -> None:
        tokens = tokenize("Éléphant naïve résumé")
        assert tokens == ["éléphant", "naïve", "résumé"]

    def test_hyphen_splits_tokens(self) -> None:
        # Hyphens are not letters → split on them
        assert tokenize("vis-à-vis") == ["vis", "à", "vis"]

    def test_multiple_separators(self) -> None:
        assert tokenize("un  deux---trois") == ["un", "deux", "trois"]

    def test_single_char_tokens_included(self) -> None:
        # Single chars are valid tokens (e.g. "à")
        assert "à" in tokenize("aller à Paris")


class TestGetTextFields:
    def _make_doc(
        self,
        article: str | None = "42",
        titre: str | None = "Mon titre",
        texte: str | None = "Mon texte",
    ) -> etree._Element:
        doc = etree.Element("document")
        if article is not None:
            el = etree.SubElement(doc, "article")
            el.text = article
        if titre is not None:
            el = etree.SubElement(doc, "titre")
            el.text = titre
        if texte is not None:
            el = etree.SubElement(doc, "texte")
            el.text = texte
        return doc

    def test_full_document(self) -> None:
        doc_id, text = get_text_fields(self._make_doc())
        assert doc_id == "42"
        assert "Mon titre" in text
        assert "Mon texte" in text

    def test_text_is_concatenation_of_titre_and_texte(self) -> None:
        doc_id, text = get_text_fields(self._make_doc(titre="A", texte="B"))
        assert text == "A B"

    def test_missing_article_gives_empty_doc_id(self) -> None:
        doc_id, _ = get_text_fields(self._make_doc(article=None))
        assert doc_id == ""

    def test_missing_titre(self) -> None:
        _, text = get_text_fields(self._make_doc(titre=None, texte="Seul texte"))
        assert text == "Seul texte"

    def test_missing_texte(self) -> None:
        _, text = get_text_fields(self._make_doc(titre="Seul titre", texte=None))
        assert text == "Seul titre"

    def test_both_fields_missing(self) -> None:
        _, text = get_text_fields(self._make_doc(titre=None, texte=None))
        assert text == ""

    def test_strips_whitespace_from_doc_id(self) -> None:
        doc_id, _ = get_text_fields(self._make_doc(article="  7  "))
        assert doc_id == "7"


class TestLoadCorpus:
    def test_returns_corpus_root(self, mini_corpus_path: Path) -> None:
        root = load_corpus(mini_corpus_path)
        assert root.tag == "corpus"

    def test_has_three_documents(self, mini_corpus_path: Path) -> None:
        root = load_corpus(mini_corpus_path)
        assert len(root.findall("document")) == 3

    def test_missing_file_raises(self, tmp_path: Path) -> None:
        with pytest.raises(OSError):
            load_corpus(tmp_path / "nonexistent.xml")


class TestSegmente:
    def test_output_file_is_created(
        self, mini_corpus_path: Path, tmp_path: Path
    ) -> None:
        out = tmp_path / "tokens.tsv"
        segmente(mini_corpus_path, out)
        assert out.exists()

    def test_each_line_has_two_tab_columns(
        self, mini_corpus_path: Path, tmp_path: Path
    ) -> None:
        out = tmp_path / "tokens.tsv"
        segmente(mini_corpus_path, out)
        lines = out.read_text(encoding="utf-8").splitlines()
        assert len(lines) > 0
        for line in lines:
            parts = line.split("\t")
            assert len(parts) == 2, f"Expected 2 columns, got: {line!r}"

    def test_doc_ids_match_article_elements(
        self, mini_corpus_path: Path, tmp_path: Path
    ) -> None:
        out = tmp_path / "tokens.tsv"
        segmente(mini_corpus_path, out)
        doc_ids = {
            line.split("\t")[0] for line in out.read_text(encoding="utf-8").splitlines()
        }
        assert doc_ids == {"1", "2", "3"}

    def test_tokens_are_lowercase(self, mini_corpus_path: Path, tmp_path: Path) -> None:
        out = tmp_path / "tokens.tsv"
        segmente(mini_corpus_path, out)
        tokens = [
            line.split("\t")[1] for line in out.read_text(encoding="utf-8").splitlines()
        ]
        for token in tokens:
            assert token == token.lower(), f"Token not lowercased: {token!r}"

    def test_known_tokens_appear(self, mini_corpus_path: Path, tmp_path: Path) -> None:
        out = tmp_path / "tokens.tsv"
        segmente(mini_corpus_path, out)
        all_tokens = {
            line.split("\t")[1] for line in out.read_text(encoding="utf-8").splitlines()
        }
        # Words present in fixture titles/texts
        assert "chat" in all_tokens
        assert "chercheurs" in all_tokens

    def test_document_without_article_id_is_skipped(self, tmp_path: Path) -> None:
        corpus = tmp_path / "corpus.xml"
        corpus.write_text(
            "<?xml version='1.0'?><corpus>"
            "<document><titre>Test</titre><texte>Corps</texte></document>"
            "</corpus>",
            encoding="utf-8",
        )
        out = tmp_path / "tokens.tsv"
        segmente(corpus, out)
        assert out.read_text(encoding="utf-8") == ""
