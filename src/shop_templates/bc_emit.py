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

  Check 3 — scenario-hash staleness, WORK-SCOPED + SOURCE-FRESH (hashes
            ea9c1bbd9be87d72, aabbc009bad6fe86, 613ddd886f6dc431)
      SOURCE-FRESH (scenario 227, 613ddd886f6dc431): the staleness scan reads the
      scenario blocks from the FETCHED `origin/main` tree (after a `git fetch
      origin`), NOT from the BC primary checkout's possibly-lagging LOCAL working
      tree — mirroring the Check 2 reachability posture (scenario 177), which
      likewise fetches and reasons about origin/main. This removes the false
      refusal lead-b2iz observed: when local main lagged origin/main, a scenario
      already reconciled on origin/main still carried its OLD body/tag locally,
      the local recompute mismatched, and the wrapper refused — misnaming a
      scenario-hash recompute-mismatch and misdirecting toward `--force` or
      hand-editing an already-correct scenario. The INVARIANT holds: a block
      genuinely stale on origin/main (its on-disk tag does not reproduce against
      its as-committed origin/main body) still refuses, naming the staleness
      check. Only WHICH TREE is read changed — distinct from scenario 225, which
      changed WHICH scenarios are scanned.

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


def _local_feature_texts(repo: Path) -> dict[str, str]:
    """Read `features/*.feature` from the repo's LOCAL working tree.

    This is the source `check_scenario_hashes` falls back to when no explicit
    `feature_texts` is supplied (e.g. a direct unit-test call). The CLI work-done
    path does NOT use it — it injects the fetched origin/main tree instead
    (scenario 227); see `fetch_origin_main_feature_texts`. Keyed by file basename,
    mirroring the prior `fpath.name`-keyed error messages.
    """
    features_dir = repo / "features"
    if not features_dir.is_dir():
        return {}
    return {
        p.name: p.read_text() for p in sorted(features_dir.glob("*.feature"))
    }


def fetch_origin_main_feature_texts(repo: Path) -> dict[str, str]:
    """Check 3 SOURCE-FRESHNESS (scenario 227, hash 613ddd886f6dc431).

    Performs a `git fetch origin` and returns the `features/*.feature` texts as
    they stand on the FETCHED `origin/main` tree — NOT the (possibly lagging)
    local working tree. This mirrors the Check 2 reachability posture (scenario
    177, hash 461d6066ef7dca0a), which likewise `git fetch origin`s and reasons
    about `origin/main` HEAD rather than the local checkout.

    Motivation (lead-b2iz mechanism observation): the earlier Check 3 recomputed
    the in-scope `@scenario_hash` tags against the BC primary checkout's LOCAL
    working tree. When local main lagged `origin/main`, a scenario block that was
    already reconciled on `origin/main` still carried its OLD body/tag locally;
    the local recompute mismatched; and the wrapper FALSE-refused — naming a
    scenario-hash recompute-mismatch and misdirecting the BC toward `--force` or
    toward hand-editing an already-correct scenario. Reading the fetched
    `origin/main` tree removes that false-refuse: a block consistent on
    `origin/main` but stale only in the lagging local checkout no longer refuses.
    The INVARIANT is preserved — a block genuinely stale on `origin/main` (its
    on-disk tag does not reproduce against its as-committed `origin/main` body)
    still recomputes to a divergent value here and still refuses.

    Returns a {basename: file-text} mapping, the same shape
    `check_scenario_hashes` consumes from `_local_feature_texts`, so the scan,
    work-scoping (scenario 225), and block-only canonicalization (scenario 179)
    are entirely unchanged — only the TREE the text is read from changes.
    """
    _git(repo, "fetch", "origin")
    ls = _git(repo, "ls-tree", "-r", "--name-only", "origin/main", "features/")
    texts: dict[str, str] = {}
    for path in ls.stdout.splitlines():
        path = path.strip()
        if not path.endswith(".feature"):
            continue
        show = _git(repo, "show", f"origin/main:{path}")
        texts[path.rsplit("/", 1)[-1]] = show.stdout
    return texts


