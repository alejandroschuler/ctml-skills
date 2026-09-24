#!/usr/bin/env python3
"""The five-state scanner. Writes nothing, except ARTEFACTS.md on request.

Three sources get joined here:

  the records     what was built, with the hash and commit recorded at the time
  the compiler    what the manuscript actually opened and expanded
  snakemake       what would re-run if you built right now

The second one is the part people usually get wrong. Grepping .tex for
\\includegraphics finds text that looks like a reference, including inside
commented-out blocks and branches of \\if that never fire, which produces
confident and wrong answers. LaTeX already knows the truth: `make pdf` compiles
with -recorder, so main.fls lists every file the compiler opened, and
artefacts.sty logs every generated macro that actually expanded.

When that record is missing, the two states that depend on it, unused and
orphan, are not reported at all, and the scanner says which command fixes
that. Guessing would over-report both, and a check that cries wolf is one you
stop reading.

With --check it exits nonzero on drifted and orphan. It reports stale without
failing: stale means the code moved on since a build, which is the normal state
of a wip branch, and every stale artefact still carries its true commit.
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
    head_commit,
    info,
    load_config,
    load_records,
    ok,
    rel,
    sha256_file,
    warn,
)

STATES = ("current", "stale", "drifted", "orphan", "unused")

# The dry run covers both targets, so notes artefacts get a staleness answer
# too. `rule all` alone would leave every notes artefact looking current.
TARGETS = ("all", "notes")

# --------------------------------------------------------------------------
# What the manuscript actually uses
# --------------------------------------------------------------------------


def read_fls(cfg: Config) -> set[str] | None:
    """Files the LaTeX compiler opened, from main.fls.

    Written under -recorder, which `make pdf` passes. Authoritative for
    figures, tables and any \\input, because it records what was opened rather
    than what appears in the source.
    """
    fls = (cfg.root / cfg.main_tex).with_suffix(".fls")
    if not fls.is_file():
        return None
    pwd = fls.parent
    used: set[str] = set()
    for line in fls.read_text(errors="replace").splitlines():
        if line.startswith("PWD "):
            pwd = Path(line[4:].strip())
        elif line.startswith("INPUT "):
            p = Path(line[6:].strip())
            p = p if p.is_absolute() else (pwd / p)
            try:
                used.add(str(p.resolve().relative_to(cfg.root.resolve())))
            except (ValueError, OSError):
                continue
    return used


def latex_errored(cfg: Config) -> bool:
    """Did the last compile stop on an error?

    It matters because -recorder writes main.fls as it goes. A run that dies
    part way leaves a truncated record, and every figure after the error then
    looks unused. Better to say the reading is unreliable than to report it.
    """
    log = (cfg.root / cfg.main_tex).with_suffix(".log")
    if not log.is_file():
        return False
    for line in log.read_text(errors="replace").splitlines():
        if line.startswith("! "):
            return True
    return False


def compile_is_old(cfg: Config, used_files: set[str] | None) -> bool:
    """Has the manuscript's own source changed since the last compile?

    A pull from Overleaf brings in a coauthor's edits, and the recorder output
    still describes the manuscript as it was before them. The files compared
    are main.tex and every hand-written .tex the last compile opened. Generated
    .tex under the tiers is left out, because a rebuild changes values, not
    what is used.
    """
    fls = (cfg.root / cfg.main_tex).with_suffix(".fls")
    if not fls.is_file() or used_files is None:
        return False
    tiers = [cfg.root / cfg.tiers[t] for t in ("paper", "notes")]
    compiled = fls.stat().st_mtime
    sources = {cfg.root / cfg.main_tex} | {
        cfg.root / f for f in used_files if f.endswith(".tex")
    }
    for tex in sources:
        if any(t in tex.parents for t in tiers) or not tex.is_file():
            continue
        if tex.stat().st_mtime > compiled:
            return True
    return False


def read_macro_log(cfg: Config) -> set[str] | None:
    """Generated macros that actually expanded, logged by artefacts.sty.

    Solves unused-number detection exactly, and for free. A macro that only
    appears inside a commented block never expands and never lands here.
    """
    log = (cfg.root / cfg.main_tex).with_suffix(".artefactuse")
    if not log.is_file():
        return None
    names = set()
    for line in log.read_text(errors="replace").splitlines():
        line = line.strip()
        if line:
            names.add(line.lstrip("\\"))
    return names


# --------------------------------------------------------------------------
# What would rebuild
# --------------------------------------------------------------------------


def snakemake_status(cfg: Config) -> dict[str, str] | None:
    """Outputs a build would produce right now, with the reason for each.

    Read from a bare `snakemake --dry-run`. Do not switch this to `--summary`:
    its status column describes each output against its own direct inputs, so a
    figure two steps downstream of a changed helper still reads "ok" while the
    results file it depends on reads "updated input files". Staleness has to
    account for the whole DAG, and the dry run is what does.
    """
    proc = None
    for targets in (list(TARGETS), []):
        try:
            proc = subprocess.run(
                ["snakemake", "--dry-run", *targets],
                cwd=str(cfg.root), capture_output=True, text=True, timeout=300,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return None
        if proc.returncode == 0:
            break
    if proc is None or proc.returncode != 0:
        return None

    pending: dict[str, str] = {}
    outputs: list[str] = []
    for raw in proc.stdout.splitlines():
        line = raw.strip()
        if line.startswith("output:"):
            outputs = [p.strip() for p in line[len("output:"):].split(",") if p.strip()]
        elif line.startswith("reason:"):
            reason = line[len("reason:"):].strip()
            for o in outputs:
                pending[o] = reason
            outputs = []
        elif line.startswith(("rule ", "localrule ")):
            # A new job block. Flush anything the previous block left without a
            # reason line, so versions that do not print reasons still report.
            for o in outputs:
                pending.setdefault(o, "would be rebuilt")
            outputs = []
    for o in outputs:
        pending.setdefault(o, "would be rebuilt")
    return pending


# --------------------------------------------------------------------------
# Classification
# --------------------------------------------------------------------------


def classify(
    cfg: Config,
    tier: str,
    key: str,
    rec: dict,
    used_files: set[str] | None,
    used_macros: set[str] | None,
    sm: dict[str, str] | None,
) -> tuple[str, str]:
    """Return (state, reason) for one artefact."""
    path = cfg.root / key

    recorded = rec.get("sha256")
    if recorded and sha256_file(path) != recorded:
        # Drift is a comparison against the hash written at build time. It
        # catches a file edited or replaced after the build, which is what
        # the Overleaf web uploader does. It does not predict what a
        # rebuild would produce; staleness carries that meaning.
        return "drifted", (
            "the file on disk differs from the hash recorded when it was "
            "built, so it was edited or replaced after the fact"
        )

    stale = (key in sm) if sm is not None else None
    if stale:
        return "stale", sm.get(key) or "a dependency changed"

    # Only the paper tier is judged against the manuscript. Notes artefacts are
    # read by notes documents, and main.tex must never use them, so measuring
    # them against it would flag every one. Methods settings and methods tables
    # are exempt too: tracking a value the text types by hand is their point.
    if tier == "paper":
        macros = set(rec.get("macros", {}))
        results = {m for m in macros if not cfg.is_methods_macro(m)}
        if macros and used_macros is not None:
            if results and not (macros & used_macros):
                return "unused", "none of its macros appear in the manuscript"
        elif (not macros and not cfg.is_methods_table(key)
              and used_files is not None and key not in used_files):
            return "unused", "nothing in the manuscript references it"

    if stale is None:
        return "current", "up to date as far as the recorded hashes go"
    return "current", "up to date"


# Files that live in a tier directory but are scaffolding rather than results.
# The manuscript opens them, so they show up in .fls, and flagging them as
# orphans every single run would train you to ignore the orphan list.
SUPPORT_FILES = {"artefacts.tex", "artefacts.sty", "BUILD.json", "README.md"}


def find_orphans(
    cfg: Config, known: set[str], used_files: set[str] | None
) -> list[dict]:
    """Things the manuscript uses that no recorded build produced."""
    orphans: list[dict] = []
    if used_files is None:
        return orphans
    tier_roots = {str(cfg.tiers["paper"]), str(cfg.tiers["notes"])}
    for f in sorted(used_files):
        if f in known or Path(f).name in SUPPORT_FILES:
            continue
        if any(f.startswith(t + "/") for t in tier_roots):
            orphans.append(
                {"key": f, "kind": "file", "reason": "no recorded build produced this file"}
            )
    # Orphan macros need no check here. A macro the manuscript uses but nothing
    # emits is undefined, and LaTeX stops with "undefined control sequence",
    # which is louder and earlier than anything this tool could say.
    return orphans


# --------------------------------------------------------------------------
# Reports
# --------------------------------------------------------------------------


def build_report(cfg: Config, uncompiled: bool) -> dict:
    used_files = read_fls(cfg)
    used_macros = read_macro_log(cfg)
    sm = snakemake_status(cfg)
    paper_repo = cfg.root / cfg.paper_dir

    artefacts: dict[str, dict] = {}
    for tier in ("paper", "notes"):
        for key, rec in load_records(cfg, tier).items():
            state, reason = classify(cfg, tier, key, rec, used_files, used_macros, sm)
            artefacts[key] = {
                **rec,
                "tier": tier,
                "state": state,
                "reason": reason,
            }

    # An output the build would write that has no record yet: a new entry in
    # the registry, or a file deleted to force a rebuild.
    for out, reason in (sm or {}).items():
        if out in artefacts or Path(out).name in SUPPORT_FILES:
            continue
        for tier in ("paper", "notes"):
            if out.startswith(str(cfg.tiers[tier]) + "/"):
                artefacts[out] = {
                    "tier": tier,
                    "state": "stale",
                    "reason": f"not built yet ({reason})",
                }

    return {
        "code_commit": head_commit(cfg.root),
        "paper_commit": (
            head_commit(paper_repo) if (paper_repo / ".git").exists() else None
        ),
        "used_set": (
            "not available (run `make pdf`)" if uncompiled
            else "observed (fls + macro log)"
        ),
        "staleness": "unknown (snakemake unavailable)" if sm is None else "from snakemake",
        "artefacts": artefacts,
        "orphans": find_orphans(cfg, set(artefacts), used_files),
    }


def write_artefacts_md(cfg: Config, report: dict) -> Path:
    """ARTEFACTS.md in the Social Science Data Editors schema.

    Written by `make package` rather than on every build, because the schema
    expects data availability statements that a methods paper does not have
    until submission time.
    """
    rows = []
    for key, rec in sorted(report["artefacts"].items()):
        if rec["tier"] != "paper":
            continue
        rows.append(
            "| {label} | {program} | {out} | {note} |".format(
                label=rec.get("label") or Path(key).stem,
                program=rec.get("rule") or "",
                out=key,
                note=rec["state"] if rec["state"] != "current" else "",
            )
        )

    body = [
        "# List of tables and programs",
        "",
        f"Generated by `make package` from code commit `{report['code_commit'][:8]}`.",
        "",
        "| Figure/Table # | Program | Output file | Note |",
        "|---|---|---|---|",
        *rows,
        "",
    ]
    path = cfg.root / "ARTEFACTS.md"
    path.write_text("\n".join(body), encoding="utf-8")
    return path


def print_status(report: dict) -> int:
    buckets: dict[str, list[tuple[str, str]]] = {s: [] for s in STATES}
    for key, rec in sorted(report["artefacts"].items()):
        buckets[rec["state"]].append((key, rec["reason"]))

    print(f"used set:   {report['used_set']}")
    print(f"staleness:  {report['staleness']}")
    print()

    for state in STATES:
        items = buckets.get(state, [])
        if state == "orphan":
            items = [(o["key"], o["reason"]) for o in report["orphans"]]
        if not items:
            continue
        label = f"{state} ({len(items)})"
        if state == "current":
            ok(label)
            continue
        if state in ("unused", "stale"):
            warn(label)
        else:
            fail(label)
        for key, reason in items:
            info(f"{key}: {reason}")

    if not any(buckets[s] for s in STATES) and not report["orphans"]:
        ok("no artefacts recorded yet")

    # Only drift and orphans fail. `unused` is the normal state of a paper in
    # progress, and `stale` is the normal state of a wip branch.
    blocking = len(buckets["drifted"]) + len(report["orphans"])
    return 1 if blocking else 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument(
        "--write-report", action="store_true", help="also write ARTEFACTS.md"
    )
    ap.add_argument(
        "--check", action="store_true", help="exit nonzero on drifted or orphan"
    )
    args = ap.parse_args(argv)

    try:
        cfg = load_config()
        uncompiled = read_fls(cfg) is None or read_macro_log(cfg) is None
        if uncompiled:
            warn(
                "The manuscript has not been compiled here, so 'unused' and "
                "'orphan' cannot be judged. Fix with: make pdf"
            )
        elif latex_errored(cfg):
            warn(
                "The last LaTeX run stopped on an error, so main.fls is truncated "
                "and anything after the error will look unused. Fix the compile, "
                "then run `make pdf` again."
            )
        elif compile_is_old(cfg, read_fls(cfg)):
            warn(
                "A .tex file changed after the last compile, so 'unused' and "
                "'orphan' describe the old manuscript. Run `make pdf` first."
            )
        report = build_report(cfg, uncompiled)
    except ArtefactError as exc:
        fail(str(exc))
        return 1

    if args.write_report:
        ok(f"wrote {rel(cfg, write_artefacts_md(cfg, report))}")

    status = print_status(report)
    return status if args.check else 0


if __name__ == "__main__":
    sys.exit(main())
