#!/usr/bin/env python3
"""Check a write before it happens, record what it produced, merge the records.

Provenance is implemented once, here, and both language front-ends call it.
artefacts.py imports it; artefacts.R shells out to it. Two implementations of
"what commit built this" would drift, and the drift would be invisible until
the day it mattered.

validate_write() is the last of three places that enforce the tier rules, and
the only one nothing can go around. The Makefile and the Snakefile's `onstart`
check when a build starts; this checks when a script is about to write, which
also covers a script run directly, outside make and snakemake.

Sidecars are per-artefact so parallel Snakemake jobs never race on a shared
file. They live in the code repo under .artefacts/prov and are gitignored.
BUILD.json is the merged view, and it lives next to the artefacts in the paper
repo so that checking out any paper commit tells you what produced it, with no
access to the code repo at all.

The commit is read from git here, at write time. It is deliberately not a
Snakemake `params` value: params are a rerun trigger, so threading the commit
through them would mark every artefact in the project stale on every commit.

Usage:
    record_provenance.py --validate --path paper/artefacts/numbers/fit.tex \\
        [--macros macros.json]
    record_provenance.py --path paper/artefacts/figures/fig-primary.pdf \\
        [--rule fig_primary] [--label fig:primary] \\
        [--macros macros.json] [--reads reads.json] [--extra extra.json]
    record_provenance.py --merge
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from _common import (
    ArtefactError,
    Config,
    branch_name,
    dirty_paths,
    fail,
    head_commit,
    load_config,
    load_records,
    load_sidecars,
    ok,
    rel,
    sha256_file,
)

MACRO_NAME = re.compile(r"^[A-Za-z]+$")


def validate_macros(cfg: Config, tier: str, macros: dict[str, str] | None) -> None:
    """Check every macro name before anything is written.

    Writing the .tex and then discovering a bad name leaves a file on disk that
    breaks the compile for every coauthor, which turns a local mistake into
    everyone's problem. Validate, then write.

    Only one rule is enforced, because only one of them can break a build:
    LaTeX accepts letters in a macro name and nothing else. A naming convention
    such as a res/wip prefix helps a reader, and is deliberately not checked
    here. Tier membership is recorded in BUILD.json, so the tooling already
    knows which tier a macro came from without reading its name. The one prefix
    the tools do read is `mth`, which marks a methods setting for
    `make methods`.
    """
    for name in (macros or {}):
        if not MACRO_NAME.match(name):
            raise ArtefactError(
                f"'{name}' is not a legal LaTeX macro name. Names accept letters "
                "only, so use camelCase: resPrimaryAte, not res_primary_ate or "
                "resTable2N. Emitting it would break the Overleaf compile for "
                "everyone on the project."
            )


def tier_for(cfg: Config, path: Path) -> str:
    tier = cfg.tier_of(path)
    if tier is None:
        raise ArtefactError(
            f"{rel(cfg, path)} is not inside any configured tier. Artefacts go "
            f"under {cfg.tiers['paper']} or {cfg.tiers['notes']}; throwaway output "
            f"goes under {cfg.tiers['scratch']} and is not recorded."
        )
    return tier


def validate_write(cfg: Config, path: Path) -> str:
    """Refuse a write that the tier rules forbid. Returns the tier.

    Scratch has no rules. Notes needs a real branch other than main. The paper
    tier needs main. Both need a clean code tree, because otherwise no commit
    describes the code that is about to produce the file. build_guard commits
    on a wip branch before a build starts, so a build through `make` passes;
    a script run by hand on a dirty tree does not.
    """
    tier = tier_for(cfg, path)
    if tier == "scratch":
        return tier

    where = rel(cfg, path)
    branch = branch_name(cfg.root)
    if branch is None:
        raise ArtefactError(
            f"Refusing to write {where}: HEAD is detached, so no branch holds the "
            "commit that would stamp it. Get onto a branch first."
        )
    if tier == "paper" and branch != cfg.main_branch:
        raise ArtefactError(
            f"Refusing to write {where}: manuscript artefacts are built on "
            f"{cfg.main_branch}, and this is '{branch}'. Write to "
            f"{cfg.tiers['notes']} instead, or promote the work and run "
            f"`make build` on {cfg.main_branch}."
        )
    if tier == "notes" and branch == cfg.main_branch:
        raise ArtefactError(
            f"Refusing to write {where}: exploratory output is not built on "
            f"{cfg.main_branch}. Start a branch with `make wip TOPIC=<topic>`."
        )
    pending = dirty_paths(cfg.root)
    if pending:
        shown = ", ".join(pending[:5]) + (" ..." if len(pending) > 5 else "")
        raise ArtefactError(
            f"Refusing to write {where}: the code tree has uncommitted changes "
            f"({shown}), so no commit describes the code that would produce it. "
            "Build with `make notes` or `make build`, which commit or check first."
        )
    return tier


def _hash_reads(cfg: Config, reads: list[str] | None) -> dict[str, str]:
    """Each file that was read, with its content hash.

    The hash matters most for data. The commit pins the code, but data is
    usually gitignored, and a path alone cannot say which version was read.
    """
    out = {}
    for r in sorted(set(reads or [])):
        f = cfg.root / r
        if f.is_file():
            out[r] = sha256_file(f)
    return out


def record(
    cfg: Config,
    path: Path,
    rule: str | None = None,
    label: str | None = None,
    macros: dict[str, str] | None = None,
    reads: list[str] | None = None,
    extra: dict | None = None,
) -> Path:
    """Write the sidecar for one artefact.

    `extra` adds fields a helper wants recorded next to the file, such as the
    grid counts that grid_table() computes. It cannot replace a core field.
    """
    key = rel(cfg, path)
    tier = tier_for(cfg, path)
    if tier == "scratch":
        # Scratch is the cheap path. It stays cheap by not being tracked.
        return cfg.prov_dir / "_scratch_ignored"

    validate_macros(cfg, tier, macros)

    commit = head_commit(cfg.root)
    if dirty_paths(cfg.root):
        # validate_write refuses a dirty tree before the write, so the tree
        # changed while this artefact was being made. Record that, rather than
        # a commit that does not describe the code that ran.
        commit = f"{commit}-dirty"

    rec = {
        "path": key,
        "tier": tier,
        "sha256": sha256_file(cfg.root / key),
        "commit": commit,
        "built_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "rule": rule,
        "label": label,
        "macros": macros or {},
        "reads": _hash_reads(cfg, reads),
    }
    for name, value in (extra or {}).items():
        if name in rec:
            raise ArtefactError(f"'{name}' is a core provenance field and cannot be set as extra.")
        rec[name] = value

    cfg.prov_dir.mkdir(parents=True, exist_ok=True)
    sidecar = cfg.prov_dir / (key.replace("/", "__") + ".json")
    sidecar.write_text(json.dumps(rec, indent=2, sort_keys=True) + "\n")
    return sidecar


def merge(cfg: Config) -> list[Path]:
    """Write one BUILD.json per tier from the existing records plus the sidecars.

    It starts from the BUILD.json already there, so records written on another
    machine survive a build on this one. The file is rewritten only when a
    record changed, and it carries no timestamp of its own, so
    `git log -p BUILD.json` in the paper repo shows only real changes.
    """
    written = []
    for tier in ("paper", "notes"):
        records = load_records(cfg, tier)
        target = cfg.build_json(tier)
        if not records and not target.exists():
            continue
        payload = {
            "note": (
                "Generated. Records what produced each file in this directory. "
                "Do not edit; see the code repository."
            ),
            "artefacts": records,
        }
        text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
        if target.is_file() and target.read_text() == text:
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)
        written.append(target)

    # The artefact is gone, so its sidecar goes too. There is then no cache to
    # clean by hand and no stale entry to confuse the next report.
    for rec in load_sidecars(cfg):
        if not (cfg.root / rec["path"]).exists():
            (cfg.prov_dir / (rec["path"].replace("/", "__") + ".json")).unlink(
                missing_ok=True
            )
    return written


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--path")
    ap.add_argument("--rule")
    ap.add_argument("--label")
    ap.add_argument("--macros", help="path to a JSON object of name -> rendered value")
    ap.add_argument("--reads", help="path to a JSON array of project-relative paths")
    ap.add_argument("--extra", help="path to a JSON object of further fields to record")
    ap.add_argument("--merge", action="store_true", help="merge sidecars into BUILD.json")
    ap.add_argument(
        "--validate",
        action="store_true",
        help="check the tier rules and macro names, write nothing (used before emitting)",
    )
    args = ap.parse_args(argv)

    try:
        cfg = load_config()
        if args.merge:
            for p in merge(cfg):
                ok(f"wrote {rel(cfg, p)}")
            return 0
        if not args.path:
            ap.error("--path is required unless --merge is given")
        macros = json.loads(Path(args.macros).read_text()) if args.macros else None
        reads = json.loads(Path(args.reads).read_text()) if args.reads else None
        extra = json.loads(Path(args.extra).read_text()) if args.extra else None
        if args.validate:
            tier = validate_write(cfg, Path(args.path))
            validate_macros(cfg, tier, macros)
            return 0
        record(
            cfg,
            Path(args.path),
            rule=args.rule,
            label=args.label,
            macros=macros,
            reads=reads,
            extra=extra,
        )
    except ArtefactError as exc:
        fail(str(exc))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
