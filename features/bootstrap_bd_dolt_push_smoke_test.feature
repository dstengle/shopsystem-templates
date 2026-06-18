Feature: bootstrap runs a bd dolt push smoke-test against the rendered beads config

  After rendering .beads/config.yaml with the product sync.remote, bootstrap
  proves the freshly-wired tracker can actually reach its configured remote by
  running a `bd dolt push` smoke-test. On success it reports success; on a
  failed push it exits non-zero with a diagnostic — so a misconfigured or
  unreachable remote is caught at bootstrap time, not at the first mid-work
  work_done emission. (tmpl-4k7 / PDR-019 U5 / ADR-040.)

  @scenario_hash:62eb2a8b9b617f4b @bc:shopsystem-templates
  Scenario: shop-templates bootstrap runs a bd dolt push smoke-test against the rendered beads config
    Given an existing git repository at a target directory "<target>" with the beads config rendered by bootstrap
    When the bootstrap smoke-test step runs
    Then it performs a "bd dolt push" against the configured "sync.remote" and reports success
    And bootstrap exits non-zero with a diagnostic if the "bd dolt push" smoke-test fails
