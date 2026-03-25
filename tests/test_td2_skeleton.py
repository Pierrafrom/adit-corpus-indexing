"""TD2 skeleton smoke tests — verify all stubs raise NotImplementedError."""

import pytest

from adit_corpus_indexing import tfidf, tokenizer
from backup import antidictionary2


class TestTokenizerStubs:
    def test_load_corpus_raises(self, tmp_path):
        with pytest.raises(NotImplementedError):
            tokenizer.load_corpus(tmp_path / "corpus.xml")

    def test_get_text_fields_raises(self):
        from lxml import etree

        doc = etree.Element("document")
        with pytest.raises(NotImplementedError):
            tokenizer.get_text_fields(doc)

    def test_tokenize_raises(self):
        with pytest.raises(NotImplementedError):
            tokenizer.tokenize("some text")

    def test_segmente_raises(self, tmp_path):
        with pytest.raises(NotImplementedError):
            tokenizer.segmente(tmp_path / "corpus.xml", tmp_path / "tokens.tsv")


class TestTfidfStubs:
    def test_compute_tf_raises(self, tmp_path):
        with pytest.raises(NotImplementedError):
            tfidf.compute_tf(tmp_path / "tokens.tsv", tmp_path / "tf.tsv")

    def test_compute_idf_raises(self, tmp_path):
        with pytest.raises(NotImplementedError):
            tfidf.compute_idf(tmp_path / "tokens.tsv", tmp_path / "idf.tsv")

    def test_compute_tfidf_raises(self, tmp_path):
        with pytest.raises(NotImplementedError):
            tfidf.compute_tfidf(
                tmp_path / "tf.tsv", tmp_path / "idf.tsv", tmp_path / "tfidf.tsv"
            )


class TestAntidictionaryStubs:
    def test_build_antidictionary_raises(self, tmp_path):
        with pytest.raises(NotImplementedError):
            antidictionary2.build_antidictionary(
                tmp_path / "idf.tsv", tmp_path / "antidico.tsv", threshold=0.5
            )

    def test_substitue_raises(self, tmp_path):
        with pytest.raises(NotImplementedError):
            antidictionary2.substitue("some text", tmp_path / "antidico.tsv")

    def test_apply_to_corpus_raises(self, tmp_path):
        with pytest.raises(NotImplementedError):
            antidictionary2.apply_to_corpus(
                tmp_path / "corpus.xml",
                tmp_path / "antidico.tsv",
                tmp_path / "corpus_filtered.xml",
            )
