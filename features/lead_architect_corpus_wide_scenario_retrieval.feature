@bc_internal
Feature: lead-architect template directs corpus-wide scenario retrieval through the installed scenarios CLI aggregate commands, not a hand-scoped grep

    @scenario_hash:b4795e33b958f6e2 @bc:shopsystem-templates
    Scenario: lead-architect template directs corpus-wide scenario retrieval (existence, ownership, conflict enumeration) through the installed scenarios CLI's own aggregate commands, not a hand-scoped grep against an assumed file or directory
    When I read the lead-architect template via "shop-templates show lead-architect"
    Then the content directs the architect that any corpus-wide scenario question — whether a hash is live anywhere in the tree, which BC owns a scenario, or which scenarios conflict with a proposed change — is answered by invoking the installed "scenarios" CLI's own aggregate commands over the full "features/" tree, such as "scenarios journal rebuild" or "scenarios validate --aggregate", not by a hand-scoped "Grep" invocation against a single assumed file or directory
    And the content names a hand-scoped single-file "Grep" search as insufficient to establish what exists corpus-wide, citing the missed-sibling-file conflict-enumeration gap this discipline exists to prevent
    And the content permits plain "Grep" or "Read" for retrieving the full text of a specific, already-identified scenario, distinguishing that use from corpus-wide discovery
    And the content directs the architect to apply this corpus-wide-retrieval requirement to the existing @scenario_hash conflict-enumeration step required whenever a dispatch retires, supersedes, or contradicts prior BC-side coverage
