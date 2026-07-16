# ============================================================================
# RETIREMENT PROVENANCE (lead-ym67i, ADR-064 D1/D2) — this feature is now fully
# retired-to-empty: its ONE scenario is retired with NO successor.
# lead-npm2w's shop_type==bc call-site gate on the .fabro/ pour
# (cli.py _cmd_bootstrap/_cmd_update) means a lead-type pour no longer emits
# /workspace/.fabro/, so this scenario's originally-authored Given/When —
# UNCONDITIONAL, with no shop_type qualifier ("Given the shopsystem-templates
# BC is installed / When a shop-templates pour is run in a workspace") — and
# its unscoped Then ("a pour emits /workspace/.fabro/ … for ALL pour contexts")
# are genuinely WRONG as pinned, not merely stale: as pinned the scenario is
# wrongly satisfied by a lead-type pour too. The body is DELETED from any live
# block so the retired hash is UNREACHABLE by block-only recompute; the original
# body is preserved here for audit only (these `#`-comment lines are outside
# every canonical scenario region).
#
# COVERAGE NOTE: e7668df366a93a60 was the ONLY live pinned scenario asserting
# that a pour EMITS /workspace/.fabro/ (941d1df69c9b62dd pins double-pour
# DETERMINISM, not emission; 2786d8415362757b pins ADR-062 retry). Bare-retiring
# it therefore leaves "a BC-type pour emits /workspace/.fabro/ alongside
# /workspace/.claude/" canonically UNPINNED — guarded meanwhile only by
# lead-npm2w's code-level regression test. That gap is ACCEPTED and TRACKED by
# the lead as lead-7mboj (PO-authored, BC-scoped-Given successor, dispatched
# separately as a fresh request_bugfix); no successor is authored or minted here
# per the clarify_response (canonical scenario authorship stays lead-side).
#
# @scenario_hash:e7668df366a93a60 RETIRED (lead-ym67i, 2026-07-16),
# superseded-by: NOTHING (tracked successor follow-up: lead-7mboj)
# reason: shop_type==bc pour gate (lead-npm2w) makes the unconditional,
#   shop_type-agnostic Given/When/Then wrong for ALL pour contexts — a lead-type
#   pour no longer emits /workspace/.fabro/. Original body (audit):
#     Scenario: a shop-templates pour emits the "/workspace/.fabro/" fabro-engage projection — a static ADR-051 skeleton poured verbatim plus generated node bodies — alongside "/workspace/.claude/"
#       Given the shopsystem-templates BC is installed
#       And the single canonical source of the BC work-loop content is the shopsystem-templates role prompts "bc-implementer", "bc-reviewer", "bc-router", "bc-review", "bc-sufficiency-check" and "work-done-gate" plus the vendored skills, unchanged as the authoring surface
#       When a shop-templates pour is run in a workspace
#       Then a "/workspace/.fabro/" fabro-engage projection is emitted alongside the existing "/workspace/.claude/" projection, both out of the same pour
#       And "/workspace/.fabro/" carries the ADR-051 topology skeleton — the "workflow.fabro" graph, the native-gate "script=" nodes, and the "workflow.toml", "project.toml" and "vaults/default" scaffold — poured VERBATIM from a static asset, not generated from prose
#       And "/workspace/.fabro/nodes/" carries the agent-node bodies GENERATED at pour time by inlining the unchanged role-prompt and skill Markdown from the single canonical source, so that a role-prompt or skill edit changes only that one source and re-pours into both the "/workspace/.claude/" and "/workspace/.fabro/" projections
# ============================================================================
@bc_internal
Feature: shop-templates pours the /workspace/.fabro/ fabro-engage projection (ADR-051) alongside /workspace/.claude/ — RETIRED to empty (lead-ym67i)
