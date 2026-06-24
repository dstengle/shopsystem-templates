"""Pins the skills package-data surface and its content guardrails."""
import pytest
from shop_templates.cli import (
    iter_skill_files,
    iter_lead_skill_files,
    _mirror_skills,
    _read_template,
    read_gitignore_template,
)


# ---------------------------------------------------------------------------
# lead-1e8d (supersede scenario 159, hash d29c551ef3f58dc9): skills-dir
# pruning must be scoped to canonical-managed members ONLY. _mirror_skills
# previously removed ANY file/dir under .claude/skills/ not in the shipped
# set, over-pruning legitimate experimentally-adopted PM skill dirs
# (problem-framing-canvas, jobs-to-be-done, ...). Architect option (b): a
# .claude/skills/<name>/ dir is pruned IFF <name> is a canonical-managed
# member; non-members survive byte-for-byte.
# ---------------------------------------------------------------------------

def test_mirror_skills_prunes_only_canonical_managed_members(tmp_path):
    """_mirror_skills must never remove a .claude/skills/<name>/ directory
    whose <name> is not a canonical-managed member. An experimentally-adopted
    unmanaged skill dir must survive byte-for-byte across a mirror."""
    skills_root = tmp_path / ".claude" / "skills"
    skills_root.mkdir(parents=True)

    # Seed an unmanaged, experimentally-adopted skill dir whose name is NOT a
    # member of the lead skill-group being mirrored.
    members = {
        rel.split("/", 1)[0]
        for rel, _ in iter_lead_skill_files()
    }
    assert "problem-framing-canvas" not in members, (
        "test premise broken: problem-framing-canvas is now a managed member"
    )
    unmanaged_dir = skills_root / "problem-framing-canvas"
    unmanaged_dir.mkdir()
    unmanaged_body = b"# problem-framing-canvas\n\nexperimental PM skill\n"
    (unmanaged_dir / "SKILL.md").write_bytes(unmanaged_body)

    # Mirror the canonical LEAD skill-group into the same root.
    _mirror_skills(tmp_path, iter_lead_skill_files)

    # The managed members are present...
    for name in members:
        assert (skills_root / name / "SKILL.md").is_file(), (
            f"managed member {name!r} missing after mirror"
        )
    # ...and the unmanaged dir survived byte-for-byte (the over-prune bug).
    survivor = unmanaged_dir / "SKILL.md"
    assert survivor.is_file(), (
        "unmanaged skill dir problem-framing-canvas/ was over-pruned by "
        "_mirror_skills; pruning is not scoped to canonical-managed members"
    )
    assert survivor.read_bytes() == unmanaged_body, (
        "unmanaged skill content was not preserved byte-for-byte"
    )


def test_iter_skill_files_yields_relative_paths_and_bytes():
    files = dict(iter_skill_files())
    assert "test-driven-development/SKILL.md" in files
    for rel, body in files.items():
        assert not rel.startswith("/")
        assert "\\" not in rel
        assert isinstance(body, bytes) and len(body) > 0


def _skill(name):
    files = dict(iter_skill_files())
    return files[f"{name}/SKILL.md"].decode()


# bc-router classifies all three message types and names the gate paths
ROUTER_PINS = ["assign_scenarios", "request_maintenance", "request_bugfix",
               "shop-msg", "watch", "clarify", "reviewer"]


@pytest.mark.parametrize("needle", ROUTER_PINS)
def test_bc_router_pins(needle):
    assert needle.lower() in _skill("bc-router").lower()


def test_tdd_is_mandatory_and_clarify_only_exception():
    body = _skill("test-driven-development").lower()
    assert "mandatory" in body
    assert "clarify" in body  # the only exception path routes to the lead


def test_work_done_gate_carries_three_checks():
    body = _skill("work-done-gate").lower()
    assert "git status --porcelain" in body
    assert "origin/main" in body
    assert "scenario_hash" in body or "scenarios hash" in body


def test_writing_plans_is_beads_backed_no_doc():
    body = _skill("writing-plans-bdd").lower()
    assert "bd " in body or "beads" in body
    assert "no plan document" in body or "no doc" in body


