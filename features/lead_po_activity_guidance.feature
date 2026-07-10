@bc_internal
Feature: lead-po template — every post-PDR-033 PO activity carries guidance or a guidance-pending marker

  @scenario_hash:eaa4fc5b6bc7ed75 @bc:shopsystem-templates
  Scenario: every post-PDR-033 PO activity named in the lead-po template carries either one-line guidance or an explicit "guidance pending" marker
    Given the post-PDR-033 PO activities "Maintain product brief", "Write PDR for new functionality", "Write Gherkin scenarios as requirements", and "Respond to BC `clarify` (scope, vocabulary)"
    When I read the lead-po template via "shop-templates show lead-po"
    Then for each activity in that list, the content has a contiguous block — either a subsection that names the activity or a line that names the activity — that contains at minimum one sentence of guidance OR an explicit marker of the form "guidance pending" (case-insensitive)
    And no post-PDR-033 PO activity appears as a bare list item with neither guidance nor a "guidance pending" marker
