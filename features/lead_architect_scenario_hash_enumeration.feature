Feature: lead-architect template: BC @scenario_hash pre-state enumeration discipline

  @scenario_hash:0d384c6b92004c8d @bc:shopsystem-templates
  Scenario: lead-architect template's pre-state-verification discipline directs the architect to empirically enumerate the BC's pinned @scenario_hash set whenever the dispatch retires, supersedes, or contradicts prior BC-side coverage
    When I read the lead-architect template via "shop-templates show lead-architect"
    Then the content names "@scenario_hash" as a pre-state surface the architect must verify before composing a dispatch that retires, supersedes, or contradicts prior BC-side coverage
    And the content directs the architect to enumerate that surface from the BC's "features/" directory rather than from the lead shop's scenario register
    And the content marks the enumeration as a discrete pre-state step (alongside the existing behavior-verification step), not as optional guidance the architect may skip
    And the content names at least one of the trigger conditions "retire", "supersede", or "contradict" as the gate that requires the enumeration step

  @scenario_hash:48dd1f01012efafe @bc:shopsystem-templates
  Scenario: lead-architect template names a concrete, mechanically observable enumeration mechanism for the BC @scenario_hash pre-state step — a grep across every "features/*.feature" file in the BC — so the discipline is testable rather than aspirational
    When I read the lead-architect template via "shop-templates show lead-architect"
    Then the content names the literal substring "grep" as the enumeration mechanism for the BC's @scenario_hash pre-state surface
    And the content names the literal substring "@scenario_hash" as the pattern that grep enumerates
    And the content names the BC's "features/*.feature" tree (not a single named feature file) as the surface the grep is run against
    And the content names the BC's "features/" directory as the authoritative source for the BC's pinned @scenario_hash set, in contrast to the lead shop's scenario register

  @scenario_hash:22cbdf7cc9e917ca @bc:shopsystem-templates
  Scenario: lead-architect template directs the architect to re-run the BC @scenario_hash enumeration on every dispatch in a clarify-correction chain (not only the initial dispatch), against the BC's full "features/" tree (not only the hashes a prior clarify named)
    When I read the lead-architect template via "shop-templates show lead-architect"
    Then the content names a clarify-driven correction (a follow-up dispatch that augments or amends a prior dispatch in response to an Implementer clarify) as a moment that itself requires the BC @scenario_hash pre-state enumeration
    And the content directs the architect not to limit the re-enumeration to only the @scenario_hash entries a prior clarify named, but to re-run the enumeration against the BC's full "features/" tree
    And the content frames a prior clarify as evidence that the prior enumeration was incomplete, rather than as a definitive list of every conflicting BC-side @scenario_hash
    And the content names this per-event discipline as applying independently to each dispatch in a clarify-correction chain, not only to the initial dispatch in such a chain

  @scenario_hash:744cd4a4532c28d7 @bc:shopsystem-templates
  Scenario: lead-architect template requires the dispatch text resulting from the BC @scenario_hash enumeration to carry observable evidence the discipline ran — every conflicting BC-side hash is either named by ID in the dispatch text or carries an explicit retirement instruction
    When I read the lead-architect template via "shop-templates show lead-architect"
    Then the content directs the architect that, for any dispatch that retires, supersedes, or contradicts prior BC-side coverage, the dispatch text must reference each conflicting BC-side @scenario_hash entry by its hash ID, or carry an explicit retirement instruction for that hash
    And the content frames that requirement as the observable evidence the BC Implementer can use to confirm the architect ran the enumeration step, rather than as optional context for the BC
    And the content directs the architect to cite the enumeration in the dispatch description (in the same shape that the existing behavior-verification step is cited), so the Implementer does not have to re-run the enumeration to discover conflicts the architect missed