def test_implementer_not_the_gate_reviewer_sole_emitter():
    # subagent-driven-development must tell the implementer it never emits
    # work_done for scenario work:
    sdd = _skill("subagent-driven-development").lower()
    assert "never emits `work_done`" in sdd or "never emits work_done" in sdd
    # bc-review must name the reviewer as the SOLE emitter for scenario work:
    assert "sole" in _skill("bc-review").lower()


def test_work_done_uses_repeatable_scenario_hash_flag_not_comma_joined():
    """Guard against the invalid `--scenario-hashes "<a>,<b>"` spelling.
    The CLI takes a repeatable singular `--scenario-hash` flag."""
    for name in ("bc-review", "work-done-gate"):
        assert "--scenario-hashes" not in _skill(name), (
            f"{name} uses the invalid plural flag"
        )
    assert "--scenario-hash" in _skill("bc-review")


def test_subagents_grant_skill_tool():
    for name in ("bc-implementer", "bc-reviewer"):
        body = _read_template(name)
        # the tools: frontmatter line must include Skill
        tools_line = next(l for l in body.splitlines() if l.strip().startswith("tools:"))
        assert "Skill" in tools_line, f"{name} tools line lacks Skill: {tools_line!r}"


def test_writing_plans_bdd_has_failing_test_subissue_and_deps_and_parallel():
    body = _skill("writing-plans-bdd").lower()
    assert "failing test" in body
    assert "bd dep" in body
    assert "parallel" in body


def test_subagent_driven_development_describes_parallel_and_gate():
    body = _skill("subagent-driven-development").lower()
    assert "parallel" in body
    assert "gate" in body or "between" in body and "layer" in body


def test_bc_emit_wrapper_pointer_replaces_retired_precondition_prose():
    """lead-62sy: scenarios 105-116 (prose pins of the clean-tree /
    commit-on-origin-main / scenario-hash-match preconditions) are RETIRED in
    favor of the landed bc-emit work-done wrapper (scenarios 176-181). Both
    role templates must carry the one-line bc-emit pointer prose instead."""
    pointer_tokens = [
        "bc-emit work-done wrapper enforces these preconditions",
        "clean working tree",
        "committed on origin/main",
        "scenario-hash match",
        "176-181",
        "do not check these manually",
        "--force",
    ]
    for role in ("bc-reviewer", "bc-implementer"):
        # Normalize whitespace: markdown line-wrapping of the pointer prose is
        # cosmetic and must not defeat the content check.
        low = " ".join(_read_template(role).lower().split())
        for tok in pointer_tokens:
            assert " ".join(tok.lower().split()) in low, (
                f"{role} template missing bc-emit pointer token {tok!r}"
            )


def test_retired_prose_precondition_scenarios_absent_wrapper_scenarios_present():
    """lead-62sy: the 12 retired prose-precondition scenarios (105-116) must be
    gone from features/ (no scenario block recomputes to their canonical
    block-only hash), while the 6 surviving bc-emit wrapper scenarios (176-181)
    remain. Uses the same block-only recompute the wrapper itself applies, so a
    stale on-disk tag cannot mask a still-present block."""
    import pathlib
    from shop_templates.bc_emit import _scenario_blocks
    from scenarios.hash import compute_scenario_hash

    feat_dir = pathlib.Path(__file__).resolve().parent.parent / "features"
    recomputed = set()
    for f in sorted(feat_dir.glob("*.feature")):
        for block, _carried in _scenario_blocks(f.read_text()):
            recomputed.add(compute_scenario_hash(block))

    retired = {
        # 105-108 lead-cw7 clean-tree (bc-reviewer)
        "03df7848f78f3bed", "304dec007a39b56b", "29e754e4122b9333", "0c4b28c02212d454",
        # 109-112 lead-8lm clean-tree + commit-on-origin-main (bc-implementer)
        "3c4a039dc12f9e72", "d1a890b937181543", "e98d72015796afbe", "bb41b17b6ebd0c81",
        # 113-116 lead-83l scenario-hash-match (bc-reviewer)
        "418f41d9a7789ca1", "a176ea1af49b5fa0", "f312990bd1d5ca44", "83614a2765bd73ab",
    }
    surviving = {
        # 176-181 bc-emit work-done wrapper (the durable coverage)
        "242c4de927d64339", "461d6066ef7dca0a", "12c98d2f7e5259a9",
        "ea9c1bbd9be87d72", "4a6133f7b5f061a2", "f81ee56bc163934b",
    }
    leaked = retired & recomputed
    assert not leaked, f"retired prose-precondition scenarios still present: {sorted(leaked)}"
    missing = surviving - recomputed
    assert not missing, f"surviving bc-emit wrapper scenarios disappeared: {sorted(missing)}"


