# adit-corpus-indexing

Indexing system for a corpus of ~300 HTML articles from ADIT technology watch bulletins (2011–2014).

## Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) — package manager

```bash
pip install uv  # one-time install
uv sync         # install project dependencies
```

## Commands

### Run the pipeline

```bash
uv run python -m adit_corpus_indexing.pipeline
```

Reads all HTML files from `data/BULLETINS/` and generates `outputs/corpus.xml`.

### Tests

```bash
uv run pytest           # run all tests
uv run pytest -v        # verbose mode
uv run pytest -k foo    # filter by name
```

### Code quality

```bash
uv run ruff format src/ tests/   # auto-format
uv run ruff check src/ tests/    # lint
uv run mypy src/                 # type checking
```

## Structure

```
src/adit_corpus_indexing/
├── models.py       # dataclasses (Article, Image)
├── parser.py       # HTML → Article
├── xml_builder.py  # Article → XML
└── pipeline.py     # orchestration

data/BULLETINS/     # source corpus (not versioned)
outputs/            # generated files (not versioned)
tests/              # pytest test suite
reports/            # lab reports (French)
```
