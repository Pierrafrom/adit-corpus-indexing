# Copilot Instructions — LO17 (Printemps 2026) — ADIT Corpus Indexing

## Contexte du projet
Ce projet (LO17 — Indexation et Recherche d’information — TD1) consiste à préparer un corpus d’articles issus des bulletins ADIT (France, 2011–2014, ~300+ articles) afin de produire **un unique fichier XML** facilement indexable.

Chaque article HTML contient des méta-informations (numéro bulletin, date, rubrique, titre, auteur, contacts…) et du contenu (texte, images, légendes…).  
Le livrable du TD1 est un XML structuré comme suit :

- `<corpus>`
  - `<document>`
    - `<article>` numéro d’article
    - `<bulletin>` numéro du bulletin
    - `<date>` jj/mm/aaaa
    - `<rubrique>`
    - `<titre>`
    - `<auteur>`
    - `<texte>`
    - `<images>`
      - `<image><urlImage>…</urlImage><legendeImage>…</legendeImage></image>` (0..n)
    - `<contact>`
  - …

Le pipeline doit être **robuste** (HTML variable, champs parfois absents), **UTF-8 strict**, et produire un **rapport d’exhaustivité** (combien de fichiers traités, taux de présence par champ, erreurs par fichier).

---

## Exigences de qualité du code (Clean Code)
Je veux du **Python propre**, lisible et maintenable :

- Code clair, simple, sans “magie”.
- Fonctions **courtes** (idéalement < 30–40 lignes), qui font **une seule chose** et la font bien.
- Petits blocs faciles à relire et à debugger.
- Nommage explicite (en anglais) : variables/fonctions/classes.
- Typage systématique : `typing`, `dataclasses`, `Path`, `Optional`.
- Gestion d’erreurs robuste : ne jamais arrêter le traitement global à cause d’un seul fichier.
- Logging propre (niveau INFO/WARN/ERROR) + erreurs stockées dans un report.
- Encodage : lire/écrire en **UTF-8**.

---

## Stack / outils modernes utilisés dans ce projet
- **Python 3.12** (géré par `uv`)
- **uv** : gestion projet/dépendances/venv/exécution (`uv init`, `uv add`, `uv run`)
- **BeautifulSoup4** + **lxml** : parsing HTML robuste
- **lxml.etree** : génération XML propre (escaping + pretty print)
- **rich** ou **tqdm** : progression / affichage console
- **python-dateutil** : parsing/normalisation dates si nécessaire
- Qualité :
  - **ruff** : lint + format
  - **mypy** : type checking
  - **pytest** : tests

---

## Organisation du code (architecture attendue)
Utiliser un layout `src/` propre :
