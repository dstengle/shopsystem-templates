"""bc-emit Check 3 (scenario-hash staleness) work-scoped to the dispatch's OWN
assigned set (scenario 225, @scenario_hash:aabbc009bad6fe86; work_id lead-s8j2).

PRE-STATE (the session-long over-refuse defect): `check_scenario_hashes`
recomputed EVERY `@scenario_hash` grep-able under `features/` and refused on
ANY divergence anywhere in the tree (a GLOBAL scan) — both via the per-block
stale scan and via the "missing" scan that refused whenever a features/-present
block's recompute was absent from the (narrow) payload. For a single-scenario
dispatch this refused on essentially every unrelated block, forcing every
reviewer onto the bare `--force` escape valve.

Scenario 225 scopes Check 3's staleness scan to the dispatch's OWN assigned set
— the scenario blocks under `features/` that CARRY one of the payload
`--scenario-hash` values — exactly mirroring scenario 212 (cba037e97c6a8325),
which scoped Check 1 (clean-tree) to deliverable paths. Two arms are pinned:

  (a) an otherwise-clean emit PASSES Check 3 even when an unrelated stale
      `@scenario_hash` tag exists elsewhere under `features/` (owned by a
      separate work item, never named by this dispatch). The unrelated block is
      NEITHER recomputed NOR allowed to refuse.

  (b) a stale tag WITHIN the dispatch's own assigned set STILL refuses: it
      raises PreconditionRefusal (the wrapper exits non-zero and does NOT invoke
      `shop-msg respond work_done`), names the scenario-hash staleness check as
      the cause, and names the in-scope work_id, the stale on-disk hash value,
      and the recomputed value.

Recompute is scenario-block-only canonicalization via the in-process
`scenarios.hash.compute_scenario_hash` delegate (ADR-036 D3 / scenario 179),
never the Feature-line-included wire form.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
import scenarios.hash as scenarios_hash

# Load the module under test FROM THIS WORKTREE's source by file path (not the
# ambient editable install, which may resolve to a sibling checkout).
_BC_EMIT_SRC = (
    Path(__file__).resolve().parent.parent
    / "src"
    / "shop_templates"
    / "bc_emit.py"
)
_spec = importlib.util.spec_from_file_location(
    "_bc_emit_workscope_under_test", _BC_EMIT_SRC
)
bc_emit = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bc_emit)  # type: ignore[union-attr]

_REAL_COMPUTE = scenarios_hash.compute_scenario_hash


def _hash_of_body(scenario_body: str) -> str:
    """The block-only canonical hash a CLEAN tag for this body must carry.

    The `@scenario_hash:` tag line is dropped by the canonicalization, so the
    hash is computed over the Scenario line + steps only.
    """
    return _REAL_COMPUTE(scenario_body)


def _write_feature(path: Path, tag_hash: str, scenario_body: str) -> None:
    path.write_text(
        "Feature: a test feature\n\n"
        f"  @scenario_hash:{tag_hash} @bc:shopsystem-templates\n"
        f"{scenario_body}\n"
    )


_OWN_BODY = (
    "  Scenario: the dispatch's own clean scenario\n"
    "    Given a precondition in the dispatch's own set\n"
    "    When the BC invokes the bc-emit work-done wrapper\n"
    "    Then the own block recompute equals its carried tag"
)

_UNRELATED_BODY = (
    "  Scenario: an unrelated scenario owned by a separate work item\n"
    "    Given a precondition that belongs to a different dispatch\n"
    "    When that other work is eventually dispatched\n"
    "    Then this block is reconciled by its own owner"
)


def test_clean_own_set_passes_despite_unrelated_stale_tag(tmp_path, monkeypatch):
    """Arm (a): an all-clean own assigned set PASSES Check 3 even when an
    unrelated stale @scenario_hash tag exists elsewhere under features/, and the
    unrelated (out-of-set) block is NEVER recomputed."""
    features = tmp_path / "features"
    features.mkdir()

    own_hash = _hash_of_body(_OWN_BODY)
    _write_feature(features / "own.feature", own_hash, _OWN_BODY)

    # The unrelated block carries a STALE tag (its recompute differs) and its
    # carried hash is NOT in this dispatch's payload set.
    stale_tag = "0000000000000000"
    _write_feature(features / "unrelated.feature", stale_tag, _UNRELATED_BODY)
    assert _hash_of_body(_UNRELATED_BODY) != stale_tag, "fixture must be stale"

    # Spy on the recompute delegate to prove the out-of-set block is not touched.
    seen: list[str] = []

    def _spy(text: str) -> str:
        seen.append(text)
        return _REAL_COMPUTE(text)

    monkeypatch.setattr(scenarios_hash, "compute_scenario_hash", _spy)

    # The dispatch's own assigned set is exactly [own_hash]. Must NOT raise.
    bc_emit.check_scenario_hashes(tmp_path, "lead-s8j2", [own_hash])

    joined = "\n".join(seen)
    assert "unrelated scenario owned by a separate work item" not in joined, (
        "Check 3 recomputed an OUT-OF-SET block; the staleness scan must "
        "evaluate ONLY the dispatch's own assigned set (carried hash in the "
        f"payload). Recompute calls touched:\n{joined}"
    )


def test_stale_tag_within_own_set_still_refuses(tmp_path):
    """Arm (b): a stale tag WITHIN the dispatch's own assigned set STILL refuses,
    naming the staleness check, the in-scope work_id, the stale on-disk value,
    and the recomputed value."""
    features = tmp_path / "features"
    features.mkdir()

    # The dispatch named hash X; the on-disk block carries X but its body has
    # drifted so its block-only recompute is some other value.
    intended_hash = _hash_of_body(_OWN_BODY)  # the value the dispatch named
    drifted_body = (
        "  Scenario: the dispatch's own scenario whose body drifted\n"
        "    Given a precondition that was edited after the tag was pinned\n"
        "    When the BC invokes the bc-emit work-done wrapper\n"
        "    Then the carried tag no longer matches the body"
    )
    recompute = _hash_of_body(drifted_body)
    assert recompute != intended_hash, "fixture must be stale"
    _write_feature(features / "own.feature", intended_hash, drifted_body)

    with pytest.raises(bc_emit.PreconditionRefusal) as exc:
        bc_emit.check_scenario_hashes(tmp_path, "lead-s8j2", [intended_hash])

    msg = str(exc.value)
    # Names the staleness check as the cause.
    assert "stalen" in msg.lower() or "STALE" in msg, msg
    # Names the in-scope work_id.
    assert "lead-s8j2" in msg, msg
    # Names the stale on-disk value AND the recomputed value.
    assert intended_hash in msg, msg
    assert recompute in msg, msg


def test_unrelated_stale_tag_alone_does_not_refuse(tmp_path):
    """A dispatch whose own assigned set is empty (no payload hash matches any
    block) does not refuse merely because an unrelated stale tag exists; the
    out-of-set stale tag is not in scope."""
    features = tmp_path / "features"
    features.mkdir()
    stale_tag = "1111111111111111"
    _write_feature(features / "unrelated.feature", stale_tag, _UNRELATED_BODY)
    assert _hash_of_body(_UNRELATED_BODY) != stale_tag

    # Empty payload — nothing in the dispatch's own set; must NOT raise on the
    # unrelated stale block.
    bc_emit.check_scenario_hashes(tmp_path, "lead-s8j2", [])


def test_payload_hash_with_no_carrying_block_is_orphan(tmp_path):
    """Orphan (179, preserved): a payload hash the dispatch named that no
    committed block carries refuses, classified ORPHAN."""
    features = tmp_path / "features"
    features.mkdir()
    own_hash = _hash_of_body(_OWN_BODY)
    _write_feature(features / "own.feature", own_hash, _OWN_BODY)

    absent = "abcabcabcabcabca"
    with pytest.raises(bc_emit.PreconditionRefusal) as exc:
        bc_emit.check_scenario_hashes(tmp_path, "lead-s8j2", [absent])
    msg = str(exc.value)
    assert "ORPHAN" in msg or "orphan" in msg, msg
    assert absent in msg, msg


def test_dispatched_block_present_but_untagged_is_missing(tmp_path):
    """Missing (179, preserved): a dispatched scenario block present under
    features/ whose body recomputes to a payload hash but which carries NO
    @scenario_hash tag refuses, classified MISSING."""
    features = tmp_path / "features"
    features.mkdir()
    body_hash = _hash_of_body(_OWN_BODY)
    # Write the block WITHOUT any @scenario_hash tag.
    (features / "untagged.feature").write_text(
        "Feature: a test feature\n\n"
        f"{_OWN_BODY}\n"
    )
    with pytest.raises(bc_emit.PreconditionRefusal) as exc:
        bc_emit.check_scenario_hashes(tmp_path, "lead-s8j2", [body_hash])
    msg = str(exc.value)
    assert "MISSING" in msg or "missing" in msg, msg
