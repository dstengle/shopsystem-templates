"""bc-emit Check 3 (scenario-hash staleness) SOURCE-FRESHNESS — evaluated
against the FETCHED origin/main tree, not the stale local checkout
(scenario 227, @scenario_hash:613ddd886f6dc431; work_id lead-9mog).

PRE-STATE (the false-refuse defect addressed by lead-b2iz's mechanism
observation): `check_scenario_hashes` recomputed every in-scope
`@scenario_hash` tag against the BC primary checkout LOCAL working tree
(`fpath.read_text()`). When local main lags `origin/main`, a scenario block
that has been reconciled on `origin/main` still appears with the OLD body/tag
LOCALLY; the local recompute mismatches; and the wrapper false-refuses —
naming the scenario-hash recompute-mismatch and misdirecting the BC toward
`--force` or hand-editing an already-correct scenario.

Scenario 227 (PRIMARY arm, the one implemented here): Check 3 performs a
`git fetch origin` and evaluates the staleness recompute against the FETCHED
`origin/main` tree (mirroring the Check 2 reachability posture, scenario 177).
A scenario block consistent on `origin/main` but stale only in the lagging
local checkout therefore does NOT false-refuse.

INVARIANT (must hold regardless of arm): a scenario block in the dispatch's
OWN assigned set that is genuinely STALE ON `origin/main` (its on-disk tag does
not reproduce against its as-committed body on `origin/main` HEAD) STILL exits
non-zero, does NOT invoke `shop-msg respond work_done`, and names the
scenario-hash staleness check as the cause — not masked by the local handling.

DISTINCT from scenario 225 (aabbc009bad6fe86): 225 fixed WHICH scenarios
Check 3 evaluates (the dispatch's own assigned set); 227 fixes WHICH TREE it
reads (fetched origin/main, not the local checkout). Recompute remains
scenario-block-only via the in-process `scenarios.hash.compute_scenario_hash`
delegate (ADR-036 D3 / scenario 179), never the Feature-line-included wire
form.
"""
from __future__ import annotations

import importlib.util
import subprocess
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
    "_bc_emit_source_freshness_under_test", _BC_EMIT_SRC
)
bc_emit = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bc_emit)  # type: ignore[union-attr]

_COMPUTE = scenarios_hash.compute_scenario_hash
_RECORDER = Path(__file__).resolve().parent / "_respond_recorder.py"

import sys as _sys

WORK_ID = "lead-9mog"

# A reconciled body. Its block-only hash T is the @scenario_hash tag that is
# pinned (and consistent) on origin/main.
_RECONCILED_BODY = (
    "  Scenario: the dispatch's own scenario reconciled on origin/main\n"
    "    Given a precondition reconciled on origin/main\n"
    "    When the BC invokes the bc-emit work-done wrapper for that work_id\n"
    "    Then the origin/main body recompute equals its carried tag"
)

# An OLD stale body the lagging local checkout still carries under the SAME
# pinned tag T. Its block-only hash differs from T, so a LOCAL-tree recompute
# would (wrongly) classify the in-scope block STALE.
_STALE_LOCAL_BODY = (
    "  Scenario: the dispatch's own scenario reconciled on origin/main\n"
    "    Given a precondition NOT YET reconciled in the lagging local checkout\n"
    "    When the BC invokes the bc-emit work-done wrapper for that work_id\n"
    "    Then the lagging-local body does not match the pinned tag"
)

T = _COMPUTE(_RECONCILED_BODY)


def _feature_text(tag: str, body: str) -> str:
    return (
        "Feature: bc-emit source-freshness fixture\n\n"
        f"  @scenario_hash:{tag} @bc:shopsystem-templates\n"
        f"{body}\n"
    )


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=str(repo), capture_output=True, text=True, check=True
    )


