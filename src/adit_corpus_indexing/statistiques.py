"""
statistiques.py
Analyse comparative des lemmatisations spaCy et Snowball.
"""

import math
from pathlib import Path


def charger_lemmes(chemin_tsv: Path) -> list[tuple[str, str, str, str]]:
    """
    Charge le fichier lemmes.tsv en une liste de tuples.

    Returns:
        Liste de (article_id, token, lemme_spacy, stemme_snowball).
    """
    with open(chemin_tsv, encoding="utf-8") as f:
        lignes = f.readlines()

    resultats = []
    for ligne in lignes[1:]:  # ignorer l'en-tête
        ligne = ligne.strip()
        if not ligne:
            continue
        parties = ligne.split("\t")
        if len(parties) == 4:
            resultats.append((parties[0], parties[1], parties[2], parties[3]))
    return resultats


def compter_uniques(valeurs: list[str]) -> int:
    """Retourne le nombre de valeurs uniques dans une liste."""
    return len(set(valeurs))


def calculer_distribution(valeurs: list[str]) -> dict[str, int]:
    """Retourne un dictionnaire {valeur: nombre_occurrences} trié par fréquence décroissante."""
    compteur = {}
    for v in valeurs:
        compteur[v] = compteur.get(v, 0) + 1
    return dict(sorted(compteur.items(), key=lambda x: x[1], reverse=True))


def calculer_moyenne(valeurs: list[float]) -> float:
    """Calcule la moyenne d'une liste de nombres."""
    if not valeurs:
        return 0.0
    return sum(valeurs) / len(valeurs)


def calculer_ecart_type(valeurs: list[float]) -> float:
    """Calcule l'écart-type d'une liste de nombres."""
    if not valeurs:
        return 0.0
    moyenne = calculer_moyenne(valeurs)
    variance = sum((v - moyenne) ** 2 for v in valeurs) / len(valeurs)
    return math.sqrt(variance)


def taux_reduction(tokens: list[str], formes: list[str]) -> float:
    """
    Calcule le taux de réduction du vocabulaire.
    = (nb tokens uniques - nb formes uniques) / nb tokens uniques * 100
    """
    nb_tokens = compter_uniques(tokens)
    nb_formes = compter_uniques(formes)
    if nb_tokens == 0:
        return 0.0
    return (nb_tokens - nb_formes) / nb_tokens * 100


def divergences(
    donnees: list[tuple[str, str, str, str]],
) -> list[tuple[str, str, str]]:
    """
    Retourne les cas où spaCy et Snowball produisent des résultats différents.

    Returns:
        Liste de (token, lemme_spacy, stemme_snowball).
    """
    vus = set()
    diff = []
    for _, token, spacy, snowball in donnees:
        if token not in vus and spacy != snowball:
            diff.append((token, spacy, snowball))
            vus.add(token)
    return diff


def longueur_moyenne_formes(formes: list[str]) -> float:
    """Calcule la longueur moyenne des formes (lemmes ou stems)."""
    if not formes:
        return 0.0
    return calculer_moyenne([len(f) for f in formes])


def tokens_inchanges(tokens: list[str], formes: list[str]) -> tuple[int, float]:
    """
    Compte les tokens dont la forme n'a pas changé après lemmatisation.

    Returns:
        (nombre, pourcentage)
    """
    inchanges = sum(1 for t, f in zip(tokens, formes) if t == f)
    pct = inchanges / len(tokens) * 100 if tokens else 0.0
    return inchanges, pct


def top_n(distribution: dict[str, int], n: int = 20) -> list[tuple[str, int]]:
    """Retourne les n formes les plus fréquentes."""
    items = list(distribution.items())
    return items[:n]


def repartition_par_document(
    donnees: list[tuple[str, str, str, str]],
) -> dict[str, int]:
    """Retourne le nombre de tokens par document."""
    compteur = {}
    for article_id, _, _, _ in donnees:
        compteur[article_id] = compteur.get(article_id, 0) + 1
    return dict(sorted(compteur.items(), key=lambda x: x[1], reverse=True))


