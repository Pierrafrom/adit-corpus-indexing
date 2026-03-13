"""TD2 — Anti-dictionary: identify stop words and apply substitutions."""

import logging
import math
from pathlib import Path

logger = logging.getLogger(__name__)


def build_antidictionary(idf_path: Path, output_path: Path, threshold: float) -> None:
    """Select stop-word tokens based on their IDF score.

    Tokens with idf <= threshold are considered non-informative (stop words).
    Low IDF means the token appears in almost every document.

    Output format (tab-separated, two columns):
        token\\t
    (empty substitution means "delete this token")

    Args:
        idf_path:   path to idf TSV produced by compute_idf().
        output_path: path to write the antidictionary TSV.
        threshold:  idf cutoff — tokens at or below this value are stop words.
    """
    # TODO:
    #   1. read idf_path
    #   2. select rows where idf <= threshold
    #   3. write (token, "") rows to output_path as UTF-8 TSV
    #   4. log how many stop words were selected
    raise NotImplementedError


def substitue(text: str, substitutions_path: Path) -> str:
    """Replace or delete tokens in *text* according to a substitution file.

    The substitution file is a two-column TSV:
        token\\treplacement
    An empty replacement string means the token is deleted.
    Matching is case-insensitive; word boundaries are respected.

    Args:
        text:               input text to filter.
        substitutions_path: path to the substitution TSV file.

    Returns:
        Filtered text with stop words removed and extra whitespace collapsed.
    """
    # TODO:
    #   1. load substitution file into a dict {token: replacement}
    #   2. split text into tokens (same logic as tokenizer.tokenize)
    #   3. for each token: if in substitutions dict, replace (or drop if "")
    #   4. rejoin remaining tokens and collapse whitespace
    raise NotImplementedError


def apply_to_corpus(
    corpus_path: Path,
    substitutions_path: Path,
    output_path: Path,
) -> None:
    """Produce a filtered corpus XML with stop words removed from all text fields.

    Applies substitue() to every <titre> and <texte> element in corpus.xml.

    Args:
        corpus_path:        path to the original corpus.xml.
        substitutions_path: path to the antidictionary TSV.
        output_path:        path to write the filtered corpus XML.
    """
    # TODO:
    #   1. parse corpus_path with lxml
    #   2. for each <document>, apply substitue() to <titre> and <texte> text
    #   3. write the modified tree to output_path (UTF-8, pretty_print=True)
    raise NotImplementedError


# --- Fonction interne pour extraire le contenu d'une balise ---
# Cherche les balises d'ouverture et de fermeture,
# puis récupère le texte entre les deux
def extraire(doc: str, balise: str) -> str:
    # Cherche la position du début : "<balise>"
    debut = doc.find(f"<{balise}>")
    # Cherche la position du débout de la fermeture : "</balise>"
    fin = doc.find(f"</{balise}>")
    # Si l'une des balises est manquante, retourner chaîne vide
    if debut == -1 or fin == -1:
        return ""
    # Extraire le texte : on saute "<balise>" (len(balise) + 2 caractères: < et >)
    # jusqu'au début de "</balise>"
    return doc[debut + len(balise) + 2 : fin].strip()


