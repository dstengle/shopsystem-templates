Feature: the poured /workspace/.fabro/ def passes fabro validate on the real binary and satisfies the ADR-051 invariants

@scenario_hash:eb8e74495f124e64 @bc:shopsystem-templates
  Scenario: the poured "/workspace/.fabro/" def passes "fabro validate" on the real binary, satisfies the ADR-051 invariants, and is preflighted with a live "fabro run" where feasible
    Given the shopsystem-templates BC is installed
    And a shop-templates pour has emitted the fabro def into "/workspace/.fabro/"
    When "fabro validate" is executed against the poured def using the REAL fabro binary
    Then it exits zero and reports zero diagnostics, its "--json" output carrying an empty diagnostics array, and if the real binary genuinely cannot be obtained the leg SKIPs honestly rather than papering a failure over
    And the poured def satisfies the ADR-051 graph invariants: "emit_r", the Reviewer emitter, is the SOLE gated work_done(complete) emitter on the success path, every fallible non-terminal node carries an unconditional "outcome=failed" failsafe edge to a halt or blocked-emit sink so no failed node reaches the SUCCEEDED terminal, and "vaults/default/secrets.json" holds only "__PLACEHOLDER__" for every provider-key and token slot (ADR-049)
    And where feasible a live "fabro run" preflight exercises the poured def to assert the agent-vs-native node classification authoritatively, because "fabro validate" is permissive on node attrs and confirms graph shape rather than handler classification (spike R2)
