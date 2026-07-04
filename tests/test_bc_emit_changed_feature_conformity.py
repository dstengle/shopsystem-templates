"""ADR-042 bc-emit work-done schema-conformity gate (work_id lead-vzxd.10,
tmpl-4xc).

The bc-emit work-done gate gains an additional arm: over the BC's CHANGED /
ADDED feature files (the files this work_id's commit added or modified under
`features/`), run `scenarios validate` (per-file schema conformity, v0.3.1)
and REFUSE a `work_done(complete)` emit if any added/modified scenario is
GENUINELY non-conformant — so no non-conformant scenario merges going forward.

CRITICAL GUARD (load-bearing): v0.3.1 `scenarios validate` has a known
comment-folding defect — its block extractor folds an inter-scenario comment
into the PRECEDING scenario's block, diverging from the producer/wire hash
(`scenarios hash` / compute_scenario_hash) and yielding a FALSE
E_HASH_MISMATCH on comment-adjacent scenarios whose on-disk @scenario_hash
already EQUALS the producer. This gate must:

  * REFUSE on genuine non-conformance — E_UNKNOWN_BC, E_UNKNOWN_ORIGIN,
    E_MISSING_HASH, E_STRAY_GHERKIN, W_BC_UNASSIGNED, W_ORIGIN_UNRESOLVED, and
    REAL hash mismatches (the on-disk tag does NOT reproduce the producer for
    the block); but
  * NOT refuse solely on a validate E_HASH_MISMATCH when the on-disk
    @scenario_hash already reproduces the producer/wire hash for that block —
    that is the validator defect, not a real mismatch.

These tests drive `check_changed_features_conformant` over crafted
changed-file sets against a real v0.3.1 `scenarios validate` (fixture manifest
+ origin-index), asserting refusal on each genuine class and NON-refusal on
the comment-folding false-positive.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from shop_templates.bc_emit import (
    PreconditionRefusal,
    check_changed_features_conformant,
)
from scenarios.outstanding import parse_then_block_only_hash


_MANIFEST = "bcs:\n  - name: shopsystem-templates\nservices: []\n"
_ORIGIN_INDEX = "adr-056\n"

_S1 = (
    "  Scenario: first behavior\n"
    "    Given a thing\n"
    "    When I act\n"
    "    Then it works"
)
_S2 = (
    "  Scenario: second behavior\n"
    "    Given another thing\n"
    "    When I act again\n"
    "    Then it also works"
)


def _fixture_corpus(tmp_path: Path) -> tuple[Path, Path]:
    """Return (features_dir, ...) with a legal manifest + origin-index written."""
    features = tmp_path / "features"
    features.mkdir(parents=True, exist_ok=True)
    (tmp_path / "bc-manifest.yaml").write_text(_MANIFEST)
    (tmp_path / "origin-index.txt").write_text(_ORIGIN_INDEX)
    return features, tmp_path


def _call(tmp_path: Path, changed: list[Path]) -> None:
    _, root = tmp_path, tmp_path
    check_changed_features_conformant(
        root,
        "lead-vzxd.10",
        changed_files=changed,
        manifest_path=str(root / "bc-manifest.yaml"),
        origin_index=str(root / "origin-index.txt"),
    )


def _write_feature(features: Path, name: str, body: str) -> Path:
    p = features / name
    p.write_text(body)
    return p


# --- conformant: no refusal ------------------------------------------------


def test_conformant_changed_feature_does_not_refuse(tmp_path):
    features, _ = _fixture_corpus(tmp_path)
    h1 = parse_then_block_only_hash(_S1)
    h2 = parse_then_block_only_hash(_S2)
    f = _write_feature(
        features,
        "clean.feature",
        "@bc:shopsystem-templates @origin:adr-056\n"
        "Feature: clean\n\n"
        f"  @scenario_hash:{h1}\n{_S1}\n\n"
        f"  @scenario_hash:{h2}\n{_S2}\n",
    )
    _call(tmp_path, [f])  # must NOT raise


# --- genuine non-conformance: refuse ---------------------------------------


def test_refuses_on_unknown_bc(tmp_path):
    features, _ = _fixture_corpus(tmp_path)
    h1 = parse_then_block_only_hash(_S1)
    f = _write_feature(
        features,
        "unknownbc.feature",
        "@bc:not-a-real-bc @origin:adr-056\n"
        "Feature: bad bc\n\n"
        f"  @scenario_hash:{h1}\n{_S1}\n",
    )
    with pytest.raises(PreconditionRefusal) as exc:
        _call(tmp_path, [f])
    assert "E_UNKNOWN_BC" in str(exc.value)


def test_refuses_on_unknown_origin(tmp_path):
    features, _ = _fixture_corpus(tmp_path)
    h1 = parse_then_block_only_hash(_S1)
    f = _write_feature(
        features,
        "unknownorigin.feature",
        "@bc:shopsystem-templates @origin:adr-999\n"
        "Feature: bad origin\n\n"
        f"  @scenario_hash:{h1}\n{_S1}\n",
    )
    with pytest.raises(PreconditionRefusal) as exc:
        _call(tmp_path, [f])
    assert "E_UNKNOWN_ORIGIN" in str(exc.value)


def test_refuses_on_missing_hash(tmp_path):
    features, _ = _fixture_corpus(tmp_path)
    f = _write_feature(
        features,
        "missinghash.feature",
        "@bc:shopsystem-templates @origin:adr-056\n"
        "Feature: no hash\n\n"
        f"{_S1}\n",
    )
    with pytest.raises(PreconditionRefusal) as exc:
        _call(tmp_path, [f])
    assert "E_MISSING_HASH" in str(exc.value)


def test_refuses_on_stray_gherkin(tmp_path):
    features, _ = _fixture_corpus(tmp_path)
    stray = _write_feature(features, "legacy.gherkin", "Feature: legacy\n")
    with pytest.raises(PreconditionRefusal) as exc:
        _call(tmp_path, [stray])
    assert "E_STRAY_GHERKIN" in str(exc.value)


def test_refuses_on_unassigned_bc_marker(tmp_path):
    features, _ = _fixture_corpus(tmp_path)
    h1 = parse_then_block_only_hash(_S1)
    f = _write_feature(
        features,
        "pending.feature",
        "@bc:unassigned @origin:adr-056\n"
        "Feature: pending\n\n"
        f"  @scenario_hash:{h1}\n{_S1}\n",
    )
    with pytest.raises(PreconditionRefusal) as exc:
        _call(tmp_path, [f])
    assert "W_BC_UNASSIGNED" in str(exc.value)


def test_refuses_on_real_hash_mismatch(tmp_path):
    """A scenario whose body drifted under a pinned tag (NO inter-scenario
    comment) is a REAL stale mismatch: the on-disk tag does not reproduce the
    producer for the block. Refuse."""
    features, _ = _fixture_corpus(tmp_path)
    stale_tag = parse_then_block_only_hash(_S1)  # pinned to S1's body...
    drifted = _S1.replace("When I act", "When I act very differently")  # ...but body drifted
    f = _write_feature(
        features,
        "stale.feature",
        "@bc:shopsystem-templates @origin:adr-056\n"
        "Feature: stale\n\n"
        f"  @scenario_hash:{stale_tag}\n{drifted}\n",
    )
    with pytest.raises(PreconditionRefusal) as exc:
        _call(tmp_path, [f])
    assert "E_HASH_MISMATCH" in str(exc.value) or "hash" in str(exc.value).lower()


# --- the comment-folding false-positive: MUST NOT refuse -------------------


def test_does_not_refuse_on_comment_folding_false_positive(tmp_path):
    """A comment-adjacent scenario whose on-disk @scenario_hash EQUALS the
    producer/wire hash. Real v0.3.1 `scenarios validate` raises a FALSE
    E_HASH_MISMATCH here (it folds the inter-scenario comment into the
    preceding block). The gate must cross-check against the producer and NOT
    refuse, since the on-disk tag is genuinely correct."""
    features, _ = _fixture_corpus(tmp_path)
    h1 = parse_then_block_only_hash(_S1)
    h2 = parse_then_block_only_hash(_S2)
    f = _write_feature(
        features,
        "folded.feature",
        "@bc:shopsystem-templates @origin:adr-056\n"
        "Feature: folded\n\n"
        f"  @scenario_hash:{h1}\n{_S1}\n\n"
        "  # an inter-scenario comment folded into the preceding block by v0.3.1\n"
        f"  @scenario_hash:{h2}\n{_S2}\n",
    )
    # Precondition: assert real v0.3.1 validate DOES raise a false E_HASH_MISMATCH
    # here (so the guard is genuinely exercised, not vacuously passing).
    import subprocess

    proc = subprocess.run(
        [
            "scenarios",
            "validate",
            "--json",
            "--manifest",
            str(tmp_path / "bc-manifest.yaml"),
            "--origin-index",
            str(tmp_path / "origin-index.txt"),
            str(f),
        ],
        capture_output=True,
        text=True,
    )
    assert "E_HASH_MISMATCH" in proc.stdout, (
        "fixture must reproduce the v0.3.1 comment-folding false E_HASH_MISMATCH; "
        f"validate stdout was: {proc.stdout!r}"
    )
    # The gate must NOT refuse on this validator false-positive.
    _call(tmp_path, [f])  # must NOT raise


# --- scoping: nothing changed under features/ ------------------------------


def test_no_changed_features_does_not_refuse(tmp_path):
    _fixture_corpus(tmp_path)
    _call(tmp_path, [])  # empty changed set → nothing to validate → no raise
