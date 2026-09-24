#!/usr/bin/env python3
"""Preconditions and auto-commit. Runs before a build writes anything.

It runs in two places. The Makefile calls it first, so a refused build says so
at once, even when nothing needs rebuilding: Snakemake skips `onstart` when no
job runs. The Snakefile's `onstart` calls it again, so a bare `snakemake` is
gated the same way. The helpers then check the same branch and tree rules at
the write itself (record_provenance.validate_write), which also covers a script
run directly. Running it twice is idempotent and takes milliseconds.

Committing is free here, which is the whole point. The cost of the discipline
was the reason to skip it, so on a wip branch the guard pays that cost for you,
and the rule becomes "nothing is ever built from a dirty tree" with no
exceptions to remember.

Usage:
    build_guard.py --tier {notes,paper}

Silent on success. Exits 1 with a message naming the violation otherwise.
"""

from __future__ import annotations

import argparse
import fnmatch
import sys
from datetime import datetime, timezone
from pathlib import Path

from _common import (
    ArtefactError,
    Config,
    branch_name,
    dirty_paths,
    drifted,
    fail,
    git,
    head_commit,
    info,
    load_config,
    ok,
)


def oversized(cfg: Config, paths: list[str]) -> list[tuple[str, float]]:
    limit = cfg.max_file_mb * 1024 * 1024
    out = []
    for p in paths:
        f = cfg.root / p
        if f.is_file() and f.stat().st_size > limit:
            out.append((p, f.stat().st_size / 1024 / 1024))
    return out


def secretish(cfg: Config, paths: list[str]) -> list[str]:
    hits = []
    for p in paths:
        name = Path(p).name
        if any(fnmatch.fnmatch(name, pat) for pat in cfg.secret_patterns):
            hits.append(p)
    return hits


def auto_commit(cfg: Config, tier: str) -> str:
    """Commit the code repo so the build has something to stamp against.

    Never runs on main. Committing there is a deliberate act and stays that way,
    because main is the branch the paper-tier invariant trusts.
    """
    pending = dirty_paths(cfg.root)
    if not pending:
        return head_commit(cfg.root)

    big = oversized(cfg, pending)
    if big:
        fail("Refusing to auto-commit: files above the size limit.")
        for p, mb in big:
            info(f"{p}  ({mb:.1f} MB, limit {cfg.max_file_mb:.0f} MB)")
        info("Move these out of the code repo, or add them to .gitignore.")
        info("Large derived output belongs in results/, which is gitignored.")
        raise SystemExit(1)

    secrets = secretish(cfg, pending)
    if secrets:
        fail("Refusing to auto-commit: these look like credentials.")
        for p in secrets:
            info(p)
        info("Add them to .gitignore, then run again.")
        raise SystemExit(1)

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    git("add", "-A", cwd=cfg.root)
    staged = git("diff", "--cached", "--name-only", cwd=cfg.root)
    if not staged.strip():
        return head_commit(cfg.root)
    git("commit", "-q", "-m", f"wip({tier}): {stamp}", cwd=cfg.root)
    commit = head_commit(cfg.root)
    ok(f"Auto-committed {len(staged.splitlines())} file(s) as {commit[:8]}")
    return commit


def guard_notes(cfg: Config) -> str:
    """Exploratory output: any real branch except main.

    The detached-HEAD check is the one that matters. A bare "is this main?"
    test would read a detached HEAD as "not main, therefore exploratory" and
    commit the working tree somewhere that becomes unreachable as soon as
    anything else is checked out.
    """
    branch = branch_name(cfg.root)
    if branch is None:
        fail("HEAD is detached, so there is no branch to commit onto.")
        info("Anything committed here becomes unreachable as soon as you check")
        info("out something else. Get onto a branch first:")
        info(f"    git switch -c wip/<topic> {cfg.main_branch}")
        raise SystemExit(1)

    if branch == cfg.main_branch:
        fail(f"Exploratory output cannot be built on {cfg.main_branch}.")
        info("Create a branch first, then build:")
        info("    make wip TOPIC=<topic>")
        info("Or, if this is throwaway and no one else needs it, put the script")
        info("and its output under scratch/ and run it directly.")
        raise SystemExit(1)
    return auto_commit(cfg, "notes")


def guard_paper(cfg: Config) -> str:
    branch = branch_name(cfg.root)
    if branch != cfg.main_branch:
        fail(f"Manuscript artefacts must be built on {cfg.main_branch}, not '{branch or 'a detached HEAD'}'.")
        info("Every artefact under the paper tier carries a commit that has to be")
        info(f"an ancestor of {cfg.main_branch}. Building here would produce one that")
        info("the checks reject before it can reach Overleaf.")
        if branch:
            info("")
            info("To promote this work, follow the promotion procedure, which ends:")
            info(f"    git switch {cfg.main_branch}")
            info(f"    git merge --squash {branch} && git commit")
            info("    make build")
        raise SystemExit(1)

    pending = dirty_paths(cfg.root)
    if pending:
        fail(f"The code tree is dirty on {cfg.main_branch}.")
        for p in pending[:10]:
            info(p)
        if len(pending) > 10:
            info(f"... and {len(pending) - 10} more")
        info("")
        info(f"Auto-commit never runs here, because {cfg.main_branch} is the")
        info("branch the paper-tier invariant trusts. Commit with a message that")
        info("says what changed, then build:")
        info('    git add -A && git commit -m "<what changed>"')
        raise SystemExit(1)

    # A build rewrites its own outputs, so asking git whether the tier differs
    # from the paper repo's last commit would refuse every second build before
    # a push. The question is narrower: does any file differ from what the
    # build that made it recorded? Only an edit after the build does that.
    edited = drifted(cfg, "paper")
    if edited:
        fail("Generated files under the paper tier differ from what the build wrote.")
        for p in edited:
            info(p)
        info("")
        info("Someone edited or replaced them after the build, for example through")
        info("the Overleaf file menu. A rebuild does not overwrite them by itself,")
        info("because their inputs did not change. Find out what the edit was for,")
        info("since it usually points at a real problem in the analysis. Then")
        info("delete the files and build again, which writes them from the code:")
        info(f"    rm {' '.join(edited)}")
        info("    make build")
        raise SystemExit(1)

    return head_commit(cfg.root)


GUARDS = {"notes": guard_notes, "paper": guard_paper}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--tier", required=True, choices=sorted(GUARDS))
    args = ap.parse_args(argv)

    try:
        cfg = load_config()
        GUARDS[args.tier](cfg)
    except ArtefactError as exc:
        fail(str(exc))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
