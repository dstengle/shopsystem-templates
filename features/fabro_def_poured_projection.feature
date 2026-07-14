@bc_internal
Feature: the pinned fabro-loop-def validity re-homes onto the shop-templates-POURED /workspace/.fabro/ def (ADR-057)

@scenario_hash:0bc0fb71534cc0d6 @bc:shopsystem-templates
  Scenario: the fabro loop def whose validity is pinned is the one POURED by shop-templates into "/workspace/.fabro/", and the "fabro validate" plus ADR-051 plus placeholder-vault assertions hold on the poured def once representative model IDs are bound for its node-class placeholders
    Given the shopsystem-templates BC is installed
    And a shop-templates pour has emitted the self-contained fabro loop def into "/workspace/.fabro/", not baked into bc-base, whose model_stylesheet carries the "MODEL_CODING", "MODEL_REVIEW", and "MODEL_DEFAULT" fabro input placeholders (brief-017)
    When "fabro validate" is executed against the poured fabro def at "/workspace/.fabro/" with representative literal model IDs bound via "-I MODEL_CODING", "-I MODEL_REVIEW", and "-I MODEL_DEFAULT"
    Then it exits zero and reports zero diagnostics
    And the poured def is a self-contained bc-shop Implementer->Reviewer loop graph per ADR-051: the graph file is present, every node body the graph references is present in the def alongside it so the loop is runnable from the def alone, the Reviewer node is the sole node that can emit a gated work_done on the success path, and every fallible node carries an explicit unconditional failsafe edge to a halt or blocked-emit sink so a failed node never advances to the SUCCEEDED terminal
    And the poured def's native fabro vault holds only the value "__PLACEHOLDER__" for each of its provider-key and token slots, with no real credential present in the def (ADR-049), so that any real credential the loop uses is sourced from the agent-vault surface baked in S1 and never from the fabro vault

@scenario_hash:2786d8415362757b @bc:shopsystem-templates
  Scenario: the poured fabro loop def carries real bounded exponential retry on the six LLM/ACP agent nodes and a failsafe that sources its diagnostic triple from the single shared anchor (ADR-062)
    Given the shopsystem-templates BC is installed
    And a shop-templates pour has emitted the self-contained fabro loop def into "/workspace/.fabro/", not baked into bc-base
    Then the poured def's six LLM/ACP agent nodes each carry real workflow-level bounded retry — "max_retries" with the per-node count (classify=4; suff, plan, impl, review, impl_f=3) plus "retry_policy=exponential" for spaced, per-attempt-capped, total-wait-bounded backoff — not the inert "retry=" negative control that fails-fast to the failsafe on the first 429
    And the poured def's failsafe "emit_blk" node sources its diagnostic triple — failing-node identifier plus reason-class plus infra detail-marker plus the captured run tail — from the single shared Python anchor module "shop_templates.fabro_diagnostics" (ADR-062), with the reason-class and detail-marker vocab never hardcoded into the graph and the last-resort path emitting reason-class=unknown with the captured tail rather than a bare empty block