def test_work_done_gate_check1_exempts_ambient_carveouts():
    """lead-20bt: Check 1 (clean working tree) must EXEMPT the same ambient
    carve-outs the executable bc-emit wrapper already discounts
    (.beads/issues.jsonl, .specstory, .claude/scheduled_tasks.lock). Without
    this, Check 4 closes the work_id plan bead — which writes
    .beads/issues.jsonl into the tree — and Check 1 then refuses on that very
    write, deadlocking the gate. The prose must agree with the wrapper."""
    body = _skill("work-done-gate")
    for carve in (".beads/issues.jsonl", ".specstory", ".claude/scheduled_tasks.lock"):
        assert carve in body, (
            f"work-done-gate Check 1 does not name the ambient carve-out {carve!r}; "
            "the prose still blocks on any porcelain output and deadlocks Check 4"
        )
    low = body.lower()
    assert "carve-out" in low or "carved-out" in low or "carve out" in low, (
        "work-done-gate does not describe an ambient carve-out exemption for Check 1"
    )


def test_work_done_gate_has_plan_and_test_first_artifact_checks():
    body = _skill("work-done-gate").lower()
    assert "sub-issue" in body or "sub-issues" in body  # plan artifact
    assert "test(red)" in body and "feat(green)" in body  # test-first ordering


def test_integrating_to_main_staged_commits_survive_squash():
    body = _skill("integrating-to-main").lower()
    assert "test(red)" in body and "feat(green)" in body
    assert "squash" in body


# ---------------------------------------------------------------------------
# lead-ajc9: per-work_id worktrees must live INSIDE the BC root / /workspace.
# The ../worktrees/<id> convention is the PARENT of /workspace, OUTSIDE the
# container bind-mount, and trips a hard Claude-Code permission wall even in
# bypass mode. The corrected placement is .worktrees/<work_id> in-root.
# ---------------------------------------------------------------------------

def test_using_git_worktrees_never_names_parent_worktrees_path():
    """The skill must not place worktrees at ../worktrees/<id> — that is the
    PARENT of /workspace, outside the container bind-mount."""
    body = _skill("using-git-worktrees")
    assert "../worktrees" not in body, (
        "using-git-worktrees still names the out-of-root ../worktrees path"
    )


def test_using_git_worktrees_names_in_root_worktrees_path():
    """The skill must name the in-root .worktrees/<work_id> placement."""
    body = _skill("using-git-worktrees")
    assert ".worktrees/<work_id>" in body, (
        "using-git-worktrees does not name the in-root .worktrees/<work_id> path"
    )


def test_using_git_worktrees_boundary_prose_forbids_adjacent_paths():
    """The boundary prose must no longer permit a parent/adjacent path; the
    'adjacent to' framing was the bug (../worktrees is the parent dir)."""
    body = _skill("using-git-worktrees").lower()
    assert "adjacent to" not in body, (
        "boundary prose still permits an 'adjacent to' (parent/outside) path"
    )


def test_using_git_worktrees_carries_container_rationale():
    """The skill must carry the rationale: containerized BCs cannot write
    outside /workspace (the worktree placement keeps writes in the bind-mount)."""
    body = _skill("using-git-worktrees").lower()
    assert "/workspace" in body, (
        "using-git-worktrees lacks the /workspace container rationale"
    )