def _build_repo(
    tmp_path: Path,
    *,
    origin_tag: str,
    origin_body: str,
    local_tag: str,
    local_body: str,
) -> Path:
    """Build a hermetic repo (local filesystem bare remote — no network) where:

    - commit A (the LOCAL HEAD) carries features/x.feature = (local_tag, local_body)
    - commit B (origin/main HEAD), a child of A, carries (origin_tag, origin_body)
      and a message that carries the work_id as a whole token
    - the work repo's local main is reset back to A, so its HEAD is an ANCESTOR
      of origin/main HEAD and its working tree carries the local version.
    """
    origin = tmp_path / "origin.git"
    origin.mkdir()
    subprocess.run(["git", "init", "--bare", "-q"], cwd=str(origin), check=True)

    work = tmp_path / "work"
    work.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=str(work), check=True)
    _git(work, "config", "user.email", "bc@example.test")
    _git(work, "config", "user.name", "bc tester")
    _git(work, "remote", "add", "origin", str(origin))

    features = work / "features"
    features.mkdir()
    (features / "x.feature").write_text(_feature_text(local_tag, local_body))
    _git(work, "add", "-A")
    _git(work, "commit", "-q", "-m", "seed A (local, lagging)")
    commit_a = _git(work, "rev-parse", "HEAD").stdout.strip()

    # Advance to the origin/main version (commit B) and push it.
    (features / "x.feature").write_text(_feature_text(origin_tag, origin_body))
    _git(work, "add", "-A")
    _git(work, "commit", "-q", "-m", f"reconcile B on origin/main (work_id {WORK_ID})")
    _git(work, "push", "-q", "origin", "main")

    # Local main falls behind: reset back to A. Working tree now carries the
    # lagging-local feature version; HEAD (A) is an ancestor of origin/main (B).
    _git(work, "reset", "--hard", "-q", commit_a)
    return work


def _work_done_args(repo: Path, sentinel: Path, *, scenario_hash: str):
    parser = bc_emit.build_parser()
    return parser.parse_args(
        [
            "work-done",
            "--work-id",
            WORK_ID,
            "--bc",
            "shopsystem-templates",
            "--summary",
            "source-freshness e2e",
            "--scenario-hash",
            scenario_hash,
            "--repo",
            str(repo),
            "--respond-cmd",
            _sys.executable,
            "--respond-cmd",
            str(_RECORDER),
            "--respond-cmd",
            str(sentinel),
        ]
    )


# ---------------------------------------------------------------------------
# PRIMARY ARM — Check 3 reads the fetched origin/main tree, so a lagging local
# checkout does NOT false-refuse on a scenario consistent on origin/main.
# ---------------------------------------------------------------------------


def test_fetch_origin_main_feature_texts_reads_origin_not_local(tmp_path):
    """`fetch_origin_main_feature_texts` fetches origin and returns the
    origin/main body (B), NOT the lagging local working-tree body (A)."""
    repo = _build_repo(
        tmp_path,
        origin_tag=T,
        origin_body=_RECONCILED_BODY,
        local_tag=T,
        local_body=_STALE_LOCAL_BODY,
    )
    texts = bc_emit.fetch_origin_main_feature_texts(repo)
    assert "x.feature" in texts
    # The origin/main (reconciled) body is what we got — not the stale local one.
    assert "reconciled on origin/main" in texts["x.feature"]
    assert "NOT YET reconciled in the lagging local checkout" not in texts["x.feature"]
    # Sanity: the local working tree really does carry the stale version.
    local = (repo / "features" / "x.feature").read_text()
    assert "NOT YET reconciled in the lagging local checkout" in local


def test_local_tree_read_would_false_refuse(tmp_path):
    """Regression witness: evaluating Check 3 against the LOCAL tree (the old
    behavior, the default feature_texts=None path reads local) DOES refuse the
    consistent-on-origin/main scenario — proving the bug this scenario fixes."""
    repo = _build_repo(
        tmp_path,
        origin_tag=T,
        origin_body=_RECONCILED_BODY,
        local_tag=T,
        local_body=_STALE_LOCAL_BODY,
    )
    # Reading the local tree (feature_texts omitted) false-refuses STALE.
    with pytest.raises(bc_emit.PreconditionRefusal) as exc:
        bc_emit.check_scenario_hashes(repo, WORK_ID, [T])
    assert "STALE" in str(exc.value) or "stale" in str(exc.value).lower()