def segmente(chemin_xml: str, chemin_sortie: str = "tokens.tsv") -> str:
    """
    Découpe les titres et textes du corpus XML en tokens.

    Fichier produit : TSV avec deux colonnes par ligne
        identifiant_du_document \\t token

    L'identifiant est le numéro de bulletin (<bulletin>).
    Retourne le chemin du fichier TSV produit.
    """

    # ===== ÉTAPE 1 : Lire le fichier XML brut =====
    # On charge tout le contenu en mémoire comme une grande chaîne de caractères.
    # Cela nous permet de faire des splits et des recherches simples avec find().
    with open(chemin_xml, encoding="utf-8") as f:
        contenu = f.read()

    # ===== ÉTAPE 2 : Découper en documents individuels =====
    # On divise le contenu sur la balise "<document>".
    # - Le premier élément [0] est l'en-tête du corpus (avant le premier <document>)
    # - Les éléments [1:] sont les documents eux-mêmes
    # Exemple: "<corpus>...</corpus><document>doc1</doc..."
    # → ['<corpus>...</corpus>', 'doc1</doc...', ...]
    documents = contenu.split("<document>")[1:]  # [0] est l'en-tête du corpus

    # Initialiser la liste des lignes avec l'en-tête TSV
    lignes = ["identifiant_du_document\ttoken"]

    # ===== ÉTAPE 3 : Traiter chaque document =====
    for doc in documents:
        # Extraire l'identifiant (le numéro d'article)
        identifiant = extraire(doc, "article")
        # Extraire le titre
        titre = extraire(doc, "titre")
        # Extraire le corps du texte
        texte = extraire(doc, "texte")
        # Combiner titre et texte pour une tokenisation complète
        contenu_doc = titre + " " + texte

        # ===== ÉTAPE 4 : Tokenisation (découpage en mots) =====
        # On parcourt chaque caractère et on accumule les lettres dans "mot".
        # Quand on rencontre un caractère qui n'est pas une lettre, on termine le mot.
        tokens_bruts = []
        mot = ""
        for char in contenu_doc:
            # Les lettres et les tirets (-) font partie du mot
            # (les tirets permettent de garder les mots composés comme "test-unitaire")
            if char.isalpha() or char == "-":
                mot += char
            else:
                # Caractère de séparation (espace, ponctuation, etc.)
                # Si nous avons un mot en cours, l'ajouter à la liste
                if mot:
                    tokens_bruts.append(mot)
                    mot = ""
        # Ne pas oublier le dernier mot si la chaîne ne finit pas par un séparateur
        if mot:
            tokens_bruts.append(mot)

        # ===== ÉTAPE 5 : Créer les lignes TSV =====
        # Pour chaque token, créer une ligne "identifiant\ttoken"
        # Les tokens sont convertis en minuscules pour normaliser
        for token in tokens_bruts:
            lignes.append(f"{identifiant}\t{token.lower()}")

    # ===== ÉTAPE 6 : Écrire le fichier TSV =====
    # Ouvrir un fichier en écriture et y écrire
    # toutes les lignes séparées par des retours à la ligne
    with open(chemin_sortie, "w", encoding="utf-8") as f:
        f.write("\n".join(lignes))

    # Afficher un résumé (on soustrait 1 pour exclure l'en-tête)
    nb_tokens = len(lignes) - 1
    print(f"✓ {nb_tokens} tokens écrits dans '{chemin_sortie}'")
    return chemin_sortie


# Question 2 : Compter les occurrences de tokens dans les documents
def compter_occurences(chemin_tsv: str) -> dict[str, int]:
    """
    Compte le nombre d'occurrences de chaque token dans chaque document.

    Args:
        chemin_tsv: chemin du fichier TSV produit par segmente().

    Returns:
        Un dictionnaire {(identifiant,token): nombre_d_occurrences}.
    """
    with open(chemin_tsv, encoding="utf-8") as f:
        lignes = f.readlines()
    # Ignorer l'en-tête
    tokens = []
    for ligne in lignes[1:]:
        ligne = ligne.strip()
        if ligne:
            identifiant, token = ligne.split("\t")
            tokens.append((identifiant, token))
    documents = {}
    for identifiant, token in tokens:
        if (identifiant, token) not in documents:
            documents[(identifiant, token)] = 1
        else:
            documents[(identifiant, token)] += 1
    return documents


def construire_fichier_occurences(
    occurrences: dict[str, int], chemin_sortie: str
) -> None:
    """
    Écrit les occurrences de tokens dans un fichier TSV.

    Args:
        occurrences: dictionnaire {token: [id, nombre_d_occurrences]}.
        chemin_sortie: chemin du fichier TSV à écrire.
    """
    with open(chemin_sortie, "w", encoding="utf-8") as f:
        f.write("id\ttoken\tnombre_d_occurrences\n")
        for (id, token), count in occurrences.items():
            f.write(f"{id}\t{token}\t{count}\n")
    print(f"✓ Occurrences écrites dans '{chemin_sortie}'")