def analyser(chemin_tsv: Path, chemin_rapport: Path) -> None:
    """
    Calcule toutes les statistiques comparatives et écrit un rapport TSV.

    Args:
        chemin_tsv:     chemin vers lemmes.tsv
        chemin_rapport: chemin du fichier de rapport à écrire
    """
    donnees = charger_lemmes(chemin_tsv)

    tokens = [d[1] for d in donnees]
    spacys = [d[2] for d in donnees]
    snowballs = [d[3] for d in donnees]

    # ===== CALCULS =====

    nb_total = len(tokens)
    nb_tokens_uniques = compter_uniques(tokens)
    nb_spacy_uniques = compter_uniques(spacys)
    nb_snow_uniques = compter_uniques(snowballs)

    taux_red_spacy = taux_reduction(tokens, spacys)
    taux_red_snow = taux_reduction(tokens, snowballs)

    long_moy_tokens = longueur_moyenne_formes(tokens)
    long_moy_spacy = longueur_moyenne_formes(spacys)
    long_moy_snow = longueur_moyenne_formes(snowballs)

    inchanges_spacy, pct_inch_spacy = tokens_inchanges(tokens, spacys)
    inchanges_snow, pct_inch_snow = tokens_inchanges(tokens, snowballs)

    dist_spacy = calculer_distribution(spacys)
    dist_snow = calculer_distribution(snowballs)

    diff = divergences(donnees)
    nb_divergences = len(diff)
    pct_divergences = (
        nb_divergences / nb_tokens_uniques * 100 if nb_tokens_uniques else 0
    )

    docs = repartition_par_document(donnees)

    longueurs_spacy = [len(s) for s in spacys]
    longueurs_snow = [len(s) for s in snowballs]

    # ===== AFFICHAGE =====

    lignes_rapport = []

    def section(titre: str) -> None:
        lignes_rapport.append("")
        lignes_rapport.append(f"=== {titre} ===")

    def ligne(label: str, valeur) -> None:
        lignes_rapport.append(f"{label}\t{valeur}")

    section("CORPUS")
    ligne("Nombre total de tokens (occurrences)", nb_total)
    ligne("Nombre de tokens uniques", nb_tokens_uniques)
    ligne("Nombre de documents", len(docs))

    section("VOCABULAIRE UNIQUE")
    ligne("Lemmes uniques spaCy", nb_spacy_uniques)
    ligne("Stems uniques Snowball", nb_snow_uniques)

    section("TAUX DE REDUCTION DU VOCABULAIRE")
    ligne("Taux de réduction spaCy (%)", f"{taux_red_spacy:.2f}")
    ligne("Taux de réduction Snowball (%)", f"{taux_red_snow:.2f}")

    section("LONGUEUR MOYENNE DES FORMES")
    ligne("Longueur moyenne tokens originaux", f"{long_moy_tokens:.2f}")
    ligne("Longueur moyenne lemmes spaCy", f"{long_moy_spacy:.2f}")
    ligne("Longueur moyenne stems Snowball", f"{long_moy_snow:.2f}")

    section("ECART-TYPE DES LONGUEURS")
    ligne("Écart-type longueurs spaCy", f"{calculer_ecart_type(longueurs_spacy):.2f}")
    ligne("Écart-type longueurs Snowball", f"{calculer_ecart_type(longueurs_snow):.2f}")

    section("TOKENS INCHANGES APRES LEMMATISATION")
    ligne("Tokens inchangés spaCy", f"{inchanges_spacy} ({pct_inch_spacy:.1f}%)")
    ligne("Tokens inchangés Snowball", f"{inchanges_snow} ({pct_inch_snow:.1f}%)")

    section("DIVERGENCES ENTRE SPACY ET SNOWBALL")
    ligne("Nombre de divergences (tokens uniques)", nb_divergences)
    ligne("Pourcentage de divergences (%)", f"{pct_divergences:.2f}")

    section("TOP 20 LEMMES SPACY LES PLUS FREQUENTS")
    for lemme, count in top_n(dist_spacy, 20):
        ligne(lemme, count)

    section("TOP 20 STEMS SNOWBALL LES PLUS FREQUENTS")
    for stem, count in top_n(dist_snow, 20):
        ligne(stem, count)

    section("TOKENS PAR DOCUMENT")
    for article_id, count in docs.items():
        ligne(f"Article {article_id}", count)

    section("EXEMPLES DE DIVERGENCES (50 premiers)")
    lignes_rapport.append("token\tlemme_spacy\tstemme_snowball")
    for token, spacy, snowball in diff[:50]:
        lignes_rapport.append(f"{token}\t{spacy}\t{snowball}")

    # ===== ECRITURE =====
    with open(chemin_rapport, "w", encoding="utf-8") as f:
        f.write("\n".join(lignes_rapport))

    print(f"✓ Rapport écrit dans '{chemin_rapport}'")

    # ===== RÉSUMÉ CONSOLE =====
    print(f"\n{'=' * 50}")
    print(f"  Tokens total          : {nb_total}")
    print(f"  Tokens uniques        : {nb_tokens_uniques}")
    print(f"  Lemmes uniques spaCy  : {nb_spacy_uniques}")
    print(f"  Stems uniques Snowball: {nb_snow_uniques}")
    print(f"  Réduction spaCy       : {taux_red_spacy:.1f}%")
    print(f"  Réduction Snowball    : {taux_red_snow:.1f}%")
    print(f"  Divergences           : {nb_divergences} ({pct_divergences:.1f}%)")
    print(f"{'=' * 50}")


# ============================================================
# POINT D'ENTRÉE
# ============================================================

if __name__ == "__main__":
    analyser(
        chemin_tsv=Path("outputs/lemmes.tsv"),
        chemin_rapport=Path("outputs/rapport_stats.tsv"),
    )
