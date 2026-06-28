Feature: bc-emit work-done plan-decomposition closure + bd-dolt durability
  Tightens the executable "bc-emit work-done" wrapper's bd-plan-decomposition
  preconditions (work-done-gate Check 4 + durability, ADR-036 D1/D2). The gate
  enumerates EVERY sub-issue reachable under the work_id umbrella bead from the
  BC's own bd registry — refusing on any still-OPEN sub-issue including an
  orphan from an abandoned earlier decomposition the implementer never closed —
  and verifies the decomposition-and-closure state is reachable from the pushed
  tracker remote (the configured bd-dolt remote), naming the
  bd-decomposition-non-durable precondition specifically rather than a generic
  dirty working tree. Additive to scenarios 176-181, 154, and beads-health 05;
  nothing retired.

@scenario_hash:0b48508e40fdde18 @bc:shopsystem-templates
  Scenario: bc-emit work-done refuses the emit when any sub-issue reachable under the work_id umbrella bead is still OPEN — including an orphaned sub-issue from an abandoned earlier decomposition the implementer never closed — naming each offending OPEN sub-issue
    Given a dispatched work_id whose umbrella bead carries TDD sub-issues, at least one of which is a RED sub-issue, and the implementer's real decomposition pass closed every sub-issue that pass created
    And a separate earlier abandoned decomposition left at least one orphaned sub-issue still OPEN under the same work_id umbrella bead, which the implementer never closed
    When the BC invokes the "bc-emit work-done" wrapper for that work_id
    Then the wrapper exits non-zero and does not invoke "shop-msg respond work_done"
    And the wrapper's error names the all-sub-issues-under-the-work_id-umbrella-closed precondition as the cause and lists each still-OPEN sub-issue, including the orphaned one, by its bd id
    And the precondition is evaluated by enumerating EVERY sub-issue reachable under the work_id umbrella bead — not only the set the implementer reports or itself closed — so an OPEN sub-issue the implementer did not create still blocks the emit and the prior "at least one RED sub-issue exists and all sub-issues the implementer closed are closed" check alone does NOT pass the gate
