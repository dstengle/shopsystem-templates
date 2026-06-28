Feature: bootstrap renders the single shell-sourceable bin/ops-coordinates artifact (ADR-043 Phase 1 / ADR-046) — a KEY=value env-file whose OPS_* keys are env-overridable ${OVERRIDE:-default} assignments, so sourcing it defines the load-bearing coordinate variables (OPS_NETWORK, the container-name keys, OPS_FRAMEWORK_IMAGE) non-empty for bin/shop-shell and the other bin/ ops scripts

@scenario_hash:d5d65b9cfedc24c1 @bc:shopsystem-templates
Scenario Outline: bootstrap of a "lead" shop named "<slug>" renders the single shell-sourceable ops-coordinates artifact at "bin/ops-coordinates" (the ADR-043 D2 derivation root) — a "KEY=value" env-file derived from the manifest "product:" root whose OPS_* keys are written as environment-overridable "${OVERRIDE:-default}" assignments — so that "source bin/ops-coordinates" defines the load-bearing coordinate variables that the rendered "bin/shop-shell" and the other "bin/" ops scripts consume, with the consumer keys (notably OPS_NETWORK, the container-name keys, and OPS_FRAMEWORK_IMAGE) resolving to non-empty values and never an empty launch reference
  Given an existing git repository at a target directory "/tmp/example-lead-shop" with no "bin/" subdirectory
  When I invoke the "shop-templates" bootstrap entry point with shop type "lead", shop name "<slug>", and target directory "/tmp/example-lead-shop"
  Then the exit code is 0
  And after the invocation the target directory contains a file at "bin/ops-coordinates" not under any ".claude/" subdirectory
  And sourcing "bin/ops-coordinates" in a bash shell succeeds with exit code 0 and defines the shell variables OPS_SLUG, OPS_NETWORK, OPS_POSTGRES_CONTAINER, OPS_VAULT_CONTAINER, OPS_VAULT_NAME, OPS_BROKER_ADDR, OPS_POSTGRES_PORT, OPS_VAULT_API_PORT, OPS_VAULT_PROXY_PORT, OPS_DATA_ROOT, OPS_LEAD_BEADS_REPO, OPS_BC_BEADS_REPO_FMT, OPS_ORG, and OPS_FRAMEWORK_IMAGE
  And each OPS_* assignment in "bin/ops-coordinates" is written as an environment-overridable parameter expansion of the form OPS_X="${<OVERRIDE>:-<rendered-default>}", so that an override value exported before sourcing takes precedence over the rendered default
  And after sourcing with no override environment set, OPS_SLUG resolves to "<slug>", OPS_NETWORK resolves to "<slug>", OPS_POSTGRES_CONTAINER resolves to "<slug>-postgres", and OPS_VAULT_CONTAINER resolves to "<slug>-agent-vault"
  And after sourcing with no override environment set, OPS_FRAMEWORK_IMAGE resolves to the canonical product-neutral default "ghcr.io/dstengle/shopsystem-bc-lead:latest" regardless of "<slug>"
  And after sourcing, each of the load-bearing consumer keys OPS_NETWORK, OPS_POSTGRES_CONTAINER, OPS_VAULT_CONTAINER, and OPS_FRAMEWORK_IMAGE resolves to a non-empty value, so the rendered "bin/shop-shell" never resolves an empty docker network, an empty container reference, or an empty launch image
  And exporting "<SLUG_UPPER>_POSTGRES_PORT" with value "<override_port>" before sourcing makes OPS_POSTGRES_PORT resolve to "<override_port>" rather than its rendered default, demonstrating the env-overridable precedence end-to-end

  Examples:
    | slug       | SLUG_UPPER | override_port |
    | shopsystem | SHOPSYSTEM | 6000          |
    | dummyco    | DUMMYCO    | 6001          |