def test_wrapper_does_not_false_refuse_on_lagging_local_checkout(tmp_path):
    """PRIMARY arm end-to-end: the `bc-emit work-done` wrapper performs a
    `git fetch origin`, evaluates Check 3 against the fetched origin/main tree,
    and does NOT refuse on a block consistent on origin/main but stale only in
    the lagging local checkout — it proceeds to invoke shop-msg respond."""
    repo = _build_repo(
        tmp_path,
        origin_tag=T,
        origin_body=_RECONCILED_BODY,
        local_tag=T,
        local_body=_STALE_LOCAL_BODY,
    )
    sentinel = tmp_path / "respond_invoked"
    args = _work_done_args(repo, sentinel, scenario_hash=T)
    rc = bc_emit._cmd_work_done(args)

    assert rc == 0, "wrapper false-refused a lagging-but-consistent emit"
    assert sentinel.exists(), (
        "the wrapper did NOT invoke shop-msg respond work_done — it refused "
        "even though the scenario is consistent on origin/main"
    )
    recorded = sentinel.read_text()
    assert "respond" in recorded and "work_done" in recorded
    assert T in recorded


# ---------------------------------------------------------------------------
# INVARIANT — a scenario genuinely STALE on origin/main in the own set STILL
# refuses, naming the scenario-hash staleness check (not masked by local handling).
# ---------------------------------------------------------------------------


def test_genuinely_stale_on_origin_main_still_refuses_at_check(tmp_path):
    """A block in the dispatch's own set that is genuinely stale on origin/main
    (origin/main body does not reproduce its on-disk tag) STILL raises
    PreconditionRefusal, naming the staleness check, the work_id, the stale
    on-disk value, and the block-only recomputed value."""
    # origin/main carries the STALE body under tag T (hash(stale) != T).
    repo = _build_repo(
        tmp_path,
        origin_tag=T,
        origin_body=_STALE_LOCAL_BODY,
        local_tag=T,
        local_body=_RECONCILED_BODY,
    )
    origin_texts = bc_emit.fetch_origin_main_feature_texts(repo)
    with pytest.raises(bc_emit.PreconditionRefusal) as exc:
        bc_emit.check_scenario_hashes(
            repo, WORK_ID, [T], feature_texts=origin_texts
        )
    msg = str(exc.value)
    assert "Check 3" in msg and ("STALE" in msg or "stalen" in msg.lower())
    assert WORK_ID in msg
    assert T in msg  # stale on-disk value
    # The block-only recompute of the origin/main stale body is named.
    assert _COMPUTE(_STALE_LOCAL_BODY) in msg
    # Block-only delegate, not the Feature-line-included wire form.
    assert _COMPUTE(_STALE_LOCAL_BODY) != T


def test_genuinely_stale_on_origin_main_wrapper_refuses_and_no_respond(tmp_path):
    """INVARIANT end-to-end: when origin/main itself carries a genuinely stale
    in-scope block, the wrapper exits non-zero, does NOT invoke shop-msg
    respond work_done, and names the scenario-hash staleness check."""
    repo = _build_repo(
        tmp_path,
        origin_tag=T,
        origin_body=_STALE_LOCAL_BODY,
        local_tag=T,
        local_body=_RECONCILED_BODY,
    )
    sentinel = tmp_path / "respond_invoked"
    args = _work_done_args(repo, sentinel, scenario_hash=T)

    import io
    import contextlib

    err = io.StringIO()
    with contextlib.redirect_stderr(err):
        rc = bc_emit._cmd_work_done(args)

    assert rc == 1
    assert not sentinel.exists(), "respond was invoked on a genuine staleness refusal"
    captured = err.getvalue()
    assert "Check 3" in captured and (
        "STALE" in captured or "stalen" in captured.lower()
    )
