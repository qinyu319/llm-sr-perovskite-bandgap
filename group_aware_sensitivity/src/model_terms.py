from __future__ import annotations

from itertools import combinations


CORE_TERMS = ["Sn", "Br", "Cl", "Sn2", "Br2", "Cl2", "SnBr", "SnCl", "BrCl"]
A_SITE_EXTENSION_TERMS = ["Cs", "Cs2", "CsSn", "CsBr", "CsCl"]
ALL_TERMS = CORE_TERMS + A_SITE_EXTENSION_TERMS
FINAL_M4_TERMS = ["Sn", "Br", "Cl", "Cs", "Sn2", "Br2", "CsSn", "CsCl"]

STAGE_CANDIDATES = {
    "M0": ["Sn", "Br", "Cl"],
    "M1": ["Sn", "Br", "Cl", "Sn2", "Br2", "Cl2"],
    "M2": CORE_TERMS,
    "M3": CORE_TERMS + A_SITE_EXTENSION_TERMS,
}

TERM_REQUIREMENTS = {
    "Sn2": {"Sn"},
    "Br2": {"Br"},
    "Cl2": {"Cl"},
    "Cs2": {"Cs"},
    "SnBr": {"Sn", "Br"},
    "SnCl": {"Sn", "Cl"},
    "BrCl": {"Br", "Cl"},
    "CsSn": {"Cs", "Sn"},
    "CsBr": {"Cs", "Br"},
    "CsCl": {"Cs", "Cl"},
}


def is_hierarchical(terms: tuple[str, ...]) -> bool:
    term_set = set(terms)
    for term, required in TERM_REQUIREMENTS.items():
        if term in term_set and not required.issubset(term_set):
            return False
    return True


def candidate_family(terms: tuple[str, ...]) -> str:
    if set(terms).intersection(A_SITE_EXTENSION_TERMS):
        return "A_site_extension"
    return "core"


def generate_candidate_terms(max_terms: int = 10, enforce_hierarchy: bool = True) -> list[tuple[str, tuple[str, ...], str]]:
    seen: set[tuple[str, ...]] = set()
    candidates: list[tuple[str, tuple[str, ...], str]] = []

    for stage, terms in STAGE_CANDIDATES.items():
        ordered = tuple(t for t in ALL_TERMS if t in terms)
        seen.add(ordered)
        candidates.append((stage, ordered, candidate_family(ordered)))

    for k in range(1, max_terms + 1):
        for combo in combinations(ALL_TERMS, k):
            if enforce_hierarchy and not is_hierarchical(combo):
                continue
            if combo in seen:
                continue
            seen.add(combo)
            candidates.append(("M4_subset", combo, candidate_family(combo)))
    return candidates
