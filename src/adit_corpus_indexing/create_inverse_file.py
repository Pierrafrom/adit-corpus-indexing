# -*- coding: utf-8 -*-
"""
create_inverse_file.py — TD3 : Création des fichiers inverses.

À partir du corpus XML lemmatisé et filtré, crée des fichiers inverses pour
chaque balise importante (titre, texte, rubrique, date, bulletin).

Format de sortie :
    terme \\t article_id:fréquence \\t bulletin_id:fréquence \\t ...
"""

import logging
from pathlib import Path
from collections import defaultdict
from lxml import etree

logger = logging.getLogger(__name__)


def tokenize_field(text: str | None) -> list[str]:
    """
    Tokenize un champ texte en tokens simples (séparés par espaces).

    Ignore les lignes vides et les tokens vides.

    Args:
        text: texte à tokenizer

    Returns:
        Liste de tokens (tokens vides supprimés)
    """
    if not text:
        return []

    # Diviser par espaces et filtrer les tokens vides
    tokens = [t.lower().strip() for t in text.split()]
    return [t for t in tokens if t]


def build_inverse_index_per_field(
    corpus_path: Path,
    field_name: str,
    output_path: Path,
) -> None:
    """
    Crée un fichier inverse pour un champ donné (titre, texte, rubrique, date...).

    Format de sortie (TSV, sans en-tête) :
        terme \\t article_id:fréquence \\t article_id:fréquence \\t ...

    Args:
        corpus_path: chemin vers le corpus XML filtré
        field_name: nom de la balise à indexer ('titre', 'texte', 'rubrique', 'date')
        output_path: chemin du fichier inverse
    """
    # Dictionnaire : terme -> {article_id: fréquence}
    index: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

    # Parser le corpus XML
    tree = etree.parse(str(corpus_path))
    root = tree.getroot()

    nb_docs = 0

    # Itérer sur tous les documents
    for doc_elem in root.findall("document"):
        nb_docs += 1

        # Récupérer l'ID de l'article
        article_elem = doc_elem.find("article")
        if article_elem is None or not article_elem.text:
            logger.warning("Document sans ID article")
            continue
        article_id = article_elem.text.strip()

        # Récupérer le champ à indexer
        field_elem = doc_elem.find(field_name)
        if field_elem is None or not field_elem.text:
            logger.debug("Champ '%s' absent pour article %s", field_name, article_id)
            continue

        field_text = field_elem.text.strip()

        # Tokenizer et compter les occurrences
        tokens = tokenize_field(field_text)
        for token in tokens:
            index[token][article_id] += 1

    # Écrire le fichier inverse
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        for terme in sorted(index.keys()):
            # Construire la ligne : terme \t article_id:freq \t article_id:freq ...
            postings = " ".join(
                f"{aid}:{freq}" for aid, freq in sorted(index[terme].items())
            )
            f.write(f"{terme}\t{postings}\n")

    logger.info(
        "build_inverse_index_per_field: %d termes, %d documents → %s",
        len(index),
        nb_docs,
        output_path,
    )
    print(f"✓ Index inverse pour '{field_name}' → '{output_path}'")
    print(f"  Documents traités : {nb_docs}")
    print(f"  Termes uniques    : {len(index)}")


