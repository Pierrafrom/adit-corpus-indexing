# LO17 — Moteur de recherche ADIT

**Pierre Fromont Boissel & Maxime Doudy** — UTC Printemps 2026

Système d'indexation et de recherche d'information sur ~326 articles HTML
issus des bulletins de veille technologique ADIT (2011–2014).

---

## Lancer l'application

### Option A — Sans Docker (recommandé)

**Prérequis :** Python 3.12+ et `uv`

```bash
# Installer uv (si pas déjà fait)
pip install uv
```

```bash
# Installer les dépendances
uv sync --no-group nlp --no-group dev

# Lancer l'interface
uv run streamlit run app.py
```

Ouvrir **http://localhost:8501** dans le navigateur.

### Option B — Avec Docker

**Prérequis :** Docker Desktop (inclut Compose v2)

```bash
docker compose up
```

Ouvrir **http://localhost:8501** dans le navigateur.
Arrêter : `Ctrl+C` puis `docker compose down`.

> **WSL2 uniquement** — si erreur `docker-credential-desktop.exe not found` :
> éditer `~/.docker/config.json` → remplacer `"credsStore": "desktop.exe"` par `"credsStore": ""`

---

## Structure

```
src/adit_corpus_indexing/
├── io/          # parseur HTML, constructeur XML
├── nlp/         # tokenizer, lemmatizer, antidictionnaire, correcteur, parseur de requêtes
├── indexing/    # TF-IDF, construction des index inversés
├── search/      # moteur de recherche, évaluateur, chargeur d'index
├── pipelines/   # pipelines TD1–TD6
└── models.py    # dataclasses (Article, ParsedQuery, SearchResult…)

outputs/td3/
├── indexes/     # index inversés (titre, texte, rubrique, date…)
├── corpus_final.xml      # corpus nettoyé et lemmatisé
└── lemmes_snowball.tsv   # lexique Snowball (utilisé comme correcteur)

data/
└── ground_truth.json     # jeu d'évaluation (10 requêtes)

reports/
└── compte-rendu-td6.md   # rapport de TD

tests/                    # suite pytest — 369 tests, couverture 93%
app.py                    # interface Streamlit
```

---

## Tests

```bash
uv sync --group dev
uv run pytest
```
