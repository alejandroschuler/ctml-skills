#!/usr/bin/env python3
"""Do the declared dependencies cover what the build actually read?

This tests the guarantee rather than the implementation. Reviewing the Snakefile
tells you the declarations look right. Comparing them against what the build
recorded reading tells you whether they are sufficient, which is the only claim
anyone cares about.

The check is static. `snakemake --dry-run --forceall` prints every rule with its
complete inputs and outputs without running anything, and the transitive closure
of an artefact's inputs is the set of files a change to which would rebuild it.
That set is then compared against the `reads` each artefact recorded.

Reading the declared graph is exact, costs one subprocess, and never modifies a
file. Do not be tempted to perturb modification times instead: Snakemake does
not treat a bare mtime bump on an input as a reason to rerun, so a probe built
that way reports every helper as under-declared.

What it reports:

  under-declared   the build read a file that is not in the artefact's declared
                   closure. FAILS. A change to that file leaves the artefact
                   looking fresh when it is not, and a wrong number in a
                   published paper is what that looks like downstream.

Only that direction is reported. The opposite one, a declared input the build
never read, is safe and cannot be judged fairly here: the read instrumentation
does not see intermediate results files, so most such warnings would be false.
Over-declaration costs needless rebuilds, and the fix for that is to split the
topic directory, which the timing tells you about anyway.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from _common import (
    ArtefactError,
    Config,
    fail,
    info,
    load_config,
    load_records,
    ok,
    warn,
)


def declared_graph(cfg: Config) -> dict[str, set[str]] | None:
    """Output path -> its declared direct inputs, for every rule in the DAG.

    --forceall puts every rule in the plan, so the listing is complete rather
    than limited to what happens to be out of date right now. Both targets are
    named, because notes rules sit outside `rule all` on purpose.
    """
    try:
        proc = subprocess.run(
            ["snakemake", "--dry-run", "--forceall", "all", "notes"],
            cwd=str(cfg.root), capture_output=True, text=True, timeout=600,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None

    graph: dict[str, set[str]] = {}
    inputs: set[str] = set()
    for raw in proc.stdout.splitlines():
        line = raw.strip()
        if line.startswith("input:"):
            inputs = {p.strip() for p in line[len("input:"):].split(",") if p.strip()}
        elif line.startswith("output:"):
            for out in (p.strip() for p in line[len("output:"):].split(",")):
                if out:
                    graph[out] = set(inputs)
            inputs = set()
        elif line.startswith(("rule ", "localrule ")):
            inputs = set()
    return graph


def closure(graph: dict[str, set[str]], target: str) -> set[str]:
    """Everything a change to which would reach `target`."""
    seen: set[str] = set()
    stack = list(graph.get(target, ()))
    while stack:
        node = stack.pop()
        if node in seen:
            continue
        seen.add(node)
        stack.extend(graph.get(node, ()))
    return seen


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--only", help="check a single artefact (path relative to root)")
    args = ap.parse_args(argv)

    try:
        cfg = load_config()
    except ArtefactError as exc:
        fail(str(exc))
        return 1

    graph = declared_graph(cfg)
    if graph is None:
        fail("Could not read the workflow graph from snakemake.")
        info("Is snakemake installed, and does `snakemake -n --forceall all notes`")
        info("succeed? This check has nothing to compare against without it.")
        return 1

    artefacts: dict[str, dict] = {}
    for tier in ("paper", "notes"):
        artefacts.update(load_records(cfg, tier))
    if args.only:
        artefacts = {k: v for k, v in artefacts.items() if k == args.only}
    if not artefacts:
        warn("No artefacts recorded yet. Build something first, then run this.")
        return 0

    failures = 0
    unjudged: list[str] = []

    for key, rec in sorted(artefacts.items()):
        reads = set(rec.get("reads", []))
        if not reads:
            continue
        if key not in graph:
            # The records live in the paper repo and are shared by every
            # branch, but the Snakefile is not. A branch that forked before a
            # rule existed has nothing to compare that artefact against.
            unjudged.append(key)
            continue
        declared = closure(graph, key)
        missed = reads - declared

        if missed:
            failures += 1
            fail(f"{key}: read files that are not declared inputs")
            for m in sorted(missed):
                info(m)
            info("Add the file, or the directory holding it, to that rule's inputs.")
            info("A change to it would otherwise leave this artefact looking fresh.")
        else:
            ok(key)

    if unjudged:
        warn(f"{len(unjudged)} recorded artefact(s) have no rule on this branch, so they were not checked:")
        for key in unjudged:
            info(key)

    print()
    if failures:
        fail(f"{failures} artefact(s) with undeclared dependencies. The dangerous kind.")
        return 1
    ok("declared dependencies cover everything the build read")
    return 0


if __name__ == "__main__":
    sys.exit(main())
