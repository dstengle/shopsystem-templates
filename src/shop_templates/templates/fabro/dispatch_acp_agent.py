#!/usr/bin/env python3
"""ADR-058 reactive-dispatcher worker: watch a BC inbox and dispatch ONE
bc-shop-loop ACP agent per inbound lead message.

This is the native `dispatch` node of ``dispatcher.fabro`` (the ``fabro engage``
entrypoint graph). The engage runs ``fabro run dispatcher.toml`` ->
``dispatcher.fabro`` -> (this script). For every message on the BC's inbox it
spawns a ``fabro run workflow.fabro -I BC_NAME=<bc> -I WORK_ID=<work_id>`` run --
the ADR-051 Implementer->Reviewer->GATED-work_done loop keyed to a single
work_id -- as a detached ACP agent, then returns to watching. The per-message
loop lives entirely in the SIBLING ``workflow.fabro`` def poured alongside this
file; the dispatcher only reacts to arrivals and hands each off.

Design notes:
  * The reactive channel is ``shop-msg watch --bc <name>`` (the postgres
    LISTEN/NOTIFY watcher that emits one line per new inbox message). On startup
    the dispatcher first drains any already-pending messages via
    ``shop-msg pending inbox`` so nothing that arrived before the watcher armed
    is missed, then streams new arrivals from the watcher.
  * ``BC_NAME`` arrives from the ``[run.environment.env]`` overlay declared in
    dispatcher.toml (native ``script=`` sandboxes do not see ``{{ inputs }}``);
    ``--bc`` overrides it. This keeps a single source for the supervised BC name.
  * Each dispatched run is DETACHED (``fabro run ... --detach``) so the reactive
    loop never blocks behind one work item -- the supervisor stays responsive to
    the next arrival, matching the router's re-arm-and-drain standing rule.
  * No node reads a real secret; dispatched agents inherit HTTPS_PROXY ->
    agent-vault from the parent env. The fabro vault holds only __PLACEHOLDER__.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

# The sibling per-message loop def, resolved relative to this script so the
# dispatcher runs correctly with cwd == the poured `.fabro/` dir (where the
# engage invokes `fabro run dispatcher.toml`).
_WORKFLOW_DEF = "workflow.fabro"


def _def_dir() -> Path:
    """Directory the dispatcher def lives in (the poured `.fabro/`)."""
    return Path(__file__).resolve().parent


def _pending_work_ids(bc_name: str) -> list[str]:
    """Return the work_ids of messages already pending on the BC inbox, drained
    at startup so a message that arrived before the watcher armed is not missed."""
    res = subprocess.run(
        ["shop-msg", "pending", "inbox", "--bc", bc_name],
        capture_output=True,
        text=True,
    )
    if res.returncode != 0:
        return []
    return _parse_work_ids(res.stdout)


def _parse_work_ids(text: str) -> list[str]:
    """Extract work_ids from a `shop-msg pending inbox` / `watch` line stream.

    Each row names a work_id token (e.g. `lead-5qj1`); tokens are collected in
    first-seen order with duplicates suppressed so each message dispatches once.
    """
    seen: list[str] = []
    for line in text.splitlines():
        for tok in line.replace(":", " ").split():
            if "-" in tok and tok not in seen and any(c.isdigit() for c in tok):
                seen.append(tok)
    return seen


def dispatch_one(bc_name: str, work_id: str, def_dir: Path | None = None) -> int:
    """Spawn a single detached bc-shop-loop ACP agent for (bc_name, work_id).

    Runs `fabro run workflow.fabro -I BC_NAME=<bc> -I WORK_ID=<work_id> --detach`
    with cwd == the poured def dir so the sibling def resolves. Returns the
    `fabro run` exit code (0 on a successful detach hand-off)."""
    def_dir = def_dir or _def_dir()
    argv = [
        "fabro",
        "run",
        _WORKFLOW_DEF,
        "-I",
        f"BC_NAME={bc_name}",
        "-I",
        f"WORK_ID={work_id}",
        "--detach",
    ]
    return subprocess.run(argv, cwd=str(def_dir)).returncode


def watch_and_dispatch(bc_name: str) -> int:
    """Reactive supervise loop: drain pending, then stream new arrivals from
    `shop-msg watch --bc`, dispatching one detached ACP agent per work_id.

    Returns 0 when the watcher stream ends cleanly, nonzero on a watcher error
    (the dispatcher.fabro `dispatch` node maps nonzero -> `halt`)."""
    def_dir = _def_dir()
    dispatched: set[str] = set()

    # Startup drain: dispatch anything already pending before the watcher arms.
    for wid in _pending_work_ids(bc_name):
        if wid not in dispatched:
            dispatch_one(bc_name, wid, def_dir)
            dispatched.add(wid)

    # Reactive stream: one line per new inbox arrival.
    proc = subprocess.Popen(
        ["shop-msg", "watch", "--bc", bc_name],
        stdout=subprocess.PIPE,
        text=True,
    )
    try:
        assert proc.stdout is not None
        for line in proc.stdout:
            for wid in _parse_work_ids(line):
                if wid not in dispatched:
                    dispatch_one(bc_name, wid, def_dir)
                    dispatched.add(wid)
    finally:
        proc.terminate()
    return proc.wait()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="ADR-058 reactive dispatcher: watch a BC inbox and dispatch "
        "one bc-shop-loop ACP agent per inbound message."
    )
    parser.add_argument(
        "--bc",
        default=os.environ.get("BC_NAME"),
        help="BC name to supervise (defaults to $BC_NAME from the "
        "[run.environment.env] overlay).",
    )
    parser.add_argument(
        "--work-id",
        default=None,
        help="Dispatch exactly this work_id once and exit, instead of running "
        "the reactive watch loop (one-shot mode).",
    )
    args = parser.parse_args(argv)

    if not args.bc:
        parser.error("no BC name: pass --bc or set $BC_NAME")

    if args.work_id:
        return dispatch_one(args.bc, args.work_id)
    return watch_and_dispatch(args.bc)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
