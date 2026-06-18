# shopsystem-starter

A standalone, forkable **"Use this template"** repository that stands a new
product up on solid footing. This repo carries **no framework code** — the
framework lives only in the published image. What ships here is the minimal,
deterministic runway: a `compose.yaml`, a single `bin/bootstrap` entry point,
and this README.

## Prerequisites (zero-install)

You need exactly two things:

- **Docker** (to run the published image and the product services), and
- **a GitHub account** (to host your product's repos).

There is nothing else to install — no language toolchain, no `pip install`,
no framework checkout. Every tool the run needs (`shop-templates`, `bd`,
`gh`, `claude`) is carried by the published **bc-base / bc-launcher** image,
which `bin/bootstrap` pulls and runs in its interactive bootstrap mode.

## Stand up your product

1. Click **"Use this template"** on GitHub to create your own repository from
   this starter. Name it `<product>-lead` (e.g. `acme-lead`). If you named it
   something else, that is fine — `bin/bootstrap` will offer to
   `gh repo rename` it into the `<product>-lead` shape for you.
2. Clone your new repo and run:

   ```sh
   cp .env.example .env
   ./bin/bootstrap
   ```

   `bin/bootstrap` derives `<product>` from your repo name, resolves the
   floating image tag at run time (recording the resolved digest in `.env`),
   brings the broker up, and runs the **one** up-front auth gate (Claude
   OAuth + GitHub PAT + owner password). After the gate the run is
   non-interactive: it pours the lead structure, creates
   `<product>-lead-beads`, wires the git and beads remotes, and proves solid
   footing with a green `git push` and `bd dolt push`.

That is the whole runway. `bin/bootstrap` **stops** at solid footing.

## Next step — Discovery (NOT part of this script)

Product **Discovery** is an explicit, agent-driven **next step** you start
**after** confirming the footing. It is deliberately **not part of**
`bin/bootstrap` — the bootstrap is the deterministic, pre-agent runway up to
solid footing and no further. Once footing is green, begin Discovery as its
own step.
