# BC superpowers-style skill architecture — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. **Tracker of record is beads** (epic `shopsystem-templates-8he`); the checkboxes here are an execution aid, not a substitute for `bd update`/`bd close`.

**Goal:** Replace the flat-prose BC role prompts with composable superpowers-style skills, driven by a top-level `bc-router` skill and executed via subagent-driven development with mandatory TDD, while preserving the lead↔BC wire contract.

**Architecture:** A `bc-router` skill (loaded by the main BC agent) classifies inbound `shop-msg` messages and dispatches to two thin bias-shim subagents (`bc-implementer`, `bc-reviewer`) that compose vendored, adapted skills. Skills are package data under `src/shop_templates/templates/skills/` and are poured into a BC's `.claude/skills/` by the `shop-templates` CLI. The `.claude/skills/` tree is fully canonical-managed (mirror semantics).

**Tech Stack:** Python 3.10+ stdlib (`argparse`, `importlib.resources`, `pathlib`, `shutil`, `subprocess`), pytest + pytest-bdd, Gherkin feature files, beads (`bd`).

**Spec:** `docs/superpowers/specs/2026-06-03-bc-superpowers-skills-design.md`

---

## File Structure

**Created:**
- `src/shop_templates/templates/skills/bc-router/SKILL.md` — top-level loop
- `src/shop_templates/templates/skills/bc-sufficiency-check/SKILL.md` — clarify-vs-proceed
- `src/shop_templates/templates/skills/writing-plans-bdd/SKILL.md` — beads-backed planning
- `src/shop_templates/templates/skills/subagent-driven-development/SKILL.md`
- `src/shop_templates/templates/skills/using-git-worktrees/SKILL.md`
- `src/shop_templates/templates/skills/integrating-to-main/SKILL.md`
- `src/shop_templates/templates/skills/bc-review/SKILL.md`
- `src/shop_templates/templates/skills/work-done-gate/SKILL.md`
- `features/cli_pours_skills_on_bootstrap.feature`
- `features/cli_repours_skills_on_update.feature`
- `features/bc_skill_set_content.feature` — Tier-2 content guardrails
- `tests/test_skills.py` — Tier-2 content assertions (mirrors `test_templates.py`)

**Modified:**
- `src/shop_templates/templates/skills/test-driven-development/SKILL.md` — make TDD mandatory
- `src/shop_templates/cli.py` — skill accessors + pour on bootstrap/update
- `src/shop_templates/templates/bc-implementer.md` — shrink to bias-shim
- `src/shop_templates/templates/bc-reviewer.md` — shrink to bias-shim
- `.claude/canonical/bc-primer.md` — router-first wording (+ shipped `templates/claude/bc.md` body if it carries operating-model prose)
- `tests/conftest.py` — step defs for the new CLI feature files
- `pyproject.toml` — confirm `templates/skills/**/*` package-data glob (already present)

**Skill-set decision:** for now skill-pouring applies to **bc** shops only. Lead shops pour no skills (the per-shop-type skill set is the deferred open question in the spec). Update therefore only mirrors `.claude/skills/` when `shop_type == "bc"`.

---

## Phase A — CLI pours skills (TDD, real code)

> beads: `kup` (Tier-1 scenarios) then `8nr` (CLI impl). Claim `kup`, then `8nr`.

### Task A1: Skill package-data accessor — iterate shipped skill files

**Files:**
- Modify: `src/shop_templates/cli.py`
- Test: `tests/test_skills.py` (Create)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_skills.py
"""Pins the skills package-data surface and its content guardrails."""
from shop_templates.cli import iter_skill_files


def test_iter_skill_files_yields_relative_paths_and_bytes():
    files = dict(iter_skill_files())
    # Every shipped skill exposes a SKILL.md at <skill-name>/SKILL.md
    assert "test-driven-development/SKILL.md" in files
    assert "bc-router/SKILL.md" in files
    # Values are bytes, non-empty, and POSIX-relative (no leading slash)
    for rel, body in files.items():
        assert not rel.startswith("/")
        assert "\\" not in rel  # POSIX separators only
        assert isinstance(body, bytes) and len(body) > 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_skills.py::test_iter_skill_files_yields_relative_paths_and_bytes -v`
Expected: FAIL — `ImportError: cannot import name 'iter_skill_files'`

> Note: `bc-router/SKILL.md` does not exist yet (authored in Phase B). To keep Phase A self-contained, this test asserts only `test-driven-development/SKILL.md` until Phase B lands; add the `bc-router` assertion in Phase E. For the first RED, drop the `bc-router` line, then re-add it in Task E1.

- [ ] **Step 3: Write minimal implementation**

```python
# src/shop_templates/cli.py  (add near the other accessors)
_SKILLS_PKG = "shop_templates.templates.skills"


