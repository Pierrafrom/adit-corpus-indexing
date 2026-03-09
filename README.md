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
uv run pytest           # run all tests (coverage report included)
uv run pytest -v        # verbose mode
uv run pytest -k foo    # filter by name
```

Coverage is measured automatically on every run. The CI enforces a minimum of 80%.

### Code quality

```bash
uv run ruff format src/ tests/   # auto-format
uv run ruff check src/ tests/    # lint
uv run mypy src/                 # type checking
```

## CI / GitHub Actions

| Workflow | Trigger | What it does |
|---|---|---|
| `ci.yml` | push on all branches / PR on `main` | ruff lint + format, mypy, pytest |
| `corpus-run.yml` | manual (`workflow_dispatch`) | runs the pipeline, uploads `corpus.xml` as artifact |

To trigger a corpus run: GitHub > Actions > **Corpus pipeline** > **Run workflow**.
An optional `sample_size` input limits the number of files processed (0 = all).
The generated `corpus.xml` is available as a downloadable artifact for 30 days.

Dependabot checks for dependency updates weekly and opens PRs automatically.

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

## Contributing

### Branch workflow

```
main          ← protected: CI required, 1 review required, linear history only
feat/<topic>  ← feature branches — open a PR to merge into main
fix/<topic>   ← bug fix branches
refactor/...  ← refactoring branches
```

### To contribute

```bash
git checkout -b feat/my-feature
# ... work ...
git push origin feat/my-feature
gh pr create   # open PR via GitHub CLI
```

### Local pre-push hook

Install once after cloning:

```bash
cp scripts/pre-push .git/hooks/pre-push
chmod +x .git/hooks/pre-push
```

Runs ruff lint, ruff format check, and pytest before every push.

### CI checks (run automatically on every push)

- `ruff check` — linting
- `ruff format --check` — formatting
- `mypy` — type checking
- `pytest` — unit tests

All four must pass for a PR to be mergeable into `main`.
