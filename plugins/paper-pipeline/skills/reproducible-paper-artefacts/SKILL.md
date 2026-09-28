---
name: reproducible-paper-artefacts
description: Keeps a code repo and its Overleaf manuscript in step, so every figure, table and inline number is built by the pipeline and stamped with the commit that made it. If the repo has .artefacts.toml at its root, use this skill for any task that could produce output (a simulation, an analysis, a model fit, a figure, a table, a number in the text), even when the request does not mention reproducibility. Also use it to set up or migrate a paper-plus-code project, to move exploratory results into the paper, to push to or pull from Overleaf, or when the manuscript may disagree with the pipeline, in its results or in its methods (learners, tuning grids, folds, sample sizes), for example after a figure was edited by hand or uploaded through Overleaf.
---

# Reproducible paper artefacts

The manuscript is a view over a pipeline. An artefact is a file the pipeline
generates for a write-up: a figure, a table, or a file of numbers. It is
identified by its path, its content hash, and its stamp: the commit that
produced it. Every project rule protects that triple.

This skill applies to a project when `.artefacts.toml` sits at the repo root.
Check for it before producing output. The request will usually not mention any
of this, because the person asking wants a number and not a conversation about
git.

## The project rules

The project rules live in the project's `CLAUDE.md`. The setup script,
`scripts/setup_project.py`, copies them there from `assets/project-CLAUDE.md`,
so they are in context on every turn in the project, whether or not this skill
loads. If the project's `CLAUDE.md` does not carry them, read
`assets/project-CLAUDE.md` now. This file holds the procedures.

The project rules define three tiers of output. Scratch output is for this
conversation only, and lives under `scratch/`. Notes are for coauthors, live
under `paper/notes/artefacts/`, and are built on a wip (work in progress)
branch. Paper artefacts are for the manuscript, live under `paper/artefacts/`,
and are built on `main`.

## The shape of a project

```
project/                  code repo, pushed to GitHub
├── .artefacts.toml       the marker
├── CLAUDE.md             the project rules, always in context here
├── Makefile              the named targets
├── Snakefile
├── tools/                the checkers
├── R/lib/  py/lib/       helper code, in topic directories
├── results/              expensive intermediates, gitignored
├── scratch/              throwaway scripts and output, gitignored
└── paper/                separate repo, tied to Overleaf, gitignored here
    ├── artefacts/        manuscript output
    └── notes/            notes documents
        └── artefacts/    exploratory output
```

Overleaf's git bridge holds one branch and refuses force pushes, so all
branching lives in the code repo, and every repair on the paper side is a new
commit.

## Make or change an artefact

1. Pick the tier by who will see the output. For scratch, put the script and
   its output under `scratch/`, run it directly, and stop here.
2. Get on the right branch. Notes need a wip branch: from `main`, run
   `make wip TOPIC=<topic>` and say so in one line. Paper artefacts are built
   on `main`, after a promotion or with a commit that says what changed.
3. Add the name to the registry at the top of the Snakefile (`FIGURES`,
   `TABLES` and `NUMBERS`, or `NOTES_FIGURES`, `NOTES_TABLES` and
   `NOTES_NUMBERS`) and write its Snakemake rule. Declare the helper code it
   uses with `lib()`. Expensive work writes a file under `results/`, and the
   artefact's rule reads that file, so a plotting change does not re-run a
   simulation.
4. In the script, source `R/lib/artefacts.R` or `import artefacts`. Take every
   path from Snakemake's `output`, wrap data reads in `track_read()`, and write
   through the emit helpers: `emit_numbers`, `save_figure` or `save_table`.
   Use one numbers file per computation, rounded in code. Emit the methods
   settings the computation used, read from what ran, as `mth` macros in the
   same call.
5. Run `make notes` for the notes tier, or `make build` for the paper tier.
6. Use the artefact in the `.tex`: `\includegraphics{artefacts/figures/x.pdf}`,
   `\input{artefacts/tables/x.tex}`, or a macro such as `\resPrimaryAte`.