def build_combined_inverse_index(
    corpus_path: Path,
    fields: list[str],
    output_path: Path,
    field_weights: dict[str, float] | None = None,
) -> None:
    """
    Crée un fichier inverse combiné à partir de plusieurs champs.

    Les fréquences de chaque champ peuvent être pondérées différemment
    (par ex. titre + 2 * texte pour favoriser les occurrences en titre).

    Format de sortie :
        terme \\t article_id:score_combiné \\t article_id:score_combiné \\t ...

    Args:
        corpus_path: chemin vers le corpus XML filtré
        fields: liste des balises à combiner
        output_path: chemin du fichier inverse
        field_weights: dict {field_name: poids} pour pondérer les champs
                      Par défaut : poids=1.0 pour tous les champs
    """
    if field_weights is None:
        field_weights = {f: 1.0 for f in fields}

    # Dictionnaire : terme -> {article_id: score combiné}
    index: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))

    # Parser le corpus XML
    tree = etree.parse(str(corpus_path))
    root = tree.getroot()

    nb_docs = 0

    # Itérer sur tous les documents
    for doc_elem in root.findall("document"):
        nb_docs += 1

        # Récupérer l'ID de l'article
        article_elem = doc_elem.find("article")
        if article_elem is None or not article_elem.text:
            logger.warning("Document sans ID article")
            continue
        article_id = article_elem.text.strip()

        # Traiter chaque champ
        for field_name in fields:
            field_elem = doc_elem.find(field_name)
            if field_elem is None or not field_elem.text:
                continue

            field_text = field_elem.text.strip()
            weight = field_weights.get(field_name, 1.0)

            # Tokenizer et accumuler les scores pondérés
            tokens = tokenize_field(field_text)
            for token in tokens:
                index[token][article_id] += weight

    # Écrire le fichier inverse
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        for terme in sorted(index.keys()):
            # Construire la ligne avec les scores combinés
            postings = " ".join(
                f"{aid}:{score:.2f}" for aid, score in sorted(index[terme].items())
            )
            f.write(f"{terme}\t{postings}\n")

    logger.info(
        "build_combined_inverse_index: %d termes, %d documents → %s",
        len(index),
        nb_docs,
        output_path,
    )
    print(f"✓ Index inverse combiné → '{output_path}'")
    print(f"  Documents traités : {nb_docs}")
    print(f"  Termes uniques    : {len(index)}")
    print(f"  Champs combinés   : {', '.join(fields)}")
    print(f"  Poids appliqués   : {field_weights}")


def build_date_index(
    corpus_path: Path,
    output_path: Path,
) -> None:
    """
    Crée un fichier inverse pour les dates (par mois/année).

    Format de sortie :
        date (mm/yyyy) \\t article_id \\t article_id \\t ...

    Args:
        corpus_path: chemin vers le corpus XML filtré
        output_path: chemin du fichier d'index des dates
    """
    from collections import defaultdict

    # Dictionnaire : date -> liste d'article_id
    index: dict[str, list[str]] = defaultdict(list)

    # Parser le corpus XML
    tree = etree.parse(str(corpus_path))
    root = tree.getroot()

    for doc_elem in root.findall("document"):
        # Récupérer l'ID de l'article
        article_elem = doc_elem.find("article")
        if article_elem is None or not article_elem.text:
            continue
        article_id = article_elem.text.strip()

        # Récupérer la date et extraire mm/yyyy
        date_elem = doc_elem.find("date")
        if date_elem is None or not date_elem.text:
            continue

        date_text = date_elem.text.strip()
        # Format attendu : dd/mm/yyyy
        try:
            parts = date_text.split("/")
            if len(parts) == 3:
                mm_yyyy = f"{parts[1]}/{parts[2]}"  # mm/yyyy
                index[mm_yyyy].append(article_id)
        except Exception as e:
            logger.warning("Erreur parsing date '%s': %s", date_text, e)

    # Écrire le fichier d'index
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        for date_key in sorted(index.keys()):
            articles = " ".join(index[date_key])
            f.write(f"{date_key}\t{articles}\n")

    logger.info(
        "build_date_index: %d périodes distinctes → %s",
        len(index),
        output_path,
    )
    print(f"✓ Index par date → '{output_path}'")
    print(f"  Périodes uniques : {len(index)}")


def build_rubrique_index(
    corpus_path: Path,
    output_path: Path,
) -> None:
    """
    Crée un fichier inverse pour les rubriques.

    Format de sortie :
        rubrique \\t article_id \\t article_id \\t ...

    Args:
        corpus_path: chemin vers le corpus XML filtré
        output_path: chemin du fichier d'index des rubriques
    """
    from collections import defaultdict

    # Dictionnaire : rubrique -> liste d'article_id
    index: dict[str, list[str]] = defaultdict(list)

    # Parser le corpus XML
    tree = etree.parse(str(corpus_path))
    root = tree.getroot()

    for doc_elem in root.findall("document"):
        # Récupérer l'ID de l'article
        article_elem = doc_elem.find("article")
        if article_elem is None or not article_elem.text:
            continue
        article_id = article_elem.text.strip()

        # Récupérer la rubrique
        rubrique_elem = doc_elem.find("rubrique")
        if rubrique_elem is None or not rubrique_elem.text:
            continue

        rubrique = rubrique_elem.text.strip().lower()
        index[rubrique].append(article_id)

    # Écrire le fichier d'index
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        for rubrique in sorted(index.keys()):
            articles = " ".join(index[rubrique])
            f.write(f"{rubrique}\t{articles}\n")

    logger.info(
        "build_rubrique_index: %d rubriques distinctes → %s",
        len(index),
        output_path,
    )
    print(f"✓ Index par rubrique → '{output_path}'")
    print(f"  Rubriques uniques : {len(index)}")


