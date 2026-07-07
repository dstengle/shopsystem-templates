@bc:shopsystem-templates @origin:adr-043
Feature: bootstrap wires the functional bd dolt remote to <bc>-beads on the create-bc path (ADR-043 D5)

  The prior create-bc fix (@scenario_hash:ef4f4d86d3e4d153, lead-jq9b) corrected
  only the COSMETIC `.beads/config.yaml` `sync.remote` YAML key — which
  bootstrap's own docstring records bd IGNORES for `bd dolt push`. The
  FUNCTIONAL bd dolt remote — the one `_configure_bd_dolt_remote` creates via
  `bd dolt remote add` and that `bd dolt push` actually uses — was left as
  `_product_beads_remote`'s `<product>-lead-beads` lead form (for a bc slug like
  `shopsystem-knowledge`, `shopsystem-knowledge-lead-beads`, WRONG). Per ADR-043
  D5 the functional dolt remote for `--shop-type bc` must target
  `<owner>/<bc>-beads`, consistent with bc-launcher standup. Additive tightening
  of the single-source pin @scenario_hash:cb8fca2c0eb2b920 and the sync.remote
  pin @scenario_hash:ef4f4d86d3e4d153; no BC-side hash is retired. The
  sync.remote YAML key is NOT touched here (separate validation lead-kcdu).

@scenario_hash:8db8399c92702704 @bc:shopsystem-templates
Scenario: shop-templates bootstrap wires the functional bd dolt remote for a scaffolded BC to the owner's <bc>-beads, not the <bc>-lead-beads lead form
  Given a new BC whose shop-name slug is "<bc>" is scaffolded from a lead whose GitHub owner resolves to "<owner>"
  When I invoke "shop-templates" bootstrap with shop type "bc", shop name "<bc>", and a target directory in that lead's context
  Then "bd dolt remote list" in the target directory lists the functional bd dolt push remote that bd actually uses for "bd dolt push"
  And that functional dolt remote's repository name equals "<bc>-beads" so its URL targets "<owner>/<bc>-beads"
  And that functional dolt remote's repository name is NOT "<bc>-lead-beads" and is NOT the "<product>-lead-beads" lead form returned by "_product_beads_remote"
  And neither "bd dolt remote list" nor the bootstrap "bd dolt push" smoke-test target references "<bc>-lead-beads"
  And the scaffolded ".beads/config.yaml" "sync.remote" repository name also stays "<bc>-beads", consistent with the functional dolt remote
