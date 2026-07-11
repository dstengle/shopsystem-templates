Feature: the /workspace/.fabro/ projection pour is byte-identical across re-pours (deterministic by construction)

@scenario_hash:941d1df69c9b62dd @bc:shopsystem-templates
  Scenario: running the shop-templates pour twice over the identical single source yields a byte-identical "/workspace/.fabro/" projection
    Given the shopsystem-templates BC is installed
    And a fixed single canonical source of the BC work-loop role prompts and vendored skills
    When a shop-templates pour is run twice over that identical single source into two separate workspaces
    Then every artifact under "/workspace/.fabro/" has the same sha256 across the two pours, so the two projections are byte-identical
    And a "/workspace/.fabro/" committed from one pour is provably equal to a fresh pour of the same source, the no-drift property that makes a committed projection equal a re-pour (the ADR-019 scenarios single-source doctrine and the progressive-disclosure byte-identical precedent)
    And the generation is deterministic by construction — sorted iteration, no timestamps, no randomness — so the byte-identity holds on every re-pour
