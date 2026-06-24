Feature: converged ops scaffolding (lead shop, PDR-020) — bin/shop-shell is a thin bc-container-delegating wrapper, the ops set is exactly six shop-owned files with no dedicated shell Dockerfile, and a non-default render carries zero cross-product literals

  @scenario_hash:725562869d9df919 @bc:shopsystem-templates
  Scenario Outline: bootstrap of a "lead" shop named "<slug>" writes "bin/shop-shell" as a thin wrapper that DELEGATES the brokered Claude launch to "bc-container" running in an ephemeral LAUNCHER image carrying the docker CLI ("shopsystem-bc-lead") — it brings up the compose supporting services, assembles the operator agent-vault "--env-file", then runs "bc-container launch" standing up the leaf-BC session ALSO on the "shopsystem-bc-lead" runtime image (the leaf needs the docker CLI too so its own router can run "bc-container launch"), attaching the leaf to the slug-scoped compose network via "--network" so it reaches postgres + agent-vault by compose hostname, mounting the lead repo as the workspace with the lead-only docker socket and a LEAD startup-prompt override, and "bc-container attach" — while constructing NO proxy URL, fetching NO CA, building NO shell image, and mounting NO host credentials
    Given an existing git repository at a target directory "/tmp/example-lead-shop" with no "bin/" subdirectory
    When I invoke the "shop-templates" bootstrap entry point with shop type "lead", shop name "<slug>", and target directory "/tmp/example-lead-shop"
    Then the exit code is 0
    And after the invocation the target directory contains a file at "bin/shop-shell" whose owner-execute permission bit is set and whose first line is exactly "#!/usr/bin/env bash"
    And the body of "bin/shop-shell" contains the literal substring "docker compose" followed somewhere later in the file by the literal substring "up -d postgres agent-vault", so it brings up both supporting services per ADR-028 D1
    And the body of "bin/shop-shell" assembles the operator agent-vault credentials into an env-file by referencing the literal substring "--env-file"
    And the body of "bin/shop-shell" launches the ephemeral LAUNCHER by the literal substring "docker run --rm" carrying the interactive flag literal substring "-it" and the launcher image reference by the literal substring "ghcr.io/dstengle/shopsystem-bc-lead:latest", because the launcher must carry the docker CLI to run "bc-container"
    And the body of "bin/shop-shell" mounts the host docker socket into that ephemeral launcher by the literal substring "/var/run/docker.sock:/var/run/docker.sock"
    And the body of "bin/shop-shell" mounts the lead repository into that ephemeral launcher so the inner "bc-container" can see it
    And the body of "bin/shop-shell" inside that ephemeral launcher invokes "bc-container launch" carrying the literal substring "--workspace-mount" and the literal substring "--mount-docker-socket", so the launched lead session mounts the live lead working tree and is granted the lead-only docker-daemon access
    And the body of "bin/shop-shell" hands the leaf-BC session its runtime image by the literal substring "shopsystem-bc-lead", so the launched session runs on the lead-launcher image because the leaf needs the docker CLI to run "bc-container launch" itself
    And the body of "bin/shop-shell" attaches the launched leaf-BC session to the slug-scoped compose network by the inner "bc-container launch" carrying the literal substring "--network", so the launched session reaches the compose postgres and agent-vault by hostname (the outer launcher's network does not attach the separate leaf container)
    And the body of "bin/shop-shell" passes a lead-specific startup prompt into the launch by the literal substring "--startup-prompt", overriding the BC-default session-start so the launched session runs the router session-start
    And the body of "bin/shop-shell" drops the operator into the brokered session by the literal substring "bc-container attach"
    And the body of "bin/shop-shell" does not contain the literal substring "14322" and does not contain the literal substring "HTTPS_PROXY", because proxy-URL construction is delegated to the launcher and not re-derived in the wrapper
    And the body of "bin/shop-shell" does not contain the literal substring "agent-vault ca fetch" and does not contain the literal substring "agent-vault-check", because CA sourcing and the readiness check are delegated to the launcher and bc-base entrypoint
    And the body of "bin/shop-shell" does not contain the literal substring "SHOPSYSTEM_SHELL_IMAGE" and does not contain the literal substring "docker build", because the dedicated shell image and its Dockerfile are retired
    And the body of "bin/shop-shell" does not contain the literal substring "$HOME/.claude" and does not contain the literal substring "$HOME/.gitconfig" and does not contain the literal substring "~/.claude" and does not contain the literal substring "~/.gitconfig", so no host credentials are mounted

    Examples:
      | slug       |
      | shopsystem |
      | dummyco    |

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

  @scenario_hash:166b86d779ecd0e7 @bc:shopsystem-templates
  Scenario: the ops scaffolding rendered by bootstrap for a non-default-slug "lead" shop carries zero cross-product SLUG-derived literals — for shop name "dummyco" the rendered "compose.yaml" contains no case-insensitive occurrence of the literal "shopsystem" and no case-insensitive occurrence of the literal "fleet", and the rendered "bin/shop-shell" contains "shopsystem" ONLY as part of the product-neutral framework image references "shopsystem-bc-lead" and "shopsystem-bc-base" (per scenario 172, exempt under the compose.yaml product-neutral-image precedent) and no case-insensitive occurrence of the literal "fleet", confirming the generification leaves no default-product slug name baked into a non-default render while the shared framework image references are preserved
    Given an existing git repository at a target directory "/tmp/example-lead-shop"
    When I invoke the "shop-templates" bootstrap entry point with shop type "lead", shop name "dummyco", and target directory "/tmp/example-lead-shop"
    Then the exit code is 0
    And the byte contents of "compose.yaml" in the target directory contain no case-insensitive occurrence of the literal substring "shopsystem" and no case-insensitive occurrence of the literal substring "fleet"
    And the byte contents of "bin/shop-shell" in the target directory, after every case-insensitive occurrence of the product-neutral framework image reference literals "shopsystem-bc-lead" and "shopsystem-bc-base" is removed, contain no remaining case-insensitive occurrence of the literal substring "shopsystem" and no case-insensitive occurrence of the literal substring "fleet"
    And the byte contents of "bin/shop-shell" in the target directory contain the literal substring "shopsystem-bc-lead", confirming the product-neutral launcher image reference is preserved and not slug-rewritten to "dummyco-bc-lead"
    And the byte contents of "bin/shop-shell" in the target directory contain the literal substring "shopsystem-bc-base", confirming the product-neutral leaf-BC runtime image reference is preserved and not slug-rewritten to "dummyco-bc-base"
    And the target directory contains no top-level file named "Dockerfile.dummyco-shell"
    And the target directory contains no top-level file named "Dockerfile.shopsystem-shell"

  @scenario_hash:82c3a716143014a6 @bc:shopsystem-templates
  Scenario: the ops scaffolding files written by bootstrap for a "lead" shop ("compose.yaml", "bin/shop-shell") are shop-owned (in the PDR-003 path F sense) — they are bootstrap-time starter content the operator may freely customize, and they do not sit under ".claude/canonical/" because they are not subject to the canonical-managed re-pour contract that ".claude/canonical/" implies; and no dedicated shell Dockerfile is written, because PDR-020 retires it
    Given an existing git repository at a target directory "/tmp/example-lead-shop"
    When I invoke the "shop-templates" bootstrap entry point with shop type "lead", shop name "shopsystem-product", and target directory "/tmp/example-lead-shop"
    Then the exit code is 0
    And after the invocation the target directory contains a top-level file named "compose.yaml" at the path "/tmp/example-lead-shop/compose.yaml" (not under any ".claude/" subdirectory)
    And after the invocation the target directory contains a file at "/tmp/example-lead-shop/bin/shop-shell" (not under any ".claude/" subdirectory)
    And after the invocation the target directory contains no top-level file named "Dockerfile.shopsystem-shell"
    And after the invocation the directory at "/tmp/example-lead-shop/.claude/canonical/" does not contain a file named "compose.yaml", "shop-shell", or "Dockerfile.shopsystem-shell"
