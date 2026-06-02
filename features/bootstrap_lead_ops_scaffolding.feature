Feature: bootstrap renders ops scaffolding (lead-shop only): compose.yaml, bin/shop-shell, Dockerfile.shopsystem-shell

  @scenario_hash:90138f78dfa46697 @bc:shopsystem-templates
  Scenario: bootstrap of a "lead" shop writes a top-level "compose.yaml" defining a postgres service on the "shopsystem" docker network with the pgdata bind mounted from "${SHOPSYSTEM_DATA:-${HOME}/.local/share/shopsystem}/pgdata", so the rendered file matches the prototype that the operator runs with "docker compose up -d postgres" via "./bin/shop-shell"
  Given an existing git repository at a target directory "/tmp/example-lead-shop" with no top-level "compose.yaml" file
  When I invoke the "shop-templates" bootstrap entry point with shop type "lead", shop name "shopsystem-product", and target directory "/tmp/example-lead-shop"
  Then the exit code is 0
  And after the invocation the target directory contains a top-level file named "compose.yaml"
  And the file at "compose.yaml" in the target directory parses as valid YAML
  And the parsed YAML contains a top-level key "services" whose value is a mapping containing a key "postgres"
  And the "services.postgres" mapping has an "image" value whose string form begins with the literal "postgres:"
  And the "services.postgres" mapping has a "networks" entry naming the "shopsystem" network
  And the "services.postgres" mapping has a "volumes" entry whose source string contains the literal substring "${SHOPSYSTEM_DATA:-${HOME}/.local/share/shopsystem}/pgdata" and whose target string is exactly "/var/lib/postgresql/data"
  And the parsed YAML contains a top-level key "networks" whose value is a mapping containing a key "shopsystem"
  And no service entry under "services" mounts a volume whose source path resolves underneath "/tmp/example-lead-shop"

  @scenario_hash:3d94639d5af360d7 @bc:shopsystem-templates
  Scenario: bootstrap of a "lead" shop writes "bin/shop-shell" as an executable bash script whose body brings up the compose-defined postgres if not already running and execs "docker run" against the shell image, so a fresh operator can run "./bin/shop-shell" with no further configuration
  Given an existing git repository at a target directory "/tmp/example-lead-shop" with no "bin/" subdirectory
  When I invoke the "shop-templates" bootstrap entry point with shop type "lead", shop name "shopsystem-product", and target directory "/tmp/example-lead-shop"
  Then the exit code is 0
  And after the invocation the target directory contains a file at "bin/shop-shell"
  And the file at "bin/shop-shell" in the target directory has its owner-execute permission bit set
  And the first line of the file at "bin/shop-shell" is exactly "#!/usr/bin/env bash"
  And the body of "bin/shop-shell" contains the literal substring "docker compose" followed somewhere later in the file by the literal substring "up -d postgres"
  And the body of "bin/shop-shell" contains the literal substring "docker run"
  And the body of "bin/shop-shell" references the environment variable "SHOPSYSTEM_DATA" with a default of "$HOME/.local/share/shopsystem"
  And the body of "bin/shop-shell" references the environment variable "SHOPSYSTEM_SHELL_IMAGE" for the shell image tag
  And the body of "bin/shop-shell" contains the literal substring "/var/run/docker.sock:/var/run/docker.sock"

  @scenario_hash:9bc85eced7685a40 @bc:shopsystem-templates
  Scenario: bootstrap of a "lead" shop writes a top-level "Dockerfile.shopsystem-shell" containing the recipe for the daily-driver shell image referenced by "bin/shop-shell", so an operator without a published shopsystem-shell image can build it locally with "docker build -t shopsystem-shell:dev -f Dockerfile.shopsystem-shell ."
  Given an existing git repository at a target directory "/tmp/example-lead-shop" with no top-level "Dockerfile.shopsystem-shell" file
  When I invoke the "shop-templates" bootstrap entry point with shop type "lead", shop name "shopsystem-product", and target directory "/tmp/example-lead-shop"
  Then the exit code is 0
  And after the invocation the target directory contains a top-level file named "Dockerfile.shopsystem-shell"
  And the file at "Dockerfile.shopsystem-shell" in the target directory contains a "FROM" instruction whose literal image reference is "ghcr.io/dstengle/devcontainer-python-node-claude:latest", which is the same devcontainer base image the lead host and bc-launcher containers run and which already ships a working docker CLI on PATH for the non-root shell user
  And the file at "Dockerfile.shopsystem-shell" in the target directory does not contain the literal substring "docker-ce-cli", because the docker CLI is provided by the devcontainer base image rather than by an explicit apt-install layer
  And the file at "Dockerfile.shopsystem-shell" in the target directory contains a "USER" instruction whose literal token form names a non-root user, so the built image runs the shell as that user and the base image's socket-GID reconciler can make the mounted docker socket reachable
  And the file at "Dockerfile.shopsystem-shell" in the target directory installs at least one of the framework CLIs by literal substring match against the set "shop-msg", "scenarios", or "shop-templates"
  And the file at "Dockerfile.shopsystem-shell" in the target directory contains a "CMD" or "ENTRYPOINT" instruction whose literal token form references "/bin/bash" or "bash"

  @scenario_hash:82c069bd3fb3b1d4 @bc:shopsystem-templates
  Scenario: bootstrap of a "bc" shop does not write the lead-shop ops scaffolding (no "compose.yaml", no "bin/shop-shell", no "Dockerfile.shopsystem-shell") because a BC runs inside a bc-launcher container and never owns its own postgres or shell image
  Given an existing git repository at a target directory "/tmp/example-bc-shop" with no top-level "compose.yaml", no "bin/" subdirectory, and no top-level "Dockerfile.shopsystem-shell"
  When I invoke the "shop-templates" bootstrap entry point with shop type "bc", shop name "shopsystem-messaging", and target directory "/tmp/example-bc-shop"
  Then the exit code is 0
  And after the invocation the target directory contains no top-level file named "compose.yaml"
  And after the invocation the target directory contains no file at "bin/shop-shell"
  And after the invocation the target directory contains no top-level file named "Dockerfile.shopsystem-shell"

  @scenario_hash:8cf5656c55b466e7 @bc:shopsystem-templates
  Scenario: the ops scaffolding files written by bootstrap for a "lead" shop ("compose.yaml", "bin/shop-shell", "Dockerfile.shopsystem-shell") are shop-owned (in the PDR-003 path F sense) — they are bootstrap-time starter content the operator may freely customize, and they do not sit under ".claude/canonical/" because they are not subject to the canonical-managed re-pour contract that ".claude/canonical/" implies
  Given an existing git repository at a target directory "/tmp/example-lead-shop"
  When I invoke the "shop-templates" bootstrap entry point with shop type "lead", shop name "shopsystem-product", and target directory "/tmp/example-lead-shop"
  Then the exit code is 0
  And after the invocation the target directory contains a top-level file named "compose.yaml" at the path "/tmp/example-lead-shop/compose.yaml" (not under any ".claude/" subdirectory)
  And after the invocation the target directory contains a file at "/tmp/example-lead-shop/bin/shop-shell" (not under any ".claude/" subdirectory)
  And after the invocation the target directory contains a top-level file named "Dockerfile.shopsystem-shell" at the path "/tmp/example-lead-shop/Dockerfile.shopsystem-shell" (not under any ".claude/" subdirectory)
  And after the invocation the directory at "/tmp/example-lead-shop/.claude/canonical/" does not contain a file named "compose.yaml", "shop-shell", or "Dockerfile.shopsystem-shell"

  @scenario_hash:43e085e8627c7756 @bc:shopsystem-templates
  Scenario: the postgres "pgdata" volume source string in the bootstrap-rendered "compose.yaml" for a "lead" shop is derived from the "SHOPSYSTEM_DATA" environment variable with a "$HOME/.local/share/shopsystem" default, and never resolves to a path underneath the target shop's own repository — so an operator who runs "docker compose up -d postgres" from a freshly bootstrapped shop does not pollute the repo with a "pgdata/" directory
  Given an existing git repository at a target directory "/tmp/example-lead-shop"
  When I invoke the "shop-templates" bootstrap entry point with shop type "lead", shop name "shopsystem-product", and target directory "/tmp/example-lead-shop"
  Then the exit code is 0
  And after the invocation the file at "compose.yaml" in the target directory parses as valid YAML
  And the source string of the volume mount on "services.postgres" whose target is "/var/lib/postgresql/data" contains the literal substring "SHOPSYSTEM_DATA"
  And the source string of that volume mount expresses a default whose literal substring is "${HOME}/.local/share/shopsystem" or "$HOME/.local/share/shopsystem"
  And the source string of that volume mount does not contain the literal substring "/tmp/example-lead-shop"
  And the body of "compose.yaml" in the target directory contains no path beginning with the literal "./pgdata" or "pgdata:"