def iter_skill_files():
    """Yield (relative_posix_path, content_bytes) for every file under the
    skills package-data tree, recursively.

    The relative path is rooted at templates/skills/ (e.g.
    "test-driven-development/SKILL.md"). Served from importlib.resources
    package data — never read from a filesystem path under the working dir.
    """
    root = files(_SKILLS_PKG)

    def _walk(node, prefix):
        for child in node.iterdir():
            rel = f"{prefix}{child.name}" if prefix == "" else f"{prefix}/{child.name}"
            if child.is_dir():
                yield from _walk(child, rel)
            elif child.is_file():
                yield rel, child.read_bytes()

    yield from _walk(root, "")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_skills.py::test_iter_skill_files_yields_relative_paths_and_bytes -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/shop_templates/cli.py tests/test_skills.py
git commit -m "feat(cli): iter_skill_files() accessor over skills package data

Refs: shopsystem-templates-8nr"
```

---

### Task A2: bootstrap pours skills into `<target>/.claude/skills/` (bc only)

**Files:**
- Modify: `src/shop_templates/cli.py:_cmd_bootstrap`
- Create: `features/cli_pours_skills_on_bootstrap.feature`
- Modify: `tests/conftest.py`

- [ ] **Step 1: Write the failing scenario**

```gherkin
# features/cli_pours_skills_on_bootstrap.feature
Feature: shop-templates bootstrap pours canonical skills into a BC

  @bc:shopsystem-templates
  Scenario: bootstrapping a bc shop pours every skill file under .claude/skills byte-for-byte
    Given an existing git repository at a target directory "/tmp/skills-bc-shop"
    When I bootstrap a "bc" shop named "skills-bc-shop" at "/tmp/skills-bc-shop"
    Then the exit code of the bootstrap invocation is 0
    And every shipped skill file appears under ".claude/skills/" in the target byte-for-byte

  @bc:shopsystem-templates
  Scenario: bootstrapping a lead shop pours no skills
    Given an existing git repository at a target directory "/tmp/skills-lead-shop"
    When I bootstrap a "lead" shop named "skills-lead-shop" at "/tmp/skills-lead-shop"
    Then the exit code of the bootstrap invocation is 0
    And the target directory contains no ".claude/skills/" directory
```

- [ ] **Step 2: Write the step defs**

```python
# tests/conftest.py  (append; reuse existing given for the target repo)
from shop_templates.cli import iter_skill_files


@when(parsers.parse('I bootstrap a "{shop_type}" shop named "{name}" at "{target}"'))
def when_bootstrap_shop(shop_type, name, target, context, tmp_path):
    ws = context["bootstrap_workspace"]
    context["bootstrap_result"] = _run_shop_templates_with_bd_shim(
        ["bootstrap", "--shop-type", shop_type, "--shop-name", name,
         "--target", str(ws)],
        context, tmp_path,
    )


@then("every shipped skill file appears under \".claude/skills/\" in the target byte-for-byte")
def then_skills_poured(context):
    ws = Path(context["bootstrap_workspace"])
    for rel, body in iter_skill_files():
        dest = ws / ".claude" / "skills" / rel
        assert dest.exists(), f"missing poured skill file: {rel}"
        assert dest.read_bytes() == body, f"skill file content drift: {rel}"


@then(parsers.parse('the target directory contains no ".claude/skills/" directory'))
def then_no_skills_dir(context):
    ws = Path(context["bootstrap_workspace"])
    assert not (ws / ".claude" / "skills").exists()
