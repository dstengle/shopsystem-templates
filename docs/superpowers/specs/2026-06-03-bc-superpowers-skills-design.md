# BC superpowers-style skill architecture — design

**Date:** 2026-06-03
**Branch:** `experimental/superpowers-bc-skills`
**Status:** Approved design, pre-implementation
**Scope:** BC role templates only (`bc-implementer`, `bc-reviewer`). Lead
templates (`lead-po`, `lead-architect`) are explicitly out of scope.

## Problem

The BC role prompts shipped by `shopsystem-templates` are long, flat prose
(the `bc-implementer` template is ~475 lines). Discipline is duplicated across
roles, hard to maintain, and impossible to recompose or to target with
different models. A precedent for a better shape already exists: commit
`f3c577f` "baked" the superpowers `test-driven-development` skill in as package
data and referenced it from `bc-implementer.md` — but there is no mechanism to
actually land skills in a BC's `.claude/skills/`, so the bake is inert.

## Goal

Refactor the BC operating model into **composable, superpowers-style skills**
drawn from (and adapted from) `https://github.com/dstengle/superpowers`, driven
by a **top-level router skill**, executed through **subagent-driven development
with mandatory TDD**, while **preserving the existing wire contract** with the
lead shop: accept messages → work until done → emit `work_done`.

Secondary goal: make it possible to point implementation subagents at different
models (the ability, not an assumption of cheaper models at first).

## Non-goals

- No changes to lead templates.
- No `brainstorming` skill in a BC — work arrives pre-specified from the lead.
- No change to the message schema or the `shop-msg` CLI surface.
- Not attempting to relax the `origin/main` reachability contract.

## Architecture

### Operating model: router-skill-first

The main BC agent loads a **`bc-router`** skill at session start. The router
owns the whole loop: Monitor / `shop-msg` intake, message-type classification,
sufficiency triage, workspace setup, dispatch to role subagents, and the
outbox-emission decision per contract.

The two roles stay as **subagents** (`.claude/agents/bc-implementer.md`,
`bc-reviewer.md`) but shrink to thin, **bias-carrying shims** that compose the
shared skills. The subagent boundary is retained deliberately: it gives each
role an overall bias (implementer = make it real; reviewer = adversarial gate)
and a context boundary, and lets each be pointed at a different model via a
`model:` frontmatter field.

### Chosen granularity

Several small single-responsibility skills (rejected: a couple of fat skills,
which would just relocate the monolith).

### Skill inventory (vendored & adapted into `templates/skills/`)

| Skill | Origin | Adaptation |
|---|---|---|
| `bc-router` | new | Intake (Monitor/`shop-msg`), classify message type, dispatch, outbox decision per contract |
| `bc-sufficiency-check` | new (extracted from current role prose) | clarify-vs-proceed checks per message type; router runs it before dispatch |
| `writing-plans` | superpowers, heavily adapted | Decompose work into **bd sub-issues** of the lead bead (one behavior each); **no plan doc**; respects the BDD outer loop |
| `test-driven-development` | already vendored | Tighten from optional-with-exception → **mandatory** inner loop |
| `subagent-driven-development` | superpowers, adapted | Implementer's per-sub-issue execution loop with context isolation + mandatory TDD |
| `using-git-worktrees` | superpowers, adapted | Isolate the dispatch's work in a worktree/branch |
| `integrating-to-main` | from `finishing-a-development-branch` | Merge the work branch to the BC's main + push so the pre-emit `origin/main` check can pass |
| `bc-review` | from requesting/receiving-code-review + current adversarial reviewer | Reviewer's adversarial probe |
| `work-done-gate` | from `verification-before-completion` + current pre-emit steps | Clean tree, work_id reachable on `origin/main`, scenario_hash integrity (ADR-010) → emit `work_done` |

### Roles as thin bias-shims

- **`bc-implementer.md`** — bias: *make the assigned behavior real via TDD; you
  are not the gate.* Loads `bc-sufficiency-check` (scenario-level),
  `writing-plans`, `subagent-driven-development`, `test-driven-development`,
  `using-git-worktrees`, `integrating-to-main`. Never emits `work_done` for
  scenario work.
- **`bc-reviewer.md`** — bias: *adversarial gate.* Loads `bc-review` +
  `work-done-gate`. **Sole** emitter of `work_done` for scenario work.
- Both carry a `model:` field so they can target different models.

### Control flow per message type (preserves the wire contract)

