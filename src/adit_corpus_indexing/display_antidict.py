"""TD3 — Affinage de l'anti-dictionnaire sur les lemmes spaCy."""

import logging
import math
from pathlib import Path

logger = logging.getLogger(__name__)


# ============================================================
# EXTRACTION DES LEMMES SPACY DEPUIS lemmes.tsv
# ============================================================


def extraire_lemmes_spacy(lemmes_path: Path, output_path: Path) -> None:
    """Extrait les colonnes (article_id, lemme_spacy) depuis lemmes.tsv.

    lemmes.tsv a un en-tête et quatre colonnes :
        article_id \\t token \\t lemme_spacy \\t stemme_snowball

    Le fichier produit n'a PAS d'en-tête (format attendu par _read_tokens) :
        article_id \\t lemme_spacy

    Args:
        lemmes_path: chemin vers lemmes.tsv
        output_path: chemin du fichier de sortie
    """
    with open(lemmes_path, encoding="utf-8") as f:
        lignes = f.readlines()

    nb_ecrites = 0
    with open(output_path, "w", encoding="utf-8") as f:
        for ligne in lignes[1:]:  # [1:] ignore l'en-tête
            ligne = ligne.strip()
            if not ligne:
                continue
            parties = ligne.split("\t")
            if len(parties) != 4:
                logger.warning("extraire_lemmes_spacy: ligne malformée — %s", ligne)
                continue
            article_id = parties[0]
            lemme_spacy = parties[2]
            f.write(f"{article_id}\t{lemme_spacy}\n")
            nb_ecrites += 1

    logger.info(
        "extraire_lemmes_spacy: %d lignes écrites → %s", nb_ecrites, output_path
    )
    print(f"✓ {nb_ecrites} lemmes extraits → '{output_path}'")


# ============================================================
# PLOT DE DISTRIBUTION DES SCORES IDF
# ============================================================


