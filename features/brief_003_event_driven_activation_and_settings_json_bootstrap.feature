Feature: brief 003: event-driven shop activation and canonical .claude/settings.json bootstrap extension

  @scenario_hash:f83e03ee69261242 @bc:shopsystem-templates
  Scenario Outline: bootstrap writes the canonical ".claude/settings.json" for the shop type into the target directory, byte-for-byte equal to the current canonical package-data file
  Given an existing git repository at a target directory "<target>" with no ".claude/settings.json" file
  When I invoke the "shop-templates" bootstrap entry point with shop type "<shop_type>", shop name "<shop_name>", and target directory "<target>"
  Then the exit code is 0
  And the target directory contains a file at ".claude/settings.json"
  And the content of that file equals the package-data file contents of the canonical ".claude/settings.json" template for shop type "<shop_type>" byte-for-byte

  Examples:
    | shop_type | shop_name               | target                       |
    | bc        | shopsystem-messaging    | /tmp/example-bc-shop         |
    | lead      | shopsystem-product      | /tmp/example-lead-shop       |

  @scenario_hash:d29cd723439faae1 @bc:shopsystem-templates
  Scenario Outline: the "shop-templates" update entry point re-pours ".claude/settings.json" from the current canonical package data, treating it as bootstrap-managed (not init-only); stale content is replaced and already-current content is preserved
  Given an existing git repository at a target directory "<target>" that was previously bootstrapped as a "<shop_type>" shop named "<shop_name>"
  And the file at ".claude/settings.json" in the target directory differs from the current canonical ".claude/settings.json" template for shop type "<shop_type>"
  When I invoke the "shop-templates" update entry point against the target directory "<target>"
  Then the exit code is 0
  And after the invocation the file at ".claude/settings.json" in the target directory equals the current canonical ".claude/settings.json" template for shop type "<shop_type>" byte-for-byte

  Examples:
    | shop_type | shop_name               | target                       |
    | bc        | shopsystem-messaging    | /tmp/example-bc-shop         |
    | lead      | shopsystem-product      | /tmp/example-lead-shop       |

  @scenario_hash:d3066d4476d0a975 @bc:shopsystem-templates
  Scenario Outline: invoking "shop-templates" update against a target directory whose ".claude/settings.json" already equals the current canonical leaves the file byte-for-byte unchanged
  Given an existing git repository at a target directory "<target>" that was previously bootstrapped as a "<shop_type>" shop named "<shop_name>"
  And the file at ".claude/settings.json" in the target directory equals the current canonical ".claude/settings.json" template for shop type "<shop_type>" byte-for-byte
  When I invoke the "shop-templates" update entry point against the target directory "<target>"
  Then the exit code is 0
  And after the invocation the file at ".claude/settings.json" in the target directory still equals the current canonical ".claude/settings.json" template for shop type "<shop_type>" byte-for-byte

  Examples:
    | shop_type | shop_name               | target                       |
    | bc        | shopsystem-messaging    | /tmp/example-bc-shop         |
    | lead      | shopsystem-product      | /tmp/example-lead-shop       |

  @scenario_hash:cad1153ef4dfd18c @bc:shopsystem-templates
  Scenario Outline: the top-level "CLAUDE.md" that bootstrap writes names the host-level prereqs the canonical SessionStart activation hook depends on ("inotify-tools" providing "inotifywait", and "coreutils" providing "stdbuf"), so an operator on a host missing those packages has a documented expectation to point at
  Given an existing git repository at a target directory "<target>" with no top-level "CLAUDE.md"
  When I invoke the "shop-templates" bootstrap entry point with shop type "<shop_type>", shop name "<shop_name>", and target directory "<target>"
  Then the exit code is 0
  And the target directory contains a top-level file named "CLAUDE.md"
  And the content of that file contains the literal substring "inotify-tools"
  And the content of that file contains the literal substring "coreutils"
  And the content of that file contains the literal substring "inotifywait"
  And the content of that file contains the literal substring "stdbuf"

  Examples:
    | shop_type | shop_name               | target                       |
    | bc        | shopsystem-messaging    | /tmp/example-bc-shop         |
    | lead      | shopsystem-product      | /tmp/example-lead-shop       |

  @scenario_hash:6bc3eb5f62115d91 @bc:shopsystem-templates
  Scenario Outline: the canonical "CLAUDE.md" primer template for each shop type names the host-level prereqs the canonical SessionStart activation hook depends on, so the prereq naming is package-data property and not a per-shop hand-edit
  When I ask the "shop-templates" package for the canonical "CLAUDE.md" primer template for shop type "<shop_type>" through its public template-access surface
  Then a non-empty template body is returned
  And the returned body contains the literal substring "inotify-tools"
  And the returned body contains the literal substring "coreutils"
  And the returned body contains the literal substring "inotifywait"
  And the returned body contains the literal substring "stdbuf"

  Examples:
    | shop_type |
    | bc        |
    | lead      |

  @scenario_hash:3957f255c35aff60 @bc:shopsystem-templates
  Scenario: on session start in a bootstrapped lead shop, every BC CLI installed into the product venv (for example "shop-msg", "shop-templates") resolves invocations to the current source tree of that BC's clone under "repos/", so an edit to a BC's source is reflected in the next CLI invocation without an intervening manual reinstall
  Given an existing git repository at a target directory "/tmp/example-lead-shop" that was previously bootstrapped as a "lead" shop named "shopsystem-product"
  And the target directory contains a sibling BC clone at "repos/shopsystem-messaging/" whose installed package name is "shop-msg"
  And a fresh edit has been made to a Python source file under "repos/shopsystem-messaging/src/" that changes observable CLI behavior of "shop-msg"
  When a Claude Code session starts in the target directory and the "SessionStart" hooks declared by ".claude/settings.json" complete
  And the agent invokes the "shop-msg" CLI through its normal entry point
  Then the invocation exhibits the post-edit observable behavior
  And no manual "pip install" step is required between the source edit and the invocation

  @scenario_hash:ff882696856530a4 @bc:shopsystem-templates
  Scenario: bootstrap of a lead shop installs each sibling BC clone under "repos/" into the product venv in editable mode, so that source-tree edits in a BC clone are immediately reflected in subsequent CLI invocations against the lead shop's venv without an intervening manual reinstall
  Given a target directory "/tmp/example-lead-shop" containing an existing git repository
  And the target directory contains a sibling BC clone at "repos/shopsystem-messaging/" with a valid Python package whose installed entry point name is "shop-msg"
  When I invoke the "shop-templates" bootstrap entry point with shop type "lead", shop name "shopsystem-product", and target directory "/tmp/example-lead-shop"
  Then the exit code is 0
  And the product venv reports the installed location of the "shop-msg" distribution as pointing into "repos/shopsystem-messaging/" of the target directory
  And the "pip show shop-msg" output for the product venv records the install as editable

  # ---------------------------------------------------------------------
  # brief-003 realization revision (lead-pn9 / parent lead-o00):
  # the activation mechanism shifts from a SessionStart hook running
  # `inotifywait -m` (which Claude Code awaits synchronously and so
  # hangs session startup) to a router-side instruction in the canonical
  # CLAUDE.md primer to arm the in-session Monitor tool on the same
  # pipeline. Scenarios 71-75 below carry the revised realization;
  # scenarios 57, 58, 59, 65, 68 (hashes 1621b59b0ea8b20b,
  # 679d227f04533ad4, c1e7f31eeef73e05, a9379ab3a162158d,
  # 287e6a4f31533336) were retired in this round.
  # ---------------------------------------------------------------------

  @scenario_hash:206ca3d0fa40bcad @bc:shopsystem-templates
  Scenario Outline: the canonical "CLAUDE.md" primer template for each shop type contains an instruction telling the session router to arm the in-session "Monitor" tool, at session start, on a line-buffered "inotifywait" pipeline watching the shop-type's inbound mailbox surface, so the in-session Monitor primitive — not a synchronous SessionStart hook — carries the reactivity invariant
    When I ask the "shop-templates" package for the canonical "CLAUDE.md" primer template for shop type "<shop_type>" through its public template-access surface
    Then a non-empty template body is returned
    And the returned body contains the literal substring "Monitor"
    And the returned body contains the literal substring "session start"
    And the returned body contains the literal substring "stdbuf -oL inotifywait"
    And the returned body contains the literal substring "-m -e create,moved_to"
    And the returned body contains the literal substring "<watch_target>"
    And the returned body does not contain any instruction to arm the watcher via a "SessionStart" hook in ".claude/settings.json"

    Examples:
      | shop_type | watch_target       |
      | bc        | inbox/             |
      | lead      | repos/*/outbox/    |

  @scenario_hash:d87ccb133fa64d2f @bc:shopsystem-templates
  Scenario Outline: the activation instruction in the canonical "CLAUDE.md" primer template for each shop type explicitly names both host prerequisites the router's Monitor invocation depends on AND explicitly instructs the router to refuse to arm the watcher and surface a visible diagnostic when either prerequisite is missing, so that the loud-fail invariant carrying over from the prior hook-realization is preserved as a router-honored instruction
    When I ask the "shop-templates" package for the canonical "CLAUDE.md" primer template for shop type "<shop_type>" through its public template-access surface
    Then a non-empty template body is returned
    And the returned body contains the literal substring "inotifywait"
    And the returned body contains the literal substring "stdbuf"
    And the returned body contains an instruction substring directing the router to verify these executables are on PATH before arming the Monitor
    And the returned body contains an instruction substring directing the router to refuse to arm the Monitor and surface a visible diagnostic when either executable is missing
    And the returned body does not contain any instruction telling the router to silently fall back to a no-watcher state when a prerequisite is missing

    Examples:
      | shop_type |
      | bc        |
      | lead      |

  @scenario_hash:9f15982aa00829f1 @bc:shopsystem-templates
  Scenario Outline: the top-level "CLAUDE.md" that bootstrap writes into the target directory contains the router-side Monitor activation instruction for the shop type, so a freshly-bootstrapped shop is reactive on its first session start without depending on a SessionStart hook
    Given an existing git repository at a target directory "<target>" with no top-level "CLAUDE.md"
    When I invoke the "shop-templates" bootstrap entry point with shop type "<shop_type>", shop name "<shop_name>", and target directory "<target>"
    Then the exit code is 0
    And the target directory contains a top-level file named "CLAUDE.md"
    And the content of that file contains the literal substring "Monitor"
    And the content of that file contains the literal substring "session start"
    And the content of that file contains the literal substring "stdbuf -oL inotifywait"
    And the content of that file contains the literal substring "-m -e create,moved_to"
    And the content of that file contains the literal substring "<watch_target>"

    Examples:
      | shop_type | shop_name               | target                       | watch_target       |
      | bc        | shopsystem-messaging    | /tmp/example-bc-shop         | inbox/             |
      | lead      | shopsystem-product      | /tmp/example-lead-shop       | repos/*/outbox/    |

  @scenario_hash:11cf1e054f79fed4 @bc:shopsystem-templates
  Scenario: the canonical ".claude/settings.json" template for shop type "bc" parses as a JSON object whose "hooks" key maps to a JSON object containing no "SessionStart" entries, so a BC shop's canonical settings.json carries no activation hook and no speculative non-activation hooks today
    When I ask the "shop-templates" package for the canonical ".claude/settings.json" template for shop type "bc" through its public template-access surface
    And the returned body is parsed as JSON
    Then the parsed value at top-level key "hooks" is a JSON object
    And the parsed value at "hooks" has no key named "SessionStart", or the value at "hooks.SessionStart" is a JSON array of length 0
    And the returned body does not contain the literal substring "inotifywait"
    And the returned body does not contain the literal substring "stdbuf"

  @scenario_hash:71797e9017c95fed @bc:shopsystem-templates
  Scenario: the canonical ".claude/settings.json" template for shop type "lead" declares "bd prime" as the sole inner-hook command under "SessionStart", carries no activation hook, and conforms to the Claude Code matcher+hooks wrapper schema
    When I ask the "shop-templates" package for the canonical ".claude/settings.json" template for shop type "lead" through its public template-access surface
    And the returned body is parsed as JSON
    Then the parsed value at top-level key "hooks" is a JSON object
    And the parsed value at "hooks.SessionStart" is a JSON array of length at least 1
    And exactly one JSON-object element of "hooks.SessionStart" has an inner "hooks" array containing an entry whose "command" string equals "bd prime"
    And no element of "hooks.SessionStart" has an inner "hooks" array containing an entry whose "command" string contains the substring "inotifywait"
    And no element of "hooks.SessionStart" has an inner "hooks" array containing an entry whose "command" string contains the substring "stdbuf"
    And every element of "hooks.SessionStart" is a JSON object with a "matcher" key whose value is a string and a "hooks" key whose value is a JSON array of length at least 1
