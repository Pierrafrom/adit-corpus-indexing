# CLAUDE.md — adit-corpus-indexing (LO17, UTC Spring 2026)

## Role

You assist engineering students working on the LO17 project at UTC.
The goal is to build a complete Information Retrieval system on a corpus of ~300 HTML articles
from ADIT technology watch bulletins (2011–2014), built incrementally, one lab session at a time.

This file covers **TD1 only**. It will be updated as new lab sessions are introduced.
Do not infer or anticipate future requirements — work strictly from what is documented here.

If the student asks about something not yet covered, say so clearly and ask them to share
the relevant lab sheet before proceeding.

---

## Language policy

- **All code** (variable names, function names, comments, docstrings, module names): **English**
- **Lab reports** (`reports/`): French
- **This file**: English

---

## Tech stack

| Tool | Purpose |
|---|---|
| Python 3.12+ | Main language (version pinned in `.python-version`) |
| uv | Package manager and virtual env (`uv run`, `uv add`) — never use pip directly |
| pyproject.toml | Single source of truth for deps and tool config |
| BeautifulSoup4 + lxml | HTML parsing of ADIT corpus |
| lxml.etree | XML construction and validation |
| pytest | Unit tests |
| ruff | Linting + formatting |
| mypy | Static type checking |
| logging | Tracing (never `print()` in `src/`) |

### Key commands

```bash
uv run pytest                        # run tests
uv run ruff check src/ tests/        # lint
uv run ruff format src/ tests/       # format
uv run mypy src/                     # type check
uv run python -m adit_corpus_indexing.pipeline  # run main pipeline
```

---

## Recommended project structure

The current repo uses an ad-hoc layout. Below is the recommended structure following
modern Python packaging conventions (PyPA src layout, PEP 517/518):

```
adit-corpus-indexing/
│
├── src/
│   └── adit_corpus_indexing/       # main package (underscores, not hyphens)
│       ├── __init__.py
│       ├── parser.py               # TD1: HTML → Python dict
│       ├── xml_builder.py          # TD1: dict → corpus.xml
│       └── pipeline.py             # TD1: orchestrates parser + xml_builder
│
├── tests/
│   ├── conftest.py                 # shared fixtures
│   ├── fixtures/                   # sample HTML files for testing
│   │   └── sample_article.html
│   ├── test_parser.py
│   └── test_xml_builder.py
│
├── data/
│   └── BULLETINS/                  # source HTML corpus (read-only, gitignored)
│
├── outputs/                        # generated files: corpus.xml, indexes, etc.
│                                   # gitignored — never commit generated artifacts
│
├── reports/                        # lab reports in French (.md or .pdf)
│
├── .github/
│   └── workflows/
│       └── ci.yml                  # run ruff + mypy + pytest on push
│
├── .gitignore
├── .python-version
├── pyproject.toml
├── uv.lock
└── CLAUDE.md
```

**Why src layout?** Placing the package under `src/` prevents accidental imports of the
local directory instead of the installed package, and is now the recommended standard
by PyPA. The package name must use underscores (`adit_corpus_indexing`), not hyphens.

**Why no `sandbox/`?** Use git branches for exploration (`feat/explore-*`).
A committed `sandbox/` folder tends to accumulate dead code and confuse contributors.

---

## Tool configuration (pyproject.toml)

Add these sections to `pyproject.toml`:

```toml
[tool.ruff]
line-length = 88
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "N", "W", "B", "UP"]
# E/W: pycodestyle  F: pyflakes  I: isort  N: naming  B: bugbear  UP: pyupgrade

[tool.ruff.lint.isort]
known-first-party = ["adit_corpus_indexing"]

[tool.ruff.format]
quote-style = "double"
indent-style = "space"

[tool.mypy]
python_version = "3.12"
strict = true
warn_return_any = true
warn_unused_ignores = true

[tool.pytest.ini_options]
testpaths = ["tests"]
```

Ruff replaces black + isort + flake8 in a single tool. Run `ruff format` before every commit.

---

## Code quality rules

### Prefer OOP
Default to object-oriented design. Use classes to model domain concepts
(`Article`, `Corpus`, `XmlBuilder`, etc.).
Only fall back to plain functions or a functional style when the OOP equivalent
would be meaningfully more complex or verbose — and call out why when you do.

