# Instructions de lancement — LO17 Moteur de recherche ADIT

**Pierre Fromont Boissel & Maxime Doudy** — UTC Printemps 2026

---

## Option A — Sans Docker (local, recommandé)

### Prérequis

| Outil | Version minimale | Installation |
|---|---|---|
| Python | 3.12 | [python.org/downloads](https://www.python.org/downloads/) |
| uv | toute version récente | `pip install uv` |

Vérifier :
```bash
python --version   # Python 3.12.x
uv --version       # uv x.y.z
```

### Étapes

```bash
# 1. Installer les dépendances (index déjà générés, SpaCy non nécessaire)
uv sync --no-group nlp --no-group dev

# 2. Lancer l'interface
uv run streamlit run app.py
```

Ouvrir **http://localhost:8501** dans le navigateur.

> Les fichiers `outputs/td3/` (index inversés, corpus, TF-IDF…) sont fournis dans le zip.
> Il n'est **pas nécessaire** de relancer les pipelines TD1–TD3.

---

## Option B — Avec Docker

### Prérequis

| Outil | Notes |
|---|---|
| Docker Desktop | [docker.com/products/docker-desktop](https://www.docker.com/products/docker-desktop/) — inclut Compose v2 |

Vérifier :
```bash
docker --version          # Docker version 24+
docker compose version    # Docker Compose version v2+
```

### Étapes

```bash
# Construire l'image et démarrer le conteneur
docker compose up
```

Ouvrir **http://localhost:8501** dans le navigateur.

Arrêter :
```bash
Ctrl+C
docker compose down
```

> **WSL2 uniquement** — si l'erreur suivante apparaît au lancement :
> ```
> error getting credentials - err: exec: "docker-credential-desktop.exe":
> executable file not found in $PATH
> ```
> Éditer `~/.docker/config.json` et remplacer :
> ```json
> { "credsStore": "desktop.exe" }
> ```
> par :
> ```json
> { "credsStore": "" }
> ```
> puis relancer `docker compose up`.

---

## Régénérer les index (optionnel)

> Nécessite le corpus source dans `data/BULLETINS/` (disponible sur Moodle LO17).
> Durée : environ 5 minutes.

```bash
# Installer toutes les dépendances (inclut SpaCy + fr-core-news-sm)
uv sync

# Pipeline complet TD1 → TD3 (parsing HTML, anti-dictionnaire, lemmatisation, index)
uv run adit-pipeline
```

---

## Tests

```bash
# Installer les dépendances de développement
uv sync --group dev

# Lancer la suite de tests (369 tests, couverture 93%+)
uv run pytest
```
