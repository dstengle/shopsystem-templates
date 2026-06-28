Feature: converged ops scaffolding (lead shop, PDR-020) — bin/shop-shell is a thin bc-container-delegating wrapper, the ops set is exactly six shop-owned files with no dedicated shell Dockerfile, and a non-default render carries zero cross-product literals

  @scenario_hash:a3b723341d9f2872 @bc:shopsystem-templates
  Scenario: bootstrap of a "lead" shop writes "bin/shop-shell" as an executable bash script whose body brings up the compose-defined postgres if not already running, so a fresh operator can run "./bin/shop-shell" with no further configuration
    Given an existing git repository at a target directory "/tmp/example-lead-shop" with no "bin/" subdirectory
    When I invoke the "shop-templates" bootstrap entry point with shop type "lead", shop name "shopsystem-product", and target directory "/tmp/example-lead-shop"
    Then the exit code is 0
    And after the invocation the target directory contains a file at "bin/shop-shell"
    And the file at "bin/shop-shell" in the target directory has its owner-execute permission bit set
    And the first line of the file at "bin/shop-shell" is exactly "#!/usr/bin/env bash"
    And the body of "bin/shop-shell" contains the literal substring "docker compose" followed somewhere later in the file by the literal substring "up -d postgres"
    And the body of "bin/shop-shell" references the environment variable "SHOPSYSTEM_DATA" with a default of "$HOME/.local/share/shopsystem"
    And the body of "bin/shop-shell" does not contain the literal substring "SHOPSYSTEM_SHELL_IMAGE", because the dedicated shell image is retired and the wrapper launches an ephemeral bc-lead launcher (which stands up the leaf-BC on bc-base) instead of a separately-built shell image

@scenario_hash:b764caa1dea99fcb @bc:shopsystem-templates
  Scenario Outline: the ops scaffolding file-set written by bootstrap for a "lead" shop named "<slug>" enumerates exactly six shop-owned files additively — "compose.yaml", "bin/shop-shell", "bin/shop-scenario-completion", "bin/agent-vault-provision", "bin/agent-vault-check", and "bin/agent-vault-approve-claude" — each at a shop-owned path outside any ".claude/" subdirectory, and writes NO dedicated shell Dockerfile, because per PDR-020 the shell image is retired and "bin/shop-shell" launches an ephemeral bc-lead launcher (which stands up the leaf-BC on bc-base) instead, and per lead-9s46 the lead-only "bin/agent-vault-approve-claude" Claude-OAuth proposal approval tool joined the converged ops-tool set as its sixth member
    Given an existing git repository at a target directory "/tmp/example-lead-shop"
    When I invoke the "shop-templates" bootstrap entry point with shop type "lead", shop name "<slug>", and target directory "/tmp/example-lead-shop"
    Then the exit code is 0
    And after the invocation the target directory contains a top-level file named "compose.yaml" not under any ".claude/" subdirectory
    And after the invocation the target directory contains a file at "bin/shop-shell" not under any ".claude/" subdirectory
    And after the invocation the target directory contains a file at "bin/shop-scenario-completion" not under any ".claude/" subdirectory
    And after the invocation the target directory contains a file at "bin/agent-vault-provision" not under any ".claude/" subdirectory
    And after the invocation the target directory contains a file at "bin/agent-vault-check" not under any ".claude/" subdirectory
    And after the invocation the target directory contains a file at "bin/agent-vault-approve-claude" not under any ".claude/" subdirectory
    And after the invocation the target directory contains no top-level file named "Dockerfile.<slug>-shell"
    And after the invocation the target directory contains no top-level file named "Dockerfile.shopsystem-shell"
    And the directory at "/tmp/example-lead-shop/.claude/canonical/" does not contain a file named "compose.yaml", "shop-shell", "shop-scenario-completion", "agent-vault-provision", "agent-vault-check", or "agent-vault-approve-claude"
    And the bootstrap-enumerated converged ops-tool set for a "lead" shop contains exactly six shop-owned entries — "compose.yaml", "bin/shop-shell", "bin/shop-scenario-completion", "bin/agent-vault-provision", "bin/agent-vault-check", and "bin/agent-vault-approve-claude" — and no seventh shop-owned ops file beyond those six

    Examples:
      | slug       |
      | shopsystem |
      | dummyco    |

  @scenario_hash:82c3a716143014a6 @bc:shopsystem-templates
  Scenario: the ops scaffolding files written by bootstrap for a "lead" shop ("compose.yaml", "bin/shop-shell") are shop-owned (in the PDR-003 path F sense) — they are bootstrap-time starter content the operator may freely customize, and they do not sit under ".claude/canonical/" because they are not subject to the canonical-managed re-pour contract that ".claude/canonical/" implies; and no dedicated shell Dockerfile is written, because PDR-020 retires it
    Given an existing git repository at a target directory "/tmp/example-lead-shop"
    When I invoke the "shop-templates" bootstrap entry point with shop type "lead", shop name "shopsystem-product", and target directory "/tmp/example-lead-shop"
    Then the exit code is 0
    And after the invocation the target directory contains a top-level file named "compose.yaml" at the path "/tmp/example-lead-shop/compose.yaml" (not under any ".claude/" subdirectory)
    And after the invocation the target directory contains a file at "/tmp/example-lead-shop/bin/shop-shell" (not under any ".claude/" subdirectory)
    And after the invocation the target directory contains no top-level file named "Dockerfile.shopsystem-shell"
    And after the invocation the directory at "/tmp/example-lead-shop/.claude/canonical/" does not contain a file named "compose.yaml", "shop-shell", or "Dockerfile.shopsystem-shell"
