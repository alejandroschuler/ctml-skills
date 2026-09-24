# Setting up a project

`scripts/setup_project.py` does all of this. It is a dry run by default, so
running it to see the plan costs nothing, and the dry run reports what
`--apply` will do, including for files that a migration moves into place.

```
python3 scripts/setup_project.py --root ~/research/my-paper \
    --overleaf https://git.overleaf.com/<project-id>
python3 scripts/setup_project.py --root ~/research/my-paper \
    --overleaf https://git.overleaf.com/<project-id> --apply
```

The manual steps are below, both because a blocked script should never leave
you stuck and because knowing what the pieces do makes the failures legible.

## Requirements

- Snakemake 8 or newer on PATH. Python rules run under Snakemake's own
  interpreter, so their packages go there too: with a uv install,
  `uv tool install snakemake --with pandas --with matplotlib`.
- Python 3.11 or newer as `python3`, for the tools (they need `tomllib`).
- R with ggplot2 and knitr, for the R emit helpers.
- A local TeX installation with latexmk, for `make pdf`.

## Order matters in exactly one place

The code repo's `.gitignore` has to contain `/paper/` before the first commit.
Miss that and `git add -A` records `paper` as a bare commit hash, a submodule
entry with no `.gitmodules` behind it, and every clone after that is broken in
a way that is annoying to undo. The script adds the line to an existing
`.gitignore`, including one that a migration brings up from `code/`. Everything
else can be done in any order.

## From nothing

```
mkdir my-paper && cd my-paper
git init -b main
```

Write `.gitignore` with `/paper/`, `/results/`, `/scratch/`, `/.artefacts/`,
`/logs/` and `Rplots.pdf` in it. The last two are files a build can leave
behind; an untracked file makes the tree dirty, and the emit helpers refuse to
write from a dirty tree. Then clone the paper in:

```
git clone https://git.overleaf.com/<project-id> paper
```

Overleaf's git bridge authenticates with a token as the password, generated
under Account Settings and Git integration. The username can be anything.

Then write `.artefacts.toml`, copy the assets into place, and point git at the
tracked hooks directory:

```
git config core.hooksPath .githooks
```

That last line is the difference between a hook that survives a clone and one
that silently exists on a single machine. It is also the reason the tooling
lives in `tools/` inside the project rather than in the skill directory: every
clone of the project has to be able to run the checks.

## Detect the paper's branch, never assume it

Older Overleaf projects come back on `master` and newer ones on `main`, so
`setup_project.py` reads the branch rather than assuming one.

There is a second case it handles. When the remote's HEAD names a branch that
does not exist, `git clone` leaves an unborn HEAD and an empty working tree,
and every later step then fails somewhere unrelated to the real cause. The
script asks the remote directly and checks the branch out. If it cannot tell
which branch is meant, it stops and says so rather than picking one.

## Migrating two sibling repos

This is the case that applies to existing projects. The layout goes from

```
project/
├── code/     git repo
└── paper/    git repo, Overleaf
```

to the code repo being the top level, with `paper/` inside it and ignored.

`setup_project.py` handles it: it moves `code/.git` up to the project root,
moves the contents up with it, and leaves the paper repo completely alone. The
Overleaf history is never touched, which matters because the bridge holds one
branch and refuses force pushes, so there is no undo. Before it moves anything,
it checks every name. If a name exists both in `code/` and in the project
folder, it stops, because the move would overwrite one of the two.

What the script cannot do is convert the manuscript. That part is manual and
best done gradually:

1. Add `\usepackage{artefacts}` and `\input{artefacts/artefacts.tex}` to the
   preamble.
2. Inventory what is already generated. Every `\includegraphics` pointing at a
   figure some script produced is an artefact waiting for a Snakemake rule.
3. Convert one computation at a time. Pick a model fit, write its Snakemake rule, have it
   emit its numbers, and replace those numbers in the prose with macros. A
   half-converted paper is fine and stays compilable throughout.
4. Hand-typed numbers are the slow part. Search the body for decimals:
   `grep -nE '[0-9]+\.[0-9]+' main.tex` finds most of them. Each one is either
   a number that code or config produced, which becomes a macro, or a fixed
   convention like a significance level, which stays.

There is no value in converting everything before using the system. Staleness
tracking on the six numbers that matter beats nothing at all on forty.

## Running setup again

It is safe on a project that is already set up. It refreshes the checkers in
`tools/`, the R and Python emit helpers, `artefacts.sty`, and the project rules
block in `CLAUDE.md`, which sits between two comment lines so the rest of the
file is left alone. It adds any missing `.gitignore` lines. It keeps the
Makefile and the Snakefile, and when either differs from the skill's copy it
prints the `diff` command to compare them.

An older version of this setup also installed
`.github/workflows/artefacts.yml`. The script says to remove it: it read
`BUILD.json` from `paper/`, which CI never has, so it passed on zero records.

## What setup writes, and why each piece is there

| Path | Why |
|---|---|
| `.artefacts.toml` | The marker. Its presence is how the tools, and Claude, know the project rules apply. `[methods] strict` sets whether methods warnings fail `make check`. |
| `CLAUDE.md` | The project rules, between two comment lines, in context on every turn in this project whichever skill loads. |
| `.gitignore` | `/paper/` first of all, then the build's own leftovers. |
| `Makefile` | The named targets. `make build` and `make notes` run the guard, `tools/build_guard.py`, first. |
| `Snakefile` | The pipeline skeleton, with the `lib()` helper, the registry lists, and the notes split. |
| `tools/*.py` | The checkers. Tracked, so every clone can run them. |
| `.githooks/pre-push` | Tracked, so it survives a clone. |
| `paper/artefacts.sty` | Collision detection, use logging, and spacing for generated macros. |
| `paper/artefacts/README.md` | The do-not-edit notice, written for a coauthor looking at Overleaf. The notes tier gets a copy. |
| `paper/artefacts/artefacts.tex` | An empty stub, so the preamble's `\input` works before the first build. |
| `R/lib/artefacts.R`, `py/lib/artefacts.py` | The emit helpers each language's scripts load. |
| `paper/.gitignore` | LaTeX build output, including the compiled PDFs of the manuscript and the notes documents, so `make push-paper` never sends them to Overleaf. |

## After setup

1. Add `\usepackage{artefacts}` and `\input{artefacts/artefacts.tex}` to the
   manuscript preamble.
2. `git add -A && git commit -m "set up artefact pipeline"`
3. `make pdf`. It compiles with the recorder on and writes `main.fls` and
   `main.artefactuse`, which tell `make status` what the manuscript uses.
   Until then, `make status` still reports `current`, `stale` and `drifted`,
   and says that `unused` and `orphan` cannot be judged yet.
   `status-and-repair.md` defines the five states.
4. `make status`
