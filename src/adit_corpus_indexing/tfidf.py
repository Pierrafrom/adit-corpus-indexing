"""TD2 — TF-IDF computation: build tf, idf, and tf-idf tables from tokens TSV."""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def compute_tf(tokens_path: Path, output_path: Path) -> None:
    """Compute term frequency for each (doc_id, token) pair.

    TF formula: tf(t, d) = count(t in d) / total_tokens(d)

    Input:  tokens TSV — columns: doc_id, token
    Output: tf TSV    — columns: doc_id, token, tf
    """
    # TODO:
    #   1. read tokens_path, group by doc_id
    #   2. count occurrences of each token per document
    #   3. divide by total token count in that document
    #   4. write (doc_id, token, tf) rows to output_path as UTF-8 TSV
    raise NotImplementedError


def compute_idf(tokens_path: Path, output_path: Path) -> None:
    """Compute inverse document frequency for each token.

    IDF formula: idf(t) = log10(N / df(t))
      where N   = total number of documents
            df(t) = number of documents containing token t

    Input:  tokens TSV — columns: doc_id, token
    Output: idf TSV   — columns: token, idf
    """
    # TODO:
    #   1. read tokens_path
    #   2. count distinct doc_ids (= N)
    #   3. for each token count distinct doc_ids it appears in (= df)
    #   4. compute idf = log10(N / df) using math.log10
    #   5. write (token, idf) rows to output_path as UTF-8 TSV
    raise NotImplementedError


def compute_tfidf(tf_path: Path, idf_path: Path, output_path: Path) -> None:
    """Compute tf-idf score for each (doc_id, token) pair.

    Output format: doc_id, token, tfidf  (tab-separated)

    Input:  tf TSV  — columns: doc_id, token, tf
            idf TSV — columns: token, idf
    Output: tfidf TSV — columns: doc_id, token, tfidf
    """
    # TODO:
    #   1. load idf table into a dict {token: idf}
    #   2. stream tf_path, multiply tf * idf for each row
    #   3. write (doc_id, token, tfidf) rows to output_path as UTF-8 TSV
    raise NotImplementedError