7. Run `make pdf`, then `make check`.
8. Report what you built and its tier. Do not push unless asked.

The emit helpers check every write before it happens. A paper-tier path off
`main`, a notes path on `main`, or a dirty code tree makes them refuse, and
nothing is written. When that happens, the fix is the branch or the commit, not
a way around the helper.

`references/making-artefacts.md` has the Snakemake rule shapes, the emit helper
API, macro naming and rounding, and what the read tracking can and cannot see.

## Knowing what is real

`make status` classifies every artefact:

| State | Meaning | Repair |
|---|---|---|
| current | matches its recorded hash, and nothing upstream changed | none |
| stale | a dependency changed since the build | `make build`, or `make notes` for notes |
| drifted | the file differs from the hash recorded at build time | find out why, delete the file, rebuild |
| orphan | the manuscript uses it, and no recorded build made it | write its Snakemake rule |
| unused | a paper artefact the manuscript does not use | place it, or drop its Snakemake rule before submission |

`stale` and `unused` are warnings. `drifted` and `orphan` fail `make check`.
`unused` and `orphan` come from what the LaTeX compiler opened, so run `make
pdf` first. `references/status-and-repair.md` has each repair in detail.

## Methods

Many code-paper mismatches sit in the methods: learners, grids, folds, sample
sizes, repetitions. Each setting is manual, tracked, or generated, and the user
chooses which. A tracked setting is an `mth` macro recorded from what ran,
such as the folds from the fitted search, and the text may still type it by
hand. A generated setting is one the text prints through its macro, or a
methods table from `grid_table()`. `make methods` shows every tracked setting,
whether the text prints it, and whether it changed since the last review.
`make check` warns about changes the text may have missed. Everything that
stays prose gets the methods audit. `references/methods.md` has the helpers,
the grid check, and the audit.

## Promotion

Promotion turns a notes artefact into a paper artefact, through a squash-merge
onto `main` and a rebuild there. The order of the steps matters. The rebuild is
what makes the ancestry check pass, which requires the stamp of every paper
artefact to be an ancestor of `main`. `references/promotion-and-recovery.md`
has the steps, and one recovery for each way it goes wrong.

## Pushing and pulling

`make push-paper` runs `make check`, pushes `main` of the code repo, and then
commits what the tooling wrote in the paper repo and pushes it to Overleaf,
with retries for Overleaf's usual failures. Other changes in the paper repo,
such as prose, need `MSG="what changed"`; without it, `push-paper` stops before
it pushes anything. Run it only when asked.

`make pull-paper` is the other direction, for when a coauthor has edited on
Overleaf. Run `make pdf` after it, so `make status` and `make check` see the
new manuscript.

A pull brings only the text. Review comments and tracked changes stay on
Overleaf. The `overleaf-comments` skill in the `overleaf-tools` plugin reads
them.

## Setting up

`scripts/setup_project.py` creates a project, or migrates a code repo and a
paper repo that sit side by side into this layout. It is a dry run by default;
pass `--apply` to carry it out. Running it again on a project refreshes the
checkers in `tools/` and the project rules in `CLAUDE.md`.
`references/setup.md` has the details, and the manuscript conversion that the
script cannot do.

## Working with other skills

`design-and-report-simulations` decides what to compute and how to write it up.
This skill decides where the output lands, which branch it runs on, and what
commit stamps it. They compose, and both should load. `supervised-learning`
decides which learners and grids to use; `grid_table()` reports them in the
methods and applies its edge rule to the recorded fits.

## Reference files

| When | Read |
|---|---|
| writing a Snakemake rule or a script, or naming a number | `references/making-artefacts.md` |
| promoting notes work, or git went wrong | `references/promotion-and-recovery.md` |
| recording a methods setting, or reviewing the methods section | `references/methods.md` |
| `make status` or `make check` reports a problem | `references/status-and-repair.md` |
| creating or migrating a project | `references/setup.md` |
