# shopsystem-starter

A standalone, forkable **"Use this template"** repository that stands a new
product up on solid footing. This repo carries **no framework code** and no
infra files — the framework lives only in the published image, and the
`compose.yaml` / `.env.example` are **rendered** into your fork by
`bin/bootstrap` (versioned WITH the image), not copied from here. What ships in
the starter is the minimal, deterministic runway: a single `bin/bootstrap`
entry point and this README.

## Prerequisites (zero-install)

You need exactly two things:

- **Docker** (to run the published image and the product services), and
- **a GitHub account** (to host your product's repos).

There is nothing else to install — no language toolchain, no `pip install`,
no framework checkout, and no infra files to copy by hand. Every tool the run
needs (`shop-templates`, `bd`, `gh`, `claude`) is carried by the published
**bc-base / bc-launcher** image, which `bin/bootstrap` pulls and runs in its
interactive bootstrap mode.

## Stand up your product

1. Click **"Use this template"** on GitHub to create your own repository from
   this starter. Name it `<product>-lead` (e.g. `acme-lead`). If you named it
   something else, that is fine — `bin/bootstrap` will offer to
   `gh repo rename` it into the `<product>-lead` shape for you.
2. Clone your new repo and run:

   ```sh
   ./bin/bootstrap
   ```

   `bin/bootstrap` derives `<product>` from your repo name, resolves the
   floating image tag at run time (recording the resolved digest in `.env`),
   and runs `shop-templates bootstrap` in-container to **render** the lead
   structure into your fork — including `compose.yaml` and `.env.example`,
   versioned WITH the published image. You do **not** copy them from this
   starter; the starter no longer carries them. It then brings the broker up
   and runs **footing**: the **one** up-front auth gate (Claude OAuth + GitHub
   PAT + owner password), pours the lead structure, creates
   `<product>-lead-beads`, wires the git and beads remotes, and proves solid
   footing with a green `git push` and `bd dolt push`.

That is the whole runway: **fork → `./bin/bootstrap` → render + footing → stop
at footing**. `bin/bootstrap` **stops** there.

## Next step — Discovery (NOT part of this script)

Product **Discovery** is an explicit, agent-driven **next step** you start
**after** confirming the footing. It is deliberately **not part of**
`bin/bootstrap` — the bootstrap is the deterministic, pre-agent runway up to
solid footing and no further. Once footing is green, begin Discovery as its
own step.
