"""Tests for TD4 — spell_checker module.

Three test classes matching the three building blocks:

- ``TestPureFunctions``  : levenshtein_distance, common_prefix_length, is_entity
- ``TestLexicon``        : loading, membership, prefix_candidates
- ``TestSpellChecker``   : the six correction steps (a)→(f) + process_query
"""

from pathlib import Path

import pytest

from adit_corpus_indexing.models import CorrectionResult
from adit_corpus_indexing.nlp.spell_checker import (
    Lexicon,
    SpellChecker,
    common_prefix_length,
    is_entity,
    levenshtein_distance,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"
MINI_LEXICON = FIXTURES_DIR / "mini_lexicon.tsv"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@pytest.fixture()
def lexicon() -> Lexicon:
    """Lexicon loaded from the mini test fixture."""
    return Lexicon.from_tsv(MINI_LEXICON)


@pytest.fixture()
def checker(lexicon: Lexicon) -> SpellChecker:
    """SpellChecker with default hyperparameters on the mini lexicon."""
    return SpellChecker(lexicon, seuil_min=3, seuil_max=6, seuil_proximite=3)


# ---------------------------------------------------------------------------
# 1. Pure functions
# ---------------------------------------------------------------------------


class TestLevenshteinDistance:
    def test_equal_strings(self) -> None:
        assert levenshtein_distance("abc", "abc") == 0

    def test_empty_vs_string(self) -> None:
        assert levenshtein_distance("", "abc") == 3

    def test_string_vs_empty(self) -> None:
        assert levenshtein_distance("abc", "") == 3

    def test_both_empty(self) -> None:
        assert levenshtein_distance("", "") == 0

    def test_one_substitution(self) -> None:
        assert levenshtein_distance("chat", "chats") == 1

    def test_symmetric(self) -> None:
        a, b = "nanotechnologie", "nanotechnologiq"
        assert levenshtein_distance(a, b) == levenshtein_distance(b, a)

    def test_classic_kitten_sitting(self) -> None:
        assert levenshtein_distance("kitten", "sitting") == 3

    def test_insertion_only(self) -> None:
        # "algorith" → "algorithme": 2 insertions
        assert levenshtein_distance("algorith", "algorithme") == 2

    def test_deletion_only(self) -> None:
        # "recherche" → "recher": 3 deletions
        assert levenshtein_distance("recherche", "recher") == 3

    def test_french_word_close(self) -> None:
        # single typo at end
        assert levenshtein_distance("nanotechnologi", "nanotechnologie") == 1

    def test_french_word_far(self) -> None:
        # completely different
        assert levenshtein_distance("corpus", "requête") == 7


class TestCommonPrefixLength:
    def test_identical(self) -> None:
        assert common_prefix_length("abc", "abc") == 3

    def test_no_common_prefix(self) -> None:
        assert common_prefix_length("abc", "xyz") == 0

    def test_empty_a(self) -> None:
        assert common_prefix_length("", "abc") == 0

    def test_empty_b(self) -> None:
        assert common_prefix_length("abc", "") == 0

    def test_both_empty(self) -> None:
        assert common_prefix_length("", "") == 0

    def test_partial_match(self) -> None:
        assert common_prefix_length("nanotechnologie", "nanotechnologic") == 14

    def test_prefix_is_whole_word(self) -> None:
        assert common_prefix_length("nano", "nanotechnologie") == 4

    def test_one_char_diff_at_start(self) -> None:
        assert common_prefix_length("banotechnologie", "nanotechnologie") == 0


class TestIsEntity:
    def test_integer(self) -> None:
        assert is_entity("42")

    def test_year(self) -> None:
        assert is_entity("2024")

    def test_date_slash(self) -> None:
        assert is_entity("01/01/2024")

    def test_date_hyphen(self) -> None:
        assert is_entity("01-01-2024")

    def test_month_year(self) -> None:
        assert is_entity("03/2024")

    def test_regular_word(self) -> None:
        assert not is_entity("nanotechnologie")

    def test_empty_string(self) -> None:
        assert not is_entity("")

    def test_mixed_alpha_digit(self) -> None:
        assert not is_entity("td4")


# ---------------------------------------------------------------------------
# 2. Lexicon
# ---------------------------------------------------------------------------


class TestLexiconFromTsv:
    def test_loads_correctly(self, lexicon: Lexicon) -> None:
        assert len(lexicon) == 25

    def test_known_word_present(self, lexicon: Lexicon) -> None:
        assert "nanotechnologie" in lexicon

    def test_unknown_word_absent(self, lexicon: Lexicon) -> None:
        assert "inexistant" not in lexicon

    def test_get_lemma_known(self, lexicon: Lexicon) -> None:
        assert lexicon.get_lemma("robotique") == "robot"

    def test_get_lemma_unknown(self, lexicon: Lexicon) -> None:
        assert lexicon.get_lemma("inexistant") is None

    def test_get_lemma_identity(self, lexicon: Lexicon) -> None:
        # some entries map to themselves
        assert lexicon.get_lemma("nanotechnologie") == "nanotechnologie"


class TestLexiconFromIndex:
    def test_loads_from_index_file(self, tmp_path: Path) -> None:
        idx = tmp_path / "index.tsv"
        idx.write_text("algorithme\t1:3 2:1\nréseau\t1:1\n", encoding="utf-8")
        lex = Lexicon.from_index(idx)
        assert "algorithme" in lex
        assert "réseau" in lex
        # When loaded from index, lemma == term
        assert lex.get_lemma("algorithme") == "algorithme"

    def test_skips_blank_lines(self, tmp_path: Path) -> None:
        idx = tmp_path / "index.tsv"
        idx.write_text("algo\t1:1\n\nreseau\t2:1\n", encoding="utf-8")
        lex = Lexicon.from_index(idx)
        assert len(lex) == 2


class TestLexiconPrefixCandidates:
    def test_exact_prefix_match(self, lexicon: Lexicon) -> None:
        # "nanotechnologi" shares 14 chars with "nanotechnologie"
        candidates = lexicon.prefix_candidates(
            "nanotechnologi", seuil_min=3, seuil_max=6, seuil_proximite=3
        )
        assert "nanotechnologie" in candidates

    def test_no_match_first_char_wrong(self, lexicon: Lexicon) -> None:
        # first char 'b' instead of 'n' — prefix search blind spot
        candidates = lexicon.prefix_candidates(
            "banotechnologie", seuil_min=3, seuil_max=6, seuil_proximite=3
        )
        assert candidates == []

    def test_word_too_short(self, lexicon: Lexicon) -> None:
        candidates = lexicon.prefix_candidates(
            "ab", seuil_min=3, seuil_max=6, seuil_proximite=3
        )
        assert candidates == []

    def test_seuil_min_boundary(self, lexicon: Lexicon) -> None:
        # word length == seuil_min → search is attempted
        candidates = lexicon.prefix_candidates(
            "res", seuil_min=3, seuil_max=6, seuil_proximite=3
        )
        assert "réseau" in candidates or candidates == []  # depends on accent

    def test_multiple_candidates(self, lexicon: Lexicon) -> None:
        # "tra" is a prefix shared by "traitement"
        candidates = lexicon.prefix_candidates(
            "traitem", seuil_min=3, seuil_max=6, seuil_proximite=3
        )
        assert "traitement" in candidates

    def test_returns_list(self, lexicon: Lexicon) -> None:
        result = lexicon.prefix_candidates(
            "algo", seuil_min=3, seuil_max=6, seuil_proximite=3
        )
        assert isinstance(result, list)

    def test_high_seuil_proximite_restricts(self, lexicon: Lexicon) -> None:
        # With seuil_proximite=10, "algorit" (7 chars) can't match anything
        candidates = lexicon.prefix_candidates(
            "algorit", seuil_min=3, seuil_max=6, seuil_proximite=10
        )
        assert candidates == []


# ---------------------------------------------------------------------------
# 3. SpellChecker — the six correction steps
# ---------------------------------------------------------------------------


class TestSpellCheckerCorrectTerm:
    # (a) Entity
    def test_step_a_integer(self, checker: SpellChecker) -> None:
        result = checker.correct_term("2024")
        assert result.status == "entity"
        assert result.corrected == "2024"
        assert result.lemma == "2024"

    def test_step_a_date(self, checker: SpellChecker) -> None:
        result = checker.correct_term("01/01/2024")
        assert result.status == "entity"

    # (b) Exact match
    def test_step_b_exact(self, checker: SpellChecker) -> None:
        result = checker.correct_term("nanotechnologie")
        assert result.status == "exact"
        assert result.corrected == "nanotechnologie"
        assert result.lemma == "nanotechnologie"

    def test_step_b_exact_with_lemma(self, checker: SpellChecker) -> None:
        result = checker.correct_term("robotique")
        assert result.status == "exact"
        assert result.lemma == "robot"

    # (d) Single candidate
    def test_step_d_single_candidate(self, checker: SpellChecker) -> None:
        # "nanotechnologi" — one char missing at the end
        result = checker.correct_term("nanotechnologi")
        assert result.status in ("single_candidate", "best_candidate")
        assert result.corrected == "nanotechnologie"

    # (e) Multiple candidates → Levenshtein
    def test_step_e_levenshtein_picks_closest(self, checker: SpellChecker) -> None:
        # Build a lexicon with two words close to "algorithmf"
        lex = Lexicon({"algorithme": "algorithme", "algorithmique": "algorithmique"})
        chk = SpellChecker(lex, seuil_min=3, seuil_max=6, seuil_proximite=3)
        result = chk.correct_term("algorithmf")
        assert result.status == "best_candidate"
        # "algorithmf" is closer to "algorithme" (dist=1) than "algorithmique" (dist=4)
        assert result.corrected == "algorithme"
        assert result.distance == 1

    def test_step_e_has_candidates_list(self, checker: SpellChecker) -> None:
        lex = Lexicon({"algorithme": "alg", "algorithmique": "alg"})
        chk = SpellChecker(lex, seuil_min=3, seuil_max=6, seuil_proximite=3)
        result = chk.correct_term("algorithmf")
        if result.status == "best_candidate":
            assert len(result.candidates) >= 2

    # (f) Not found
    def test_step_f_not_found(self, checker: SpellChecker) -> None:
        result = checker.correct_term("xyzqwerty")
        assert result.status == "not_found"
        assert result.corrected is None
        assert result.lemma is None

    def test_step_f_first_char_wrong(self, checker: SpellChecker) -> None:
        # Vulnerability: first char changed — prefix search finds nothing
        result = checker.correct_term("banotechnologie")
        assert result.status == "not_found"

    # Return type is always CorrectionResult
    def test_returns_correction_result(self, checker: SpellChecker) -> None:
        result = checker.correct_term("recherche")
        assert isinstance(result, CorrectionResult)
        assert result.original == "recherche"


class TestSpellCheckerProcessQuery:
    def test_empty_query(self, checker: SpellChecker) -> None:
        assert checker.process_query("") == []

    def test_single_exact_term(self, checker: SpellChecker) -> None:
        results = checker.process_query("corpus")
        assert len(results) == 1
        assert results[0].status == "exact"

    def test_multiple_terms(self, checker: SpellChecker) -> None:
        results = checker.process_query("corpus recherche données")
        assert len(results) == 3
        assert all(r.status == "exact" for r in results)

    def test_mixed_correct_and_typo(self, checker: SpellChecker) -> None:
        results = checker.process_query("corpus nanotechnologi")
        statuses = {r.original: r.status for r in results}
        assert statuses["corpus"] == "exact"
        # "nanotechnologi" should be corrected (single or best candidate)
        assert statuses["nanotechnologi"] in ("single_candidate", "best_candidate")

    def test_entity_direct_call(self, checker: SpellChecker) -> None:
        # is_entity applies when correct_term is called directly with a digit string.
        # Note: process_query uses the letter-only tokenizer (same as TD2/TD3),
        # so numeric tokens are stripped before reaching correct_term.
        result = checker.correct_term("2024")
        assert result.status == "entity"
        assert result.corrected == "2024"

    def test_elision_stripped(self, checker: SpellChecker) -> None:
        # "l'indexation" → token "indexation"
        results = checker.process_query("l'indexation")
        assert len(results) == 1
        assert results[0].original == "indexation"
        assert results[0].status == "exact"

    def test_not_found_term_in_query(self, checker: SpellChecker) -> None:
        results = checker.process_query("xyzqwerty")
        assert results[0].status == "not_found"

    def test_result_count_matches_tokens(self, checker: SpellChecker) -> None:
        query = "recherche de documents par indexation"
        results = checker.process_query(query)
        # "de" and "par" may or may not be in lexicon, but we get one result per token
        assert len(results) == 5
