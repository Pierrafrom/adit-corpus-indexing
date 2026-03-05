"""Script de test rapide du parser."""

import sys
import types
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

# Chargement manuel des modules (le répertoire contient un tiret)
spec_models = spec_from_file_location(
    "adit_corpus_indexing.models",
    Path(__file__).parent.parent / "src/adit-corpus-indexing/models.py",
)
models = module_from_spec(spec_models)  # type: ignore[arg-type]
spec_models.loader.exec_module(models)  # type: ignore[union-attr]

pkg = types.ModuleType("adit_corpus_indexing")
pkg.models = models  # type: ignore[attr-defined]
sys.modules["adit_corpus_indexing"] = pkg
sys.modules["adit_corpus_indexing.models"] = models

spec_parser = spec_from_file_location(
    "adit_corpus_indexing.parser",
    Path(__file__).parent.parent / "src/adit-corpus-indexing/parser.py",
)
parser = module_from_spec(spec_parser)  # type: ignore[arg-type]
spec_parser.loader.exec_module(parser)  # type: ignore[union-attr]

FILES = ["67068.htm", "67071.htm", "67383.htm", "68273.htm", "69533.htm"]

for filename in FILES:
    art = parser.parse_article(Path("data/BULLETINS") / filename)
    print(f"\n{'=' * 60}")
    print("fichier  :", filename)
    print("code     :", art.code)
    print("bulletin :", art.bulletin)
    print("date     :", art.date)
    print("rubrique :", art.rubrique)
    print("title    :", art.title)
    if art.author:
        print("auteur   :", art.author.name, "|", art.author.email)
    else:
        print("auteur   : (absent)")
    for c in art.contacts:
        print(f"contact  : {c.name} | email={c.email} | url={c.url} | tel={c.phone}")
    print("images   :", len(art.images), "image(s)")
    print("body     :", art.body[:80].replace("\n", " "))
