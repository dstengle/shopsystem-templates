Feature: bc-reviewer template enforces clean working tree and origin/main commit before work_done (complete) emit

  @scenario_hash:9457dfff7e3f9e90 @bc:shopsystem-templates
  Scenario: bc-reviewer template directs the reviewer to verify the BC's working tree is clean AND the work_id's change is committed to origin/main before emitting work_done (complete)
    When I read the bc-reviewer template via "shop-templates show bc-reviewer"
    Then the content names "git status --porcelain" as a pre-emit verification step the reviewer must run before composing a work_done with status complete
    And the content names "git log" or "git rev-parse" (against the BC's "origin/main" ref) as a pre-emit verification step that confirms the work_id's change is present on the BC's main branch
    And the content directs the reviewer that when "git status --porcelain" produces any non-empty output the reviewer must NOT emit work_done with status complete, and instead must surface the uncommitted state as a blocker (e.g., emit work_done with status blocked, or stop and report) with the offending paths named in the response summary
    And the content directs the reviewer that when the BC's "origin/main" HEAD does NOT carry a commit for the dispatched work_id the reviewer must NOT emit work_done with status complete, and instead must surface the missing-commit state as a blocker with the work_id named in the response summary
    And the content marks both checks as discrete pre-emit steps (alongside the existing BDD-rerun and scenario-hash-presence steps), not as optional guidance the reviewer may skip

  @scenario_hash:2b5d558d548b0606 @bc:shopsystem-templates
  Scenario: bc-reviewer template directs the reviewer to block a work_done (complete) emit when tracked files in the BC root are modified but uncommitted, and to name the dirty paths in the response
    When I read the bc-reviewer template via "shop-templates show bc-reviewer"
    Then the content directs the reviewer that, prior to emitting work_done with status complete, the reviewer must invoke "git status --porcelain" in the BC root and inspect its output
    And the content directs the reviewer that any line in "git status --porcelain" output with a tracked-file modification marker (lines beginning with " M", "M ", "MM", " D", "D ", "A ", "AM", " R", "R ", " C", "C ", or "UU") is a precondition failure
    And the content directs the reviewer that on such a precondition failure the reviewer does NOT compose "shop-msg respond work_done --status complete" and instead emits "shop-msg respond work_done --status blocked" with a summary that names the tracked paths reported by "git status --porcelain"
    And the content frames the dirty-tracked-files check as a step the reviewer runs even when the BDD suite passes, so a green BDD result does not bypass the check

  @scenario_hash:6d0a7a957b340274 @bc:shopsystem-templates
  Scenario: bc-reviewer template directs the reviewer to block a work_done (complete) emit when untracked files are present in the BC root, and to name the untracked paths in the response
    When I read the bc-reviewer template via "shop-templates show bc-reviewer"
    Then the content directs the reviewer that the same "git status --porcelain" inspection that catches modified-tracked-files (per scenario 106) also catches untracked files (lines beginning with "??") and treats them as a precondition failure
    And the content directs the reviewer that on untracked-files failure the reviewer does NOT compose "shop-msg respond work_done --status complete" and instead emits "shop-msg respond work_done --status blocked" with a summary that names the untracked paths reported by "git status --porcelain"
    And the content explicitly directs the reviewer that the untracked-files check is NOT satisfied by adding the paths to .gitignore unless the paths are genuinely outside the BC's scope of work; the reviewer must confirm with the implementer (or by inspection of the dispatch) whether the untracked paths are work product that should be committed before re-attempting the emit

  @scenario_hash:721dcf075edcd9c7 @bc:shopsystem-templates
  Scenario: bc-reviewer template directs the reviewer to block a work_done (complete) emit when the BC's origin/main branch does not carry a commit attributable to the dispatched work_id, and to name the missing work_id and current origin/main HEAD in the response
    When I read the bc-reviewer template via "shop-templates show bc-reviewer"
    Then the content directs the reviewer that, prior to emitting work_done with status complete, the reviewer must verify by "git log origin/main" (or equivalent "git log" against the BC's main branch) that at least one commit attributable to the dispatched work_id is reachable from "origin/main" HEAD
    And the content names a concrete attribution mechanism the reviewer may use to recognize the work_id's commit (for example, the work_id substring appearing in the commit message subject or body, or a tag/note pointing at the work_id), so the reviewer does not have to invent a convention
    And the content directs the reviewer that when no commit attributable to the work_id is reachable from "origin/main" HEAD the reviewer does NOT compose "shop-msg respond work_done --status complete" and instead emits "shop-msg respond work_done --status blocked" with a summary that names the dispatched work_id and the current "origin/main" HEAD short SHA
    And the content directs the reviewer that committing the work_id's change to any branch OTHER than the BC's main branch (e.g., a local feature branch that has not been merged or pushed to origin/main) does NOT satisfy this precondition; the only outcome that satisfies the precondition is the work_id's commit being reachable from "origin/main" HEAD
    And the content directs the reviewer that "git fetch origin" should be run as part of the verification so a stale local view of "origin/main" does not produce a false positive
