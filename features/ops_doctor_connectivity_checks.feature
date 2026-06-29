Feature: rendered bin/doctor operator diagnostic (lead shop, lead-q3r1) — the bootstrap-rendered bin/doctor ops command performs the messaging-DB (SHOPMSG_DSN/postgres), agent-vault broker (reachability + CA trust), and Claude-credential (CLAUDE_OAUTH refreshable) checks, emitting a named pass/fail line with a remediation hint per check, and reports an aggregate pass/fail diagnosis whose exit code is 0 on overall pass and non-zero on any failure

  @scenario_hash:a6f8c0656a9e1cd9 @bc:shopsystem-templates
  Scenario: the rendered "bin/doctor" connectivity check for messaging asserts SHOPMSG_DSN is set and the product postgres is reachable, reporting a named pass/fail line with a remediation hint on failure
    Given a "lead" shop bootstrapped by "shop-templates" with the rendered ops command "bin/doctor"
    When the operator runs "bin/doctor" in a session whose "SHOPMSG_DSN" is set and whose product postgres is reachable at that DSN
    Then "bin/doctor" emits a check line named for the messaging-DB connection (a "SHOPMSG_DSN / postgres" check) whose status is an explicit pass
    And the same check, run in a session where "SHOPMSG_DSN" is unset or points at a postgres that is not reachable, emits that same named check line whose status is an explicit fail
    And the fail line carries a remediation hint naming the corrective action (set "SHOPMSG_DSN" / bring up the product postgres) rather than only reporting that the check failed
