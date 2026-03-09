# Copilot Instructions — adit-corpus-indexing

## Language
All code in English: variable names, function names, comments, docstrings.
Lab reports in `reports/` are in French — do not translate them.

## Stack
- Python 3.12+, managed with `uv` (never suggest `pip install`)
- BeautifulSoup4 + lxml for HTML parsing
- lxml.etree for XML construction — never build XML by string concatenation
- pytest for tests
- ruff for linting and formatting (replaces black + isort + flake8)
- mypy in strict mode

## Design
- Prefer OOP: model domain concepts as classes (`Article`, `Corpus`, `XmlBuilder`...).
  Use plain functions only when OOP would be meaningfully more complex — comment why.

## Code style
- Line length: 88 characters
- Double quotes for strings
- Full type annotations on every public function
- `str | None` union syntax (Python 3.10+), not `Optional[str]`
- `pathlib.Path` for all file paths, never `os.path`
- `logging` for all output in `src/`, never `print()`

```python
# logger pattern — one per module
import logging
logger = logging.getLogger(__name__)
```

## Architecture rules
- One function = one responsibility. If "and" describes it, split it.
- DRY in production code. Acceptable duplication in tests for clarity.
- Package lives in `src/adit_corpus_indexing/` (underscores, not hyphens)
- Generated files go in `outputs/` — never committed

## Defensive extraction (critical — corpus is noisy)
Always guard before accessing `.text` or tag attributes.

```python
# ✅
tag = soup.find("span", class_="date")
if tag is None:
    logger.warning("Missing date in %s", source_file)
    return None
return tag.get_text(strip=True)

# ❌ will crash on missing fields
return soup.find("span", class_="date").text
```

## UTF-8
Every `open()` call must specify `encoding="utf-8"`.
Use `errors="replace"` when reading source HTML files.

## Tests
- One test per extraction function minimum
- Cover edge cases: missing field, empty value, accented characters
- Fixtures in `tests/fixtures/` — real HTML samples from the corpus
- Naming: `test_<function>_<expected_behaviour>`

## Git
- Conventional Commits: `feat:`, `fix:`, `refactor:`, `test:`, `docs:`
- Branch naming: `feat/<topic>`, `fix/<topic>`
- Never suggest committing: `outputs/`, `data/`, `__pycache__/`, `.mypy_cache/`