# Question 3 : Compter le nombre de documents par token et calculer les coefficients IDF
def compter_apparitions_documents(
    occurrences: dict[tuple[str, str], int],
) -> dict[str, tuple[list[str], int]]:
    """Compte le nombre de documents dans lesquels chaque token apparaît.

    Args:
        occurrences: dictionnaire {(id_document, token): nombre_d_occurrences}.

    Returns:
        Un dictionnaire {token: ([liste_des_documents], nombre_de_documents)}.

    Exemple:
        {"physique": (["1", "4", "7"], 3)}
    """

    doc_counts: dict[str, tuple[list[str], int]] = {}
    for id_doc, token in occurrences.keys():
        if token not in doc_counts:
            # Première apparition du token : on crée la structure
            doc_counts[token] = ([id_doc], 1)
        else:
            # Le token existe déjà : on ajoute l'identifiant et on incrémente
            docs, count = doc_counts[token]
            docs.append(id_doc)
            doc_counts[token] = (docs, count + 1)

    return doc_counts


def creer_coefficients(doc_counts: dict[str, int], total_docs: int) -> dict[str, float]:
    """
    Calcule les coefficients IDF pour chaque token.

    Args:
        doc_counts: dictionnaire {token: [liste des documents]}.
        total_docs: nombre total de documents dans le corpus.

    Returns:
        Un dictionnaire {token: idf}.
    """
    idf_scores = {}
    for token, (_, count) in doc_counts.items():
        idf_scores[token] = math.log(total_docs / count, 10)  # IDF = log(N / df)
    return idf_scores


def construire_fichier_idf(idf_scores: dict[str, float], chemin_sortie: str) -> None:
    """
    Écrit les scores IDF dans un fichier TSV.

    Args:
        idf_scores: dictionnaire {token: idf}.
        chemin_sortie: chemin du fichier TSV à écrire.
    """
    with open(chemin_sortie, "w", encoding="utf-8") as f:
        f.write("token\tidf\n")
        for token, idf in idf_scores.items():
            f.write(f"{token}\t{idf}\n")
    print(f"✓ IDF scores écrits dans '{chemin_sortie}'")


def creer_tf_idf(
    occurrences: dict[tuple[str, str], int], idf_scores: dict[str, float]
) -> dict[tuple[str, str], float]:
    """
    Calcule les scores TF-IDF pour chaque token dans chaque document.

    Args:
        occurrences: dictionnaire {(id_document, token): nombre_d_occurrences}.
        idf_scores: dictionnaire {token: idf}.
    Returns:
        Un dictionnaire {(id_document, token): tf_idf}.
    """
    tf_idf_scores = {}
    for (id_doc, token), count in occurrences.items():
        tf = count  # Term Frequency (nombre d'occurrences du token dans le document)
        idf = idf_scores[token]  # IDF du token (0 si non trouvé)
        tf_idf_scores[(id_doc, token)] = tf * idf  # TF-IDF = TF * IDF
    return tf_idf_scores


def construire_fichier_tf_idf(
    tf_idf_scores: dict[tuple[str, str], float], chemin_sortie: str
) -> None:
    """
    Écrit les scores TF-IDF dans un fichier TSV.

    Args:
        tf_idf_scores: dictionnaire {(id_document, token): tf_idf}.
        chemin_sortie: chemin du fichier TSV à écrire.
    """
    with open(chemin_sortie, "w", encoding="utf-8") as f:
        f.write("id\ttoken\ttf_idf\n")
        for (id_doc, token), tf_idf in tf_idf_scores.items():
            f.write(f"{id_doc}\t{token}\t{tf_idf}\n")
    print(f"✓ TF-IDF scores écrits dans '{chemin_sortie}'")


# Pour les tests, on peut exécuter ce script directement
# pour produire les fichiers tokens.tsv et occurrences.tsv
# à partir du corpus.xml généré précédemment.
if __name__ == "__main__":
    segmente(r"outputs/corpus.xml", "outputs/tokens.tsv")
    occ = compter_occurences("outputs/tokens.tsv")
    construire_fichier_occurences(occ, "outputs/occurrences.tsv")
    doc_counts = compter_apparitions_documents(occ)
    with open("tests/document_counts.tsv", "w", encoding="utf-8") as f:
        f.write("token\tdocuments\n")
        for cle in doc_counts.keys():
            # f.write(f"{cle}\t{', '.join(occ[cle])}\n")
            f.write(f"{cle}\t->\t{doc_counts[cle]}\n")
    idf_scores = creer_coefficients(doc_counts, total_docs=326)
    construire_fichier_idf(idf_scores, "outputs/idf.tsv")
    tf_idf_scores = creer_tf_idf(occ, idf_scores)
    construire_fichier_tf_idf(tf_idf_scores, "outputs/tf_idf.tsv ")
