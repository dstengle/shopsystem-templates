Feature: shopsystem-templates — CLI surface and role-discipline structure

  @scenario_hash:9029808f48b613d8 @bc:shopsystem-templates
  Scenario: lead-architect template carries the structural sections that architecture and message-type discipline depend on
    When I read the lead-architect template via "shop-templates show lead-architect"
    Then the content contains a "## Your default posture: PRE-STATE DETERMINES VEHICLE — VERIFIED EMPIRICALLY" section header
    And the content contains a "## Sufficiency check — message-type selection" section header
    And the content contains a "## Sufficiency check — `assign_scenarios`" section header
    And the content contains a "## Sufficiency check — `request_bugfix`" section header
    And the content contains a "## Sufficiency check — `request_maintenance`" section header
    And the content contains a "## Anti-rationalization" section header
    And the content contains a "## Reporting back" section header

  @scenario_hash:98fe33cee55daf55 @bc:shopsystem-templates
  Scenario: lead-architect template requires empirical pre-state verification (Finding 17 / S16 pin)
    When I read the lead-architect template via "shop-templates show lead-architect"
    Then the content names "empirical" pre-state verification as the discipline for choosing between assign_scenarios, request_bugfix, and request_maintenance
    And the content distinguishes "reading code" (hypothesis) from "running it" (fact) as the basis for that choice
