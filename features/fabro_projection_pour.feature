Feature: shop-templates pours the /workspace/.fabro/ fabro-engage projection (ADR-051) alongside /workspace/.claude/

@scenario_hash:e7668df366a93a60 @bc:shopsystem-templates
  Scenario: a shop-templates pour emits the "/workspace/.fabro/" fabro-engage projection — a static ADR-051 skeleton poured verbatim plus generated node bodies — alongside "/workspace/.claude/"
    Given the shopsystem-templates BC is installed
    And the single canonical source of the BC work-loop content is the shopsystem-templates role prompts "bc-implementer", "bc-reviewer", "bc-router", "bc-review", "bc-sufficiency-check" and "work-done-gate" plus the vendored skills, unchanged as the authoring surface
    When a shop-templates pour is run in a workspace
    Then a "/workspace/.fabro/" fabro-engage projection is emitted alongside the existing "/workspace/.claude/" projection, both out of the same pour
    And "/workspace/.fabro/" carries the ADR-051 topology skeleton — the "workflow.fabro" graph, the native-gate "script=" nodes, and the "workflow.toml", "project.toml" and "vaults/default" scaffold — poured VERBATIM from a static asset, not generated from prose
    And "/workspace/.fabro/nodes/" carries the agent-node bodies GENERATED at pour time by inlining the unchanged role-prompt and skill Markdown from the single canonical source, so that a role-prompt or skill edit changes only that one source and re-pours into both the "/workspace/.claude/" and "/workspace/.fabro/" projections
