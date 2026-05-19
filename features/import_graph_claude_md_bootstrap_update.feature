Feature: import-graph CLAUDE.md: typed files, bootstrap, and update contracts (PDR-003 alt F)

  @scenario_hash:cad9ccb5b462978d @bc:shopsystem-templates
  Scenario Outline: the "shop-templates" package exposes a canonical "CLAUDE.md" body template per shop type through its public template-access surface; this is the canonical-managed file that bootstrap writes to the target root and that update rewrites from package data
  When I ask the "shop-templates" package for the canonical "CLAUDE.md" body template for shop type "<shop_type>" through its public template-access surface
  Then a non-empty template body is returned
  And the returned body contains an "@" import line referencing ".claude/shop/name.md"
  And the returned body contains an "@" import line referencing ".claude/shop/type.md"
  And the returned body contains an "@" import line referencing ".claude/canonical/<shop_type>-primer.md"
  And the returned body contains an "@" import line referencing ".claude/shop/primer.md"

  Examples:
    | shop_type |
    | bc        |
    | lead      |

  @scenario_hash:2b9bd9c82017b0c6 @bc:shopsystem-templates
  Scenario Outline: bootstrap writes the top-level "CLAUDE.md" with body byte-for-byte equal to the canonical "CLAUDE.md" body template for the chosen shop type, with no shop-specific splicing into the file itself
  Given an existing git repository at a target directory "<target>" with no top-level "CLAUDE.md"
  When I invoke the "shop-templates" bootstrap entry point with shop type "<shop_type>", shop name "<shop_name>", and target directory "<target>"
  Then the exit code is 0
  And the target directory contains a top-level file named "CLAUDE.md"
  And the byte contents of the file at "CLAUDE.md" in the target directory equal the canonical "CLAUDE.md" body template for shop type "<shop_type>" byte-for-byte

  Examples:
    | shop_type | shop_name               | target                       |
    | bc        | shopsystem-messaging    | /tmp/example-bc-shop         |
    | lead      | shopsystem-product      | /tmp/example-lead-shop       |

  @scenario_hash:207dcfa0f8b3ca91 @bc:shopsystem-templates
  Scenario Outline: bootstrap writes ".claude/shop/name.md" into the target directory containing exactly the value passed as "--shop-name", with no other content
  Given an existing git repository at a target directory "<target>" with no ".claude/shop/" subdirectory
  When I invoke the "shop-templates" bootstrap entry point with shop type "<shop_type>", shop name "<shop_name>", and target directory "<target>"
  Then the exit code is 0
  And the target directory contains a file at ".claude/shop/name.md"
  And the byte contents of that file are exactly the literal string "<shop_name>" with a single trailing newline and no other content

  Examples:
    | shop_type | shop_name               | target                       |
    | bc        | shopsystem-messaging    | /tmp/example-bc-shop         |
    | lead      | shopsystem-product      | /tmp/example-lead-shop       |

  @scenario_hash:510520660d55522a @bc:shopsystem-templates
  Scenario Outline: bootstrap writes ".claude/shop/type.md" into the target directory containing exactly the value passed as "--shop-type", with no other content
  Given an existing git repository at a target directory "<target>" with no ".claude/shop/" subdirectory
  When I invoke the "shop-templates" bootstrap entry point with shop type "<shop_type>", shop name "<shop_name>", and target directory "<target>"
  Then the exit code is 0
  And the target directory contains a file at ".claude/shop/type.md"
  And the byte contents of that file are exactly the literal string "<shop_type>" with a single trailing newline and no other content

  Examples:
    | shop_type | shop_name               | target                       |
    | bc        | shopsystem-messaging    | /tmp/example-bc-shop         |
    | lead      | shopsystem-product      | /tmp/example-lead-shop       |

  @scenario_hash:35c34f0e2d11c092 @bc:shopsystem-templates
  Scenario Outline: bootstrap writes ".claude/canonical/<shop_type>-primer.md" into the target directory with body byte-for-byte equal to the canonical primer template for the chosen shop type, as exposed by the "shop-templates" public template-access surface
  Given an existing git repository at a target directory "<target>" with no ".claude/canonical/" subdirectory
  When I invoke the "shop-templates" bootstrap entry point with shop type "<shop_type>", shop name "<shop_name>", and target directory "<target>"
  Then the exit code is 0
  And the target directory contains a file at ".claude/canonical/<shop_type>-primer.md"
  And the byte contents of that file equal the canonical "CLAUDE.md" primer template for shop type "<shop_type>" byte-for-byte

  Examples:
    | shop_type | shop_name               | target                       |
    | bc        | shopsystem-messaging    | /tmp/example-bc-shop         |
    | lead      | shopsystem-product      | /tmp/example-lead-shop       |

  @scenario_hash:0bba99e6f592a788 @bc:shopsystem-templates
  Scenario Outline: bootstrap writes ".claude/shop/primer.md" into the target directory as a shop-authored placeholder file that the operator may populate later; the file exists after bootstrap and contains no canonical primer text
  Given an existing git repository at a target directory "<target>" with no ".claude/shop/" subdirectory
  When I invoke the "shop-templates" bootstrap entry point with shop type "<shop_type>", shop name "<shop_name>", and target directory "<target>"
  Then the exit code is 0
  And the target directory contains a file at ".claude/shop/primer.md"
  And the byte contents of that file do not contain any non-trivial substring (length 64 or greater) that also appears in the canonical "CLAUDE.md" primer template for shop type "<shop_type>"

  Examples:
    | shop_type | shop_name               | target                       |
    | bc        | shopsystem-messaging    | /tmp/example-bc-shop         |
    | lead      | shopsystem-product      | /tmp/example-lead-shop       |

  @scenario_hash:68ce85606d46d7bb @bc:shopsystem-templates
  Scenario Outline: after bootstrap, the "CLAUDE.md" that bootstrap wrote at the target root, when its "@" import directives are resolved against the target directory, has assistant-observable startup content that includes the literal contents of all four typed files written by bootstrap (".claude/shop/name.md", ".claude/shop/type.md", ".claude/canonical/<shop_type>-primer.md", ".claude/shop/primer.md")
  Given an existing git repository at a target directory "<target>" with no top-level "CLAUDE.md"
  When I invoke the "shop-templates" bootstrap entry point with shop type "<shop_type>", shop name "<shop_name>", and target directory "<target>"
  And I resolve the "@" import directives in the bootstrapped "CLAUDE.md" against the target directory
  Then the exit code of the bootstrap invocation is 0
  And the resolved content contains the byte contents of the file at ".claude/shop/name.md" in the target directory
  And the resolved content contains the byte contents of the file at ".claude/shop/type.md" in the target directory
  And the resolved content contains the byte contents of the file at ".claude/canonical/<shop_type>-primer.md" in the target directory
  And the resolved content contains the byte contents of the file at ".claude/shop/primer.md" in the target directory

  Examples:
    | shop_type | shop_name               | target                       |
    | bc        | shopsystem-messaging    | /tmp/example-bc-shop         |
    | lead      | shopsystem-product      | /tmp/example-lead-shop       |

  @scenario_hash:c458502d8632952b @bc:shopsystem-templates
  Scenario Outline: update overwrites the top-level "CLAUDE.md" in the target directory with the canonical "CLAUDE.md" body template for the shop's declared type when the target's "CLAUDE.md" has drifted from canonical; this contradicts and replaces scenario 39's byte-for-byte non-touch invariant on "CLAUDE.md" itself (the shop-authored-content preservation invariant moves to ".claude/shop/primer.md", pinned by scenario 87)
  Given an existing git repository at a target directory "/tmp/example-shop" that was previously bootstrapped as a "<shop_type>" shop named "<shop_name>"
  And the file at "CLAUDE.md" in the target directory has been edited since bootstrap so that its byte contents are not equal to the canonical "CLAUDE.md" body template for shop type "<shop_type>"
  When I invoke the "shop-templates" update entry point against the target directory "/tmp/example-shop"
  Then the exit code is 0
  And after the invocation the byte contents of the file at "CLAUDE.md" in the target directory equal the canonical "CLAUDE.md" body template for shop type "<shop_type>" byte-for-byte

  Examples:
    | shop_type | shop_name               |
    | bc        | shopsystem-messaging    |
    | lead      | shopsystem-product      |

  @scenario_hash:ce122bcb7d794888 @bc:shopsystem-templates
  Scenario Outline: update overwrites ".claude/canonical/<shop_type>-primer.md" in the target directory with the canonical primer template for the shop's declared type when the on-disk file has drifted from canonical
  Given an existing git repository at a target directory "/tmp/example-shop" that was previously bootstrapped as a "<shop_type>" shop named "<shop_name>"
  And the file at ".claude/canonical/<shop_type>-primer.md" in the target directory has been edited since bootstrap so that its byte contents are not equal to the canonical "CLAUDE.md" primer template for shop type "<shop_type>"
  When I invoke the "shop-templates" update entry point against the target directory "/tmp/example-shop"
  Then the exit code is 0
  And after the invocation the byte contents of the file at ".claude/canonical/<shop_type>-primer.md" in the target directory equal the canonical "CLAUDE.md" primer template for shop type "<shop_type>" byte-for-byte

  Examples:
    | shop_type | shop_name               |
    | bc        | shopsystem-messaging    |
    | lead      | shopsystem-product      |

  @scenario_hash:3d3f8c8427366491 @bc:shopsystem-templates
  Scenario Outline: update does not overwrite or otherwise modify ".claude/shop/name.md" in the target directory, even when the canonical "CLAUDE.md" body template, the canonical primer template, or the role-prompt templates have changed since the shop was bootstrapped
  Given an existing git repository at a target directory "/tmp/example-shop" that was previously bootstrapped as a "<shop_type>" shop named "<shop_name>"
  And the file at ".claude/shop/name.md" in the target directory has been edited since bootstrap so that its content includes a literal shop-authored sentence
  And I record the byte contents of the file at ".claude/shop/name.md" in the target directory before the invocation
  When I invoke the "shop-templates" update entry point against the target directory "/tmp/example-shop"
  Then the exit code is 0
  And after the invocation the file at ".claude/shop/name.md" in the target directory has byte-for-byte the same on-disk contents as before the invocation

  Examples:
    | shop_type | shop_name               |
    | bc        | shopsystem-messaging    |
    | lead      | shopsystem-product      |

  @scenario_hash:ca3fc9ec7c67ddb2 @bc:shopsystem-templates
  Scenario Outline: update does not overwrite or otherwise modify ".claude/shop/type.md" in the target directory, even when the canonical "CLAUDE.md" body template, the canonical primer template, or the role-prompt templates have changed since the shop was bootstrapped
  Given an existing git repository at a target directory "/tmp/example-shop" that was previously bootstrapped as a "<shop_type>" shop named "<shop_name>"
  And I record the byte contents of the file at ".claude/shop/type.md" in the target directory before the invocation
  When I invoke the "shop-templates" update entry point against the target directory "/tmp/example-shop"
  Then the exit code is 0
  And after the invocation the file at ".claude/shop/type.md" in the target directory has byte-for-byte the same on-disk contents as before the invocation

  Examples:
    | shop_type | shop_name               |
    | bc        | shopsystem-messaging    |
    | lead      | shopsystem-product      |

  @scenario_hash:91e2db0f9e3e58d5 @bc:shopsystem-templates
  Scenario Outline: update does not overwrite or otherwise modify ".claude/shop/primer.md" in the target directory, even when the canonical "CLAUDE.md" body template, the canonical primer template, or the role-prompt templates have changed since the shop was bootstrapped
  Given an existing git repository at a target directory "/tmp/example-shop" that was previously bootstrapped as a "<shop_type>" shop named "<shop_name>"
  And the file at ".claude/shop/primer.md" in the target directory has been edited since bootstrap so that its content includes a literal shop-authored sentence
  And I record the byte contents of the file at ".claude/shop/primer.md" in the target directory before the invocation
  When I invoke the "shop-templates" update entry point against the target directory "/tmp/example-shop"
  Then the exit code is 0
  And after the invocation the file at ".claude/shop/primer.md" in the target directory has byte-for-byte the same on-disk contents as before the invocation

  Examples:
    | shop_type | shop_name               |
    | bc        | shopsystem-messaging    |
    | lead      | shopsystem-product      |

  @scenario_hash:ac5a21e046564d01 @bc:shopsystem-templates
  Scenario Outline: update is idempotent when both the top-level "CLAUDE.md" and ".claude/canonical/<shop_type>-primer.md" already match package data byte-for-byte; the invocation exits zero, emits no diagnostic on stderr, and leaves the on-disk byte contents and mtimes of those two files unchanged
  Given an existing git repository at a target directory "/tmp/example-shop" that was previously bootstrapped as a "<shop_type>" shop named "<shop_name>"
  And the file at "CLAUDE.md" in the target directory has byte contents equal to the canonical "CLAUDE.md" body template for shop type "<shop_type>"
  And the file at ".claude/canonical/<shop_type>-primer.md" in the target directory has byte contents equal to the canonical "CLAUDE.md" primer template for shop type "<shop_type>"
  And I record the byte contents and mtimes of those two files before the invocation
  When I invoke the "shop-templates" update entry point against the target directory "/tmp/example-shop"
  Then the exit code is 0
  And the stderr output of the invocation is empty
  And after the invocation the byte contents of the file at "CLAUDE.md" in the target directory equal the recorded byte contents
  And after the invocation the mtime of the file at "CLAUDE.md" in the target directory equals the recorded mtime
  And after the invocation the byte contents of the file at ".claude/canonical/<shop_type>-primer.md" in the target directory equal the recorded byte contents
  And after the invocation the mtime of the file at ".claude/canonical/<shop_type>-primer.md" in the target directory equals the recorded mtime

  Examples:
    | shop_type | shop_name               |
    | bc        | shopsystem-messaging    |
    | lead      | shopsystem-product      |

  @scenario_hash:f55678f733a5427a @bc:shopsystem-templates
  Scenario Outline: update determines which shop type's canonical templates to apply to the target directory by reading the literal contents of ".claude/shop/type.md" at the target root; the operator does not pass a shop-type flag to update, and the shop type captured at bootstrap is authoritative for subsequent updates
  Given an existing git repository at a target directory "/tmp/example-shop" that was previously bootstrapped as a "<bootstrap_shop_type>" shop named "<shop_name>"
  And the file at ".claude/shop/type.md" in the target directory contains exactly the literal string "<bootstrap_shop_type>"
  When I invoke the "shop-templates" update entry point against the target directory "/tmp/example-shop" with no additional shop-type argument
  Then the exit code is 0
  And after the invocation the byte contents of the file at "CLAUDE.md" in the target directory equal the canonical "CLAUDE.md" body template for shop type "<bootstrap_shop_type>" byte-for-byte
  And after the invocation the target directory contains a file at ".claude/canonical/<bootstrap_shop_type>-primer.md" whose byte contents equal the canonical "CLAUDE.md" primer template for shop type "<bootstrap_shop_type>" byte-for-byte

  Examples:
    | bootstrap_shop_type | shop_name               |
    | bc                  | shopsystem-messaging    |
    | lead                | shopsystem-product      |

  @scenario_hash:e51ac69bba8fd909 @bc:shopsystem-templates
  Scenario: when update runs against a target directory that lacks ".claude/shop/type.md" (a legacy-bootstrap shop predating PDR-003 alternative F), update exits non-zero, writes a diagnostic to stderr naming the migration steps the operator must perform, and touches no files in the target
  Given an existing git repository at a target directory "/tmp/example-legacy-shop" that contains a top-level "CLAUDE.md" and has no file at ".claude/shop/type.md"
  And I record the recursive listing of file paths and the byte contents of every file in the target directory before the invocation
  When I invoke the "shop-templates" update entry point against the target directory "/tmp/example-legacy-shop"
  Then the exit code is non-zero
  And the stderr output of the invocation contains the literal substring ".claude/shop/type.md"
  And the stderr output of the invocation contains the literal substring "migration"
  And after the invocation the recursive listing of file paths in the target directory equals the recorded listing
  And after the invocation the byte contents of every file in the target directory equal the corresponding recorded byte contents
