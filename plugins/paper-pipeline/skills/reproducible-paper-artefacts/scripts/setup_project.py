#!/usr/bin/env python3
"""Create or migrate a reproducible paper-plus-code project.

Run from the skill directory, never copied into a project.

    python3 scripts/setup_project.py --root ~/research/my-paper
    python3 scripts/setup_project.py --root ~/research/my-paper \\
        --overleaf https://git.overleaf.com/<project-id> --apply

Dry run is the default and prints every action without touching anything.
Pass --apply to carry it out. The dry run reads files that a move will bring
into place, so it reports what --apply will do, not what the tree looks like
before the moves.

The shape it produces:

    my-paper/                 code repo, pushed to GitHub
    ├── .artefacts.toml       marker; tooling looks for this
    ├── .gitignore            ignores /paper/, results/, scratch/
    ├── CLAUDE.md             the rules, always in context here
    ├── Makefile              the single entry point
    ├── Snakefile
    ├── .githooks/pre-push    tracked, so it survives a clone
    ├── tools/                the checkers; tracked, so every clone has them
    ├── R/lib/  py/lib/       topic directories for helpers
    ├── results/              expensive intermediates, gitignored
    ├── scratch/              throwaway scripts and output, gitignored
    └── paper/                separate repo, tied to Overleaf, gitignored here
        ├── artefacts/        manuscript artefacts
        └── notes/            notes documents
            └── artefacts/    exploratory artefacts

Migration is handled: if the target already holds a code repo and a paper repo
side by side, the code contents move up one level and the paper repo is left
exactly as it is. The Overleaf history is never touched, which matters because
the git bridge holds one branch and refuses force pushes.

Running it again on a set-up project is safe. It refreshes the tools, the
helpers and the rules block in CLAUDE.md, adds any missing .gitignore lines,
and keeps the Makefile and Snakefile, saying so when they differ from the
skill's copies.
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent
ASSETS = SKILL / "assets"

CODE_GITIGNORE = """\
# The paper is a separate repository tied to Overleaf. Ignoring it here keeps
# the two histories independent and stops `git add -A` from recording a gitlink.
/paper/

# Expensive intermediates. Regenerable, and large enough that committing them
# would make every auto-commit slow and the history unpleasant.
/results/

# Throwaway scripts and output. Nothing here is ever stamped or referenced by
# the paper.
/scratch/

# Provenance sidecars, merged into paper/artefacts/BUILD.json by the build.
/.artefacts/

# Generated reports
/ARTEFACTS.md
/artefact-dag.pdf

