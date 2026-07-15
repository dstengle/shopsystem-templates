# ============================================================================
# RETIREMENT PROVENANCE (lead-ifye3.6, ADR-064 D1/D2) — this feature is now
# fully retired-to-empty: both of its scenarios are retired with NO successor.
# fabro >= v0.267.0-nightly.0 (the new bc-base image) makes `{{ }}` inside a
# fabro `model_stylesheet` a HARD PARSE ERROR, so the poured placeholder shape
# these two scenarios pinned crashed a nested-container launch at validation.
# The lead-ifye3.6 pour fix drops the `model_stylesheet` attribute entirely, so
# these placeholder-mechanism scenarios are unrunnable, not merely stale.
# Bodies are DELETED from any live block so the retired hashes are UNREACHABLE
# by block-only recompute; the original bodies are preserved here for audit
# only (these `#`-comment lines are outside every canonical scenario region).
#
# @scenario_hash:7653d06bddda72ed RETIRED (lead-ifye3.6), superseded-by: NOTHING
# reason: fabro >= v0.267 hard-parse-errors `{{ }}` in model_stylesheet; the
#   poured model_stylesheet no longer carries any `{{ inputs.X }}` placeholder,
#   so the pinned "expresses each node-class as a fabro input placeholder"
#   contract is false. Original body (audit):
#     Scenario: the poured model_stylesheet skeleton expresses each pinned node-class as a fabro input placeholder, not a literal provider-bound model ID
#       Given the shopsystem-templates BC is installed
#       And the canonical model_stylesheet skeleton asset is authored with one fabro "{{ inputs.<NAME> }}" placeholder per pinned node-class selector ".coding", ".review", and "*", using the input names "MODEL_CODING", "MODEL_REVIEW", and "MODEL_DEFAULT" respectively
#       When a shop-templates pour is run in a workspace
#       Then the poured "/workspace/.fabro/workflow.fabro" carries a model_stylesheet attribute reading ".coding { model: {{ inputs.MODEL_CODING }} } .review { model: {{ inputs.MODEL_REVIEW }} } * { model: {{ inputs.MODEL_DEFAULT }} }"
#       And no node-class selector in the poured model_stylesheet resolves to a literal provider-bound model ID string such as "claude-sonnet-4-5" or "claude-haiku-4-5"
#
# @scenario_hash:8aab2c5c071e349f RETIRED (lead-ifye3.6), superseded-by: NOTHING
# reason: same root cause. The poured model_stylesheet attribute is now absent,
#   so the pinned "abstract-labeled placeholders pour as a static, verbatim
#   skeleton" contract no longer has a placeholder to pour. Original body (audit):
#     Scenario: the abstract-labeled model_stylesheet still pours as a static, verbatim skeleton — no per-provider or per-model resolution happens at pour time
#       Given the shopsystem-templates BC is installed
#       And the canonical model_stylesheet skeleton asset carries the abstract-labeled node-class placeholders
#       When a shop-templates pour is run twice over the identical skeleton asset into two separate workspaces
#       Then the poured "/workspace/.fabro/workflow.fabro" model_stylesheet attribute is byte-identical across both pours
#       And the templates BC's pour mechanism performs no substitution of any placeholder into a literal model ID at pour time — every placeholder is poured verbatim, exactly as authored, unresolved
#       And the tier+effort-to-model mapping table and the active-provider dial are both absent from the templates BC's pour surface — resolving a placeholder to a literal model ID is not a templates-BC behavior
# ============================================================================
@bc_internal
Feature: the poured .fabro/ model_stylesheet is abstracted to fabro input placeholders (brief-017 / cand-002) — RETIRED to empty (lead-ifye3.6)
