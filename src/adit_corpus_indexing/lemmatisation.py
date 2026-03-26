"""Lemmatisation du corpus filtré avec spaCy et Snowball."""

from pathlib import Path

import spacy
from nltk.stem.snowball import SnowballStemmer  # type: ignore[import-untyped]

from adit_corpus_indexing.models import (
    LemmatizedToken,  # noqa: F401  (kept for script use)
)


def lemmatiser(corpus_path: Path, output_path: Path) -> None:
    """
    Applique spaCy et Snowball sur les <titre> et <texte> du corpus filtré.

    Produit un fichier TSV à trois colonnes :
        article_id \\t token \\t lemme_spacy \\t stemme_snowball

    Args:
        corpus_path: chemin vers le corpus XML filtré.
        output_path: chemin du fichier TSV de sortie.
    """

    # ===== Chargement des outils =====
    nlp = spacy.load("fr_core_news_sm")
    stemmer = SnowballStemmer("french")

    # ===== Lecture du corpus XML brut =====
    with open(corpus_path, encoding="utf-8") as f:
        contenu = f.read()

    # ===== Découpage en documents =====
    documents = contenu.split("<document>")[1:]

    tokens: list[LemmatizedToken] = []

    for doc in documents:

        def extraire(balise: str, content: str) -> str:
            """Extract text between opening and closing tags."""
            debut = content.find(f"<{balise}>")
            fin = content.find(f"</{balise}>")
            if debut == -1 or fin == -1:
                return ""
            return content[debut + len(balise) + 2 : fin].strip()

        article_id = extraire("article", doc)
        titre = extraire("titre", doc)
        texte = extraire("texte", doc)
        contenu_doc = titre + " " + texte

        # ===== spaCy : lemmatisation =====
        doc_spacy = nlp(contenu_doc)

        for spacy_token in doc_spacy:
            # On ignore la ponctuation et les espaces
            if not spacy_token.is_alpha:
                continue
            mot = spacy_token.text.lower()
            lemme_spacy = spacy_token.lemma_.lower()
            stemme_snowball = stemmer.stem(mot)
            tokens.append(
                LemmatizedToken(
                    article_id=article_id,
                    token=mot,
                    lemma=lemme_spacy,
                    stem=stemme_snowball,
                )
            )

    # ===== Écriture du fichier TSV =====
    lines = ["article_id\ttoken\tlemme_spacy\tstemme_snowball"]
    for token in tokens:
        lines.append(f"{token.article_id}\t{token.token}\t{token.lemma}\t{token.stem}")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f" {len(tokens)} tokens écrits dans '{output_path}'")


# ============================================================
# POINT D'ENTRÉE
# ============================================================

if __name__ == "__main__":
    lemmatiser(
        corpus_path=Path("outputs/corpus_filtre.xml"),
        output_path=Path("outputs/lemmes.tsv"),
    )
