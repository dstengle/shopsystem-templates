@bc:shopsystem-templates @origin:lead-7jc2
Feature: bootstrap writes the derived GitHub owner into the scaffolded beads sync.remote on the create-bc path

  On the create-bc path (`shop-templates bootstrap --shop-type bc`) no footing
  reconcile runs, so nothing substitutes the ORIGIN_OWNER placeholder that the
  lead-only footing fill (@scenario_hash:c1b769fb49c6ebfb) would otherwise
  supply. Bootstrap must therefore write the DERIVED GitHub owner — resolved
  from the lead's context — into the scaffolded `.beads/config.yaml`
  `sync.remote` itself, so the scaffolded tracker's JSONL-sync remote targets
  `<owner>/<bc>-beads` rather than surviving to launch with a literal
  `ORIGIN_OWNER` and a nonexistent owner. Additive tightening of the
  single-source pin @scenario_hash:cb8fca2c0eb2b920 (deriving the owner is not
  baking a hardcoded org); no BC-side hash is retired.

@scenario_hash:ef4f4d86d3e4d153 @bc:shopsystem-templates
Scenario: shop-templates bootstrap writes the derived GitHub owner into the scaffolded beads sync.remote instead of the ORIGIN_OWNER placeholder
  Given a new BC whose shop-name slug is "<bc>" is scaffolded from a lead whose GitHub owner resolves to "<owner>"
  When I invoke "shop-templates bootstrap" with shop type "bc", shop name "<bc>", and a target directory in that lead's context
  Then the scaffolded ".beads/config.yaml" "sync.remote" contains no literal "ORIGIN_OWNER" placeholder
  And the "sync.remote" owner segment equals the derived GitHub owner "<owner>"
  And the "sync.remote" repository name equals "<bc>-beads" so the URL targets "<owner>/<bc>-beads"
