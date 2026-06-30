"""bc-emit — executable pre-emit wrapper over the work-done gate.

`bc-emit work-done` is the EXECUTABLE form of the work-done-gate skill
(currently prose at templates/skills/work-done-gate/SKILL.md). It runs the
BC-side preconditions and, only when they all pass, invokes the real
`shop-msg respond work_done` primitive. On any precondition refusal it exits
non-zero, prints a named-cause error that directs the BC to SELF-RESOLVE its
own bead/commit/working-tree state and re-invoke the wrapper, and does NOT
invoke `shop-msg respond`.

Preconditions (lead-m56e):

  Check 1 — clean working tree, DELIVERABLE-SCOPED (hash cba037e97c6a8325)
      `git status --porcelain` is evaluated against the work-done-gate Check 1
      DELIVERABLE-SCOPE model: the emit is refused ONLY when a path under a
      deliverable directory (`features/`, `src/`, `tests/`) is dirty. A tree
      whose only modified, staged, or untracked paths are non-deliverable
      harness/config paths — e.g. `.claude/canonical/bc-primer.md`,
      `.claude/settings.json`, or the ambient carve-outs `.specstory`,
      `.claude/scheduled_tasks.lock`, `.beads/issues.jsonl` — is treated as
      clean and proceeds to the remaining preconditions. The ambient
      carve-out set is just a subset of non-deliverable scope; this replaces
      the earlier narrow carve-out allowlist (which false-refused clean
      deliverable emits on harness churn). On refusal the error names the
      clean-working-tree precondition and lists each offending DELIVERABLE
      path verbatim as `git status --porcelain` reported it.

  Check 2 — reachability (hashes 461d6066ef7dca0a, 12c98d2f7e5259a9)
      Two deliverable modes:
        commit  — a commit attributable to the work_id (the work_id as a
                  WHOLE TOKEN — word-boundary match — in a commit
                  subject/body, NOT a loose substring) must be reachable from
                  `origin/main` HEAD after a `git fetch origin`. A commit on
                  a local/unmerged branch does NOT satisfy. On refusal the
                  error names the work_id and the current origin/main HEAD
                  short SHA.
        tag     — the named release tag must exist after
                  `git fetch origin --tags` AND its commit lineage must
                  carry/anchor the work_id (the same canonical word-boundary
                  attribution check_commit_reachable uses, scoped to the
                  tag's history). Satisfaction comes from the tag's lineage
                  anchoring the work_id, NOT from work_id reachability on
                  origin/main HEAD — so a tag whose lineage carries the
                  work_id satisfies the check even though origin/main HEAD has
                  advanced past the tagged commit (the release case). A tag
                  that merely exists with a non-empty `git rev-list` but whose
                  lineage carries no work_id-attributed commit (e.g. a tag on
                  the repo's unrelated seed commit) does NOT satisfy: it
                  refuses, naming the tag-lineage-anchors-work_id precondition,
                  the offending tag, and the work_id.

  Check 3 — scenario-hash staleness, WORK-SCOPED (hashes ea9c1bbd9be87d72,
            aabbc009bad6fe86)
      The staleness scan is SCOPED to the dispatch's OWN assigned set — the
      scenario blocks under features/ that CARRY one of the payload
      `--scenario-hash` values. A block whose carried `@scenario_hash` is NOT
      one this dispatch named is owned by a SEPARATE work item: it is NEITHER
      recomputed NOR allowed to refuse the emit (scenario 225, aabbc009bad6fe86,
      mirroring scenario 212's deliverable-scope of Check 1). This REPLACES the
      earlier GLOBAL scan, which recomputed every `@scenario_hash` under
      features/ and refused on ANY divergence anywhere — the over-refuse that
      forced reviewers onto `--force`. For each in-scope block, recompute the
      candidate hash by delegating IN-PROCESS to
      `scenarios.hash.compute_scenario_hash` using scenario-BLOCK-ONLY
      canonicalization (the enclosing `Feature:` header line is NOT part of the
      hashed text). Classify any divergent member — FOR IN-SCOPE SCENARIOS ONLY
      (scenario 179, ea9c1bbd9be87d72, preserved) — as stale (in-scope carried
      hash whose recompute differs), missing (a dispatched scenario block whose
      recompute is named but which carries no @scenario_hash tag), or orphan (a
      payload hash matching no committed features/ block). On divergence the
      error names the scenario-hash staleness check (Check 3) as the cause, the
      in-scope work_id, the classification, the affected hash value, and the
      scenario; a stale refusal names the in-scope work_id, the stale on-disk
      value, and the recomputed value. The recompute uses ONLY the block-only
      delegate, never the Feature-line-included canonicalization carried on the
      wire.

Self-resolve messaging (hash 4a6133f7b5f061a2): every refusal's named-cause
error directs the BC to fix its OWN state and re-invoke `bc-emit work-done`;
it never instructs/requests/implies that the lead, the router, or any
non-BC actor commit/push/reconcile the BC's repo state.

--force independence (hash f81ee56bc163934b): the bare messaging primitive
`shop-msg respond work_done --force` is an INDEPENDENT path that bypasses
this wrapper entirely. It lives in the `shop-msg` package (outside this BC
root); this wrapper neither implements nor gates it. Landing this wrapper
and retiring the prose preconditions does not remove `--force`.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

# NOTE: `scenarios.hash.compute_scenario_hash` is imported LAZILY inside
# `check_scenario_hashes` (the work-done hash-check path), NOT at module top
# level. This keeps `bc-emit --help` and every non-work-done path importable
# and runnable even when the `scenarios` package is absent (e.g. before its
# VCS dependency resolves on a fresh install). The work-done hash check is the
# only path that needs scenarios, and it imports it on demand. (lead-ld7i /
# tmpl-20n: a module-top-level import here made the console-script
# dead-on-arrival in launched BCs.)

# DELIVERABLE directories: the clean-working-tree precondition is scoped to
# these. Only a dirty path UNDER one of these blocks the emit; everything else
# (harness/config such as `.claude/...`, repository-root config files, and the
# ambient carve-outs below) is non-deliverable and does NOT block. This matches
# the work-done-gate Check 1 DELIVERABLE-SCOPE model and replaces the earlier
# narrow carve-out ALLOWLIST, which false-refused clean deliverable emits on
# `.claude` harness churn (router session-start bc-primer.md / settings.json
# rewrites — another role's in-flight work, neither safe to commit under this
# work_id nor revert). Matched against the porcelain PATH (the bytes after the
# 2-char status + space, with any rename "old -> new" reduced to the new path).
_DELIVERABLE_DIRS = (
    "features",
    "src",
    "tests",
)

# The ambient carve-outs are now simply a NAMED SUBSET of non-deliverable
# scope: none lives under a deliverable directory, so the deliverable-scope
# check already treats them as clean. Retained as documentation of the
# non-idempotent ambient artifacts the durability precondition reasons about
# (e.g. `.beads/issues.jsonl`).
_CARVE_OUTS = (
    ".specstory",
    ".claude/scheduled_tasks.lock",
    ".beads/issues.jsonl",
)

# A standard self-resolution directive appended to every refusal. It speaks
# only to the BC about the BC's own state — never to the lead/router.
_SELF_RESOLVE = (
    "To resolve: the BC must self-resolve its OWN bead, commit, and "
    "working-tree state — commit its own changes or correct its own scenario "
    "hashes itself — and then re-invoke `bc-emit work-done`. Do NOT ask the "
    "lead, the router, or any other actor to commit, push, or reconcile this "
    "BC's repository state; that is the BC's own responsibility."
)


class PreconditionRefusal(Exception):
    """Raised when a pre-emit precondition refuses the emit.

    The message is the full named-cause error (precondition name + offending
    evidence + the self-resolve directive). Carrying it as an exception keeps
    the "do NOT invoke shop-msg respond on refusal" guarantee structural: the
    respond invocation only happens on the no-exception path.
    """


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args],
        cwd=str(repo),
        capture_output=True,
        text=True,
    )


def _work_id_attribution_grep(work_id: str) -> list[str]:
    """The CANONICAL `git log` attribution arguments for a work_id.

    Both attribution sites (`check_commit_reachable` over origin/main and
    `check_tag_reachable` over a tag's lineage) recognize a commit as
    attributable to the work_id by the SAME mechanism, so they stay
    consistent — the bc-emit wrapper and the shared work-done-gate attribution
    helper share this canonical form.

    The match is EXACT / WORD-BOUNDARY (whole-token), NOT loose substring
    (lead-8vwf): the work_id must appear as a WHOLE TOKEN — bounded by
    start/end-of-line or non-identifier characters — in the commit subject or
    body. A work_id that is a strict PREFIX of another commit's work_id (e.g.
    `lead-8v` as a prefix of `lead-8vwf`) therefore does NOT match, so it can no
    longer false-positive-attribute the wrong commit's lineage.

    Implemented as an extended-regex (`-E`) `--grep` with `\\b` word boundaries
    around the regex-escaped work_id. `re.escape` neutralizes any regex
    metacharacters in the work_id so the only thing the boundaries gate is the
    literal token. A hyphen in the work_id (e.g. `lead-8vwf`) is a
    non-identifier character, so `\\b` correctly anchors at both ends of the
    full token rather than at the internal hyphen.
    """
    return ["-E", f"--grep=\\b{re.escape(work_id)}\\b"]


def _is_deliverable_path(path: str) -> bool:
    """Return True iff a porcelain path lives under a deliverable directory.

    Deliverable directories are `features/`, `src/`, `tests/`. A path is
    deliverable when it lives UNDER one of them (e.g. "features/foo.feature",
    "src/pkg/mod.py", "tests/test_x.py") or is the directory itself. Anything
    else — `.claude/...` harness/config, repository-root config files, and the
    ambient carve-outs (`.specstory`, `.claude/scheduled_tasks.lock`,
    `.beads/issues.jsonl`) — is non-deliverable and does NOT block the emit.
    """
    normalized = path.rstrip("/")
    for d in _DELIVERABLE_DIRS:
        if normalized == d or normalized.startswith(d + "/"):
            return True
    return False


def _porcelain_path(line: str) -> str:
    """Return the path a `git status --porcelain` line refers to.

    Porcelain lines are "XY <path>" (XY is the 2-char status). Rename/copy
    lines are "XY <old> -> <new>"; we take the new path. Quoted paths
    (core.quotepath) are returned with quotes stripped — good enough for the
    carve-out membership test.
    """
    body = line[3:] if len(line) > 3 else line.strip()
    if " -> " in body:
        body = body.split(" -> ", 1)[1]
    return body.strip().strip('"')


def check_clean_working_tree(repo: Path) -> None:
    """Check 1 — clean working tree, DELIVERABLE-SCOPED.

    Refuses (raising PreconditionRefusal) ONLY when a porcelain entry names a
    path under a deliverable directory (`features/`, `src/`, `tests/`), listing
    each offending DELIVERABLE path verbatim. A tree whose only modified,
    staged, or untracked paths are non-deliverable harness/config paths (e.g.
    `.claude/canonical/bc-primer.md`, `.claude/settings.json`) or the ambient
    carve-outs (`.specstory`, `.claude/scheduled_tasks.lock`,
    `.beads/issues.jsonl`) is treated as clean and proceeds, because no
    deliverable path is dirty.
    """
    # `-uall` lists untracked files individually rather than collapsing them
    # to a parent directory entry (e.g. "?? src/"), so a deliverable path like
    # "src/pkg/mod.py" appears verbatim and is scoped individually rather than
    # the whole directory being summarized.
    result = _git(repo, "status", "--porcelain", "-uall")
    offending: list[str] = []
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        path = _porcelain_path(line)
        if not _is_deliverable_path(path):
            # Non-deliverable harness/config/ambient path — does NOT block.
            continue
        # The full porcelain line is the verbatim evidence the scenario
        # asks for ("as git status --porcelain reported it").
        offending.append(line)
    if offending:
        paths = "\n".join(offending)
        raise PreconditionRefusal(
            "refused: the clean-working-tree precondition failed. The BC "
            "working tree carries modified, staged, or untracked paths under a "
            "deliverable directory (features/, src/, tests/). Only deliverable "
            "paths block the emit; non-deliverable harness/config paths (e.g. "
            ".claude/canonical/bc-primer.md, .claude/settings.json) and the "
            "ambient carve-outs (.specstory, .claude/scheduled_tasks.lock, "
            ".beads/issues.jsonl) do not. Offending deliverable paths, verbatim "
            f"from `git status --porcelain`:\n{paths}\n{_SELF_RESOLVE}"
        )


def _origin_main_head(repo: Path) -> str:
    rev = _git(repo, "rev-parse", "--short", "origin/main")
    return rev.stdout.strip()


def check_commit_reachable(repo: Path, work_id: str) -> None:
    """Check 2 (commit mode) — work_id commit reachable from origin/main HEAD.

    Fetches origin first (so a stale local ref does not produce a false
    pass/fail), then searches commits reachable from origin/main HEAD for the
    work_id as a WHOLE TOKEN (word-boundary match) in the subject or body — a
    strict-prefix work_id does NOT match. A commit attributable to the
    work_id that exists only on another branch (un-merged/un-pushed local
    branch) is NOT reachable from origin/main HEAD and therefore does NOT
    satisfy. On refusal names the work_id and the current origin/main HEAD
    short SHA.
    """
    _git(repo, "fetch", "origin")
    # Search ONLY commits reachable from origin/main HEAD. The attribution
    # match is the canonical WORD-BOUNDARY (whole-token) form shared with the
    # tag-mode site below — the work_id must appear as a whole token in the
    # commit subject/body, so a strict-prefix work_id does NOT false-match.
    log = _git(
        repo,
        "log",
        "origin/main",
        *_work_id_attribution_grep(work_id),
        "--oneline",
    )
    if log.stdout.strip():
        return
    head = _origin_main_head(repo)
    raise PreconditionRefusal(
        "refused: the work_id-commit-on-origin-main precondition failed. No "
        f"commit attributable to work_id {work_id!r} is reachable from "
        f"origin/main HEAD ({head}) after `git fetch origin`. A commit that "
        "exists only on a local/unmerged branch does NOT satisfy this "
        "precondition; only reachability from origin/main HEAD does. "
        f"{_SELF_RESOLVE}"
    )


def check_tag_reachable(repo: Path, work_id: str, tag: str) -> None:
    """Check 2 (tag/release mode) — named tag's lineage anchors the work_id.

    Satisfaction is established by the named tag EXISTING (after
    `git fetch origin --tags`) AND its commit lineage carrying/anchoring the
    dispatched work_id — NOT by the work_id being reachable from origin/main
    HEAD. This is the release case: origin/main HEAD may have legitimately
    advanced to a later commit that does not carry the work_id, and that does
    NOT refuse the emit so long as the TAG's own lineage anchors the work_id.

    "Points at the expected commit lineage" means the work_id is attributable
    to a commit in the TAG's history — the SAME attribution mechanism
    `check_commit_reachable` uses (the canonical word-boundary `--grep` over
    the commit subject/body), but scoped to the tag's reachable history
    (`git log <tag> ...`) instead of origin/main HEAD. Mere tag existence with
    a non-empty `git rev-list` does NOT satisfy: an unrelated tag pointing at
    a commit that bears no relationship to the work_id (e.g. the repo's seed
    commit) carries the work_id in neither subject nor body of any commit in
    its lineage, so it refuses. The check deliberately does NOT consult
    origin/main HEAD for reachability.
    """
    _git(repo, "fetch", "origin", "--tags")
    # The tag must exist and resolve to a commit.
    resolved = _git(repo, "rev-parse", "--verify", "--quiet", f"{tag}^{{commit}}")
    if resolved.returncode != 0 or not resolved.stdout.strip():
        head = _origin_main_head(repo)
        raise PreconditionRefusal(
            "refused: the tag-deliverable reachability precondition failed. "
            f"The named release tag {tag!r} does not exist (or does not "
            "resolve to a commit) after `git fetch origin --tags`. Tag-mode "
            "satisfaction comes from the tag's lineage anchoring the work_id, "
            f"not from work_id {work_id!r} being reachable from origin/main "
            f"HEAD ({head}). {_SELF_RESOLVE}"
        )
    # The tag's commit LINEAGE must carry/anchor the work_id. This mirrors
    # check_commit_reachable's attribution (the canonical word-boundary
    # whole-token --grep over commit subject+body) but is scoped to the TAG's
    # reachable history
    # rather than origin/main HEAD. A tag whose lineage is intact (non-empty
    # rev-list) but carries no work_id-attributed commit — e.g. a tag pointing
    # at the repo's unrelated seed commit — does NOT satisfy.
    in_lineage = _git(
        repo,
        "log",
        tag,
        *_work_id_attribution_grep(work_id),
        "--oneline",
    )
    if not in_lineage.stdout.strip():
        raise PreconditionRefusal(
            "refused: the tag-lineage-anchors-work_id precondition failed. The "
            f"named release tag {tag!r} exists and resolves to a commit with a "
            f"non-empty `git rev-list`, but no commit attributable to work_id "
            f"{work_id!r} is present in the tag's commit lineage "
            f"(`git log {tag} -E --grep=\\b{work_id}\\b`). Mere tag "
            "existence with a non-empty rev-list does NOT satisfy tag-mode "
            "reachability; only a tag whose lineage carries/anchors the "
            "dispatched work_id does (a tag pointing at an unrelated commit, "
            "e.g. the repository's seed commit, refuses). "
            f"{_SELF_RESOLVE}"
        )
    # Satisfied — the tag's lineage anchors the work_id; return without
    # consulting origin/main HEAD.


def _scenario_blocks(feature_text: str) -> list[tuple[str, str | None]]:
    """Split a feature file into (block_text, carried_hash) per scenario.

    block_text is the scenario block (the `Scenario:` line and its steps,
    plus the tag line) WITHOUT the enclosing `Feature:` header line — the
    exact text compute_scenario_hash canonicalizes (it discards the
    @scenario_hash: tag line itself). carried_hash is the value of the
    block's `@scenario_hash:` tag, or None if the block carries no such tag.
    """
    lines = feature_text.splitlines()
    blocks: list[tuple[str, str | None]] = []
    current: list[str] | None = None

    def _flush() -> None:
        if current is None:
            return
        text = "\n".join(current)
        m = re.search(r"@scenario_hash:([0-9a-fA-F]+)", text)
        carried = m.group(1) if m else None
        blocks.append((text, carried))

    pending_tag: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("Feature:"):
            # Feature header is never part of any block.
            continue
        if stripped.startswith("@"):
            # A tag line; it belongs to the scenario that follows it.
            pending_tag.append(line)
            continue
        if stripped.startswith("Scenario:"):
            _flush()
            current = list(pending_tag) + [line]
            pending_tag = []
            continue
        if current is not None:
            current.append(line)
        # lines before the first scenario (blank etc.) are ignored
        pending_tag = pending_tag if not stripped else pending_tag
    _flush()
    return blocks


def check_scenario_hashes(
    repo: Path, work_id: str, payload_hashes: list[str]
) -> None:
    """Check 3 — scenario-hash staleness, WORK-SCOPED to the dispatch's OWN
    assigned set (scenario 225, hash aabbc009bad6fe86).

    The staleness scan evaluates ONLY the scenario blocks in the dispatch's own
    assigned set — the blocks under features/ that CARRY one of the payload
    `--scenario-hash` values (`payload_hashes`). A scenario block whose carried
    `@scenario_hash` is NOT one this dispatch named is owned by a SEPARATE work
    item; it is NEITHER recomputed NOR allowed to refuse the emit. This mirrors
    scenario 212 (cba037e97c6a8325), which scoped Check 1 (clean-tree) to
    deliverable paths.

    This REPLACES the earlier GLOBAL scan, which recomputed every
    `@scenario_hash` grep-able under features/ and refused on ANY divergence
    anywhere in the tree — including unrelated work items' tags. For a narrow
    (e.g. single-scenario) dispatch that global scan refused on essentially
    every unrelated block (the old "missing" arm fired for every features/-
    present block whose recompute was not echoed in the narrow payload),
    forcing reviewers onto the bare `--force` escape valve. The scope of the
    refusal — NOT its classifications — is what changed: stale, missing, and
    orphan all still hold, now FOR IN-SCOPE SCENARIOS ONLY (scenario 179,
    ea9c1bbd9be87d72, preserved):

      stale   — a block in the dispatch's own set (its carried @scenario_hash is
                one this dispatch named) whose block-only recompute differs from
                the carried value (the body drifted under the pinned tag).
      missing — a dispatched scenario block present under features/ whose
                block-only recompute IS one this dispatch named but which
                carries NO @scenario_hash tag (the pin is missing).
      orphan  — a payload hash the dispatch named that NO committed scenario
                block under features/ carries.

    On any divergence: raise PreconditionRefusal naming the scenario-hash
    staleness check (Check 3) as the cause, the in-scope work_id, the
    classification, the affected hash value, and the scenario; for a stale
    block it names the in-scope work_id, the stale on-disk value, and the
    recomputed value.

    The recompute uses ONLY the block-only delegate
    (scenarios.hash.compute_scenario_hash), never the Feature-line-included
    canonicalization carried on the wire.
    """
    # Lazy import (lead-ld7i / tmpl-20n): scenarios is only needed on this
    # work-done hash-check path, so it is imported here rather than at module
    # top level. This keeps `bc-emit --help` and other subcommands working even
    # when the `scenarios` package is not installed; the VCS dependency
    # declared in pyproject guarantees resolution for this path in real
    # installs.
    from scenarios.hash import compute_scenario_hash

    payload_set = list(payload_hashes)
    payload_lookup = set(payload_set)
    features_dir = repo / "features"
    feature_files = (
        sorted(features_dir.glob("*.feature"))
        if features_dir.is_dir()
        else []
    )

    accounted: set[str] = set()  # payload hashes carried by an in-scope block
    # Untagged blocks are collected but NOT recomputed up front — they are only
    # recomputed if an unaccounted payload hash forces the missing/orphan
    # distinction below. This keeps the happy path from recomputing any
    # out-of-set block at all.
    untagged_blocks: list[tuple[str, str]] = []  # (block_text, "title in file")

    for fpath in feature_files:
        text = fpath.read_text()
        for block_text, carried in _scenario_blocks(text):
            title = _scenario_title(block_text)
            if carried is None:
                untagged_blocks.append((block_text, f"{title!r} in {fpath.name}"))
                continue
            if carried not in payload_lookup:
                # OUT OF SCOPE: this block's carried @scenario_hash is owned by
                # a separate work item the dispatch never named. Do NOT
                # recompute it and do NOT refuse on it (scenario 225 arm a).
                continue
            # IN SCOPE: recompute the block-only canonical hash and compare to
            # the carried (== dispatch-named) value.
            recompute = compute_scenario_hash(block_text)
            if carried != recompute:
                raise PreconditionRefusal(
                    "refused: the scenario-hash staleness check (Check 3) — "
                    "the scenario_hashes-match precondition — "
                    f"failed for work_id {work_id} (classification: STALE). The "
                    f"scenario block {title!r} in {fpath.name} is in the "
                    "dispatch's own assigned scenario set (its carried "
                    f"@scenario_hash {carried} is one this dispatch named) but "
                    f"its scenario-block-only recompute is {recompute}. "
                    f"In-scope work_id: {work_id}; stale on-disk @scenario_hash "
                    f"value: {carried}; recomputed value: {recompute}. "
                    "(Recomputed in-process via "
                    "scenarios.hash.compute_scenario_hash, the block-only "
                    "canonicalization — never the Feature-line-included wire "
                    f"form.) {_SELF_RESOLVE}"
                )
            accounted.add(carried)

    # For any payload hash NOT accounted for by an in-scope carrying block,
    # distinguish MISSING (the dispatched scenario is present but untagged) from
    # ORPHAN (no such scenario exists). Only NOW do we recompute the untagged
    # blocks, and only to resolve this in-scope question — out-of-set TAGGED
    # blocks are never recomputed.
    unaccounted = [h for h in payload_set if h not in accounted]
    if unaccounted:
        untagged_recompute: dict[str, str] = {}
        for block_text, where in untagged_blocks:
            untagged_recompute.setdefault(compute_scenario_hash(block_text), where)
        for h in unaccounted:
            where = untagged_recompute.get(h)
            if where is not None:
                raise PreconditionRefusal(
                    "refused: the scenario-hash staleness check (Check 3) — "
                    "the scenario_hashes-match precondition — "
                    f"failed for work_id {work_id} (classification: MISSING). "
                    f"The dispatched scenario block {where} is present under "
                    "features/ with scenario-block-only recompute "
                    f"{h} (one this dispatch named) but carries NO "
                    "@scenario_hash tag — the pin is missing. (Recomputed via "
                    "scenarios.hash.compute_scenario_hash, block-only "
                    "canonicalization, never the Feature-line wire form.) "
                    f"{_SELF_RESOLVE}"
                )
            raise PreconditionRefusal(
                "refused: the scenario-hash staleness check (Check 3) — the "
                "scenario_hashes-match precondition — failed "
                f"for work_id {work_id} (classification: ORPHAN). The payload "
                f"--scenario-hash {h} matches no scenario block under features/ "
                "— no committed block carries it. (Block-only canonicalization "
                "via scenarios.hash.compute_scenario_hash, never the "
                f"Feature-line wire form.) {_SELF_RESOLVE}"
            )


def check_retirement_removal(
    repo: Path, work_id: str, retire_hashes: list[str]
) -> None:
    """Retirement-removal precondition (lead-acoo).

    When the consumed dispatch named one or more `@scenario_hash` values for
    retirement (passed via `--retire-hash`), refuse the emit if any of them is
    still carried by a scenario block under the as-committed `features/` tree —
    whether the old retired block was left in place OR the hash was duplicated
    onto a newly added block. Removing the named-for-retirement hash from
    `features/` is the only thing that satisfies this precondition; adding a new
    scenario block with a fresh body and hash does NOT, and the stale-hash /
    orphan checks passing on the surviving blocks does not exempt this refusal.
    """
    if not retire_hashes:
        return
    features_dir = repo / "features"
    carried: set[str] = set()
    if features_dir.is_dir():
        for fpath in sorted(features_dir.glob("*.feature")):
            for _block_text, carried_hash in _scenario_blocks(fpath.read_text()):
                if carried_hash is not None:
                    carried.add(carried_hash)
    still_reachable = [h for h in retire_hashes if h in carried]
    if still_reachable:
        names = ", ".join(sorted(set(still_reachable)))
        raise PreconditionRefusal(
            "refused: the retirement-removal precondition failed for work_id "
            f"{work_id}. The consumed dispatch named scenario hash(es) for "
            "retirement that are STILL reachable under the as-committed "
            f"features/ tree: {names}. Removing the named-for-retirement "
            "hash(es) from features/ is the only thing that satisfies this "
            "precondition — leaving the old retired block in place, or "
            "duplicating the hash onto a newly added block, does not; and the "
            "stale-hash / orphan checks passing on the surviving blocks does "
            "not exempt this refusal. "
            f"{_SELF_RESOLVE}"
        )


def _scenario_title(block_text: str) -> str:
    for line in block_text.splitlines():
        s = line.strip()
        if s.startswith("Scenario:"):
            return s[len("Scenario:"):].strip()
    return "<unknown scenario>"


# =======================================================================
# Plan-decomposition preconditions (Check 4 + durability) — bd-registry side.
#
# The bd plan decomposition for a work_id lives under an UMBRELLA bead in the
# BC's own bd registry. These two checks run INSIDE the BC container against
# that registry (ADR-036 D2), via the `bd` CLI (seamable for tests through
# `bd_cmd`). They run ONLY when an umbrella bead is named (`--plan-umbrella`),
# so a non-scenario / flat-maintenance emit that carries no decomposition is
# unaffected and the existing wrapper scenarios are untouched.
# =======================================================================


def _bd(repo: Path, *args: str, bd_cmd: tuple[str, ...] = ("bd",)) -> subprocess.CompletedProcess:
    return subprocess.run(
        [*bd_cmd, *args],
        cwd=str(repo),
        capture_output=True,
        text=True,
    )


def _subissue_status(subissue: dict) -> str:
    return str(subissue.get("status") or "").strip().lower()


def _subissue_is_red(subissue: dict) -> bool:
    """A sub-issue is a RED (failing-test) sub-issue when its title carries the
    RED nomenclature — "failing test", "(red)", or "test(red)"."""
    title = str(subissue.get("title") or "").lower()
    return (
        "failing test" in title
        or "(red)" in title
        or "test(red)" in title
    )


def _default_children_provider(
    bd_cmd: tuple[str, ...],
):
    """Build the default sub-issue enumerator: `bd children <umbrella> --json`.

    `bd children` includes CLOSED issues by default, so the returned set is
    EVERY sub-issue reachable under the umbrella bead in the BC's own bd
    registry — including an orphan from an abandoned earlier decomposition that
    the implementer never created or closed. This independent registry
    enumeration is exactly what catches orphans the implementer would not
    self-report.
    """
    def provider(repo: Path, umbrella: str) -> list[dict]:
        result = _bd(repo, "children", umbrella, "--json", bd_cmd=bd_cmd)
        try:
            data = json.loads(result.stdout or "[]")
        except json.JSONDecodeError:
            data = []
        return [d for d in data if isinstance(d, dict)]
    return provider


def check_plan_subissues_closed(
    repo: Path,
    work_id: str,
    umbrella: str,
    *,
    bd_cmd: tuple[str, ...] = ("bd",),
    children_provider=None,
) -> None:
    """Check 4 (hash 0b48508e40fdde18) — every sub-issue reachable under the
    work_id umbrella bead must be CLOSED, and at least one must be RED.

    The precondition is evaluated by INDEPENDENTLY enumerating EVERY sub-issue
    reachable under the work_id umbrella bead from the BC's own bd registry —
    NOT only the set the implementer reports or itself closed. An OPEN sub-issue
    the implementer never created (an orphan from an abandoned earlier
    decomposition the implementer never closed) therefore still blocks the
    emit. The prior "at least one RED sub-issue exists and all sub-issues the
    implementer closed are closed" check alone does NOT pass the gate.

    On refusal: raise PreconditionRefusal naming the
    all-sub-issues-under-the-work_id-umbrella-closed precondition and listing
    EACH still-OPEN sub-issue (including the orphaned one) by its bd id.
    """
    if children_provider is None:
        children_provider = _default_children_provider(bd_cmd)
    subissues = children_provider(repo, umbrella)

    if not subissues:
        raise PreconditionRefusal(
            "refused: the bd-plan-decomposition precondition failed for work_id "
            f"{work_id}. No bd plan sub-issues are reachable under the work_id "
            f"umbrella bead {umbrella}. A scenario-carrying dispatch must be "
            "decomposed into TDD sub-issues (at least one explicit RED "
            f"failing-test sub-issue) and all of them closed. {_SELF_RESOLVE}"
        )

    open_subissues = [s for s in subissues if _subissue_status(s) != "closed"]
    if open_subissues:
        open_ids = ", ".join(
            str(s.get("id") or "<unknown-id>") for s in open_subissues
        )
        raise PreconditionRefusal(
            "refused: the all-sub-issues-under-the-work_id-umbrella-closed "
            f"precondition failed for work_id {work_id} (umbrella {umbrella}). "
            "The following sub-issue(s) reachable under the work_id umbrella "
            "bead are still OPEN — including any orphan from an abandoned "
            "earlier decomposition the implementer never created or closed: "
            f"{open_ids}. The precondition is evaluated by enumerating EVERY "
            "sub-issue reachable under the work_id umbrella bead — not only the "
            "set the implementer reports or itself closed — so an OPEN "
            "sub-issue the implementer did not create still blocks the emit, "
            "and the prior 'at least one RED sub-issue exists and all "
            "sub-issues the implementer closed are closed' check alone does NOT "
            f"pass the gate. {_SELF_RESOLVE}"
        )

    if not any(_subissue_is_red(s) for s in subissues):
        raise PreconditionRefusal(
            "refused: the bd-plan-decomposition precondition failed for work_id "
            f"{work_id} (umbrella {umbrella}). Every sub-issue reachable under "
            "the work_id umbrella bead is closed, but NONE is an explicit RED "
            "(failing-test) sub-issue, so there is no test-first decomposition "
            f"artifact. {_SELF_RESOLVE}"
        )


def _default_durability_probe(
    bd_cmd: tuple[str, ...],
):
    """Build the default bd-dolt reachability probe.

    Durability is established by the decomposition-and-closure STATE being
    reachable from the pushed tracker remote — the configured bd-dolt remote —
    NOT by the `.beads/issues.jsonl` working-tree bytes being clean (that path
    is a carved-out non-idempotent ambient artifact under Check 1, so a clean
    tree cannot by itself establish durability). bd is dolt-backed (ADR-036
    implementation guidance), so the concrete surface is the bd-dolt push: a
    `bd dolt push` that exits zero means the closure state is reachable from
    the configured remote — the same unpushable-tracker durability signal the
    BC session-start work-tracker health step uses (beads-health
    43a05feaefc1d046).
    """
    def probe(repo: Path) -> bool:
        result = _bd(repo, "dolt", "push", bd_cmd=bd_cmd)
        return result.returncode == 0
    return probe


def check_plan_decomposition_durable(
    repo: Path,
    work_id: str,
    *,
    bd_cmd: tuple[str, ...] = ("bd",),
    durability_probe=None,
) -> None:
    """Durability precondition (hash 7bcfc89161c0b2ee) — the work_id's
    sub-issue decomposition-and-closure STATE must be reachable from the pushed
    tracker remote.

    Refuses when the decomposition and closures exist only in an uncommitted or
    locally-staged `.beads` registry that is NOT reachable from the BC's pushed
    tracker remote (the configured bd-dolt remote). The refusal names the
    bd-decomposition-durability precondition SPECIFICALLY and names the work_id
    — it does NOT report a generic dirty-working-tree cause, because
    `.beads/issues.jsonl` is a carved-out non-idempotent ambient artifact whose
    clean-tree state cannot by itself establish that the closures are durable.
    """
    if durability_probe is None:
        durability_probe = _default_durability_probe(bd_cmd)
    if not durability_probe(repo):
        raise PreconditionRefusal(
            "refused: the bd-decomposition-durability precondition failed for "
            f"work_id {work_id}. The work_id's sub-issue decomposition and "
            "closures are NOT reachable from the pushed tracker remote — the "
            "configured bd-dolt remote — so they exist only in an uncommitted "
            "or locally-staged .beads registry. This is NOT a generic "
            "dirty-working-tree cause: the durability precondition is satisfied "
            "by the decomposition-and-closure state being reachable from the "
            "pushed tracker remote, NOT by the .beads/issues.jsonl working-tree "
            "bytes being clean (that path is a carved-out non-idempotent "
            "ambient artifact under the clean-working-tree precondition, so the "
            "carve-out cannot by itself establish that the closures are "
            f"durable). {_SELF_RESOLVE}"
        )


def _invoke_respond(
    respond_cmd: list[str],
    work_id: str,
    status: str,
    bc: str | None,
    summary: str | None,
    scenario_hashes: list[str],
) -> int:
    """Invoke the real `shop-msg respond work_done` primitive.

    Reached ONLY when every precondition passed. respond_cmd is the base
    command (default ["shop-msg"]) — overridable so a test can inject a
    seam that records whether/how respond was invoked.
    """
    cmd = list(respond_cmd) + ["respond", "work_done", "--work-id", work_id, "--status", status]
    if bc is not None:
        cmd += ["--bc", bc]
    if summary is not None:
        cmd += ["--summary", summary]
    for h in scenario_hashes:
        cmd += ["--scenario-hash", h]
    result = subprocess.run(cmd)
    return result.returncode


def _cmd_work_done(args: argparse.Namespace) -> int:
    repo = Path(args.repo).resolve()
    try:
        # Check 1 — clean working tree (carve-outs discounted).
        check_clean_working_tree(repo)
        # Retirement-removal — any hash the consumed dispatch named for
        # retirement must be absent from the as-committed features/ tree.
        check_retirement_removal(repo, args.work_id, list(args.retire_hash or []))
        # Check 2 — reachability, by deliverable mode.
        if args.deliverable == "tag":
            if not args.tag:
                raise PreconditionRefusal(
                    "refused: --deliverable tag requires --tag <name>. "
                    f"{_SELF_RESOLVE}"
                )
            check_tag_reachable(repo, args.work_id, args.tag)
        else:
            check_commit_reachable(repo, args.work_id)
        # Check 3 — scenario-hash staleness, WORK-SCOPED to the dispatch's own
        # assigned set (the --scenario-hash set the emit carries).
        check_scenario_hashes(repo, args.work_id, list(args.scenario_hash or []))
        # Check 4 + durability — bd plan decomposition, against the BC's own bd
        # registry. Run ONLY when an umbrella bead is named: a non-scenario /
        # flat-maintenance emit carries no decomposition and is unaffected.
        if args.plan_umbrella:
            bd_cmd = tuple(args.bd_cmd) if args.bd_cmd else ("bd",)
            # Check 4 — every sub-issue reachable under the work_id umbrella
            # bead is closed (orphaned-OPEN detection; hash 0b48508e40fdde18).
            check_plan_subissues_closed(
                repo, args.work_id, args.plan_umbrella, bd_cmd=bd_cmd
            )
            # Durability — the decomposition-and-closure state is reachable
            # from the pushed tracker remote (hash 7bcfc89161c0b2ee).
            check_plan_decomposition_durable(repo, args.work_id, bd_cmd=bd_cmd)
    except PreconditionRefusal as refusal:
        # On ANY precondition refusal: do NOT invoke shop-msg respond; exit
        # non-zero with the named-cause + self-resolve error.
        print(str(refusal), file=sys.stderr)
        return 1

    # All preconditions passed — invoke the real respond primitive.
    respond_cmd = args.respond_cmd if args.respond_cmd else ["shop-msg"]
    return _invoke_respond(
        respond_cmd,
        args.work_id,
        args.status,
        args.bc,
        args.summary,
        list(args.scenario_hash or []),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="bc-emit")
    sub = parser.add_subparsers(dest="command", required=True)

    wd = sub.add_parser(
        "work-done",
        help="run pre-emit preconditions, then invoke shop-msg respond work_done",
    )
    wd.add_argument("--work-id", required=True, help="dispatched work_id")
    wd.add_argument(
        "--deliverable",
        choices=("commit", "tag"),
        default="commit",
        help="reachability mode: commit (work_id on origin/main) or tag (release)",
    )
    wd.add_argument("--tag", default=None, help="release tag name (tag mode)")
    wd.add_argument(
        "--scenario-hash",
        action="append",
        default=[],
        help="scenario hash echoed in the payload (repeatable)",
    )
    wd.add_argument(
        "--retire-hash",
        action="append",
        default=[],
        help=(
            "a scenario hash the consumed dispatch named for retirement "
            "(repeatable); the emit is refused while any of these is still "
            "carried by a scenario block under the as-committed features/ tree"
        ),
    )
    wd.add_argument(
        "--plan-umbrella",
        default=None,
        help=(
            "the bd umbrella bead id carrying the work_id's TDD sub-issue "
            "decomposition. When provided, the wrapper enforces the bd-plan "
            "preconditions: every sub-issue reachable under the umbrella bead "
            "must be closed (with at least one RED failing-test sub-issue) and "
            "the decomposition-and-closure state must be reachable from the "
            "pushed tracker remote. Independently enumerated from the BC's own "
            "bd registry, so an orphaned OPEN sub-issue the implementer never "
            "created still blocks the emit. Omitted for non-scenario / "
            "flat-maintenance emits that carry no decomposition."
        ),
    )
    wd.add_argument(
        "--bd-cmd",
        action="append",
        default=None,
        help=(
            "base command used to invoke the bd CLI for the plan-decomposition "
            "preconditions (default: bd); repeatable to pass a multi-token "
            "command. Seam tests use to inject a fake bd."
        ),
    )
    wd.add_argument(
        "--status",
        choices=("complete", "partial", "blocked"),
        default="complete",
        help="work_done status forwarded to shop-msg respond",
    )
    wd.add_argument("--bc", default=None, help="canonical BC name (pass-through)")
    wd.add_argument("--summary", default=None, help="work_done summary (pass-through)")
    wd.add_argument(
        "--repo",
        default=".",
        help="BC repository root the preconditions inspect (default: cwd)",
    )
    wd.add_argument(
        "--respond-cmd",
        action="append",
        default=None,
        help=(
            "base command used to invoke the real respond primitive "
            "(default: shop-msg); repeatable to pass a multi-token command. "
            "This is the seam tests use to observe whether respond was "
            "invoked — the wrapper does NOT invoke it on any precondition "
            "refusal."
        ),
    )
    wd.set_defaults(func=_cmd_work_done)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