```
bc-router (main agent):
  arm Monitor on `shop-msg watch` ─▶ on NOTIFY: shop-msg read ─▶ classify
  └─ sufficiency fails ─────────────▶ shop-msg respond clarify; stop
  ├─ assign_scenarios / scenario-bugfix:
  │     worktree+branch ▶ bc-implementer (plan→TDD per bd sub-issue→BDD green
  │                       →integrate to main→push)
  │                     ▶ bc-reviewer (re-run BDD, adversarial probe,
  │                       work-done-gate) → emits work_done
  └─ request_maintenance / empty-scenario bugfix:
        worktree+branch ▶ bc-implementer (work→integrate→push→work-done-gate)
                          → emits work_done directly
  (mechanism_observation channel preserved on every path)
```

### Contract elements explicitly retained

- Intake only via `shop-msg` (never direct mailbox storage).
- Type→gate mapping: reviewer gates scenario work (`assign_scenarios` /
  scenario-carrying `request_bugfix`); implementer emits `work_done` directly
  for `request_maintenance` / empty-`scenarios` `request_bugfix`.
- `work_done` emitted via `shop-msg respond` with the scenario-hash **subset**
  rule (ADR-010), `status` complete/blocked.
- The three pre-emit checks: clean working tree, work_id commit reachable from
  `origin/main`, scenario_hash integrity.
- `mechanism_observation` channel on every path.
- BC-root-only operation.
- "Assigned scenarios pass against a clean tree" = `work_done` evidence (the
  BDD outer loop). TDD transcripts are process, **not** part of the payload.

### Worktree ↔ contract reconciliation

Work happens on a branch/worktree, but because the gate requires the work_id
commit reachable from `origin/main`, the implementer **integrates to the BC's
main and pushes** before the gate runs (decision: *BC integrates + pushes*).
The BC still owns and pushes its own main; the contract is unchanged.

## CLI / distribution changes

- Add a `templates/skills/**` → `<target>/.claude/skills/` pour to **both**
  `bootstrap` and `update`, managed/reconciled the same way agent files are:
  re-pour on update; leave byte+mtime unchanged when identical; remove
  managed-but-removed skills; never touch shop-owned files.
- A pure `importlib.resources` accessor for skills package data (mirrors the
  existing template accessors; no filesystem path under the working dir).
- Rewrite the BC role-template bodies and the `bc-primer` / CLAUDE wording to
  the router-first model.

## Test / BDD strategy

This repo is itself a BDD/TDD shop; new behavior must be pinned by scenarios.
Two tiers plus one honest boundary.

**Tier 1 — Executable CLI scenarios (real TDD, high value).** Skill-pouring is
new *code*, driven by failing scenarios first:
- `bootstrap` pours `templates/skills/**` into `<target>/.claude/skills/`
  (tree + byte-equality).
- `update` re-pours skills; idempotent (byte+mtime unchanged when identical);
  removes managed-but-removed skills; never touches shop-owned files.
- BC shop receives the BC skill set.

**Tier 2 — Content-invariant scenarios (guardrails, moderate value).**
Analogues of the existing `*_sections` tests, repointed at the new structure
and kept **semantic, not literal-header**: router classifies all three message
types to the right gate path; TDD skill is mandatory (no self-granted
exception); `work-done-gate` carries the three pre-emit checks; `writing-plans`
is beads-backed + BDD-aware; implementer never emits scenario `work_done` /
reviewer is sole emitter.

**Honest boundary:** the router's *runtime* behavior (arming the Monitor,
spawning subagents, looping) is **not unit-testable in this package** — it is
agent-runtime, the same limitation the repo already has (it tests template
*content*, never agent *behavior*). It is pinned by content scenarios here and
only truly exercised when a lead shop drives a live BC.

### Handling the existing suite

Decision: **keep both during transition.** The scenarios that pin the old
prose structure (`bc_implementer_sections`, `bc_reviewer_sections`,
`*_cli_naming`, the prose-section `pre_emit_*`) remain in place (failing /
`xfail`) alongside the new scenarios until the design settles, then are cleaned
up. This preserves a visible diff of what changed.

## Branch & integration

All work on `experimental/superpowers-bc-skills`. No PR / merge to `main`
unless explicitly requested.

## Open questions deferred to planning

- Exact split between `bc-router` and `bc-sufficiency-check` (one skill vs two).
- Whether `integrating-to-main` is its own skill or folded into
  `work-done-gate` / `using-git-worktrees`.
- Per-shop-type skill sets in the CLI (BC vs lead) once lead comes into scope.