# ============================================================
# POINT D'ENTRÉE
# ============================================================

if __name__ == "__main__":
    # 1. Créer des fichiers inverses pour chaque champ important
    print("\n" + "=" * 60)
    print("CRÉATION DES FICHIERS INVERSES")
    print("=" * 60 + "\n")

    corpus_path = Path("outputs/corpus_final.xml")

    # Index pour les titres
    build_inverse_index_per_field(
        corpus_path=corpus_path,
        field_name="titre",
        output_path=Path("outputs/index_titre.tsv"),
    )
    print()

    # Index pour le texte complet
    build_inverse_index_per_field(
        corpus_path=corpus_path,
        field_name="texte",
        output_path=Path("outputs/index_texte.tsv"),
    )
    print()

    # Index par rubriques (facettes)
    build_rubrique_index(
        corpus_path=corpus_path,
        output_path=Path("outputs/index_rubrique.tsv"),
    )
    print()

    # Index par dates (facettes)
    build_date_index(
        corpus_path=corpus_path,
        output_path=Path("outputs/index_date.tsv"),
    )
    print()

    # 2. Index combiné avec poids : titre × 2 + texte × 1
    build_combined_inverse_index(
        corpus_path=corpus_path,
        fields=["titre", "texte"],
        output_path=Path("outputs/index_combined.tsv"),
        field_weights={"titre": 2.0, "texte": 1.0},
    )
    print()

    # ============================================================
    # ANALYSE ET RECOMMANDATIONS
    # ============================================================

    print("\n" + "=" * 60)
    print("RECOMMANDATIONS POUR AMÉLIORER L'INDEXATION")
    print("=" * 60)

    recommendations = """
2. AMÉLIORATION DE LA QUALITÉ DE L'INDEXATION

➤ SÉLECTION DES CHAMPS À INDEXER :
  • Titre : poids élevé (2-3×) — termes précis et explicites
  • Texte complet : poids standard (1×) — contexte global
  • Rubrique : index facettes — filtrage thématique
  • Date : index facettes — filtrage temporel
  • Auteur : index optionnel — recherche par personne

➤ PONDÉRATION DES CHAMPS :
  • Favoriser les occurrences en titre (plus discriminantes)
  • Réduire le poids des répétitions en texte
  • Utiliser TF-IDF pour normaliser par fréquence relative

➤ NETTOYAGE TEXTUEL :
  • ✓ Lemmatisation spaCy (effectuée en TD3 phase 1)
  • ✓ Anti-dictionnaire v2 (stop words dépendant du contexte)
  • Note : Possibilité de supprimer les termes très rares (hapaxes)
  • Note : Normalisation des caractères accentués (déjà fait)

➤ INDEXATION MULTI-CHAMPS :
  • Considérer BM25 (Okapi) au lieu du TF-IDF simple
  • Implémenter la recherche booléenne (AND, OR, NOT)
  • Ajouter la recherche par plage (range queries) sur dates

➤ ANALYSE LINGUISTIQUE :
  • Regroupement entités nommées (noms de lieux, organisations)
  • Extraction d'expressions composées (n-grams)
  • Détection d'acronymes et expansion

➤ ÉVALUATION ET FEEDBACK :
  • Collecter les requêtes utilisateur et leurs résultats
  • Ajuster manuellement les seuils de pertinence
  • Re-entrainer l'anti-dictionnaire sur requêtes fréquentes
  • Analyser les cas de faux négatifs/positifs

➤ PERFORMANCES :
  • Indexation incrémentale pour corpus en croissance
  • Compression du fichier inverse (delta encoding, VByte)
  • Cache des requêtes fréquentes

➤ RAPPEL vs PRÉCISION :
  • Diminuer le seuil IDF → plus de rappel (moins de filtrage)
  • Augmenter le seuil IDF → plus de précision (plus de filtrage)
  • Adapter selon le cas d'usage métier
"""
    print(recommendations)
