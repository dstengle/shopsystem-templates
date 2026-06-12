Feature: ops scaffolding is slug-parametric (lead shop) — compose/shop-shell/Dockerfile derive every product literal from the shop slug, with collision-free host ports and a broker-wired shop-shell, leaving no default-product name in a non-default render

  @scenario_hash:8fcf898fdeebc6be @bc:shopsystem-templates
  Scenario Outline: bootstrap of a "lead" shop named "<slug>" writes a top-level "compose.yaml" whose docker network, postgres container, agent-vault container, and agent-vault data volume are all derived from the shop slug "<slug>" (superseding the literal-"shopsystem" assertion of scenario 133) — so a non-default product slug renders a fully <slug>-scoped compose with no "shopsystem" name leaking through
    Given an existing git repository at a target directory "/tmp/example-lead-shop" with no top-level "compose.yaml" file
    When I invoke the "shop-templates" bootstrap entry point with shop type "lead", shop name "<slug>", and target directory "/tmp/example-lead-shop"
    Then the exit code is 0
    And after the invocation the file at "compose.yaml" in the target directory parses as valid YAML
    And the parsed YAML contains a top-level key "networks" whose value is a mapping containing exactly the key "<slug>" and no key literally named "shopsystem" unless "<slug>" is itself "shopsystem"
    And the parsed YAML "services" mapping contains a key whose value carries a "container_name" equal to "<slug>-postgres"
    And the parsed YAML "services" mapping contains a key whose value carries a "container_name" equal to "<slug>-agent-vault"
    And the parsed YAML contains a top-level key "volumes" whose value is a mapping containing the key "<slug>-agent-vault-data"
    And every service entry under "services" attaches only to the "<slug>" network and to no network literally named "shopsystem" unless "<slug>" is itself "shopsystem"

    Examples:
      | slug       |
      | shopsystem |
      | dummyco    |

  @scenario_hash:9c8b8b40ee9ffde4 @bc:shopsystem-templates
  Scenario Outline: the postgres "pgdata" volume source string in the bootstrap-rendered "compose.yaml" for a "lead" shop named "<slug>" is derived from the slug-parametric "<SLUG_UPPER>_DATA" environment variable (tightening scenario 138, which named only "SHOPSYSTEM_DATA") with a "${HOME}/.local/share/<slug>" default — so the env var name itself tracks the slug, the path is never under the repo, and an operator may override the data root per product
    Given an existing git repository at a target directory "/tmp/example-lead-shop"
    When I invoke the "shop-templates" bootstrap entry point with shop type "lead", shop name "<slug>", and target directory "/tmp/example-lead-shop"
    Then the exit code is 0
    And after the invocation the file at "compose.yaml" in the target directory parses as valid YAML
    And the source string of the volume mount on the postgres service whose target is "/var/lib/postgresql/data" contains the literal substring "<SLUG_UPPER>_DATA"
    And that source string expresses a default whose literal substring is "${HOME}/.local/share/<slug>" or "$HOME/.local/share/<slug>"
    And that source string does not contain the literal substring "/tmp/example-lead-shop"
    And the body of "compose.yaml" in the target directory contains no path beginning with the literal "./pgdata" or "pgdata:"

    Examples:
      | slug       | SLUG_UPPER |
      | shopsystem | SHOPSYSTEM |
      | dummyco    | DUMMYCO    |

  @scenario_hash:5335c39eb06f7493 @bc:shopsystem-templates
  Scenario Outline: bootstrap of a "lead" shop named "<slug>" writes "bin/shop-shell" as an executable bash wrapper that is broker-wired (tightening scenario 134) — its body carries the agent-vault broker credentials and the :14322 HTTPS proxy, greps for the <slug>-derived container, errors when no token is present, and invokes "agent-vault-check"; while still preserving the executable bash wrapper, "docker compose up", "docker run", and "--user vscode" guarantees, and mounting no host "~/.claude" or "~/.gitconfig"
    Given an existing git repository at a target directory "/tmp/example-lead-shop" with no "bin/" subdirectory
    When I invoke the "shop-templates" bootstrap entry point with shop type "lead", shop name "<slug>", and target directory "/tmp/example-lead-shop"
    Then the exit code is 0
    And after the invocation the target directory contains a file at "bin/shop-shell" whose owner-execute permission bit is set and whose first line is exactly "#!/usr/bin/env bash"
    And the body of "bin/shop-shell" contains the literal substring "docker compose" followed somewhere later in the file by the literal substring "up -d postgres", and contains the literal substring "docker run", and contains the literal substring "--user vscode"
    And the body of "bin/shop-shell" references the environment variable "AGENT_VAULT_ADDR" and the environment variable "AGENT_VAULT_TOKEN" for broker credentials
    And the body of "bin/shop-shell" references the proxy endpoint by the literal substring "14322" carried on an "HTTPS_PROXY" assignment
    And the body of "bin/shop-shell" greps for a container name containing the literal substring "<slug>-postgres" or "<slug>-agent-vault"
    And the body of "bin/shop-shell" contains a token-presence guard that exits non-zero with a diagnostic when the broker token is empty or unset
    And the body of "bin/shop-shell" contains the literal substring "agent-vault-check"
    And the body of "bin/shop-shell" does not contain the literal substring "$HOME/.claude" and does not contain the literal substring "$HOME/.gitconfig" and does not contain the literal substring "~/.claude" and does not contain the literal substring "~/.gitconfig"

    Examples:
      | slug       |
      | shopsystem |
      | dummyco    |

  @scenario_hash:abe57dcb4d6f6554 @bc:shopsystem-templates
  Scenario Outline: the postgres host port published by the bootstrap-rendered "compose.yaml" for a "lead" shop named "<slug>" is collision-free per slug — it is "5432 + crc32(<slug>) % 1000" and is overridable by the slug-parametric "<SLUG_UPPER>_POSTGRES_PORT" environment variable — so two distinct products bootstrapped on one host bind distinct host ports by default while each remains operator-overridable
    Given an existing git repository at a target directory "/tmp/example-lead-shop"
    When I invoke the "shop-templates" bootstrap entry point with shop type "lead", shop name "<slug>", and target directory "/tmp/example-lead-shop"
    Then the exit code is 0
    And after the invocation the file at "compose.yaml" in the target directory parses as valid YAML
    And the postgres service's "ports" entry maps a host port whose default value equals "<computed_port>", which is "5432 + crc32(<slug>) % 1000"
    And that "ports" entry expresses the host port through the "<SLUG_UPPER>_POSTGRES_PORT" environment variable with "<computed_port>" as its default
    And the rendered host port "<computed_port>" differs from the host port that the same rule yields for any other product slug, so concurrently bootstrapped products do not collide on the postgres host port

    Examples:
      | slug       | SLUG_UPPER | computed_port |
      | shopsystem | SHOPSYSTEM | 5829          |
      | dummyco    | DUMMYCO    | 5714          |

  @scenario_hash:cb1e585684ff4a14 @bc:shopsystem-templates
  Scenario Outline: the ops scaffolding file-set written by bootstrap for a "lead" shop named "<slug>" enumerates exactly six shop-owned files additively (growing the former four-file set) — "compose.yaml", "bin/shop-shell", "Dockerfile.<slug>-shell", "bin/shop-scenario-completion", "bin/agent-vault-provision", and "bin/agent-vault-check" — each at a shop-owned path outside any ".claude/" subdirectory, so the broker-provisioning pair ships alongside the existing ops files
    Given an existing git repository at a target directory "/tmp/example-lead-shop"
    When I invoke the "shop-templates" bootstrap entry point with shop type "lead", shop name "<slug>", and target directory "/tmp/example-lead-shop"
    Then the exit code is 0
    And after the invocation the target directory contains a top-level file named "compose.yaml" not under any ".claude/" subdirectory
    And after the invocation the target directory contains a file at "bin/shop-shell" not under any ".claude/" subdirectory
    And after the invocation the target directory contains a top-level file named "Dockerfile.<slug>-shell" not under any ".claude/" subdirectory
    And after the invocation the target directory contains a file at "bin/shop-scenario-completion" not under any ".claude/" subdirectory
    And after the invocation the target directory contains a file at "bin/agent-vault-provision" not under any ".claude/" subdirectory
    And after the invocation the target directory contains a file at "bin/agent-vault-check" not under any ".claude/" subdirectory
    And the directory at "/tmp/example-lead-shop/.claude/canonical/" does not contain a file named "compose.yaml", "shop-shell", "Dockerfile.<slug>-shell", "shop-scenario-completion", "agent-vault-provision", or "agent-vault-check"

    Examples:
      | slug       |
      | shopsystem |
      | dummyco    |

  @scenario_hash:1b6dbe8a0095fb8f @bc:shopsystem-templates
  Scenario: the ops scaffolding rendered by bootstrap for a non-default-slug "lead" shop carries zero cross-product literals — for shop name "dummyco" the rendered "compose.yaml", "bin/shop-shell", and "Dockerfile.dummyco-shell" contain no case-insensitive occurrence of the literal "shopsystem" and no case-insensitive occurrence of the literal "fleet", confirming the generification leaves no default-product name baked into a non-default render
    Given an existing git repository at a target directory "/tmp/example-lead-shop"
    When I invoke the "shop-templates" bootstrap entry point with shop type "lead", shop name "dummyco", and target directory "/tmp/example-lead-shop"
    Then the exit code is 0
    And the byte contents of "compose.yaml" in the target directory contain no case-insensitive occurrence of the literal substring "shopsystem" and no case-insensitive occurrence of the literal substring "fleet"
    And the byte contents of "bin/shop-shell" in the target directory contain no case-insensitive occurrence of the literal substring "shopsystem" and no case-insensitive occurrence of the literal substring "fleet"
    And the byte contents of "Dockerfile.dummyco-shell" in the target directory contain no case-insensitive occurrence of the literal substring "shopsystem" and no case-insensitive occurrence of the literal substring "fleet"
    And the target directory contains no top-level file named "Dockerfile.shopsystem-shell"
