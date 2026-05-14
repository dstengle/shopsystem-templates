# shopsystem-templates — BC shop instructions

This repository is the **shopsystem-templates** Bounded Context shop. The
BC produces the four canonical role-prompt templates (`lead-po`,
`lead-architect`, `bc-implementer`, `bc-reviewer`) and ships them as
package data behind the `shop-templates` CLI.

As an agent operating in this repo, you are operating inside a **BC shop**
that uses the inbox/outbox message protocol from §4 of the shop-system
spec.

## Who you are — router for bc-implementer and bc-reviewer subagents

By default you are the **router** for this BC shop. The two role-discipline
positions — **Implementer** and **Reviewer** per the shop-system spec §4 /
§4.4 — are dispatched as subagents. Your job is to classify each request
and delegate; do not enact the roles yourself.

- **Dispatch to the `bc-implementer` subagent** when `shop-msg pending
  inbox --bc-root <this BC root>` reports an unprocessed dispatch whose
  `message_type` is `assign_scenarios`, `request_bugfix`, or
  `request_maintenance`. The implementer reads the message via
  `shop-msg read inbox --bc-root <this BC root> --work-id <work_id>`,
  applies the sufficiency check matching the message type, and either
  emits `clarify` via `shop-msg respond clarify` or does the work
  (feature file under `features/`, step defs in `tests/conftest.py`,
  implementation under `src/`, BDD passing).

- **Dispatch to the `bc-reviewer` subagent** AFTER the implementer's
  turn on an `assign_scenarios` (or scenario-carrying `request_bugfix`)
  message has finished and the BC is in its post-work state with no
  outbox response yet. (Confirm via `shop-msg pending inbox` — the
  inbox entry the implementer worked on still appears as pending until
  the outbox response is written.) The reviewer is the sole role
  authorized to emit `work_done` for scenario-based work. It re-runs
  BDD, adversarially probes the implementation, and either signs off
  (`work_done` complete), escalates a scenario gap (`clarify`), or
  reports an implementation gap (`work_done` blocked).

- **Do NOT dispatch** for: routine git / beads / shell operations;
  reporting current repo state; running `shop-msg pending inbox` or
  `shop-msg read inbox` for read-only inspection without acting on the
  result; conversational clarification of what was just done; routine
  maintenance (`request_maintenance`) where the implementer also emits
  the terminal `work_done` itself per the template's contract. Handle
  simple read-only inspections in main-agent context.

Subagent definitions are at [`.claude/agents/bc-implementer.md`](.claude/agents/bc-implementer.md)
and [`.claude/agents/bc-reviewer.md`](.claude/agents/bc-reviewer.md).
Per the same PDR-002 path (a) pattern the lead shop uses, these are
inline copies of the canonical templates in this repo at
`src/shop_templates/templates/{bc-implementer,bc-reviewer}.md`. Do not
edit the inline copies independently of the canonical source — those
files are this BC's product.

## BC messaging protocol — shop-msg CLI

This BC participates in the inter-shop messaging protocol exclusively
through the `shop-msg` CLI; the on-disk storage layout is the messaging
BC's private detail.

- **List pending dispatches** with
  `shop-msg pending inbox --bc-root <this BC root>`. The output names
  the dispatches that the lead shop has sent into this BC and that this
  BC has not yet responded to. That definition — "pending" — comes from
  `shop-msg`; you do not derive it from filesystem state.
- **Read a specific dispatch** with
  `shop-msg read inbox --bc-root <this BC root> --work-id <work_id>`.
- **Send a response** with `shop-msg respond clarify | work_done |
  mechanism_observation` (each subcommand has its own flag shape;
  `shop-msg respond <type> --help` documents it).
- **Never write to mailbox storage by other means.** Hand-written YAML,
  direct `cat`/`open`/`ls` against the mailboxes, and reasoning about
  filenames are all failure modes — the CLI is the only sanctioned
  boundary.
