"""bc-emit work-done — plan-decomposition closure + durability preconditions.

PRE-STATE (the defect; lead-8vny / origin lead-yyr9): the executable
`bc-emit work-done` wrapper (`src/shop_templates/bc_emit.py`) ran Check 1
(clean tree), Check 2 (reachability), and Check 3 (scenario-hash match), but
carried NO executable enforcement of the work-done-gate's bd-plan-decomposition
preconditions. Two specific invariants were unpinned:

  208 (0b48508e40fdde18) — the gate must enumerate EVERY sub-issue reachable
      under the work_id umbrella bead and refuse the emit if ANY remains OPEN,
      naming each offending OPEN sub-issue by bd id — INCLUDING an orphan from
      an abandoned earlier decomposition the implementer never created or
      closed. The prior "at least one RED exists and all sub-issues the
      implementer closed are closed" check alone must NOT pass.

  209 (7bcfc89161c0b2ee) — the gate must verify the work_id's sub-issue
      decomposition-and-closure STATE is reachable from the pushed tracker
      remote (the configured bd-dolt remote) and name the
      bd-decomposition-durability precondition SPECIFICALLY — not a generic
      dirty-working-tree cause. (.beads/issues.jsonl is a carved-out
      non-idempotent ambient artifact, so a clean working tree cannot by
      itself establish that the closures are durable.)

These tests drive the new wrapper functions directly, injecting the bd
enumeration and the dolt-push reachability probe as seams, so the RED->GREEN
transition is deterministic and does not require a live bd registry.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

# Load the module under test FROM THIS WORKTREE's source by file path (not the
# ambient editable install, which may resolve to a sibling checkout).
_BC_EMIT_SRC = Path(__file__).resolve().parent.parent / "src" / "shop_templates" / "bc_emit.py"
_spec = importlib.util.spec_from_file_location("_bc_emit_plan_under_test", _BC_EMIT_SRC)
bc_emit = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bc_emit)  # type: ignore[union-attr]


# --------------------------------------------------------------------------
# 208 (0b48508e40fdde18) — orphaned-OPEN sub-issue detection
# --------------------------------------------------------------------------

def test_orphaned_open_subissue_blocks_emit_and_names_each_open_id(tmp_path: Path) -> None:
    """An OPEN orphan from an abandoned earlier decomposition — which the
    implementer never created or closed — still blocks the emit, named by its
    bd id, even though a RED sub-issue exists and every sub-issue the
    implementer's real pass created is closed."""
    subissues = [
        {"id": "tmpl-x.1", "status": "closed",
         "title": "write the failing test (RED) for foo"},
        {"id": "tmpl-x.2", "status": "closed", "title": "implement (GREEN) foo"},
        # The orphan: OPEN, from an abandoned earlier decomposition.
        {"id": "tmpl-x.9", "status": "open",
         "title": "abandoned earlier decomposition stub"},
    ]
    with pytest.raises(bc_emit.PreconditionRefusal) as exc:
        bc_emit.check_plan_subissues_closed(
            tmp_path, "lead-x", "tmpl-x",
            children_provider=lambda repo, umbrella: subissues,
        )
    msg = str(exc.value)
    # Names the all-sub-issues-closed precondition and the offending OPEN id.
    assert "tmpl-x.9" in msg, msg
    assert "all-sub-issues" in msg or "sub-issue" in msg, msg


def test_every_open_subissue_is_named_not_just_the_first(tmp_path: Path) -> None:
    """The refusal enumerates EVERY still-OPEN sub-issue reachable under the
    umbrella, not merely the first one encountered."""
    subissues = [
        {"id": "tmpl-x.1", "status": "closed",
         "title": "write the failing test (RED) for foo"},
        {"id": "tmpl-x.7", "status": "open", "title": "orphan a"},
        {"id": "tmpl-x.8", "status": "in_progress", "title": "orphan b"},
    ]
    with pytest.raises(bc_emit.PreconditionRefusal) as exc:
        bc_emit.check_plan_subissues_closed(
            tmp_path, "lead-x", "tmpl-x",
            children_provider=lambda repo, umbrella: subissues,
        )
    msg = str(exc.value)
    assert "tmpl-x.7" in msg and "tmpl-x.8" in msg, msg


def test_all_subissues_closed_with_a_red_passes(tmp_path: Path) -> None:
    """When every sub-issue reachable under the umbrella is closed and at least
    one is a RED (failing-test) sub-issue, the check passes (no refusal)."""
    subissues = [
        {"id": "tmpl-x.1", "status": "closed",
         "title": "write the failing test (RED) for foo"},
        {"id": "tmpl-x.2", "status": "closed", "title": "implement (GREEN) foo"},
    ]
    # Must not raise.
    bc_emit.check_plan_subissues_closed(
        tmp_path, "lead-x", "tmpl-x",
        children_provider=lambda repo, umbrella: subissues,
    )


def test_no_subissues_at_all_blocks(tmp_path: Path) -> None:
    """An umbrella with no sub-issue decomposition at all blocks the emit."""
    with pytest.raises(bc_emit.PreconditionRefusal):
        bc_emit.check_plan_subissues_closed(
            tmp_path, "lead-x", "tmpl-x",
            children_provider=lambda repo, umbrella: [],
        )


def test_all_closed_but_no_red_blocks(tmp_path: Path) -> None:
    """The prior RED-presence invariant is preserved: all-closed but with no
    RED (failing-test) sub-issue still blocks."""
    subissues = [
        {"id": "tmpl-x.2", "status": "closed", "title": "implement foo"},
        {"id": "tmpl-x.3", "status": "closed", "title": "refactor foo"},
    ]
    with pytest.raises(bc_emit.PreconditionRefusal):
        bc_emit.check_plan_subissues_closed(
            tmp_path, "lead-x", "tmpl-x",
            children_provider=lambda repo, umbrella: subissues,
        )