def test_gitignore_template_lists_worktrees_dir():
    """A freshly-bootstrapped BC must gitignore .worktrees/ so the isolated
    per-work_id worktree does not pollute the main checkout."""
    body = read_gitignore_template()
    assert ".worktrees/" in body, (
        "gitignore.template does not list .worktrees/"
    )


def test_gitignore_template_ignores_env_but_keeps_example_tracked():
    """Cold-walkthrough GAP-1 (lead-7if5): INSTALL Step 2 states emphatically
    that .env (holding AGENT_VAULT_MASTER_PASSWORD, later AGENT_VAULT_TOKEN /
    owner secrets) is gitignored and must never be committed. The rendered
    .gitignore must honor that claim: ignore the bare .env file and .env.*
    secret variants, while keeping the shipped .env.example scaffold TRACKED
    via a `!.env.example` negation so `cp .env.example .env` still works."""
    body = read_gitignore_template()
    lines = [ln.strip() for ln in body.splitlines()]
    assert ".env" in lines, "gitignore.template does not ignore the bare .env"
    assert ".env.*" in lines, (
        "gitignore.template does not ignore .env.* secret variants"
    )
    assert "!.env.example" in lines, (
        "gitignore.template lacks the !.env.example negation that keeps the "
        "shipped scaffold tracked"
    )
    # Negation ordering is load-bearing: .env.* must precede !.env.example so
    # the re-include actually un-ignores the scaffold.
    assert lines.index(".env.*") < lines.index("!.env.example"), (
        "!.env.example negation must come AFTER .env.* to re-include the "
        "scaffold"
    )


def test_bootstrapped_repo_ignores_env_keeps_example_and_preserves_entries(
    tmp_path,
):
    """Behavioral pin (lead-7if5 acceptance pin 2): in a freshly-bootstrapped
    product git repo, `git check-ignore .env` matches a .gitignore rule
    (exit 0) while `git check-ignore .env.example` does NOT match (exit 1 —
    the scaffold stays tracked). Also confirms every pre-existing .gitignore
    entry survives (acceptance pin 3)."""
    import argparse
    import subprocess

    from shop_templates.cli import _cmd_bootstrap

    target = tmp_path / "product"
    target.mkdir()
    subprocess.run(
        ["git", "init", "-q"], cwd=str(target), check=True
    )

    rc = _cmd_bootstrap(
        argparse.Namespace(
            shop_type="bc",
            shop_name="example-bc",
            target=str(target),
        )
    )
    assert rc == 0, f"bootstrap returned non-zero exit {rc}"

    gitignore = target / ".gitignore"
    assert gitignore.is_file(), "bootstrap did not write a .gitignore"

    # .env is ignored (exit 0 == matched).
    env_check = subprocess.run(
        ["git", "check-ignore", "-v", ".env"],
        cwd=str(target),
        capture_output=True,
        text=True,
    )
    assert env_check.returncode == 0, (
        f".env is NOT git-ignored in the bootstrapped repo; "
        f"check-ignore stdout={env_check.stdout!r} stderr={env_check.stderr!r}"
    )

    # .env.example is NOT ignored (exit 1 == not matched) — stays tracked.
    example_check = subprocess.run(
        ["git", "check-ignore", ".env.example"],
        cwd=str(target),
        capture_output=True,
        text=True,
    )
    assert example_check.returncode == 1, (
        ".env.example must stay tracked (not matched by any ignore rule), "
        f"but check-ignore matched it: stdout={example_check.stdout!r}"
    )

    # All pre-existing entries preserved (acceptance pin 3).
    body = gitignore.read_text()
    for entry in (
        "__pycache__/",
        "*.py[cod]",
        ".dolt/",
        "*.db",
        ".beads-credential-key",
        "/inbox/",
        "/outbox/",
        ".worktrees/",
    ):
        assert entry in body, (
            f"pre-existing .gitignore entry {entry!r} was dropped"
        )