def _scenario_blocks(feature_text: str) -> list[tuple[str, str | None]]:
    """Split a feature file into (block_text, carried_hash) per scenario.

    Block-delimitation is DELEGATED to the canonical shopsystem-scenarios
    splitter (ADR-019) rather than re-implemented here: the carried
    `@scenario_hash` association comes from `scenarios.feature.iter_scenarios`
    — the exact splitter `scenarios list` uses — and the scenario boundary is
    the same `scenarios.feature._SCENARIO_RE` keyword match `iter_scenarios`
    fires on, so this scan can never drift from the canonical producer.

    block_text is the `Scenario:`/`Scenario Outline:` keyword line through the
    last step/Examples line, EXCLUDING the enclosing `Feature:` header line and
    ALL `@`-prefixed tag lines (feature-level AND per-scenario), with TRAILING
    blank / `#`-comment lines trimmed (a comment after the last step belongs to
    the following scenario/feature, not this block; comments embedded among the
    steps are retained). Because `scenarios.hash.compute_scenario_hash` drops
    `@scenario_hash:` lines and the canonical producer's per-scenario block
    reduces to the keyword line + steps (its tag line — `@scenario_hash:… @bc:…`
    — is dropped whole), this block_text canonicalizes byte-for-byte to what the
    ADR-019 producer hashes. carried_hash is the block's `@scenario_hash:` value
    per the canonical association, or None if the scenario carries no such tag.

    This is the tmpl-7ti fix (PIN 1 @scenario_hash:ea9c1bbd9be87d72): the prior
    home-grown delimitation accumulated every tag line into a `pending_tag`
    buffer and never cleared it at the `Feature:` line, so the feature-level
    `@`-tags that precede `Feature:` (e.g. `@bc:… @origin:…`) folded INTO the
    first-in-file scenario's block. Those tag lines survive
    `compute_scenario_hash` (it drops only `@scenario_hash:` lines), so the
    wrapper recomputed a hash divergent from the canonical producer and
    false-refused valid emits as STALE. Feeding the block-only keyword-through-
    steps text — with no tags at all — removes that divergence.
    """
    from scenarios.feature import _SCENARIO_RE, iter_scenarios

    # Canonical carried-hash + title association (the scenarios-BC splitter).
    carried_list = list(iter_scenarios(feature_text))

    # Block texts: the keyword line through its steps/Examples. The `Feature:`
    # header and EVERY tag line are excluded, so nothing folds into a block. The
    # boundary is the SAME `_SCENARIO_RE` keyword match iter_scenarios fires on,
    # so block_texts aligns one-to-one, in file order, with carried_list.
    block_texts: list[list[str]] = []
    current: list[str] | None = None
    for line in feature_text.splitlines():
        if _SCENARIO_RE.match(line):
            current = [line]
            block_texts.append(current)
            continue
        stripped = line.strip()
        if stripped.startswith("Feature:") or stripped.startswith("@"):
            continue
        if current is not None:
            current.append(line)

    blocks: list[tuple[str, str | None]] = []
    for (carried, _title), lines in zip(carried_list, block_texts):
        # Trim TRAILING blank / `#`-comment lines: a comment (or blank) after a
        # scenario's last step is not part of that scenario's body — it belongs
        # to the following scenario or feature. compute_scenario_hash already
        # drops blank lines, but it does NOT drop `#` comment lines, so a
        # trailing inter-scenario comment left in the block would perturb the
        # recompute and diverge from the canonical producer. Comments EMBEDDED
        # among the steps (followed by more step content) are retained — they
        # are part of the canonical body the producer hashed.
        while lines and (
            not lines[-1].strip() or lines[-1].strip().startswith("#")
        ):
            lines = lines[:-1]
        blocks.append(("\n".join(lines), carried))
    return blocks


