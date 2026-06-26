Feature: footing/compose startup hardening (broker unlock, healthcheck role, pgdata ownership)
  Three lead-reproduced startup fixes: the agent-vault broker store is reset so it
  re-keys to this run's master password (no 'wrong password' on fresh or re-run); the
  postgres healthcheck probes the configured POSTGRES_USER (no role-does-not-exist log);
  and postgres runs as the invoking host user so the bind-mounted pgdata is host-owned.

@scenario_hash:c803b65be9b7fd83 @bc:shopsystem-templates
Scenario: footing brings the stack up so the agent-vault broker unlocks and serves without "wrong password" on a fresh bootstrap and on a re-run
  Given a freshly forked "acme-lead" repository carrying the rendered compose.yaml and .env.example
  And the agent-vault broker store lives in the persistent named volume "acme-agent-vault-data"
  When footing brings the compose stack up for the first time
  Then the "acme-agent-vault" broker container reaches a running state and does not exit with "wrong password"
  And the broker store is keyed to the master password footing uses, so the broker unlocks and serves on its API port
  When footing is re-run against the same persistent "acme-agent-vault-data" volume
  Then the "acme-agent-vault" broker container again reaches a running state and does not exit with "wrong password"
  And the broker store remains consistent with the master password footing uses on the re-run, so the broker unlocks and serves

@scenario_hash:87acbbbede8b1824 @bc:shopsystem-templates
Scenario: the rendered postgres healthcheck targets the configured POSTGRES_USER so no role-does-not-exist error is logged
  Given a "lead" shop named "acme" whose bootstrap-rendered compose.yaml sets the postgres service "POSTGRES_USER" to "acme"
  When the postgres service runs its compose healthcheck on each interval
  Then the healthcheck pg_isready probe targets the configured POSTGRES_USER value "acme" rather than the literal "postgres"
  And the postgres container logs do not contain "role \"postgres\" does not exist" on any healthcheck interval

@scenario_hash:25be1dd7b421059a @bc:shopsystem-templates
Scenario: footing brings postgres up so the bind-mounted pgdata host directory is owned by the invoking host user and postgres still serves
  Given a "lead" shop named "acme" whose compose postgres service bind-mounts the host pgdata directory to "/var/lib/postgresql/data"
  And the operator invokes "./bin/bootstrap" as host user with uid "1000" and gid "1000"
  When footing prepares the pgdata host directory and brings the postgres service up
  Then the bind-mounted pgdata host directory exists and is owned by uid "1000" and gid "1000" rather than uid "999"
  And the postgres container initializes its data directory as that uid and reaches a healthy serving state accepting connections as the configured "acme" user