# Files a build can leave behind. Untracked files make the tree dirty, and the
# helpers refuse to write from a dirty tree.
/logs/
Rplots.pdf
.snakemake/
__pycache__/
.Rhistory
.RData
.Rproj.user/
.DS_Store
"""

PAPER_GITIGNORE = """\
# LaTeX build output. Overleaf regenerates all of this, and leaving it untracked
# keeps `make push-paper` from sending it to the project. The notes line covers
# compiled notes documents only; figures under notes/artefacts/ stay tracked.
/{jobname}.pdf
/notes/*.pdf
*.aux
*.bbl
*.bcf
*.blg
*.fdb_latexmk
*.fls
*.lof
*.log
*.lot
*.out
*.run.xml
*.synctex.gz
*.toc
*.artefactuse
"""

PRE_PUSH = """\
#!/bin/sh
# Tracked in .githooks and wired up with core.hooksPath, so it survives a clone.
# A hook that only exists on one machine is a hook that silently is not running.
set -e
echo "artefacts: checking invariants before push"
python3 tools/check_artefacts.py
python3 tools/artefact_status.py --check
"""

ARTEFACTS_TOML = """\
# Marker for the reproducible-paper-artefacts tooling. Its presence is how the
# tools, and Claude, know this project follows these rules.

[project]
paper_dir = "paper"
main_branch = "{main_branch}"
main_tex = "paper/{main_tex}"

[tiers]
scratch = "scratch"
notes = "paper/notes/artefacts"
paper = "paper/artefacts"

[guard]
max_file_mb = 20

[methods]
# false: a methods setting that changed after the last review of the methods
# text is a warning in `make check` and `make push-paper`. true: it fails them.
strict = false
"""

RULES_START = "<!-- reproducible-paper-artefacts -->"
RULES_END = "<!-- /reproducible-paper-artefacts -->"


class Plan:
    def __init__(self, apply: bool):
        self.apply = apply
        self.steps: list[str] = []
        # Destination -> source for every move, so a dry run can read a file at
        # the place it will be once the moves have happened.
        self.moved: dict[Path, Path] = {}

    def say(self, msg: str) -> None:
        self.steps.append(msg)
        print(("      " if self.apply else "would ") + msg)

    def effective(self, path: Path) -> Path | None:
        """Where the content of `path` is at this point in the plan, if anywhere."""
        if path.exists():
            return path
        src = self.moved.get(path)
        return src if src is not None and src.exists() else None

    def run(self, *args: str, cwd: Path) -> str:
        self.say(f"run: git {' '.join(args)}  (in {cwd})")
        if not self.apply:
            return ""
        proc = subprocess.run(
            ["git", *args], cwd=str(cwd), capture_output=True, text=True
        )
        if proc.returncode != 0:
            raise SystemExit(f"git {' '.join(args)} failed:\n{proc.stderr}")
        return proc.stdout.strip()

    def mkdir(self, path: Path) -> None:
        if path.is_dir():
            return
        self.say(f"create directory {path}")
        if self.apply:
            path.mkdir(parents=True, exist_ok=True)

    def write(self, path: Path, text: str, overwrite: bool = False) -> None:
        if self.effective(path) is not None and not overwrite:
            self.say(f"keep existing {path}")
            return
        self.say(f"write {path}")
        if self.apply:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")

    def copy(self, src: Path, dst: Path, overwrite: bool = True) -> None:
        current = self.effective(dst)
        if current is not None and not overwrite:
            if current.read_bytes() == src.read_bytes():
                self.say(f"keep existing {dst}")
            else:
                self.say(f"keep existing {dst}; it differs from the skill's copy. "
                         f"Compare: diff {dst} {src}")
            return
        self.say(f"copy {src.name} -> {dst}")
        if self.apply:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)

    def ensure_lines(self, path: Path, template: str) -> None:
        """Write the template, or add the lines an existing file is missing.

        Keeping an existing .gitignore unchanged is the dangerous choice: a
        migrated code repo brings its own, and without /paper/ in it the next
        `git add -A` records the paper repo as a gitlink.
        """
        current = self.effective(path)
        if current is None:
            self.write(path, template)
            return
        existing = current.read_text(encoding="utf-8")
        have = {line.strip() for line in existing.splitlines()}
        wanted = [line for line in template.splitlines()
                  if line.strip() and not line.startswith("#")]
        missing = [line for line in wanted if line.strip() not in have]
        if not missing:
            self.say(f"keep existing {path}; it has every line setup needs")
            return
        self.say(f"add to {path}: {' '.join(missing)}")
        if self.apply:
            block = "\n# Added by the reproducible-paper-artefacts setup.\n" + "\n".join(missing) + "\n"
            path.write_text(existing.rstrip("\n") + "\n" + block, encoding="utf-8")

    def merge_claude_md(self, src: Path, dst: Path) -> None:
        """Install the rules, or replace an older copy of them in place.

        Migrating a project is the case where this matters most, and it is also
        the case where CLAUDE.md is already there. Skipping it would leave the
        rules out of context in precisely the project that needs them. The rules
        sit between two markers, so running setup again replaces them and leaves
        the rest of the file alone. A copy from before the end marker existed
        runs to the end of the file.
        """
        block = f"{RULES_START}\n{src.read_text(encoding='utf-8').rstrip()}\n{RULES_END}\n"
        current = self.effective(dst)
        if current is None:
            self.write(dst, block)
            return
        existing = current.read_text(encoding="utf-8")
        if RULES_START not in existing:
            new = existing.rstrip() + "\n\n" + block
            action = f"append the artefact rules to the existing {dst}"
        else:
            head, rest = existing.split(RULES_START, 1)
            tail = rest.split(RULES_END, 1)[1].lstrip("\n") if RULES_END in rest else ""
            new = head + block + (("\n" + tail) if tail else "")
            if new == existing:
                self.say(f"keep {dst}; it carries the current artefact rules")
                return
            action = f"replace the artefact rules in {dst} with the current version"
        self.say(action)
        if self.apply:
            dst.write_text(new, encoding="utf-8")

    def move(self, src: Path, dst: Path) -> None:
        self.say(f"move {src} -> {dst}")
        self.moved[dst] = src
        if self.apply:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dst))


def detect_branch(repo: Path) -> tuple[str, bool]:
    """Read a repo's branch instead of assuming it.

    Overleaf clones vary. Older projects come back on master and newer ones on
    main, and assuming produces a checkout failure at the worst moment.

    There is a third case worth handling rather than defaulting through: a clone
    whose HEAD is unborn, which happens when the remote's HEAD names a branch
    that does not exist. The working tree comes back empty and every later step
    fails in a confusing place. When that happens the remote is asked directly.

    Returns (branch, needs_checkout).
    """
    proc = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        cwd=str(repo), capture_output=True, text=True,
    )
    branch = proc.stdout.strip()
    if proc.returncode == 0 and branch and branch != "HEAD":
        return branch, False

    ls = subprocess.run(
        ["git", "ls-remote", "--heads", "origin"],
        cwd=str(repo), capture_output=True, text=True,
    )
    names = [
        line.split("refs/heads/", 1)[1]
        for line in ls.stdout.splitlines()
        if "refs/heads/" in line
    ]
    if len(names) == 1:
        return names[0], True
    for candidate in ("main", "master"):
        if candidate in names:
            return candidate, True
    raise SystemExit(
        f"Cannot determine which branch {repo} should be on. It has no checked-out "
        f"branch and the remote offers: {names or 'nothing'}. Check it out by hand, "
        "then run setup again."
    )


def detect_main_tex(paper: Path) -> str:
    """The manuscript's file name. main.tex when it exists, else the one root file
    that starts a document."""
    if not paper.is_dir() or (paper / "main.tex").is_file():
        return "main.tex"
    starts = [
        p.name for p in sorted(paper.glob("*.tex"))
        if re.search(r"^\s*\\documentclass", p.read_text(errors="replace"), re.M)
    ]
    return starts[0] if len(starts) == 1 else "main.tex"


def find_sibling_code_dir(root: Path) -> Path | None:
    """Spot the two-sibling-repo layout this design replaces."""
    for name in ("code", "src", "analysis"):
        cand = root / name
        if (cand / ".git").is_dir():
            return cand
    return None


def migrate(plan: Plan, root: Path, code_dir: Path) -> None:
    """Move the code repo up one level. Checks every name before moving any."""
    if (root / ".git").is_dir():
        raise SystemExit(
            f"Both {root} and {code_dir} are git repos, so it is not clear which "
            "history to keep. Resolve that by hand, then run setup again."
        )
    items = [p for p in sorted(code_dir.iterdir()) if p.name not in (".git", ".DS_Store")]
    clashes = [p.name for p in items if (root / p.name).exists()]
    if clashes:
        raise SystemExit(
            f"These names exist both in {code_dir} and in {root}: {', '.join(clashes)}. "
            "Moving would overwrite one of each pair. Rename or remove one copy, "
            "then run setup again."
        )
    print(f"Found an existing code repo at {code_dir}. Migrating it up.\n")
    plan.move(code_dir / ".git", root / ".git")
    for item in items:
        plan.move(item, root / item.name)
    plan.say(f"remove the now-empty {code_dir}")
    if plan.apply:
        (code_dir / ".DS_Store").unlink(missing_ok=True)
        code_dir.rmdir()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--root", required=True, type=Path, help="project directory")
    ap.add_argument("--overleaf", help="Overleaf git URL, if paper/ is not there yet")
    ap.add_argument("--main-branch", default="main", help="code repo default branch")
    ap.add_argument("--apply", action="store_true", help="carry it out")
    ap.add_argument("--dry-run", action="store_true", help="default; print only")
    args = ap.parse_args(argv)

    if args.apply and args.dry_run:
        ap.error("--apply and --dry-run contradict each other")

    root = args.root.expanduser().resolve()
    plan = Plan(apply=args.apply)

    print(f"{'Applying' if args.apply else 'Planning'} setup in {root}\n")

    plan.mkdir(root)

    # Migration: code contents move up, the paper repo is left untouched.
    code_dir = find_sibling_code_dir(root)
    if code_dir:
        migrate(plan, root, code_dir)

    if plan.effective(root / ".git") is None:
        plan.run("init", "-b", args.main_branch, cwd=root)

    # The paper repo.
    paper = root / "paper"
    if (paper / ".git").is_dir():
        paper_branch, needs_checkout = detect_branch(paper)
        plan.say(f"found paper repo on branch '{paper_branch}'; leaving its history alone")
        if needs_checkout:
            # An unborn HEAD leaves the working tree empty, and every later step
            # then fails somewhere unrelated. Put the branch on disk now.
            plan.say(f"paper repo has an unborn HEAD; checking out '{paper_branch}'")
            plan.run("checkout", paper_branch, cwd=paper)
    elif args.overleaf:
        plan.run("clone", args.overleaf, "paper", cwd=root)
        if (paper / ".git").is_dir():
            paper_branch, needs_checkout = detect_branch(paper)
            if needs_checkout:
                plan.say(f"clone left an unborn HEAD; checking out '{paper_branch}'")
                plan.run("checkout", paper_branch, cwd=paper)
    else:
        plan.say("no paper/ and no --overleaf given; clone it yourself with:")
        plan.say("    git clone https://git.overleaf.com/<project-id> paper")
        plan.say("then run this again so the branch can be detected")

    main_tex = detect_main_tex(paper)

    # The gitignore has to hold /paper/ before the first commit, or paper/
    # enters the index as a gitlink and every clone after that is broken.
    plan.ensure_lines(root / ".gitignore", CODE_GITIGNORE)
    plan.ensure_lines(paper / ".gitignore",
                      PAPER_GITIGNORE.format(jobname=Path(main_tex).stem))

    plan.write(
        root / ".artefacts.toml",
        ARTEFACTS_TOML.format(main_branch=args.main_branch, main_tex=main_tex),
    )

    for d in (
        "tools", "R/lib/estimate", "R/lib/plot", "R/lib/describe", "py/lib/sim",
        "results", "scratch", ".githooks",
    ):
        plan.mkdir(root / d)
    for d in ("artefacts/figures", "artefacts/tables", "artefacts/numbers",
              "notes/artefacts/figures", "notes/artefacts/tables",
              "notes/artefacts/numbers"):
        plan.mkdir(paper / d)

    for src in sorted((ASSETS / "tools").glob("*.py")):
        plan.copy(src, root / "tools" / src.name)

    plan.copy(ASSETS / "Makefile", root / "Makefile", overwrite=False)
    plan.copy(ASSETS / "Snakefile", root / "Snakefile", overwrite=False)
    plan.merge_claude_md(ASSETS / "project-CLAUDE.md", root / "CLAUDE.md")
    plan.copy(ASSETS / "artefacts.R", root / "R" / "lib" / "artefacts.R")
    plan.copy(ASSETS / "artefacts.py", root / "py" / "lib" / "artefacts.py")
    plan.copy(ASSETS / "artefacts.sty", paper / "artefacts.sty")
    plan.copy(ASSETS / "artefacts-README.md", paper / "artefacts" / "README.md")
    plan.copy(ASSETS / "artefacts-README.md", paper / "notes" / "artefacts" / "README.md")

    # artefacts.tex is build output, so a bare \input in the preamble would
    # break the compile until the first build. An empty stub means the preamble
    # line is plain and correct from the first minute.
    plan.write(
        paper / "artefacts" / "artefacts.tex",
        "% Generated. Do not edit. Empty until the first `make build`.\n",
    )

    plan.write(root / ".githooks" / "pre-push", PRE_PUSH)
    if plan.apply:
        (root / ".githooks" / "pre-push").chmod(0o755)
    plan.run("config", "core.hooksPath", ".githooks", cwd=root)

    old_ci = root / ".github" / "workflows" / "artefacts.yml"
    if old_ci.exists():
        plan.say(f"note: {old_ci} is from an older version of this setup. It checks "
                 "nothing, because CI never has paper/. Remove it with: "
                 "git rm .github/workflows/artefacts.yml")

    print()
    if not args.apply:
        print(f"{len(plan.steps)} steps planned. Re-run with --apply to carry them out.")
    else:
        print("Done. Next:")
        print("  1. Add \\usepackage{artefacts} and \\input{artefacts/artefacts.tex}")
        print("     to the manuscript preamble.")
        print("  2. git add -A && git commit -m 'set up artefact pipeline'")
        print("  3. make pdf, so the scanner can read what the manuscript uses")
        print("  4. make status")
    return 0


if __name__ == "__main__":
    sys.exit(main())