def check_scenario_hashes(
    repo: Path,
    work_id: str,
    payload_hashes: list[str],
    *,
    feature_texts: dict[str, str] | None = None,
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

    SOURCE (scenario 227, 613ddd886f6dc431): `feature_texts` supplies the
    {basename: file-text} tree the scan reads. The CLI work-done path injects the
    FETCHED origin/main tree (fetch_origin_main_feature_texts) so a scenario
    reconciled on origin/main but stale only in a lagging local checkout does NOT
    false-refuse. When `feature_texts` is None (direct callers / unit tests), the
    LOCAL working tree is read instead. The scan, work-scoping, classifications,
    and block-only canonicalization are identical regardless of source tree.
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
    # SOURCE-FRESHNESS (scenario 227, 613ddd886f6dc431): the staleness scan
    # evaluates the feature texts from a SUPPLIED tree. The CLI work-done path
    # injects the FETCHED origin/main tree (fetch_origin_main_feature_texts) so a
    # scenario consistent on origin/main but stale only in a lagging local
    # checkout does NOT false-refuse. When no tree is supplied (direct callers /
    # unit tests), fall back to the LOCAL working tree. The scan, work-scoping
    # (scenario 225), and block-only canonicalization (scenario 179) are
    # identical regardless of which tree supplied the text.
    if feature_texts is None:
        feature_texts = _local_feature_texts(repo)

    accounted: set[str] = set()  # payload hashes carried by an in-scope block
    # Untagged blocks are collected but NOT recomputed up front — they are only
    # recomputed if an unaccounted payload hash forces the missing/orphan
    # distinction below. This keeps the happy path from recomputing any
    # out-of-set block at all.
    untagged_blocks: list[tuple[str, str]] = []  # (block_text, "title in file")

    for fname, text in sorted(feature_texts.items()):
        for block_text, carried in _scenario_blocks(text):
            title = _scenario_title(block_text)
            if carried is None:
                untagged_blocks.append((block_text, f"{title!r} in {fname}"))
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
                    f"scenario block {title!r} in {fname} is in the "
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


# =======================================================================
# Changed-feature schema-conformity gate (ADR-042, work_id lead-vzxd.10).
#
# An ADDITIONAL work-done gate arm — composed alongside Check 1-3, never
# weakening them — scoped to the CHANGED / ADDED feature files this work_id's
# commit(s) added or modified under features/. Each changed .feature is run
# through the v0.3.1 `scenarios validate` per-file schema gate; a
# work_done(complete) emit is REFUSED when any added/modified scenario is
# GENUINELY non-conformant, so no non-conformant scenario merges going forward
# (ADR-056 cutover, the "no regression past the cutover" invariant).
#
# CRITICAL GUARD — the v0.3.1 comment-folding validator defect. v0.3.1's
# validate extracts each scenario's raw block via `_iter_scenario_blocks`,
# which folds an inter-scenario comment into the PRECEDING scenario's block.
# That diverges from the producer/wire hash (`scenarios hash` == block-only
# canonicalization of the scenario's OWN block) and yields a FALSE
# E_HASH_MISMATCH on comment-adjacent scenarios whose on-disk @scenario_hash
# already EQUALS the producer. This gate cross-checks every E_HASH_MISMATCH the
# validator raises against the producer/wire hash recomputed from the on-disk
# block (block-only, comment-neutralized): if the on-disk tag reproduces the
# producer, the mismatch is the validator defect (NOT refused); if it does not,
# it is a real stale tag (refused). This preserves the wire-hash authority the
# lead-s8j2 / lead-9mog chain established while keeping the enforcement real.
# =======================================================================

# The genuine per-file / transitional codes that ALWAYS refuse when the
# validator reports them on a changed feature file. E_HASH_MISMATCH is handled
# SEPARATELY (producer cross-check) and is deliberately NOT in this set.
_GENUINE_VALIDATE_CODES = (
    "E_UNKNOWN_BC",
    "E_UNKNOWN_ORIGIN",
    "E_UNKNOWN_SERVICE",
    "E_MISSING_HASH",
    "E_STRAY_GHERKIN",
    "W_BC_UNASSIGNED",
    "W_ORIGIN_UNRESOLVED",
)


def _producer_wire_hash(block_text: str) -> str:
    """Reproduce the producer/wire hash (`scenarios hash`) for a scenario's OWN
    block, neutralizing the v0.3.1 comment-folding artifact.

    The producer/wire hash the corpus is pinned to is the BLOCK-ONLY
    canonicalization of the scenario's own block (`scenarios hash` /
    scenarios.outstanding.parse_then_block_only_hash): per-line whitespace
    stripped, blank lines dropped, and every tag line (`@...`) dropped. Because
    the ONLY thing the folding defect adds to a preceding block is a trailing
    inter-scenario COMMENT line (the next scenario's `@`-tag lines are already
    dropped by the block-only rule), this recompute ALSO drops `#` comment
    lines: the result equals the producer/wire hash for a comment-adjacent
    block and equals the ordinary block-only hash for a clean block, so a
    genuine body drift (which changes step text) still recomputes to a
    divergent value and is not masked.
    """
    import hashlib

    canonical: list[str] = []
    for line in block_text.splitlines():
        s = line.strip()
        if not s or s.startswith("@") or s.startswith("#"):
            continue
        canonical.append(s)
    return hashlib.sha256("\n".join(canonical).encode("utf-8")).hexdigest()[:16]


def _transitional_marker_codes(feature_text: str) -> list[str]:
    """Return the transitional-marker codes a changed feature file carries.

    The @bc:unassigned / @origin:unresolved transitional markers are surfaced
    by the v0.3.1 AGGREGATE gate (W_BC_UNASSIGNED / W_ORIGIN_UNRESOLVED) but
    NOT by per-file `scenarios validate` (which treats them as legal
    placeholders). Since the changed-feature gate runs per-file, it detects the
    markers directly from the tag text so an added/modified scenario that still
    carries a transitional placeholder is refused (the cutover forbids a
    non-conformant scenario merging).
    """
    codes: list[str] = []
    tokens = set()
    for line in feature_text.splitlines():
        s = line.strip()
        if not s.startswith("@"):
            continue
        for tok in s.split():
            tokens.add(tok)
    if "@bc:unassigned" in tokens:
        codes.append("W_BC_UNASSIGNED")
    if "@origin:unresolved" in tokens:
        codes.append("W_ORIGIN_UNRESOLVED")
    return codes


def _real_hash_mismatches(feature_text: str) -> list[tuple[str, str, str]]:
    """Return the REAL stale-tag mismatches in a feature file, cross-checked
    against the producer/wire hash.

    For every scenario block carrying an @scenario_hash tag, recompute the
    producer/wire hash from the on-disk block; a block whose on-disk tag does
    NOT reproduce the producer is a real stale mismatch. A comment-folding
    false-positive (on-disk tag DOES reproduce the producer) is NOT returned.
    Each entry is (scenario_title, on_disk_hash, recomputed_hash).
    """
    real: list[tuple[str, str, str]] = []
    for block_text, carried in _scenario_blocks(feature_text):
        if carried is None:
            continue
        recomputed = _producer_wire_hash(block_text)
        if recomputed != carried:
            real.append((_scenario_title(block_text), carried, recomputed))
    return real


def _changed_feature_files(repo: Path, work_id: str) -> list[Path]:
    """The feature files under features/ this work_id's commit(s) added or
    modified, as reachable on origin/main.

    Enumerated from the work_id-attributed commit history on origin/main (the
    canonical word-boundary attribution shared with Check 2), scoped to paths
    under features/ ending in .feature / .gherkin, and filtered to those still
    present in the working tree — Check 1 guarantees the working tree's
    deliverable paths equal origin/main, so validating the working-tree file is
    equivalent to validating the as-committed origin/main text.
    """
    log = _git(
        repo,
        "log",
        "origin/main",
        *_work_id_attribution_grep(work_id),
        "--name-only",
        "--pretty=format:",
    )
    names: set[str] = set()
    for line in log.stdout.splitlines():
        p = line.strip()
        if not p.startswith("features/"):
            continue
        if p.endswith(".feature") or p.endswith(".gherkin"):
            names.add(p)
    return [repo / n for n in sorted(names) if (repo / n).exists()]


def _validate_feature_codes(
    feature_path: Path,
    manifest_path: str | None,
    origin_index: str | None,
    scenarios_cmd: tuple[str, ...] = ("scenarios",),
) -> list[str]:
    """Run v0.3.1 `scenarios validate --json` over one feature file and return
    the list of violation rule codes it reports (empty when conformant)."""
    cmd = [*scenarios_cmd, "validate", "--json"]
    if manifest_path is not None:
        cmd += ["--manifest", manifest_path]
    if origin_index is not None:
        cmd += ["--origin-index", origin_index]
    cmd.append(str(feature_path))
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode == 0:
        return []
    try:
        diagnostic = json.loads(proc.stdout or "{}")
    except json.JSONDecodeError:
        # A non-zero exit with no parseable JSON diagnostic is itself a genuine
        # failure to validate — surface it as an opaque code so the gate refuses
        # rather than silently passing.
        return ["E_VALIDATE_FAILED"]
    return list(diagnostic.get("violations", []))


def check_changed_features_conformant(
    repo: Path,
    work_id: str,
    *,
    changed_files: list[Path] | None = None,
    manifest_path: str | None = None,
    origin_index: str | None = None,
    scenarios_cmd: tuple[str, ...] = ("scenarios",),
) -> None:
    """Changed-feature schema-conformity gate (ADR-042).

    Over the CHANGED / ADDED feature files this work_id touched under features/,
    run the v0.3.1 per-file `scenarios validate` schema gate and REFUSE the
    emit when any added/modified scenario is GENUINELY non-conformant —
    E_UNKNOWN_BC, E_UNKNOWN_ORIGIN, E_UNKNOWN_SERVICE, E_MISSING_HASH,
    E_STRAY_GHERKIN, W_BC_UNASSIGNED, W_ORIGIN_UNRESOLVED, or a REAL hash
    mismatch (the on-disk @scenario_hash does not reproduce the producer/wire
    hash for the block).

    The gate does NOT refuse solely on a validator E_HASH_MISMATCH whose block's
    on-disk tag already reproduces the producer/wire hash — that is the known
    v0.3.1 comment-folding validator defect, not a real mismatch. This composes
    with Check 1-3 as an ADDITIONAL arm; it never weakens them.

    `changed_files` (defaulting to the work_id-attributed features/ diff on
    origin/main) and `manifest_path` / `origin_index` (defaulting to the BC's
    repo-root bc-manifest.yaml and the provisioned .scenarios/origin-index) are
    injectable so tests can drive crafted changed-file sets against fixture
    resolution roots.
    """
    if changed_files is None:
        changed_files = _changed_feature_files(repo, work_id)
    if not changed_files:
        # Nothing changed under features/ — nothing to validate (a non-scenario
        # / flat-maintenance emit is unaffected).
        return

    if manifest_path is None:
        m = repo / "bc-manifest.yaml"
        manifest_path = str(m) if m.is_file() else None
    if origin_index is None:
        oi = repo / ".scenarios" / "origin-index"
        origin_index = str(oi) if oi.is_file() else None

    # GRACEFUL DEGRADATION (matches the bin/doctor coherence check): the @bc /
    # @origin schema gate resolves against a LAUNCHER-PROVISIONED manifest. A
    # shop with no provisioned bc-manifest.yaml cannot resolve the legal @bc /
    # @origin sets, so the per-file schema gate has nothing authoritative to
    # validate against; skip rather than false-refuse. A real launched BC
    # carries a repo-root bc-manifest.yaml, so the gate runs there.
    if manifest_path is None:
        return

    offenders: list[str] = []
    for fpath in changed_files:
        p = Path(fpath)
        # A legacy .gherkin added/modified under features/ is itself the
        # E_STRAY_GHERKIN non-conformance (the corpus must be all .feature).
        if p.suffix == ".gherkin":
            offenders.append(
                f"{p.name}: E_STRAY_GHERKIN (a legacy .gherkin file was "
                "added/modified under features/; migrate it to .feature)"
            )
            continue

        file_text = p.read_text()
        codes = _validate_feature_codes(p, manifest_path, origin_index, scenarios_cmd)
        # Transitional markers (@bc:unassigned / @origin:unresolved) are
        # aggregate-only in v0.3.1; detect them directly for the per-file gate.
        codes = codes + _transitional_marker_codes(file_text)
        if not codes:
            continue

        genuine = [c for c in codes if c in _GENUINE_VALIDATE_CODES]
        if "E_HASH_MISMATCH" in codes:
            # Producer cross-check: only REAL stale tags refuse; the
            # comment-folding false-positive (on-disk tag == producer) does not.
            real = _real_hash_mismatches(file_text)
            if real:
                for title, on_disk, recomputed in real:
                    genuine.append(
                        f"E_HASH_MISMATCH (scenario {title!r}: on-disk "
                        f"@scenario_hash {on_disk} does not reproduce the "
                        f"producer/wire hash {recomputed})"
                    )
            # else: the validator's E_HASH_MISMATCH is the v0.3.1
            # comment-folding false-positive — NOT a refusal cause.

        if genuine:
            offenders.append(f"{p.name}: {', '.join(genuine)}")

    if offenders:
        listed = "\n".join(offenders)
        raise PreconditionRefusal(
            "refused: the changed-feature schema-conformity gate (ADR-042) "
            f"failed for work_id {work_id}. One or more feature files this "
            "work_id added or modified under features/ carry a GENUINE "
            "non-conformance per the v0.3.1 `scenarios validate` schema gate — "
            "so a work_done(complete) that merges a non-conformant scenario is "
            "refused. A validator E_HASH_MISMATCH whose on-disk @scenario_hash "
            "already reproduces the producer/wire hash is treated as the known "
            "v0.3.1 comment-folding false-positive and does NOT refuse; only "
            "GENUINE non-conformance below does:\n"
            f"{listed}\n{_SELF_RESOLVE}"
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
        # assigned set (the --scenario-hash set the emit carries) and SOURCE-FRESH
        # (scenario 227): evaluated against the FETCHED origin/main tree, NOT the
        # possibly-lagging local checkout, mirroring Check 2's fetch/reachability
        # posture. A scenario reconciled on origin/main but stale only in a
        # lagging local working tree does not false-refuse; a scenario genuinely
        # stale on origin/main still refuses.
        check_scenario_hashes(
            repo,
            args.work_id,
            list(args.scenario_hash or []),
            feature_texts=fetch_origin_main_feature_texts(repo),
        )
        # Changed-feature schema-conformity gate (ADR-042) — over the feature
        # files this work_id added/modified under features/, refuse a COMPLETE
        # emit that merges a GENUINELY non-conformant scenario (per the v0.3.1
        # `scenarios validate` schema gate), with the producer cross-check guard
        # against the v0.3.1 comment-folding E_HASH_MISMATCH false-positive.
        # Scoped to --status complete: a blocked emit is not a merge of
        # completed work. Composes with Check 1-3; never weakens them.
        if args.status == "complete":
            check_changed_features_conformant(repo, args.work_id)
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