def plot_idf_distribution(idf_path: Path, output_path: Path) -> None:
    """Affiche la distribution des scores IDF pour choisir visuellement un seuil.

    Produit trois graphiques :
    - Histogramme de la distribution des scores IDF
    - Courbe cumulée (% de tokens en dessous d'un seuil donné)
    - Zoom sur les faibles valeurs IDF (candidats stop words)

    Args:
        idf_path:   chemin vers le fichier IDF (token \\t idf, sans en-tête)
        output_path: chemin du PNG à sauvegarder
    """
    import matplotlib.pyplot as plt

    # Lecture du fichier IDF
    scores: list[tuple[str, float]] = []
    with open(idf_path, encoding="utf-8") as f:
        for ligne in f:
            ligne = ligne.strip()
            if not ligne:
                continue
            parties = ligne.split("\t")
            if len(parties) != 2:
                continue
            scores.append((parties[0], float(parties[1])))

    scores.sort(key=lambda x: x[1])
    valeurs = [s[1] for s in scores]
    n = len(valeurs)

    fig, axes = plt.subplots(1, 3, figsize=(16, 5))
    fig.suptitle(
        "Distribution des scores IDF (lemmes spaCy)", fontsize=13, fontweight="bold"
    )

    # ── Graphique 1 : histogramme ──────────────────────────────────────────────
    nb_bins = 40
    min_v, max_v = min(valeurs), max(valeurs)
    pas = (max_v - min_v) / nb_bins
    bins = [min_v + i * pas for i in range(nb_bins + 1)]

    compte = [0] * nb_bins
    for v in valeurs:
        idx = min(int((v - min_v) / pas), nb_bins - 1)
        compte[idx] += 1

    centres = [bins[i] + pas / 2 for i in range(nb_bins)]
    axes[0].bar(centres, compte, width=pas * 0.9, color="#4C72B0", alpha=0.8)
    axes[0].set_xlabel("Score IDF")
    axes[0].set_ylabel("Nombre de tokens")
    axes[0].set_title("Histogramme des scores IDF")

    # ── Graphique 2 : courbe cumulée ───────────────────────────────────────────
    cumul = [(i + 1) / n * 100 for i in range(n)]
    axes[1].plot(valeurs, cumul, color="#4C72B0", linewidth=2)
    axes[1].set_xlabel("Score IDF")
    axes[1].set_ylabel("% de tokens en dessous du seuil")
    axes[1].set_title("Distribution cumulée")
    axes[1].grid(True, alpha=0.3)

    # Lignes de référence pour quelques seuils courants
    for seuil, couleur in [(0.5, "red"), (1.0, "orange"), (1.5, "green")]:
        nb_sous_seuil = sum(1 for v in valeurs if v <= seuil)
        pct = nb_sous_seuil / n * 100
        axes[1].axvline(
            seuil,
            color=couleur,
            linestyle="--",
            linewidth=1.2,
            label=f"seuil={seuil} ({pct:.1f}%)",
        )
    axes[1].legend(fontsize=8)

    # ── Graphique 3 : zoom sur les faibles IDF ────────────────────────────────
    seuil_zoom = 2.0
    valeurs_zoom = [v for v in valeurs if v <= seuil_zoom]
    tokens_zoom = [s[0] for s in scores if s[1] <= seuil_zoom]

    nb_bins_zoom = min(30, len(valeurs_zoom))
    if nb_bins_zoom > 1:
        pas_z = seuil_zoom / nb_bins_zoom
        bins_z = [i * pas_z for i in range(nb_bins_zoom + 1)]
        compte_z = [0] * nb_bins_zoom
        for v in valeurs_zoom:
            idx = min(int(v / pas_z), nb_bins_zoom - 1)
            compte_z[idx] += 1
        centres_z = [bins_z[i] + pas_z / 2 for i in range(nb_bins_zoom)]
        axes[2].bar(centres_z, compte_z, width=pas_z * 0.9, color="#C44E52", alpha=0.8)

    axes[2].set_xlabel("Score IDF")
    axes[2].set_ylabel("Nombre de tokens")
    axes[2].set_title(f"Zoom IDF ≤ {seuil_zoom} (candidats stop words)")
    axes[2].axvline(0.5, color="red", linestyle="--", linewidth=1.2, label="seuil=0.5")
    axes[2].axvline(
        1.0, color="orange", linestyle="--", linewidth=1.2, label="seuil=1.0"
    )
    axes[2].legend(fontsize=8)

    print(f"\nRépartition par seuil :")
    for seuil in [0.3, 0.5, 0.7, 1.0, 1.5, 2.0]:
        nb = sum(1 for v in valeurs if v <= seuil)
        print(f"  IDF ≤ {seuil} : {nb} tokens ({nb / n * 100:.1f}%)")

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.show()
    print(f"\n✓ Plot sauvegardé → '{output_path}'")


# ============================================================
# AFFINAGE DE L'ANTI-DICTIONNAIRE
# ============================================================