```

> If `@then("the exit code of the bootstrap invocation is 0")` and the target-repo `given` already exist in conftest (they do — line ~6975 / ~2730), reuse them; do not redefine.

- [ ] **Step 3: Run to verify it fails**

Run: `python3 -m pytest "tests/test_features.py" -k "skills into a BC or pours no skills" -v`
Expected: FAIL — bc scenario fails at `then_skills_poured` (no `.claude/skills/` poured)

- [ ] **Step 4: Implement the pour in bootstrap**

```python
# src/shop_templates/cli.py — add helper near _render_lead_ops_scaffolding
def _pour_skills(target: Path) -> None:
    """Mirror the skills package-data tree into <target>/.claude/skills/.

    The .claude/skills/ tree is fully canonical-managed.
    """
    skills_root = target / ".claude" / "skills"
    for rel, body in iter_skill_files():
        dest = skills_root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(body)
```

```python
# in _cmd_bootstrap, after the settings.json pour and before _bd_init_in:
    # Pour canonical skills (bc shops only for now; per-type sets deferred).
    if shop_type == "bc":
        _pour_skills(target)
```

- [ ] **Step 5: Run to verify it passes**

Run: `python3 -m pytest "tests/test_features.py" -k "skills into a BC or pours no skills" -v`
Expected: PASS (both scenarios)

- [ ] **Step 6: Full suite + commit**

Run: `python3 -m pytest tests/ -q`
Expected: no NEW failures (pre-existing transition failures from Phase F may not exist yet; suite should be green here)

```bash
git add src/shop_templates/cli.py features/cli_pours_skills_on_bootstrap.feature tests/conftest.py
git commit -m "feat(cli): bootstrap pours canonical skills into BC .claude/skills/

Refs: shopsystem-templates-8nr"
```

---

### Task A3: update mirrors skills (idempotent; removes managed-but-removed; bc only)

**Files:**
- Modify: `src/shop_templates/cli.py:_cmd_update`
- Create: `features/cli_repours_skills_on_update.feature`
- Modify: `tests/conftest.py`

- [ ] **Step 1: Write the failing scenarios**

```gherkin
# features/cli_repours_skills_on_update.feature
Feature: shop-templates update mirrors canonical skills into a BC

  @bc:shopsystem-templates
  Scenario: update re-pours a drifted skill file to canonical bytes
    Given a bootstrapped "bc" shop at a target directory "/tmp/upd-skills-bc"
    And the skill file ".claude/skills/test-driven-development/SKILL.md" has drifted to "STALE"
    When I run update for shop type "bc" at "/tmp/upd-skills-bc"
    Then the exit code of the update invocation is 0
    And every shipped skill file appears under ".claude/skills/" in the target byte-for-byte

  @bc:shopsystem-templates
  Scenario: update leaves an already-current skill file byte-and-mtime unchanged
    Given a bootstrapped "bc" shop at a target directory "/tmp/upd-skills-idem"
    When I record the mtime of ".claude/skills/test-driven-development/SKILL.md"
    And I run update for shop type "bc" at "/tmp/upd-skills-idem"
    Then the exit code of the update invocation is 0
    And the mtime of ".claude/skills/test-driven-development/SKILL.md" is unchanged

  @bc:shopsystem-templates
  Scenario: update removes a managed skill file that the package no longer ships
    Given a bootstrapped "bc" shop at a target directory "/tmp/upd-skills-orphan"
    And an extra file ".claude/skills/removed-skill/SKILL.md" exists in the target
    When I run update for shop type "bc" at "/tmp/upd-skills-orphan"
    Then the exit code of the update invocation is 0
    And the target directory contains no file at ".claude/skills/removed-skill/SKILL.md"
```

- [ ] **Step 2: Write the step defs**

```python
# tests/conftest.py  (append)
@given(parsers.parse('a bootstrapped "{shop_type}" shop at a target directory "{target}"'))
def given_bootstrapped_shop(shop_type, target, context, tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=ws, check=True)
    context["bootstrap_workspace"] = ws
    res = _run_shop_templates_with_bd_shim(
        ["bootstrap", "--shop-type", shop_type, "--shop-name", "probe-shop",
         "--target", str(ws)],
        context, tmp_path,
    )
    assert res.returncode == 0, res.stderr


@given(parsers.parse('the skill file "{rel}" has drifted to "{text}"'))
def given_skill_drifted(rel, text, context):
    p = Path(context["bootstrap_workspace"]) / rel
    p.write_text(text)


@given(parsers.parse('an extra file "{rel}" exists in the target'))
def given_extra_file(rel, context):
    p = Path(context["bootstrap_workspace"]) / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("orphan")


