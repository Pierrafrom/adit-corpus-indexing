"""TD2 — TF-IDF computation: build tf, idf, and tf-idf tables from tokens TSV."""

import logging
import math
from collections import Counter, defaultdict
from pathlib import Path

logger = logging.getLogger(__name__)


def _read_tokens(tokens_path: Path) -> list[tuple[str, str]]:
    """Read a tokens TSV and return a list of (doc_id, token) pairs.

    The file has no header; each line is: doc_id\\ttoken
    Lines that do not contain exactly one tab are skipped with a warning.
    """
    pairs: list[tuple[str, str]] = []
    with open(tokens_path, encoding="utf-8") as f:
        for lineno, raw in enumerate(f, start=1):
            line = raw.rstrip("\n")
            if not line:
                continue
            parts = line.split("\t", 1)
            if len(parts) != 2:
                logger.warning(
                    "_read_tokens: malformed line %d in %s — skipped",
                    lineno,
                    tokens_path,
                )
                continue
            pairs.append((parts[0], parts[1]))
    return pairs


def compute_tf(tokens_path: Path, output_path: Path) -> None:
    """Compute logarithmic term frequency for each (doc_id, token) pair.

    TF formula (logarithmic weighting, as per Salton & Buckley):
        tf(t, d) = 1 + log10(count(t, d))  if count > 0
                 = 0                        otherwise

    Rationale: document relevance does not grow proportionally with raw
    occurrence count — a document with 10 occurrences is not 10× more
    relevant than one with a single occurrence.  The log dampens this
    effect while preserving the ordering.  Unlike relative frequency
    (count / total), logarithmic TF is not normalised by document length;
    the IDF term handles inter-document comparability.

    Input:  tokens TSV — columns (no header): doc_id, token
    Output: tf TSV    — columns (no header): doc_id, token, tf
    """
    doc_tokens: dict[str, list[str]] = defaultdict(list)
    for doc_id, token in _read_tokens(tokens_path):
        doc_tokens[doc_id].append(token)

    rows: list[tuple[str, str, float]] = []
    for doc_id, tokens in doc_tokens.items():
        for token, count in Counter(tokens).items():
            rows.append((doc_id, token, 1.0 + math.log10(count)))

    with open(output_path, "w", encoding="utf-8") as f:
        for doc_id, token, tf in rows:
            f.write(f"{doc_id}\t{token}\t{tf:.8f}\n")

    logger.info("compute_tf: %d (doc, token) pairs → %s", len(rows), output_path)


def compute_idf(tokens_path: Path, output_path: Path) -> None:
    """Compute inverse document frequency for each token.

    IDF formula: idf(t) = log10(N / df(t))
      where N    = total number of distinct documents
            df(t) = number of documents containing token t

    Input:  tokens TSV — columns (no header): doc_id, token
    Output: idf TSV   — columns (no header): token, idf
    Rows are sorted by ascending idf (lowest = most common = best stop-word candidates).
    """
    doc_token_sets: dict[str, set[str]] = defaultdict(set)
    for doc_id, token in _read_tokens(tokens_path):
        doc_token_sets[doc_id].add(token)

    n_docs = len(doc_token_sets)
    if n_docs == 0:
        logger.warning("compute_idf: no documents found in %s", tokens_path)
        output_path.write_text("", encoding="utf-8")
        return

    df: dict[str, int] = defaultdict(int)
    for token_set in doc_token_sets.values():
        for token in token_set:
            df[token] += 1

    rows: list[tuple[str, float]] = [
        (token, math.log10(n_docs / dft)) for token, dft in df.items()
    ]
    rows.sort(key=lambda x: x[1])

    with open(output_path, "w", encoding="utf-8") as f:
        for token, idf in rows:
            f.write(f"{token}\t{idf:.8f}\n")

    logger.info("compute_idf: %d tokens → %s", len(rows), output_path)


def compute_tfidf(tf_path: Path, idf_path: Path, output_path: Path) -> None:
    """Compute tf-idf score for each (doc_id, token) pair.

    tf-idf(t, d) = tf(t, d) * idf(t)

    Input:  tf TSV  — columns (no header): doc_id, token, tf
            idf TSV — columns (no header): token, idf
    Output: tfidf TSV — columns (no header): doc_id, token, tfidf
    """
    idf: dict[str, float] = {}
    with open(idf_path, encoding="utf-8") as f:
        for lineno, raw in enumerate(f, start=1):
            line = raw.rstrip("\n")
            if not line:
                continue
            parts = line.split("\t", 1)
            if len(parts) != 2:
                logger.warning(
                    "compute_tfidf: malformed idf line %d — skipped", lineno
                )
                continue
            idf[parts[0]] = float(parts[1])

    rows: list[tuple[str, str, float]] = []
    with open(tf_path, encoding="utf-8") as f:
        for lineno, raw in enumerate(f, start=1):
            line = raw.rstrip("\n")
            if not line:
                continue
            parts = line.split("\t")
            if len(parts) != 3:
                logger.warning(
                    "compute_tfidf: malformed tf line %d — skipped", lineno
                )
                continue
            doc_id, token, tf_val = parts
            tfidf_score = float(tf_val) * idf.get(token, 0.0)
            rows.append((doc_id, token, tfidf_score))

    with open(output_path, "w", encoding="utf-8") as f:
        for doc_id, token, score in rows:
            f.write(f"{doc_id}\t{token}\t{score:.8f}\n")

    logger.info("compute_tfidf: %d rows → %s", len(rows), output_path)
