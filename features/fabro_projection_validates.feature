# ============================================================================
# RETIREMENT PROVENANCE (lead-ifye3.6, ADR-064 D1/D2) — this feature is now
# fully retired-to-empty: both of its scenarios are retired with NO successor.
# Both Givens literally require the poured model_stylesheet to carry the
# "MODEL_CODING"/"MODEL_REVIEW"/"MODEL_DEFAULT" fabro input placeholders, so
# once the lead-ifye3.6 pour fix drops the model_stylesheet attribute (fabro
# >= v0.267 hard-parse-errors `{{ }}` there) both scenarios are unrunnable, not
# merely stale. Bodies are DELETED from any live block so the retired hashes are
# UNREACHABLE by block-only recompute; the original bodies are preserved here
# for audit only (these `#`-comment lines are outside every canonical scenario
# region). COVERAGE NOTE: 0435d261be5031fd also carried the ADR-051 graph
# invariants (emit_r sole gated emitter, unconditional failsafe edges) and the
# ADR-049 __PLACEHOLDER__-only-vault assertions; retiring it with no successor
# is a genuine coverage gap the lead tracks separately as lead-008o8 — no
# successor is authored here per the clarify_response.
#
# @scenario_hash:610455d3a0f4e373 RETIRED (lead-ifye3.6), superseded-by: NOTHING
# reason: placeholder-mechanism-specific end to end — it pinned that an UNBOUND
#   `fabro validate` FAILS LOUD with an undefined-template-variable diagnostic
#   for the model_stylesheet placeholders. With no placeholders emitted there is
#   nothing to be undefined, so the assertion is moot. Original body (audit):
#     Scenario: the poured "/workspace/.fabro/" def's live model_stylesheet node-class placeholders make an UNBOUND "fabro validate" fail loud with an undefined-template-variable diagnostic, superseding the retired zero-diagnostics-when-unbound assertion
#       Given the shopsystem-templates BC is installed
#       And a shop-templates pour has emitted the fabro def into "/workspace/.fabro/", whose model_stylesheet carries the "MODEL_CODING", "MODEL_REVIEW", and "MODEL_DEFAULT" fabro input placeholders (brief-017)
#       When "fabro validate" is executed against the poured def using the REAL fabro binary with no "-I" input bound for any of the three node-class placeholders
#       Then it exits non-zero and reports a diagnostic naming an undefined template variable for the unbound node-class placeholder in the model_stylesheet attribute
#       And this confirms the live "{{ inputs.<NAME> }}" templating is genuinely evaluated by "fabro validate" rather than silently ignored, the same mechanism the cand-002 empirical probe directly proved, and replaces the retired assertion that an unbound "fabro validate" exits zero with zero diagnostics — that assertion no longer holds once model_stylesheet carries live per-node-class placeholders instead of literal model IDs
#
# @scenario_hash:0435d261be5031fd RETIRED (lead-ifye3.6), superseded-by: NOTHING
# reason: its Given requires the poured model_stylesheet to carry the three
#   placeholders (brief-017) and its When binds them via "-I MODEL_CODING" etc.,
#   so it is unrunnable once the attribute is dropped. Its ADR-051 graph-invariant
#   and ADR-049 vault assertions are the coverage gap tracked as lead-008o8.
#   Original body (audit):
#     Scenario: the poured "/workspace/.fabro/" def passes "fabro validate" on the real binary once representative model IDs are bound for its node-class placeholders, satisfies the ADR-051 invariants, and is preflighted with a live "fabro run" where feasible
#       Given the shopsystem-templates BC is installed
#       And a shop-templates pour has emitted the fabro def into "/workspace/.fabro/", whose model_stylesheet carries the "MODEL_CODING", "MODEL_REVIEW", and "MODEL_DEFAULT" fabro input placeholders (brief-017)
#       When "fabro validate" is executed against the poured def using the REAL fabro binary with representative literal model IDs bound via "-I MODEL_CODING", "-I MODEL_REVIEW", and "-I MODEL_DEFAULT"
#       Then it exits zero and reports zero diagnostics, its "--json" output carrying an empty diagnostics array, and if the real binary genuinely cannot be obtained the leg SKIPs honestly rather than papering a failure over
#       And the poured def satisfies the ADR-051 graph invariants: "emit_r", the Reviewer emitter, is the SOLE gated work_done(complete) emitter on the success path, every fallible non-terminal node carries an unconditional "outcome=failed" failsafe edge to a halt or blocked-emit sink so no failed node reaches the SUCCEEDED terminal, and "vaults/default/secrets.json" holds only "__PLACEHOLDER__" for every provider-key and token slot (ADR-049)
#       And where feasible a live "fabro run" preflight, with the same representative model IDs bound, exercises the poured def to assert the agent-vs-native node classification authoritatively, because "fabro validate" is permissive on node attrs and confirms graph shape rather than handler classification (spike R2)
# ============================================================================
@bc_internal
Feature: the poured /workspace/.fabro/ def passes fabro validate on the real binary and satisfies the ADR-051 invariants — RETIRED to empty (lead-ifye3.6)
