"""lead-ifye3.6 (empty-scenario request_bugfix): retire the 5 model_stylesheet
placeholder-mechanism scenarios and drop the `{{ inputs.X }}` shape from the
poured fabro `model_stylesheet`.

ROOT CAUSE: fabro >= v0.267.0-nightly.0 (the new bc-base image) makes `{{ }}`
inside a fabro `model_stylesheet` a HARD PARSE ERROR, so a nested container
launch on the new image dies at validation ("Model stylesheet parse error").
This BC's pour of `templates/fabro/workflow.fabro` still shipped the
abstract-placeholder shape (`.coding { model: {{ inputs.MODEL_CODING }} } ...`)
that lead-ifye3.1 landed. NOTE: the fabro binary in this worktree is 0.254.0
(older) and does NOT hard-error on `{{ }}`, so the >= v0.267 hard-parse-error
leg cannot run locally — this test asserts on the POUR SHAPE and the register
retirement state instead.

SCOPE (settled by the lead's clarify_response): retire ALL FIVE hashes now,
NO successor for any (the coverage gap from the ADR-051/ADR-049 invariant
scenarios is tracked separately by the lead as lead-008o8), and remove the
`{{ inputs.X }}` templating from the poured `model_stylesheet`. ADR-064 D1/D2:
each retired scenario's Given/When/Then body is DELETED from the live block so
the retired hash is UNREACHABLE by block-only recompute from every scenario
block under features/; provenance lives in a comment OUTSIDE any canonical
scenario region.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

from scenarios.hash import compute_scenario_hash

_ROOT = Path(__file__).resolve().parent.parent
_WORKFLOW_FABRO = (
    _ROOT / "src" / "shop_templates" / "templates" / "fabro" / "workflow.fabro"
)
_FEATURES = _ROOT / "features"

# The five @scenario_hash entries retired by lead-ifye3.6 (no successor).
_RETIRED = (
    "7653d06bddda72ed",  # fabro_model_stylesheet_placeholders.feature
    "8aab2c5c071e349f",  # fabro_model_stylesheet_placeholders.feature
    "610455d3a0f4e373",  # fabro_projection_validates.feature
    "0435d261be5031fd",  # fabro_projection_validates.feature
    "0bc0fb71534cc0d6",  # fabro_def_poured_projection.feature
)
# ADR-062 bounded-retry — unrelated, STAYS LIVE (same file as 0bc0fb71534cc0d6).
_KEPT = "2786d8415362757b"


def _block_only_reachable_hashes() -> set[str]:
    """Recompute the block-only (ADR-019 / scenario 117) hash of every scenario
    block under features/, using the SAME canonical producer the bc-emit
    retirement-removal gate uses (`bc_emit._scenario_blocks` + the
    shopsystem-scenarios `compute_scenario_hash`). The Feature: line is NOT part
    of the hashed text — block-only canonicalization."""
    spec = importlib.util.spec_from_file_location(
        "_bc_emit_ifye3_6", _ROOT / "src" / "shop_templates" / "bc_emit.py"
    )
    bc_emit = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bc_emit)  # type: ignore[union-attr]
    reachable: set[str] = set()
    for feature in sorted(_FEATURES.glob("*.feature")):
        for block_text, _carried in bc_emit._scenario_blocks(feature.read_text()):
            reachable.add(compute_scenario_hash(block_text))
    return reachable


def test_poured_model_stylesheet_carries_no_input_templating() -> None:
    """The poured fabro def's `model_stylesheet` no longer emits the
    `{{ inputs.X }}` templating shape that fabro >= v0.267 hard-parse-errors on.
    A bare/absent `model_stylesheet` (or any shape passing `fabro validate`)
    satisfies this — the fix is confined to that attribute."""
    text = _WORKFLOW_FABRO.read_text()
    stylesheet_lines = [ln for ln in text.splitlines() if "model_stylesheet=" in ln]
    for ln in stylesheet_lines:
        assert "{{ inputs." not in ln and "{{inputs." not in ln, (
            "the poured model_stylesheet still carries `{{ inputs.X }}` "
            "templating, which fabro >= v0.267 hard-parse-errors on: " + ln
        )


def test_five_retired_hashes_are_block_unreachable() -> None:
    """Each of the five retired scenarios' bodies is DELETED (ADR-064 D1/D2): no
    live scenario block under features/ block-only-recomputes to any retired
    hash. This is exactly the bc-emit retirement-removal gate's check."""
    reachable = _block_only_reachable_hashes()
    still_live = [h for h in _RETIRED if h in reachable]
    assert not still_live, (
        "these retired hashes are still block-only-reachable from a live "
        "scenario block under features/ (their body was not deleted): "
        + ", ".join(still_live)
    )


def test_kept_bounded_retry_hash_still_verifies() -> None:
    """The unrelated ADR-062 bounded-retry scenario 2786d8415362757b stays live
    and still block-only-verifies (the retirement did not disturb it)."""
    reachable = _block_only_reachable_hashes()
    assert _KEPT in reachable, (
        "the kept ADR-062 bounded-retry scenario 2786d8415362757b must remain "
        "block-only-reachable (live) after the retirement"
    )
