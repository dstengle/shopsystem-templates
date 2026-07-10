@bc_internal
Feature: lead-po template — outcome-ownership sufficiency criterion scoped to the commitment

  @scenario_hash:627723b55dd2ed7e @bc:shopsystem-templates
  Scenario: lead-po template carries a testable outcome-ownership sufficiency criterion scoped to the commitment, with discovery re-homed to lead-pm
    When I read the lead-po template via "shop-templates show lead-po"
    Then the outcome ownership discipline block states a sufficiency criterion that requires the commitment to name the outcome it targets as an observable behavior change rather than an output
    And the outcome ownership discipline block states that the shaped candidate the lead-po consumes already carries the validated problem or job-to-be-done, so the lead-po anchors the commitment on that candidate rather than discovering the problem itself
    And the content states that upstream problem discovery and selection — choosing which problem is worth solving — is conducted in the lead-pm main-session mode and is not a lead-po sufficiency criterion
    And the outcome ownership sufficiency criterion is expressed as a measurable outcome rather than as a constraint ("don't crash", "use judgment")