### Functions do one thing
Each function has a single, clearly named responsibility.
If you need "and" to describe what a function does, split it.

```python
# ✅
def extract_title(soup: BeautifulSoup) -> str | None: ...
def extract_date(soup: BeautifulSoup) -> str | None: ...
def build_document_element(article: Article) -> etree._Element: ...

# ❌
def extract_and_write_article(soup, xml_root): ...
```

### DRY — Don't Repeat Yourself
If the same logic appears twice, extract it into a shared function.
Duplication in tests is acceptable (clarity > DRY in test code).

### Defensive extraction — never crash on missing fields
The ADIT corpus is noisy. Fields are sometimes absent or malformed.
Always guard against `None` before accessing `.text` or attributes.

```python
# ✅
tag = soup.find("span", class_="date")
if tag is None:
    logger.warning("Missing date field in %s", source_file)
    return None
return tag.get_text(strip=True)

# ❌ — will crash on ~10% of files
return soup.find("span", class_="date").text
```

### Type annotations everywhere
All public functions must have full type annotations.
Run `mypy src/` and fix all errors before committing.

```python
def parse_article(html_path: Path) -> dict[str, str | None]: ...
```

### Logging, not print
```python
import logging
logger = logging.getLogger(__name__)

logger.debug("Parsing %s", path)           # detailed trace
logger.info("Processed %d files", count)   # progress
logger.warning("Missing field: %s", field) # expected gaps in corpus
logger.error("Failed to parse %s", path)   # unexpected failures
```

### UTF-8 everywhere — no exceptions
```python
# ✅
with open(path, encoding="utf-8") as f: ...

# ✅ with fallback
with open(path, encoding="utf-8", errors="replace") as f: ...

# ❌
with open(path) as f: ...  # system default encoding — unpredictable
```

---

## TD1 — Corpus preparation

### Objective
Parse ~300 HTML files from `data/BULLETINS/` and produce a single `outputs/corpus.xml`
aggregating all articles in a structured, queryable format.

### Target XML schema (from TD1 appendix)

```xml
<corpus>
  <document>
    <article>article number</article>
    <bulletin>bulletin number</bulletin>
    <date>dd/mm/yyyy</date>
    <rubrique>section name</rubrique>
    <titre>title</titre>
    <auteur>author</auteur>
    <texte>full article text</texte>
    <images>
      <image>
        <urlImage>image URL</urlImage>
        <legendeImage>image caption</legendeImage>
      </image>
      <!-- 0, 1 or N images per article -->
    </images>
    <contact>contact information</contact>
  </document>
  <!-- one <document> per article -->
</corpus>
```

### Recommended module breakdown

**`parser.py`** — HTML → `Article` dataclass or `dict[str, ...]`
One extraction function per field. Each returns `str | None`.
Never crashes. Logs a warning for every missing field.

**`xml_builder.py`** — `Article` → `lxml.etree._Element`
Builds the XML tree from parsed data. Does not touch files.

**`pipeline.py`** — orchestration
Iterates over all HTML files, calls parser, calls builder, writes `corpus.xml`.
Produces a validation report: total files, fields found/missing per field.

### Validation requirement (from TD1)
For every field, you must be able to answer:
- How many articles have this field?
- How many are missing it?

Implement a summary report printed at the end of the pipeline run.

### Common traps for this corpus

| Trap | Prevention |
|---|---|
| Missing field crashes the parser | Always `if tag is None: return None` |
| Encoding corruption on accents | `encoding="utf-8"` + `errors="replace"` |
| Malformed XML output | Use `lxml.etree` builders, never string concatenation |
| Duplicate articles across bulletins | Log and deduplicate on `(bulletin_id, article_id)` |
| Inconsistent rubrique spellings | Normalize to lowercase stripped string |

---

## Git conventions

- Branch naming: `feat/<topic>`, `fix/<topic>`, `refactor/<topic>`
- Commit style (Conventional Commits):
  `feat: add date extraction`, `fix: handle missing rubrique`, `test: add parser edge cases`
- Never commit: `outputs/`, `data/BULLETINS/`, `__pycache__/`, `.mypy_cache/`
- One PR per lab session or significant feature