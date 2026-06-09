from __future__ import annotations

from src.model_terms import A_SITE_EXTENSION_TERMS, CORE_TERMS, FINAL_M4_TERMS, is_hierarchical


def test_feature_dictionary_matches_protocol() -> None:
    assert CORE_TERMS == ["Sn", "Br", "Cl", "Sn2", "Br2", "Cl2", "SnBr", "SnCl", "BrCl"]
    assert A_SITE_EXTENSION_TERMS == ["Cs", "Cs2", "CsSn", "CsBr", "CsCl"]
    assert set(FINAL_M4_TERMS) == {"Sn", "Br", "Cl", "Cs", "Sn2", "Br2", "CsSn", "CsCl"}


def test_hierarchy_rule() -> None:
    assert is_hierarchical(("Sn", "Sn2"))
    assert not is_hierarchical(("Sn2",))
    assert is_hierarchical(("Cs", "Sn", "CsSn"))
    assert not is_hierarchical(("Sn", "CsSn"))
