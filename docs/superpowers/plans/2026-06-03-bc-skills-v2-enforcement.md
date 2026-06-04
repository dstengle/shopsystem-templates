# BC skills v2 — orchestration + observable-artifact enforcement

> **For agentic workers:** Tracker of record is beads (epic `shopsystem-templates-a73`). Branch `experimental/superpowers-bc-skills`.

**Goal:** Make the plan/TDD discipline actually run and be *provable*, by (1) having the router orchestrate the implementer per bd sub-issue with dependency-ordered, parallel-where-unblocked dispatch, (2) granting subagents the `Skill` tool and requiring they invoke the procedure skill, and (3) gating `work_done` on observable artifacts (bd sub-issues incl. an explicit failing-test sub-issue; a `test(red)` commit preceding its `feat(green)` commit).

**Why:** PR#1 live test — contract ran, but no bd sub-issues for the plan and no test-first evidence. Root cause: subagents have no `Skill` tool (so "Skills I load" is inert) and the only required evidence was passing scenarios.

**Architecture:** Router (main BC agent, has `Skill` + Task tools) decomposes via `writing-plans-bdd` into a bd sub-issue DAG, dispatches ready sub-issues in parallel to `bc-implementer` subagents (each invokes `test-driven-development` via the now-granted `Skill` tool, RED→GREEN→REFACTOR with staged commits), gates between dependency layers on artifacts, then dispatches `bc-reviewer` which blocks `work_done` unless the artifacts exist.

---

## Task 1 — Grant `Skill` tool + require invocation (subagent templates)

**Files:** `src/shop_templates/templates/bc-implementer.md`, `src/shop_templates/templates/bc-reviewer.md`

- [ ] Change the `tools:` frontmatter on BOTH to: `tools: Read, Edit, Write, Bash, Grep, Glob, Skill`.
- [ ] Replace the passive "## Skills I load" list with an explicit, ordered **"## FIRST ACTION"** directive: invoke the procedure skill via the `Skill` tool and follow it step-by-step. For `bc-implementer` (now a **per-sub-issue worker**): "Invoke the `test-driven-development` skill and execute its RED→GREEN→REFACTOR loop for the single bd sub-issue named in your dispatch; commit each stage with the staged-commit convention; close your sub-issue; do NOT emit `work_done`." For `bc-reviewer`: "Invoke `bc-review` then `work-done-gate` via the `Skill` tool, in that order."
- [ ] bc-implementer scope shrinks to ONE behavior/sub-issue (the router calls it once per ready sub-issue). Keep the "never emits scenario work_done" + BC-root + mechanism-observation content.

## Task 2 — `writing-plans-bdd`: dependency DAG + explicit failing-test sub-issue + parallel markers

**Files:** `src/shop_templates/templates/skills/writing-plans-bdd/SKILL.md`

- [ ] Require the plan to create, per behavior, AT LEAST these bd sub-issues with a dependency edge: a **"write failing test for <behavior>"** sub-issue (RED) that **blocks** its **"implement <behavior>"** sub-issue (GREEN). Use `bd create` + `bd dep add <green> <red>`.
- [ ] Require encoding **cross-behavior dependencies** as `bd dep` edges so the DAG is explicit.
- [ ] State the **parallel-dispatch rule**: sub-issues with no open blockers (`bd ready`) at the same layer are dispatched together; the router fans them out in parallel.
- [ ] Keep: no plan document; the assigned Gherkin scenario(s) are the outer-loop proof; decomposition must not change what `work_done` proves.

## Task 3 — `subagent-driven-development`: router's dependency-ordered parallel dispatch loop

**Files:** `src/shop_templates/templates/skills/subagent-driven-development/SKILL.md`

- [ ] Describe the loop: `bd ready` → dispatch ALL ready sub-issues **in parallel** to `bc-implementer` subagents → wait → **gate**: verify each dispatched sub-issue is closed AND its `test(red)` commit precedes its `feat(green)` commit → repeat until the DAG is drained → integrate → dispatch reviewer.
- [ ] State that independent sub-issues are dispatched concurrently; dependent ones wait for their blockers to close (the gate between layers).
- [ ] Keep: implementer never emits scenario `work_done`.

## Task 4 — Staged-commit convention (`integrating-to-main` + procedure skills)

**Files:** `src/shop_templates/templates/skills/integrating-to-main/SKILL.md`, `test-driven-development/SKILL.md`

- [ ] Define the convention: `test(red): <behavior>` (failing test committed first), then `feat(green): <behavior>` (minimal impl), then optional `refactor: <behavior>`. Commit frequently — one RED + one GREEN per behavior minimum.
- [ ] `integrating-to-main`: when integrating the work branch, the squash/merge **commit body must enumerate the staged commits** (so the test-first sequence survives the squash). The reviewer reads the *branch* history (pre-squash) for the gate.

## Task 5 — `work-done-gate` + `bc-review`: observable-artifact gate

**Files:** `src/shop_templates/templates/skills/work-done-gate/SKILL.md`, `bc-review/SKILL.md`

- [ ] Add **Check 4 — plan artifact**: bd sub-issues exist for the work_id and are closed; at least one is an explicit failing-test (RED) sub-issue. Absent → `work_done --status blocked --summary "no bd plan sub-issues for <work_id>"`.
- [ ] Add **Check 5 — test-first artifact**: for each behavior, a `test(red):` commit precedes its `feat(green):` commit in the work-branch history (verify via `git log`). Absent → `--status blocked --summary "no test-first commit sequence for <behavior>"`.
- [ ] `bc-review`: instruct the reviewer to run Checks 4–5 as part of the gate (it invokes `work-done-gate`).

## Task 6 — `bc-router`: wire the orchestration procedure

**Files:** `src/shop_templates/templates/skills/bc-router/SKILL.md`

- [ ] After sufficiency passes and the worktree is set up: invoke `writing-plans-bdd` (creates the DAG), then run the `subagent-driven-development` dispatch loop (parallel ready sub-issues, gate between layers), then `integrating-to-main`, then dispatch `bc-reviewer`.
- [ ] Note the router uses the `Skill` and Task/Agent tools; it still does not write src/tests/features itself.

## Task 7 — Tier-2 guardrails for v2

**Files:** `tests/test_skills.py`

- [ ] `Skill` appears in the implementer/reviewer template `tools:` lines (read templates via `_read_template`).
- [ ] `writing-plans-bdd` mentions an explicit failing-test sub-issue + `bd dep` + parallel dispatch.
- [ ] `subagent-driven-development` mentions parallel dispatch + a gate between dependency layers.
- [ ] `work-done-gate` mentions the plan-artifact check and the `test(red)`/`feat(green)` ordering check.
- [ ] `integrating-to-main` mentions the staged-commit convention surviving the squash.
- [ ] Full suite: 11 pre-existing failures unchanged; new guardrails pass.

## Commit convention for THIS work

Frequent staged commits: `test(red): …` before `feat(green): …` where Python is involved (Task 7 tests precede any cli changes — though v2 is mostly skill/template content). For content tasks, commit per skill with `Refs: shopsystem-templates-a73`.

## Self-review
- Skill-tool grant → T1. Failing-test sub-issue + DAG + parallel → T2. Router dispatch loop + gate → T3/T6. Staged commits + squash body → T4. Artifact gate (plan + test-first) → T5. Guardrails → T7. ✔
- Honest limitation restated: determinism comes from router orchestration + artifact gating, not subagent goodwill.
