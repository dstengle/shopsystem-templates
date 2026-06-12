"""Pins the skills package-data surface and its content guardrails."""
import pytest
from shop_templates.cli import (
    iter_skill_files,
    _read_template,
    read_gitignore_template,
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
