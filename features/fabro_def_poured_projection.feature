@bc_internal
Feature: the pinned fabro-loop-def validity re-homes onto the shop-templates-POURED /workspace/.fabro/ def (ADR-057)

@scenario_hash:d08bac49e20111f2 @bc:shopsystem-templates
  Scenario: the fabro loop def whose validity is pinned is the one POURED by shop-templates into "/workspace/.fabro/", and the "fabro validate" plus ADR-051 plus placeholder-vault assertions hold on the poured def
    Given the shopsystem-templates BC is installed
    And a shop-templates pour has emitted the self-contained fabro loop def into "/workspace/.fabro/", not baked into bc-base
    When "fabro validate" is executed against the poured fabro def at "/workspace/.fabro/"
    Then it exits zero and reports zero diagnostics
    And the poured def is a self-contained bc-shop Implementer->Reviewer loop graph per ADR-051: the graph file is present, every node body the graph references is present in the def alongside it so the loop is runnable from the def alone, the Reviewer node is the sole node that can emit a gated work_done on the success path, and every fallible node carries an explicit unconditional failsafe edge to a halt or blocked-emit sink so a failed node never advances to the SUCCEEDED terminal
    And the poured def's native fabro vault holds only the value "__PLACEHOLDER__" for each of its provider-key and token slots, with no real credential present in the def (ADR-049), so that any real credential the loop uses is sourced from the agent-vault surface baked in S1 and never from the fabro vault
