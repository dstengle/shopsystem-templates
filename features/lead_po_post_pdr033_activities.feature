@bc_internal
Feature: lead-po template — post-PDR-033 PO activities without the re-homed Interview-stakeholder activity

  @scenario_hash:3cb958e1572e9532 @bc:shopsystem-templates
  Scenario: lead-po template names every post-PDR-033 PO activity by name, without the re-homed Interview-stakeholder activity
    When I read the lead-po template via "shop-templates show lead-po"
    Then the content names the activity "Maintain product brief"
    And the content names the activity "Write PDR for new functionality"
    And the content names the activity "Write Gherkin scenarios"
    And the content names the activity "Respond to BC `clarify`" with the qualifier "scope" or "vocabulary"
    And the content does not present "Interview stakeholder" as a lead-po activity, instead attributing interview and discovery to the lead-pm main-session mode