@when(parsers.parse('I record the mtime of "{rel}"'))
def when_record_mtime(rel, context):
    p = Path(context["bootstrap_workspace"]) / rel
    context.setdefault("mtimes", {})[rel] = p.stat().st_mtime_ns


@when(parsers.parse('I run update for shop type "{shop_type}" at "{target}"'))
def when_run_update(shop_type, target, context):
    from shop_templates.cli import _cmd_update
    import argparse
    ws = context["bootstrap_workspace"]
    ns = argparse.Namespace(target=str(ws), shop_type=shop_type)
    context["update_rc"] = _cmd_update(ns)


@then("the exit code of the update invocation is 0")
def then_update_rc_zero(context):
    assert context["update_rc"] == 0


@then(parsers.parse('the mtime of "{rel}" is unchanged'))
def then_mtime_unchanged(rel, context):
    p = Path(context["bootstrap_workspace"]) / rel
    assert p.stat().st_mtime_ns == context["mtimes"][rel]


@then(parsers.parse('the target directory contains no file at "{rel}"'))
def then_no_file(rel, context):
    assert not (Path(context["bootstrap_workspace"]) / rel).exists()
```

- [ ] **Step 3: Run to verify it fails**

Run: `python3 -m pytest tests/test_features.py -k "skill file or skill file that the package" -v`
Expected: FAIL — drifted file not re-poured; orphan not removed

- [ ] **Step 4: Implement the mirror in update**

```python
# src/shop_templates/cli.py — add helper
def _mirror_skills(target: Path) -> None:
    """Mirror the skills package-data tree into <target>/.claude/skills/:
    re-pour drifted/missing files (leaving byte+mtime unchanged when
    already current) and remove managed files no longer shipped.
    """
    skills_root = target / ".claude" / "skills"
    shipped = dict(iter_skill_files())

    # 1) re-pour (idempotent on byte-equality)
    for rel, body in shipped.items():
        dest = skills_root / rel
        if dest.exists() and dest.read_bytes() == body:
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(body)

    # 2) remove managed-but-removed files
    if skills_root.exists():
        shipped_abs = {skills_root / rel for rel in shipped}
        for path in sorted(skills_root.rglob("*")):
            if path.is_file() and path not in shipped_abs:
                path.unlink()
        # prune now-empty dirs
        for path in sorted(skills_root.rglob("*"), reverse=True):
            if path.is_dir() and not any(path.iterdir()):
                path.rmdir()
```

```python
# in _cmd_update, after the canonical-primer re-pour (Step 5) and before the
# name.md drift advisory (Step 6):
    # Step 5b: mirror canonical skills (bc shops only for now).
    if shop_type == "bc":
        _mirror_skills(target)
```

- [ ] **Step 5: Run to verify it passes**

Run: `python3 -m pytest tests/test_features.py -k "skill file or skill file that the package" -v`
Expected: PASS (all three scenarios)

- [ ] **Step 6: Full suite + commit**

Run: `python3 -m pytest tests/ -q`
Expected: green

```bash
git add src/shop_templates/cli.py features/cli_repours_skills_on_update.feature tests/conftest.py
git commit -m "feat(cli): update mirrors canonical skills (idempotent + prune)

Refs: shopsystem-templates-8nr"
```

- [ ] **Step 7: Close beads**

```bash
bd close shopsystem-templates-kup shopsystem-templates-8nr --reason="CLI pours+mirrors skills; Tier-1 scenarios green"
```

---

## Phase B — Author the BC skill set

> beads: `yk4`. Claim it. Each skill below is one bd sub-issue (see Task B0). Content is pinned later by Phase E; author each skill to satisfy the **Required content** bullets, which ARE the Tier-2 assertions.

### Task B0: Create one bd sub-issue per skill

- [ ] **Step 1: Create sub-issues**

```bash
for s in bc-router bc-sufficiency-check writing-plans-bdd test-driven-development-mandatory subagent-driven-development using-git-worktrees integrating-to-main bc-review work-done-gate; do
  bd create --title="skill: $s" --type=task --priority=2 \
    --description="Author/adapt templates/skills/$s/SKILL.md per plan Phase B; content pinned by Phase E (5i4)." >/dev/null