def build_antidictionary_v2(
    idf_path: Path,
    antidico_v1_path: Path,
    output_path: Path,
    threshold: float,
) -> None:
    """Construit l'anti-dictionnaire affiné sur les lemmes spaCy.

    Sélectionne les lemmes dont idf <= threshold ET qui ne figurent
    pas déjà dans l'anti-dictionnaire v1 (pour tracer les nouveaux ajouts).

    Output format (tab-separated, sans en-tête) :
        lemme \\t
    (substitution vide = suppression)

    Args:
        idf_path:        fichier IDF des lemmes (token \\t idf, sans en-tête)
        antidico_v1_path: anti-dictionnaire du TD2 (token \\t substitution)
        output_path:     chemin du nouvel anti-dictionnaire
        threshold:       seuil IDF — lemmes à ou en dessous = stop words
    """
    # Charger l'anti-dictionnaire v1
    antidico_v1: set[str] = set()
    with open(antidico_v1_path, encoding="utf-8") as f:
        for ligne in f:
            ligne = ligne.strip()
            if not ligne:
                continue
            parties = ligne.split("\t")
            antidico_v1.add(parties[0])

    # Lire les scores IDF des lemmes
    nouveaux: list[str] = []
    tous_stopwords: list[str] = []

    with open(idf_path, encoding="utf-8") as f:
        for ligne in f:
            ligne = ligne.strip()
            if not ligne:
                continue
            parties = ligne.split("\t")
            if len(parties) != 2:
                continue
            lemme, idf = parties[0], float(parties[1])
            if idf <= threshold:
                tous_stopwords.append(lemme)
                if lemme not in antidico_v1:
                    nouveaux.append(lemme)

    # Écrire le nouvel anti-dictionnaire (union v1 + nouveaux)
    with open(output_path, "w", encoding="utf-8") as f:
        for token in antidico_v1:
            f.write(f"{token}\t\n")
        for lemme in nouveaux:
            f.write(f"{lemme}\t\n")

    print(f"✓ Anti-dictionnaire v2 → '{output_path}'")
    print(f"  Stop words v1 (TD2)       : {len(antidico_v1)}")
    print(f"  Nouveaux stop words        : {len(nouveaux)}")
    print(f"  Total stop words           : {len(antidico_v1) + len(nouveaux)}")
    if nouveaux:
        print(f"  Exemples nouveaux          : {nouveaux[:10]}")

    logger.info(
        "build_antidictionary_v2: %d nouveaux stop words (seuil=%.2f) → %s",
        len(nouveaux),
        threshold,
        output_path,
    )


# ============================================================
# POINT D'ENTRÉE
# ============================================================

if __name__ == "__main__":
    # 1. Extraire les lemmes spaCy au format attendu par compute_tf/idf
    extraire_lemmes_spacy(
        lemmes_path=Path("outputs/lemmes.tsv"),
        output_path=Path("outputs/lemmes_spacy.tsv"),
    )

    # 2. Recalculer TF, IDF, TF-IDF sur les lemmes
    from adit_corpus_indexing.tfidf import compute_tf, compute_idf, compute_tfidf

    compute_tf(
        tokens_path=Path("outputs/lemmes_spacy.tsv"),
        output_path=Path("outputs/lemmes_tf.tsv"),
    )
    compute_idf(
        tokens_path=Path("outputs/lemmes_spacy.tsv"),
        output_path=Path("outputs/lemmes_idf.tsv"),
    )
    compute_tfidf(
        tf_path=Path("outputs/lemmes_tf.tsv"),
        idf_path=Path("outputs/lemmes_idf.tsv"),
        output_path=Path("outputs/lemmes_tfidf.tsv"),
    )

    # 3. Visualiser la distribution IDF pour choisir le seuil
    plot_idf_distribution(
        idf_path=Path("outputs/lemmes_idf.tsv"),
        output_path=Path("outputs/plot_idf_lemmes.png"),
    )

    # 4. Construire l'anti-dictionnaire v2 (adapter le seuil après le plot)
    build_antidictionary_v2(
        idf_path=Path("outputs/lemmes_idf.tsv"),
        antidico_v1_path=Path("outputs/antidictionary.tsv"),
        output_path=Path("outputs/antidictionary_v2.tsv"),
        threshold=0.75,  # à ajuster selon le plot
    )

    # 5. Filtrer le corpus XML avec l'anti-dictionnaire v2
    from adit_corpus_indexing.antidictionary import apply_to_corpus

    apply_to_corpus(
        corpus_path=Path("outputs/corpus_filtre.xml"),
        substitutions_path=Path("outputs/antidictionary_v2.tsv"),
        output_path=Path("outputs/corpus_final.xml"),
    )
    print("✓ Corpus final généré → 'outputs/corpus_final.xml'")
