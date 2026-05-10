# LO17 — Moteur de recherche ADIT

**Pierre Fromont Boissel & Maxime Doudy** — UTC Printemps 2026

Système d'indexation et de recherche d'information sur ~326 articles HTML issus des
bulletins de veille technologique ADIT (2011–2014).

---

## Prérequis

### Sans Docker

| Outil | Version | Installation |
|---|---|---|
| Python | 3.12+ | [python.org](https://www.python.org/) |
| uv | latest | `pip install uv` ou `curl -LsSf https://astral.sh/uv/install.sh \| sh` |

### Avec Docker

| Outil | Version |
|---|---|
| Docker | 24+ |
| Docker Compose | v2 (intégré à Docker Desktop) |

---

## Lancer l'application

### Option A — Sans Docker (local)

```bash
# 1. Installer les dépendances (hors NLP — non nécessaire, index déjà générés)
uv sync --no-group nlp --no-group dev

# 2. Lancer l'interface Streamlit
uv run streamlit run app.py
```

Ouvrir [http://localhost:8501](http://localhost:8501) dans le navigateur.

> Les index et fichiers générés sont fournis dans `outputs/td3/`.
> Il n'est **pas nécessaire** de relancer les pipelines TD1–TD3.

### Option B — Avec Docker

```bash
docker compose up
```

Ouvrir [http://localhost:8501](http://localhost:8501) dans le navigateur.

Pour arrêter : `Ctrl+C` puis `docker compose down`.

> **WSL2** : si `docker compose up` échoue avec `docker-credential-desktop.exe not found`,
> éditer `~/.docker/config.json` et remplacer `"credsStore": "desktop.exe"` par `"credsStore": ""`.

---

## Régénérer les index (optionnel)

> Nécessite le corpus source dans `data/BULLETINS/` (disponible sur Moodle LO17).

```bash
# Installer toutes les dépendances (incluant SpaCy)
uv sync

# Lancer le pipeline complet TD1 → TD3
uv run adit-pipeline

# Ou par étape :
uv run td1   # HTML → corpus.xml
uv run td2   # anti-dictionnaire
uv run td3   # lemmatisation + index inversés
```

---

## Structure du projet

```
src/adit_corpus_indexing/
├── io/            # parseur HTML, constructeur XML
├── nlp/           # tokenizer, lemmatizer, antidictionnaire, correcteur, parseur de requêtes
├── indexing/      # TF-IDF, index inversés
├── search/        # moteur de recherche, évaluateur, chargeur d'index
├── pipelines/     # pipelines TD1–TD6
└── models.py      # dataclasses (Article, ParsedQuery, SearchResult…)

outputs/td3/       # fichiers générés (index, corpus_final.xml, lemmes…)
data/              # ground_truth.json + BULLETINS/ (non versionné)
reports/           # comptes-rendus de TD (français)
tests/             # suite pytest (369 tests, couverture 93%+)
app.py             # interface Streamlit (TD6)
```

---

## Tests

```bash
uv sync --group dev
uv run pytest
```

Couverture minimale requise : 80 % (configurée dans `pyproject.toml`).

---

## Qualité du code

```bash
uv run ruff format src/ tests/   # formatage
uv run ruff check src/ tests/    # lint
uv run mypy src/                 # typage statique
```
