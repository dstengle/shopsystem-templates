Feature: bc-emit work-done wrapper — executable pre-emit preconditions over the work-done-gate

  @scenario_hash:242c4de927d64339 @bc:shopsystem-templates
  Scenario: bc-emit work-done refuses the emit when the BC working tree carries a non-carved-out modified or untracked path, naming the offending path, and does not invoke shop-msg respond
    Given a BC repository whose "git status --porcelain" output reports at least one modified or untracked path that is NOT one of the ambient carve-outs ".specstory", ".claude/scheduled_tasks.lock", or ".beads/issues.jsonl"
    When the BC invokes the "bc-emit work-done" wrapper for its dispatched work_id
    Then the wrapper exits non-zero and does not invoke "shop-msg respond work_done"
    And the wrapper's error names the clean-working-tree precondition as the cause and lists each offending path verbatim as "git status --porcelain" reported it
    And a working tree whose ONLY non-empty "git status --porcelain" entries are the carved-out ambient artifacts ".specstory", ".claude/scheduled_tasks.lock", and ".beads/issues.jsonl" is treated as clean, so the wrapper does NOT refuse on those paths alone and proceeds to the remaining preconditions

  @scenario_hash:461d6066ef7dca0a @bc:shopsystem-templates
  Scenario: bc-emit work-done refuses the emit when the COMMIT deliverable for the work_id is not reachable from the BC's origin/main HEAD, naming the work_id and the current origin/main HEAD
    Given a dispatched work_id whose deliverable is a COMMIT attributable to that work_id
    And no commit attributable to the work_id is reachable from the BC's "origin/main" HEAD after a "git fetch origin"
    When the BC invokes the "bc-emit work-done" wrapper for that work_id
    Then the wrapper exits non-zero and does not invoke "shop-msg respond work_done"
    And the wrapper's error names the work_id-commit-on-origin-main precondition as the cause and names both the dispatched work_id and the current "origin/main" HEAD short SHA
    And a commit attributable to the work_id that exists only on a branch other than the BC's main branch (e.g. an un-merged or un-pushed local branch) does NOT satisfy the precondition; only reachability from "origin/main" HEAD satisfies it

  @scenario_hash:12c98d2f7e5259a9 @bc:shopsystem-templates
  Scenario: bc-emit work-done satisfies reachability for a TAG deliverable when the named tag exists and points at the expected commit lineage, even though origin/main HEAD has advanced past that commit
    Given a dispatched work_id whose deliverable is a release TAG that names an expected commit lineage
    And the named tag exists on "origin" after a "git fetch origin --tags" and points at the expected commit lineage
    And the BC's "origin/main" HEAD has legitimately advanced to a later commit that does NOT carry the work_id
    When the BC invokes the "bc-emit work-done" wrapper for that work_id in the TAG/release-deliverable mode
    Then the wrapper treats the reachability precondition as satisfied and does NOT refuse on the ground that the work_id is absent from "origin/main" HEAD
    And the satisfaction is established by the tag pointing at the expected commit lineage, not by the work_id being reachable from "origin/main" HEAD

  @scenario_hash:ea9c1bbd9be87d72 @bc:shopsystem-templates
  Scenario: bc-emit work-done refuses the emit when a recomputed scenario-block-only canonical hash diverges from the carried hash, names the divergence as stale, missing, or orphan, and uses the block-only delegate rather than the Feature-line-included wire form
    Given a dispatched work_id whose deliverable includes one or more scenario blocks committed under "features/" each carrying an "@scenario_hash:<hex>" tag
    And the wrapper recomputes each candidate scenario hash by delegating in-process to "scenarios.hash.compute_scenario_hash" using scenario-block-only canonicalization, with the enclosing "Feature:" header line NOT part of the hashed text
    When the recomputed set and the payload's "--scenario-hash" set diverge by at least one member — a carried hash whose recompute differs (stale), a features/-present dispatched scenario block with no carried hash (missing), or a carried hash matching no scenario block under "features/" (orphan)
    Then the wrapper exits non-zero and does not invoke "shop-msg respond work_done"
    And the wrapper's error names the scenario_hashes-match precondition as the cause, classifies the offending member as stale, missing, or orphan, and names the affected hash value and scenario
    And the recompute that produced the refusal used the scenario-block-only canonical hash from "scenarios.hash.compute_scenario_hash", never the Feature-line-included canonicalization carried on the wire "scenarios[].hash"

  @scenario_hash:4a6133f7b5f061a2 @bc:shopsystem-templates
  Scenario: on any bc-emit work-done precondition refusal the named-cause error directs the BC to self-resolve its own state and re-emit, and never names the lead or router as the actor for BC-repo state
    Given the "bc-emit work-done" wrapper refuses an emit on any of its preconditions — clean-working-tree, work_id-commit-on-origin-main, tag-deliverable reachability, or scenario_hashes-match
    When the BC reads the wrapper's named-cause error text
    Then the error directs the BC to self-resolve its OWN bead, commit, and working-tree state — committing its own changes or correcting its own hashes — and then to re-invoke "bc-emit work-done"
    And the error text does NOT instruct, request, or imply that the lead, the router, or any non-BC actor should commit, push, or reconcile the BC's repository state

  @scenario_hash:f81ee56bc163934b @bc:shopsystem-templates
  Scenario: bare shop-msg respond work_done --force deposits the work_done without running any bc-emit wrapper precondition, even when those preconditions would otherwise refuse the emit
    Given a BC whose state would cause the "bc-emit work-done" wrapper to refuse — for instance a dirty non-carved-out working tree, an unreachable work_id commit, or a scenario-hash mismatch
    When the BC invokes the bare messaging primitive "shop-msg respond work_done --force" directly rather than the "bc-emit work-done" wrapper
    Then the work_done message is deposited to the lead's inbox without any clean-working-tree, commit-or-tag-reachability, or scenario_hashes-match precondition being run by "shop-msg respond"
    And the availability of this bare forced-recovery path is independent of the wrapper, so landing the wrapper and retiring the prose preconditions does not remove the "--force" escape valve
