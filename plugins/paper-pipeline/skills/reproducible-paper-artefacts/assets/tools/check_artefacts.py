#!/usr/bin/env python3
"""The invariants. Exits nonzero when one is broken.

Called from `make check`, which the code repo's pre-push hook and
`make push-paper` both run, so nothing reaches Overleaf without it. Every check
reads BUILD.json, which lives in the paper repo, so a missing paper repo is a
failure rather than a quiet pass. That is also why there is no CI job: GitHub
Actions never has the paper repo, and a check that passes on zero records only
teaches you to stop reading it.

The checks, in order of how much they matter:

  paper-repo  the paper repo is on disk, so the other checks see real records
  ancestry    every manuscript artefact carries a commit reachable from main
  reachable   every notes artefact carries a commit that still exists
  tier-leak   nothing exploratory or throwaway reaches the manuscript
  collision   no macro name is defined twice within a tier
  naming      every emitted macro name is letters only
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from _common import (
    ArtefactError,
    Config,
    commit_exists,
    fail,
    info,
    is_ancestor,
    is_reachable,
    load_config,
    load_records,
    ok,
)

MACRO_NAME = re.compile(r"^[A-Za-z]+$")


def strip_tex_comments(text: str) -> str:
    """Remove LaTeX comments so a commented-out line does not trip a check.

    A percent sign preceded by a backslash is a literal percent and stays.
    This is a lexical pass, adequate for finding a forbidden token. Deciding
    the complete set of macros a document actually uses is a different and
    harder question, and artefact_status answers it by reading the compiler's
    own log rather than by parsing source.
    """
    out = []
    for line in text.splitlines():
        cut = None
        for i, ch in enumerate(line):
            if ch == "%" and (i == 0 or line[i - 1] != "\\"):
                cut = i
                break
        out.append(line if cut is None else line[:cut])
    return "\n".join(out)


# --------------------------------------------------------------------------


def check_paper_repo(cfg: Config) -> list[str]:
    paper = cfg.root / cfg.paper_dir
    if (paper / ".git").exists():
        return []
    return [
        f"{cfg.paper_dir}/ is not a git repo on this machine, so there is no "
        "BUILD.json to check and every other check would pass on nothing. "
        f"Clone the paper first: git clone <overleaf-url> {cfg.paper_dir}"
    ]


def _stamp_problem(key: str, commit: str | None) -> str | None:
    if not commit or commit == "unstamped":
        return f"{key}: no commit stamp"
    if commit.endswith("-dirty"):
        # Distinguish this from a genuine ancestry failure. Both block, but
        # the fixes are different, and a blocking error that explains the
        # wrong cause sends you looking in the wrong place.
        return (
            f"{key}: built from {commit[:8]} with uncommitted changes in the "
            "tree, so no commit describes the code that produced it. Commit, "
            "then rebuild."
        )
    return None


def check_ancestry(cfg: Config) -> list[str]:
    """Paper tier: the stamp must be an ancestor of the main branch.

    Stronger than asking whether the tree was clean at build time, because it
    also catches an artefact built from a pristine tree on a branch that was
    later abandoned. That artefact looks perfect and is unreproducible.
    """
    problems = []
    for key, rec in load_records(cfg, "paper").items():
        commit = rec.get("commit")
        problem = _stamp_problem(key, commit)
        if problem:
            problems.append(problem)
        elif not is_ancestor(commit, cfg.main_branch, cwd=cfg.root):
            problems.append(
                f"{key}: built from {commit[:8]}, which is not an ancestor of "
                f"{cfg.main_branch}. It was built on a branch that has not been "
                f"merged. Merge it and rebuild, or rebuild from {cfg.main_branch}."
            )
    return problems


def check_reachable(cfg: Config) -> list[str]:
    """Notes tier: the stamp must still resolve to a commit some ref holds."""
    problems = []
    for key, rec in load_records(cfg, "notes").items():
        commit = rec.get("commit")
        problem = _stamp_problem(key, commit)
        if problem:
            problems.append(problem)
        elif not commit_exists(commit, cwd=cfg.root):
            problems.append(
                f"{key}: built from {commit[:8]}, which no longer exists here, so "
                "the artefact cannot be reproduced. Rebuild it from current code, "
                "or delete it."
            )
        elif not is_reachable(commit, cwd=cfg.root):
            problems.append(
                f"{key}: built from {commit[:8]}, which no branch or tag contains, "
                "so git can delete it at the next garbage collection. While the "
                f"commit still exists, `git tag archive/<topic> {commit[:8]}` "
                "keeps it. After a squash-merge, keep or tag the wip branch "
                "instead of deleting it."
            )
    return problems


def _manuscript_opened(cfg: Config) -> tuple[set[str], bool]:
    """Files the manuscript pulled in, and whether the answer is authoritative.

    Prefers main.fls, which the compiler writes under -recorder (`make pdf`)
    and which lists every file it actually opened. Falls back to a path-string
    scan of the .tex source, which over-reports because a commented-out \\input
    still looks like one. The caller says which it got.
    """
    fls = cfg.root / Path(str(cfg.main_tex)).with_suffix(".fls")
    if fls.is_file():
        opened: set[str] = set()
        pwd = fls.parent
        for line in fls.read_text(errors="replace").splitlines():
            if line.startswith("PWD "):
                pwd = Path(line[4:].strip())
            elif line.startswith("INPUT "):
                q = Path(line[6:].strip())
                q = q if q.is_absolute() else (pwd / q)
                try:
                    opened.add(str(q.resolve().relative_to(cfg.root.resolve())))
                except (ValueError, OSError):
                    continue
        return opened, True

    text = ""
    tex = cfg.root / cfg.main_tex
    if tex.is_file():
        text = strip_tex_comments(tex.read_text(encoding="utf-8", errors="replace"))
    return {text}, False


def check_tier_leak(cfg: Config) -> list[str]:
    """Nothing exploratory or throwaway may reach the manuscript.

    This is the guard the whole tier split exists for: a number built from who
    knows what quietly becoming a claim in a paper.

    It asks about tier membership rather than about macro names. A naming
    convention can be violated or imitated; the directory a file was written to
    is what actually decides which guarantee it carries.

    Two questions, because they have different best answers. What the manuscript
    pulled in is answered by main.fls, which the compiler wrote. Whether any
    .tex anywhere in the paper points at the scratch tier is a path scan, and it
    covers the notes too, which matters because scratch output is gitignored and
    would simply be missing when Overleaf tries to compile.
    """
    problems = []
    opened, authoritative = _manuscript_opened(cfg)
    for tier in ("notes", "scratch"):
        root = str(cfg.tiers[tier])
        if authoritative:
            hits = sorted(f for f in opened if f == root or f.startswith(root + "/"))
        else:
            hits = [root] if root in next(iter(opened), "") else []
        for h in hits:
            problems.append(
                f"{cfg.main_tex} pulls in {h}, which is {tier}-tier output. "
                f"Promote it to {cfg.tiers['paper']} and rebuild from "
                f"{cfg.main_branch} instead."
            )
    if not authoritative and problems:
        problems.append(
            "(Approximate: run `make pdf` so this check can read main.fls "
            "instead of guessing from source.)"
        )

    scratch = str(cfg.tiers["scratch"])
    paper_dir = cfg.root / cfg.paper_dir
    if paper_dir.is_dir():
        for tex in sorted(paper_dir.rglob("*.tex")):
            body = strip_tex_comments(tex.read_text(encoding="utf-8", errors="replace"))
            if scratch in body:
                problems.append(
                    f"{tex.relative_to(cfg.root)} references the scratch tier "
                    f"('{scratch}'), which is never committed and will be missing "
                    "when Overleaf compiles. Move the work to the notes tier first."
                )
    return problems


def check_collision(cfg: Config) -> list[str]:
    """No macro name defined twice within a tier.

    artefacts.tex inputs every paper-tier numbers file, so two computations
    emitting the same name would resolve to whichever loaded last, silently.
    \\newcommand turns that into a compile error, which is the behaviour worth
    having. This check fires earlier, before a coauthor's Overleaf build is the
    thing that breaks.

    Names are compared within a tier, because a tier is what loads together.
    The manuscript never loads the notes tier, so a promoted number may keep
    the name its notes copy had.
    """
    problems = []
    for tier in ("paper", "notes"):
        owners: dict[str, list[str]] = {}
        for key, rec in load_records(cfg, tier).items():
            for name in rec.get("macros", {}):
                owners.setdefault(name, []).append(key)
        problems += [
            f"{tier} tier: macro \\{name} is defined by: {', '.join(sorted(files))}"
            for name, files in sorted(owners.items())
            if len(files) > 1
        ]
    return problems


def check_naming(cfg: Config) -> list[str]:
    """LaTeX macro names accept letters only.

    A name with a digit or an underscore produces a .tex that breaks the
    Overleaf compile for everyone on the project. The helpers refuse such a
    name before writing; this catches a file that arrived some other way.
    """
    problems = []
    for tier in ("paper", "notes"):
        for key, rec in load_records(cfg, tier).items():
            for name in rec.get("macros", {}):
                if not MACRO_NAME.match(name):
                    problems.append(
                        f"{key}: \\{name} is not a legal macro name. "
                        "LaTeX accepts letters only, so use camelCase."
                    )
    return problems


# --------------------------------------------------------------------------

CHECKS = [
    ("paper-repo", check_paper_repo),
    ("ancestry", check_ancestry),
    ("reachable", check_reachable),
    ("tier-leak", check_tier_leak),
    ("collision", check_collision),
    ("naming", check_naming),
]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.parse_args(argv)

    try:
        cfg = load_config()
    except ArtefactError as exc:
        fail(str(exc))
        return 1

    failed = 0
    for name, fn in CHECKS:
        try:
            problems = fn(cfg)
        except ArtefactError as exc:
            fail(f"{name}: {exc}")
            failed += 1
            continue
        if problems:
            failed += 1
            fail(f"{name}")
            for p in problems:
                info(p)
        else:
            ok(name)

    if failed:
        print()
        fail(f"{failed} check(s) failed.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