done
# Wire each as parent-child under yk4 (use bd dep add --file as in the epic wiring).
```

### Task B1: `bc-router/SKILL.md` (new)

**Files:** Create `src/shop_templates/templates/skills/bc-router/SKILL.md`

**Required content (Tier-2 pins):**
- Frontmatter `name: bc-router`, `description:` naming inbound-message routing.
- Names the intake boundary: `shop-msg pending`, `shop-msg read`, and arming the **Monitor** on `shop-msg watch` (never direct mailbox storage).
- A classification table mapping each `message_type` to its path:
  - `assign_scenarios` → implementer then **reviewer gates** `work_done`
  - `request_bugfix` with non-empty `scenarios` → same as `assign_scenarios`
  - `request_bugfix` with empty `scenarios` → implementer emits `work_done`
  - `request_maintenance` → implementer emits `work_done`
- States: run `bc-sufficiency-check` BEFORE dispatch; on failure emit `shop-msg respond clarify` and stop.
- States: set up a worktree/branch (delegates to `using-git-worktrees`) before dispatching implementation.
- States: the `mechanism_observation` channel is available on every path.
- Explicitly: the router does NOT itself write `src/`, tests, or features — it dispatches.

- [ ] Author the file to satisfy every bullet above.
- [ ] Commit: `git commit -m "feat(skill): bc-router top-level routing skill\n\nRefs: shopsystem-templates-yk4"`

### Task B2: `bc-sufficiency-check/SKILL.md` (new, extracted from current role prose)

**Required content (Tier-2 pins):** the three per-type sufficiency checks lifted from today's `bc-implementer.md` —
- `request_maintenance`: acceptance criteria present, measurable, define outcome-not-just-constraint, description specifies the thing.
- `assign_scenarios`: well-formed Gherkin (Given/When/Then), concrete steps, `@scenario_hash:` tag present, fits-existing-capability probe.
- `request_bugfix`: concrete description + (if `scenarios` non-empty) each passes the `assign_scenarios` check.
- The **anti-rationalization** and **over-asking guards** (both directions), preserved from today's template.

- [ ] Author; lift and condense the existing sections (do not lose the bidirectional guards).
- [ ] Commit (Refs: yk4).

### Task B3: `test-driven-development/SKILL.md` (modify → mandatory)

**Required content (Tier-2 pins):**
- Keep the existing Iron Law, RED-GREEN-REFACTOR, two-loops framing.
- Remove the self-granted exception language; the ONLY exception path is "emit `clarify` to the lead and await the decision."
- Add an explicit "mandatory in this BC — not optional" statement near the top.

- [ ] Edit the existing file; keep the `@testing-anti-patterns.md` reference and the companion file.
- [ ] Commit (Refs: yk4).

### Task B4: `writing-plans-bdd/SKILL.md` (new, adapted from superpowers writing-plans)

**Required content (Tier-2 pins):**
- Plan lives in **beads as sub-issues** of the work's lead bead — explicitly "no plan document."
- One bd sub-issue per behavior; each behavior is implemented via TDD inner loop.
- The assigned Gherkin scenario(s) are the BDD **outer loop**; decomposition must not change what `work_done` proves.
- References `bd create` / `bd dep add` (parent-child) idiom.

- [ ] Author. Explicitly contrast with upstream writing-plans (no `docs/.../plans/*.md` for BC runtime work).
- [ ] Commit (Refs: yk4).

### Task B5: `subagent-driven-development/SKILL.md` (new, adapted)

**Required content (Tier-2 pins):** per-sub-issue execution loop with context isolation; mandatory TDD per behavior; how the implementer dispatches/works each bd sub-issue; never emits `work_done` for scenario work.

- [ ] Author. Commit (Refs: yk4).

### Task B6: `using-git-worktrees/SKILL.md` (new, adapted)

**Required content (Tier-2 pins):** isolate the dispatch's work in a worktree/branch named for the work_id; operate only inside the BC root; hand back to `integrating-to-main` before the gate.

- [ ] Author. Commit (Refs: yk4).

### Task B7: `integrating-to-main/SKILL.md` (new, from finishing-a-development-branch)

**Required content (Tier-2 pins):**
- Merge the work branch into the BC's **main** and **push** so the work_id commit is reachable from `origin/main`.
- Commit subject/body must carry the `work_id` (attribution mechanism the gate checks).
- Explicitly: "BC role discipline does not push" is NOT a reason to skip this — pushing is part of the work.

- [ ] Author. Commit (Refs: yk4).

### Task B8: `bc-review/SKILL.md` (new, adversarial)

**Required content (Tier-2 pins):** re-run BDD; adversarial probes (faithful-vs-shortcut, unpinned adjacent cases, step-def failure modes); outcomes = sign-off / scenario-gap `clarify` / implementation-gap `work_done(blocked)`.

- [ ] Author. Commit (Refs: yk4).

### Task B9: `work-done-gate/SKILL.md` (new, from verification-before-completion + pre-emit steps)

**Required content (Tier-2 pins):** the three pre-emit checks verbatim in intent —
1. clean working tree (`git status --porcelain`),
2. work_id commit reachable from `origin/main` (with `git fetch origin` first),
3. scenario_hash integrity (ADR-010): recompute via `scenarios hash` + presence via `git grep`; subset rule.
- Each failure converts `--status complete` → `--status blocked` with named evidence.

- [ ] Author. Commit (Refs: yk4).

- [ ] **Close beads:** `bd close <each B-sub-issue>` then `bd close shopsystem-templates-yk4`.

---

## Phase C — Role templates become thin bias-shims

> beads: `eyn` (depends on yk4). Claim it.

### Task C1: Rewrite `bc-implementer.md`

**Files:** Modify `src/shop_templates/templates/bc-implementer.md`

**Required content (Tier-2 pins):**
- Frontmatter keeps `name: bc-implementer`; ADD `model:` field (commented or set to a default tier; selectable).
- Bias statement: *make the assigned behavior real via TDD; you are not the gate.*
- A "Skills I load" list naming: `bc-sufficiency-check`, `writing-plans-bdd`, `subagent-driven-development`, `test-driven-development`, `using-git-worktrees`, `integrating-to-main`.
- Retains: "never emit `work_done` for scenario work — hand off to the Reviewer"; `mechanism_observation` carve-outs; BC-root-only.
- Drops the long inline pre-emit prose (now in `work-done-gate`) EXCEPT for the implementer-emitted paths (`request_maintenance` / empty-scenario bugfix), which reference `work-done-gate`.

- [ ] Rewrite. Target ≤ ~120 lines.
- [ ] Commit (Refs: eyn).

### Task C2: Rewrite `bc-reviewer.md`

**Required content (Tier-2 pins):**
- Frontmatter keeps `name: bc-reviewer`; ADD `model:` field.
- Bias: adversarial gate; sole emitter of scenario `work_done`.
- "Skills I load": `bc-review`, `work-done-gate`.
- Retains the Outcomes triad and `mechanism_observation` carve-outs.

- [ ] Rewrite. Target ≤ ~90 lines.
- [ ] Commit (Refs: eyn). Then `bd close shopsystem-templates-eyn`.

---

## Phase D — Router-first primer / CLAUDE wording

> beads: `6g6` (depends on yk4). Claim it.

### Task D1: Update `.claude/canonical/bc-primer.md`

**Files:** Modify `.claude/canonical/bc-primer.md` (this repo's copy) and, if it carries operating-model prose, `src/shop_templates/templates/claude/bc.md`.

**Required content (Tier-2 pins):**
- "Who you are" describes the router-first model: the main agent loads `bc-router` and dispatches to `bc-implementer`/`bc-reviewer` subagents.
- Session-start still: `shop-msg prime`, `bd prime`, arm the Monitor on `shop-msg watch` — now framed as the `bc-router` skill's responsibility.
- Note skills live under `.claude/skills/` (poured by `shop-templates update`).

- [ ] Edit. Keep the do/don't and beads-discipline sections.
- [ ] Commit (Refs: 6g6). Then `bd close shopsystem-templates-6g6`.

---

## Phase E — Tier-2 content guardrails

> beads: `5i4` (depends on yk4). Claim it.

### Task E1: Parametrized content assertions in `tests/test_skills.py`

**Files:** Modify `tests/test_skills.py`

- [ ] **Step 1: Add semantic content tests (not literal-header).** For each skill, assert the load-bearing substrings from its "Required content" bullets are present. Example:

```python
import pytest
from shop_templates.cli import iter_skill_files


def _skill(name):
    files = dict(iter_skill_files())
    return files[f"{name}/SKILL.md"].decode()


ROUTER_PINS = ["assign_scenarios", "request_maintenance", "request_bugfix",
               "shop-msg", "watch", "clarify", "reviewer"]


@pytest.mark.parametrize("needle", ROUTER_PINS)
def test_bc_router_pins(needle):
    assert needle.lower() in _skill("bc-router").lower()


def test_tdd_is_mandatory_and_clarify_only_exception():
    body = _skill("test-driven-development").lower()
    assert "mandatory" in body
    assert "clarify" in body  # exceptions route to the lead, not self-granted


def test_work_done_gate_carries_three_checks():
    body = _skill("work-done-gate").lower()
    assert "git status --porcelain" in body
    assert "origin/main" in body
    assert "scenario_hash" in body or "scenarios hash" in body


def test_writing_plans_is_beads_backed_no_doc():
    body = _skill("writing-plans-bdd").lower()
    assert "bd " in body or "beads" in body
    assert "no plan document" in body or "no doc" in body
```

- [ ] **Step 2: Run** — Expected: PASS once Phase B skills exist. If any fail, fix the skill content (Phase B), not the test.
- [ ] **Step 3: Add a feature-file mirror** `features/bc_skill_set_content.feature` only if a Gherkin-visible guardrail is wanted; otherwise the `tests/test_skills.py` assertions suffice (matches `test_templates.py` precedent).
- [ ] **Step 4: Commit** (Refs: 5i4). Then `bd close shopsystem-templates-5i4`.

---

## Phase F — Transition handling for old scenarios

> beads: `qcw`. Claim it. Decision from spec: **keep both during transition.**

### Task F1: Mark old structure-pinning tests as expected-failures

**Files:** Modify `tests/test_templates.py`; annotate the obsolete `features/*` (sections, cli_naming, prose pre_emit).

- [ ] **Step 1:** In `tests/test_templates.py`, update `BC_IMPLEMENTER_REQUIRED_SECTIONS` / `BC_REVIEWER_REQUIRED_SECTIONS` — wrap the now-removed-section params with `pytest.param(..., marks=pytest.mark.xfail(reason="bc-shim refactor; see shopsystem-templates-qcw", strict=False))`. Do NOT delete yet.
- [ ] **Step 2:** For obsolete feature files that now fail (e.g. `bc_implementer_sections.feature`), add a leading `@xfail_transition` tag and register a `pytest.mark.xfail` for that tag in `conftest.py`, OR move them to `features/_transition/` (excluded from `test_features.py`'s glob — confirm the glob is `features/*.feature` so a subdir is naturally excluded). Prefer the subdir move; it keeps the file as a visible diff without red.
- [ ] **Step 3: Run full suite** — `python3 -m pytest tests/ -q` — Expected: green (xfails counted, no hard failures).
- [ ] **Step 4: Commit** (Refs: qcw). Then `bd close shopsystem-templates-qcw`.

---

## Self-Review (run before execution)

**Spec coverage:**
- Router skill → B1. Sufficiency → B2. Mandatory TDD → B3. Beads-backed plans → B4. SDD → B5. Worktrees → B6. Integrate-to-main (BC pushes) → B7. Adversarial review → B8. Work-done-gate (3 checks) → B9. Role shims + `model:` → C1/C2. Router-first primer → D1. CLI pour+mirror → A2/A3. Accessor → A1. Tier-1 scenarios → A2/A3. Tier-2 guardrails → E1. Keep-both transition → F1. ✔ all spec sections mapped.

**Placeholder scan:** CLI tasks carry complete code. Skill-authoring tasks carry concrete required-content bullets that are the literal Tier-2 assertions — actionable, not "TBD." ✔

**Type consistency:** `iter_skill_files()` (A1) is the single accessor used by `_pour_skills` (A2), `_mirror_skills` (A3), and `tests/test_skills.py` (E1). `context["bootstrap_workspace"]` is the shared target-dir key matching existing conftest fixtures. `_run_shop_templates_with_bd_shim(args, context, tmp_path)` signature matches conftest line ~2664. ✔

**Known wrinkle to verify during execution:** confirm `test_features.py` globs `features/*.feature` (non-recursive) so a `features/_transition/` subdir is excluded — Task F1 depends on it. If the glob is recursive, use the `@xfail_transition` tag approach instead.
