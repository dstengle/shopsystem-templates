"""bc-emit — executable pre-emit wrapper over the work-done gate.

`bc-emit work-done` is the EXECUTABLE form of the work-done-gate skill
(currently prose at templates/skills/work-done-gate/SKILL.md). It runs the
BC-side preconditions and, only when they all pass, invokes the real
`shop-msg respond work_done` primitive. On any precondition refusal it exits
non-zero, prints a named-cause error that directs the BC to SELF-RESOLVE its
own bead/commit/working-tree state and re-invoke the wrapper, and does NOT
invoke `shop-msg respond`.

Preconditions (lead-m56e):

  Check 1 — clean working tree (hash 242c4de927d64339)
      `git status --porcelain` must be empty AFTER discounting the ambient
      carve-outs `.specstory`, `.claude/scheduled_tasks.lock`, and
      `.beads/issues.jsonl`. A tree whose only porcelain entries are those
      carve-outs is treated as clean. Any other modified or untracked path
      refuses the emit, naming each offending path verbatim.

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

  Check 3 — scenario-hash match (hash ea9c1bbd9be87d72)
      Recompute each candidate scenario hash by delegating IN-PROCESS to
      `scenarios.hash.compute_scenario_hash` using scenario-BLOCK-ONLY
      canonicalization (the enclosing `Feature:` header line is NOT part of
      the hashed text). Compare the recomputed set against the payload's
      `--scenario-hash` set; classify any divergent member as stale
      (carried hash whose recompute differs), missing (a features/-present
      dispatched scenario block with no carried hash), or orphan (a carried
      hash matching no features/ block). On divergence the error names the
      precondition, the classification, the affected hash value, and the
      scenario. The recompute uses ONLY the block-only delegate, never the
      Feature-line-included canonicalization carried on the wire.

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

# Ambient artifacts that are NOT BC work product: a working tree whose only
# `git status --porcelain` entries are these is treated as clean. Matched
# against the porcelain PATH (the bytes after the 2-char status + space, with
# any rename "old -> new" reduced to the new path).
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


def _is_carved_out(path: str) -> bool:
    """Return True iff a porcelain path is an ambient carve-out.

    A path is carved out when it equals a carve-out entry exactly, OR when it
    lives under a carve-out treated as a directory prefix (e.g. an untracked
    file ".specstory/2026/log.md" under the ".specstory" carve-out). The two
    file-specific carve-outs (".claude/scheduled_tasks.lock",
    ".beads/issues.jsonl") match exactly; ".specstory" additionally covers its
    whole subtree.
    """
    normalized = path.rstrip("/")
    for carve in _CARVE_OUTS:
        if normalized == carve or normalized.startswith(carve + "/"):
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
    """Check 1 — clean working tree, discounting the ambient carve-outs.

    Refuses (raising PreconditionRefusal) when any porcelain entry names a
    path that is NOT one of the carve-outs, listing each offending path
    verbatim. A tree whose only entries are carve-outs proceeds.
    """
    # `-uall` lists untracked files individually rather than collapsing them
    # to a parent directory entry (e.g. "?? .beads/"), so a carved-out path
    # like ".beads/issues.jsonl" appears verbatim and is matched as a
    # carve-out rather than refusing the whole ".beads/" directory.
    result = _git(repo, "status", "--porcelain", "-uall")
    offending: list[str] = []
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        path = _porcelain_path(line)
        if _is_carved_out(path):
            continue
        # The full porcelain line is the verbatim evidence the scenario
        # asks for ("as git status --porcelain reported it").
        offending.append(line)
    if offending:
        paths = "\n".join(offending)
        raise PreconditionRefusal(
            "refused: the clean-working-tree precondition failed. The BC "
            "working tree carries modified or untracked paths that are not "
            "the ambient carve-outs (.specstory, .claude/scheduled_tasks.lock, "
            ".beads/issues.jsonl). Offending paths, verbatim from "
            f"`git status --porcelain`:\n{paths}\n{_SELF_RESOLVE}"
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
    repo: Path, payload_hashes: list[str]
) -> None:
    """Check 3 — scenario-hash match via block-only in-process recompute.

    Recomputes each scenario block under features/ with the BLOCK-ONLY
    canonical hash (scenarios.hash.compute_scenario_hash; the Feature header
    is excluded). Compares the recomputed set against the payload's
    --scenario-hash set and classifies any divergent member:

      stale   — a block carries an @scenario_hash tag whose recompute differs
                from the carried value (the body drifted under the pinned tag).
      missing — a features/-present scenario block whose recomputed hash is in
                neither the payload nor carried-and-matching, i.e. a dispatched
                scenario block with no carried hash echoed in the payload.
      orphan  — a payload hash matching no recomputed scenario block under
                features/.

    On any divergence: raise PreconditionRefusal naming the precondition, the
    classification, the affected hash value, and the scenario.
    """
    # Lazy import (lead-ld7i / tmpl-20n): scenarios is only needed on this
    # work-done hash-check path, so it is imported here rather than at module
    # top level. This keeps `bc-emit --help` and other subcommands working even
    # when the `scenarios` package is not installed; the VCS dependency
    # declared in pyproject guarantees resolution for this path in real
    # installs.
    from scenarios.hash import compute_scenario_hash

    features_dir = repo / "features"
    recomputed: dict[str, str] = {}  # recomputed_hash -> scenario title
    feature_files = (
        sorted(features_dir.glob("*.feature"))
        if features_dir.is_dir()
        else []
    )
    for fpath in feature_files:
        text = fpath.read_text()
        for block_text, carried in _scenario_blocks(text):
            recompute = compute_scenario_hash(block_text)
            title = _scenario_title(block_text)
            recomputed.setdefault(recompute, title)
            # stale: the block carries a hash that no longer matches its body.
            if carried is not None and carried != recompute:
                raise PreconditionRefusal(
                    "refused: the scenario_hashes-match precondition failed "
                    "(classification: STALE). The scenario block "
                    f"{title!r} in {fpath.name} carries @scenario_hash "
                    f"{carried} but its scenario-block-only recompute is "
                    f"{recompute}. (Recomputed in-process via "
                    "scenarios.hash.compute_scenario_hash, the block-only "
                    "canonicalization — never the Feature-line-included wire "
                    f"form.) {_SELF_RESOLVE}"
                )

    payload_set = list(payload_hashes)
    # orphan: a payload hash with no matching recomputed block.
    for h in payload_set:
        if h not in recomputed:
            raise PreconditionRefusal(
                "refused: the scenario_hashes-match precondition failed "
                "(classification: ORPHAN). The payload --scenario-hash "
                f"{h} matches no scenario block under features/ when "
                "recomputed via scenarios.hash.compute_scenario_hash "
                "(block-only canonicalization, never the Feature-line wire "
                f"form). {_SELF_RESOLVE}"
            )
    # missing: a features/-present recomputed scenario hash not echoed in the
    # payload (a dispatched scenario block with no carried hash in the
    # payload set).
    payload_lookup = set(payload_set)
    for recompute, title in recomputed.items():
        if recompute not in payload_lookup:
            raise PreconditionRefusal(
                "refused: the scenario_hashes-match precondition failed "
                "(classification: MISSING). The scenario block "
                f"{title!r} is present under features/ with recomputed "
                f"scenario-block-only hash {recompute} (via "
                "scenarios.hash.compute_scenario_hash) but that hash is "
                "absent from the payload --scenario-hash set. "
                f"{_SELF_RESOLVE}"
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
        # Check 3 — scenario-hash match (block-only recompute).
        check_scenario_hashes(repo, list(args.scenario_hash or []))
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
