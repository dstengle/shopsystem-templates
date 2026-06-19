"""bc-emit work_id->commit attribution: word-boundary (whole-token) matching.

PRE-STATE (the defect; lead-8vwf): both attribution sites in
`src/shop_templates/bc_emit.py` recognize a commit as attributable to a
work_id with a LOOSE SUBSTRING grep:

    git log <ref> --grep=<work_id> --fixed-strings

`--fixed-strings` matches the work_id anywhere in the subject/body as a raw
substring. A work_id that is a STRICT PREFIX of another commit's work_id
therefore false-positive-attributes the wrong commit's lineage. Concretely:
a commit carrying `(work_id: lead-8vwf)` is wrongly recognized as attributable
to the dispatched work_id `lead-8v`, because `lead-8v` is a substring of
`lead-8vwf`.

THE FIX (additive tightening, nothing retired): replace substring containment
with exact / WORD-BOUNDARY TOKEN matching — the work_id must appear as a WHOLE
TOKEN (bounded by start/end-of-line or non-identifier characters) in the
commit subject/body. A strict-prefix work_id must NO LONGER match, while an
exact whole-token occurrence still does. The SAME tightening applies to both
attribution sites so the bc-emit wrapper and the shared work-done-gate
attribution helper stay consistent:

  - `check_commit_reachable` — commit-mode attribution over origin/main.
  - `check_tag_reachable`    — tag-mode attribution over a tag's lineage.

The origin/main reachability GATE itself (scenario hashes 461d6066ef7dca0a
commit-mode and 12c98d2f7e5259a9 tag-mode) is UNCHANGED — this only sharpens
HOW a commit is recognized as attributable.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

# Import the two attribution sites under test directly.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from shop_templates import bc_emit  # noqa: E402


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    r = subprocess.run(["git", *args], cwd=str(repo), capture_output=True, text=True)
    if r.returncode != 0:
        raise AssertionError(f"git {' '.join(args)} failed in {repo}: {r.stderr}\n{r.stdout}")
    return r


def _init_bare_origin_and_clone(tmp_path: Path) -> tuple[Path, Path]:
    origin = tmp_path / "origin.git"
    subprocess.run(
        ["git", "init", "--bare", "-q", "-b", "main", str(origin)],
        check=True, capture_output=True,
    )
    clone = tmp_path / "bc"
    seed = tmp_path / "seed"
    subprocess.run(["git", "init", "-q", "-b", "main", str(seed)], check=True, capture_output=True)
    _git(seed, "config", "user.email", "t@t.io")
    _git(seed, "config", "user.name", "t")
    (seed / "README.md").write_text("seed\n")
    _git(seed, "add", "README.md")
    _git(seed, "commit", "-q", "-m", "seed: initial commit")
    _git(seed, "remote", "add", "origin", str(origin))
    _git(seed, "push", "-q", "origin", "main")
    subprocess.run(["git", "clone", "-q", str(origin), str(clone)], check=True, capture_output=True)
    _git(clone, "config", "user.email", "t@t.io")
    _git(clone, "config", "user.name", "t")
    return clone, origin


# --------------------------------------------------------------------------
# Commit-mode attribution (check_commit_reachable)
# --------------------------------------------------------------------------

def test_commit_mode_strict_prefix_work_id_does_not_false_match(tmp_path: Path) -> None:
    """A strict-prefix work_id (`lead-8v`) must NOT be attributed to a commit
    that only carries the LONGER work_id (`lead-8vwf`).

    Under the old `--grep=<work_id> --fixed-strings` substring check, `lead-8v`
    is a substring of `lead-8vwf` and the gate wrongly PASSES (no refusal). The
    word-boundary tightening makes it REFUSE, because `lead-8v` does not appear
    as a whole token in the commit message.
    """
    clone, _origin = _init_bare_origin_and_clone(tmp_path)
    # Only a commit for the LONGER work_id exists on origin/main.
    (clone / "f.txt").write_text("body\n")
    _git(clone, "add", "f.txt")
    _git(clone, "commit", "-q", "-m", "feat: thing (work_id: lead-8vwf)")
    _git(clone, "push", "-q", "origin", "main")
    _git(clone, "fetch", "-q", "origin")

    # The dispatched work_id is the strict PREFIX. No commit is genuinely
    # attributable to it, so the gate must REFUSE.
    with pytest.raises(bc_emit.PreconditionRefusal):
        bc_emit.check_commit_reachable(clone, "lead-8v")


def test_commit_mode_exact_whole_token_still_matches(tmp_path: Path) -> None:
    """The tightening must not regress the genuine case: an EXACT whole-token
    occurrence of the work_id in a commit reachable from origin/main still
    satisfies the precondition (no refusal)."""
    clone, _origin = _init_bare_origin_and_clone(tmp_path)
    (clone / "f.txt").write_text("body\n")
    _git(clone, "add", "f.txt")
    _git(clone, "commit", "-q", "-m", "feat: thing (work_id: lead-8vwf)")
    _git(clone, "push", "-q", "origin", "main")
    _git(clone, "fetch", "-q", "origin")

    # Exact whole-token match -> satisfied (returns without raising).
    bc_emit.check_commit_reachable(clone, "lead-8vwf")


# --------------------------------------------------------------------------
# Tag-mode attribution (check_tag_reachable)
# --------------------------------------------------------------------------

def test_tag_mode_strict_prefix_work_id_does_not_false_match(tmp_path: Path) -> None:
    """A strict-prefix work_id must NOT be attributed to a tag whose lineage
    only carries the LONGER work_id. Old substring check wrongly satisfies;
    word-boundary check refuses (naming the tag-lineage-anchors-work_id
    precondition)."""
    clone, _origin = _init_bare_origin_and_clone(tmp_path)
    (clone / "r.txt").write_text("release\n")
    _git(clone, "add", "r.txt")
    _git(clone, "commit", "-q", "-m", "feat: release (work_id: lead-8vwf)")
    _git(clone, "push", "-q", "origin", "main")
    _git(clone, "tag", "v0.1.0")
    _git(clone, "push", "-q", "origin", "v0.1.0")
    _git(clone, "fetch", "-q", "origin", "--tags")

    with pytest.raises(bc_emit.PreconditionRefusal):
        bc_emit.check_tag_reachable(clone, "lead-8v", "v0.1.0")


def test_tag_mode_exact_whole_token_still_matches(tmp_path: Path) -> None:
    """An EXACT whole-token work_id in the tag's lineage still satisfies."""
    clone, _origin = _init_bare_origin_and_clone(tmp_path)
    (clone / "r.txt").write_text("release\n")
    _git(clone, "add", "r.txt")
    _git(clone, "commit", "-q", "-m", "feat: release (work_id: lead-8vwf)")
    _git(clone, "push", "-q", "origin", "main")
    _git(clone, "tag", "v0.1.0")
    _git(clone, "push", "-q", "origin", "v0.1.0")
    _git(clone, "fetch", "-q", "origin", "--tags")

    # Exact whole-token match -> satisfied (returns without raising).
    bc_emit.check_tag_reachable(clone, "lead-8vwf", "v0.1.0")
