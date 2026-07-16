"""lead-ym67i (empty-scenario request_bugfix): retire @scenario_hash
e7668df366a93a60 — "a shop-templates pour emits the /workspace/.fabro/
fabro-engage projection … alongside /workspace/.claude/" — WITH NO SUCCESSOR
(ADR-064 D1/D2, clarify_response option b).

ROOT CAUSE: lead-npm2w's shop_type==bc call-site gate on the .fabro/ pour
(cli.py _cmd_bootstrap/_cmd_update) makes this scenario's originally-authored
Given/When — unconditional, no shop_type qualifier ("Given the
shopsystem-templates BC is installed / When a shop-templates pour is run in a
workspace") — genuinely wrong as pinned: a lead-type pour no longer emits
.fabro/, so the unscoped "every pour emits /workspace/.fabro/" Then no longer
holds for ALL pour contexts. The BC-scoped successor is authored lead-side and
tracked separately as lead-7mboj (NOT minted here).

SCOPE (clarify_response option b): retire e7668df366a93a60 now, NO successor
(the coverage gap — this was the only live pinned scenario asserting a pour
EMITS /workspace/.fabro/ — is accepted and tracked by the lead as lead-7mboj,
guarded meanwhile by lead-npm2w's code-level regression test). ADR-064 D1/D2:
the retired scenario's Given/When/Then body is DELETED from the live block so
the retired hash is UNREACHABLE by block-only recompute from every scenario
block under features/; provenance lives in a comment OUTSIDE any canonical
scenario region. 941d1df69c9b62dd (double-pour DETERMINISM,
fabro_projection_determinism.feature) is UNAFFECTED and stays live.

NOTE ON LAYOUT: e7668df366a93a60 lives in this BC's FLAT features/ tree at
features/fabro_projection_pour.feature (created by lead-7a8v / commit bd2b383),
not the aggregated-corpus nested path features/shopsystem-templates/… the lead
dispatch cited. The retirement is executed where the hash actually is.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

from scenarios.hash import compute_scenario_hash

_ROOT = Path(__file__).resolve().parent.parent
_FEATURES = _ROOT / "features"

# The @scenario_hash retired by lead-ym67i (no successor).
_RETIRED = "e7668df366a93a60"
# Double-pour determinism — unrelated, STAYS LIVE (a different file).
_KEPT = "941d1df69c9b62dd"


def _block_only_reachable_hashes() -> set[str]:
    """Recompute the block-only (ADR-019 / scenario 117) hash of every scenario
    block under features/, using the SAME canonical producer the bc-emit
    retirement-removal gate uses (`bc_emit._scenario_blocks` + the
    shopsystem-scenarios `compute_scenario_hash`). The Feature: line is NOT part
    of the hashed text — block-only canonicalization."""
    spec = importlib.util.spec_from_file_location(
        "_bc_emit_ym67i", _ROOT / "src" / "shop_templates" / "bc_emit.py"
    )
    bc_emit = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bc_emit)  # type: ignore[union-attr]
    reachable: set[str] = set()
    for feature in sorted(_FEATURES.glob("*.feature")):
        for block_text, _carried in bc_emit._scenario_blocks(feature.read_text()):
            reachable.add(compute_scenario_hash(block_text))
    return reachable


def test_retired_pour_emission_hash_is_block_unreachable() -> None:
    """The retired scenario's body is DELETED (ADR-064 D1/D2): no live scenario
    block under features/ block-only-recomputes to e7668df366a93a60. This is
    exactly the bc-emit retirement-removal gate's check."""
    reachable = _block_only_reachable_hashes()
    assert _RETIRED not in reachable, (
        "e7668df366a93a60 is still block-only-reachable from a live scenario "
        "block under features/ (its body was not deleted) — the retirement is "
        "incomplete and the bc-emit retirement-removal gate would REFUSE the emit"
    )


def test_kept_determinism_hash_still_verifies() -> None:
    """The unrelated double-pour determinism scenario 941d1df69c9b62dd stays
    live and still block-only-verifies (the retirement did not disturb it)."""
    reachable = _block_only_reachable_hashes()
    assert _KEPT in reachable, (
        "the double-pour determinism scenario 941d1df69c9b62dd must remain "
        "block-only-reachable (live) after the retirement"
    )