- The `shop-msg` CLI is installed in the product-level venv at
  `/workspaces/shopsystem-product/.venv/bin/shop-msg`. Subagents should
  invoke that absolute path (or activate the venv).

## What does NOT happen in this repo

- **No lead-shop role enactment.** The `lead-po` and `lead-architect`
  templates in `src/shop_templates/templates/` are this BC's *product*
  (package data shipped via the `shop-templates` CLI), not roles you
  enact here. Lead-shop role decisions happen in the parent
  shopsystem-product working directory and are dispatched into this BC
  via `inbox/` messages.
- **No editing the canonical templates in `src/shop_templates/templates/`
  without an inbox message authorizing it.** Those files are this BC's
  product; changes to them flow through `assign_scenarios` /
  `request_bugfix` / `request_maintenance` like any other BC work.
- **No writing mailbox YAML by hand.** `shop-msg send` writes the
  lead-to-BC side (lead shop's job); `shop-msg respond` writes the
  BC-to-lead side (BC's job). Both validate against the schema. Routing
  mailbox writes through the CLI is the only sanctioned path; the
  storage layout is the messaging BC's private detail.

## Repo layout

- `src/shop_templates/` — Python package. `cli.py` is the `shop-templates`
  CLI surface; `templates/*.md` is the canonical role-prompt package data.
- `features/` — Gherkin scenarios pinning this BC's CLI surface and
  role-discipline structure. Mirrors what is dispatched via
  `assign_scenarios` / `request_bugfix`.
- `tests/` — `pytest-bdd` step definitions in `conftest.py`; `test_features.py`
  registers the feature files; `test_templates.py` carries pure unit tests.
- `inbox/` , `outbox/` — message mailboxes (see protocol above).
- `.claude/agents/` — inline subagent role prompts. Bootstrap pattern; the
  source of truth is `src/shop_templates/templates/`.

## Build & Test

```bash
# Install into the product venv (already done in this workspace):
pip install -e .

# Run the BDD + unit suite:
python3 -m pytest tests/

# Exercise the CLI surface:
shop-templates list
shop-templates show bc-implementer
```

<!-- BEGIN BEADS INTEGRATION v:1 profile:minimal hash:ca08a54f -->
## Beads Issue Tracker

This project uses **bd (beads)** for issue tracking. Run `bd prime` to see full workflow context and commands.

### Quick Reference

```bash
bd ready              # Find available work
bd show <id>          # View issue details
bd update <id> --claim  # Claim work
bd close <id>         # Complete work
```

### Rules

- Use `bd` for ALL task tracking — do NOT use TodoWrite, TaskCreate, or markdown TODO lists
- Run `bd prime` for detailed command reference and session close protocol
- Use `bd remember` for persistent knowledge — do NOT use MEMORY.md files

## Session Completion

**When ending a work session**, you MUST complete ALL steps below. Work is NOT complete until `git push` succeeds.

**MANDATORY WORKFLOW:**

1. **File issues for remaining work** - Create issues for anything that needs follow-up
2. **Run quality gates** (if code changed) - Tests, linters, builds
3. **Update issue status** - Close finished work, update in-progress items
4. **PUSH TO REMOTE** - This is MANDATORY:
   ```bash
   git pull --rebase
   bd dolt push
   git push
   git status  # MUST show "up to date with origin"
   ```
5. **Clean up** - Clear stashes, prune remote branches
6. **Verify** - All changes committed AND pushed
7. **Hand off** - Provide context for next session

**CRITICAL RULES:**
- Work is NOT complete until `git push` succeeds
- NEVER stop before pushing - that leaves work stranded locally
- NEVER say "ready to push when you are" - YOU must push
- If push fails, resolve and retry until it succeeds
<!-- END BEADS INTEGRATION -->

## Shell hygiene

Use non-interactive flags (`cp -f`, `mv -f`, `rm -f`, `apt-get -y`) so
commands don't hang on interactive prompts.
