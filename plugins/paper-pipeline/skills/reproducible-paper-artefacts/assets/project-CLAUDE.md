# Project rules

This repo is the code. `paper/` inside it is a separate repo tied to Overleaf,
gitignored here, holding one branch. All branching happens in this repo.

Everything in the manuscript that came from code is generated. An artefact is
a file the pipeline generates for a write-up: a figure, a table, or a file of
numbers. It is identified by its path, its content hash, and its stamp: the
commit that built it.

## Pick a tier by who will see the output

| Tier | For | Output goes to | Branch | How |
|---|---|---|---|---|
| scratch | this conversation only | `scratch/`, gitignored | any | put the script there too and run it directly |
| notes | coauthors, not the manuscript | `paper/notes/artefacts/` | a wip (work in progress) branch | `make notes` |
| paper | the manuscript | `paper/artefacts/` | `main` | `make build` |

When it is unclear, it is scratch or notes. Promoting a result to the paper
tier later is cheap. Pulling a wrong number back out of a manuscript is not.

## Branches

- Exploratory work outside `scratch/` never happens on `main`. If the branch
  is `main` and the work is for the notes tier, run `make wip TOPIC=<topic>`
  and say so in one line: "Started `wip/overlap` off main." Do not ask. The
  branch costs nothing, and the question interrupts the actual request.
- A new topic branches off `main`, which is what `make wip` does. Branch off a
  wip branch only when the new work needs code that exists only there.
- After a squash-merge, keep the wip branch, or tag it
  (`git tag archive/<topic> wip/<topic>`) and then delete it. A squash puts
  none of the branch's commits on `main`, so without the branch or the tag,
  the stamps of its notes artefacts point at commits that git can delete.

## Commits and pushes

- On a wip branch, `make notes` commits for you before it builds.
- A request to change the manuscript allows the commits on `main` that the
  change needs: the squash-merge that promotes a result to the paper tier, or
  a commit whose message says what changed.
- Push either repo only when asked. `make push-paper` is visible to coauthors
  and has no undo, because Overleaf refuses force pushes.

## Never

- Edit anything under `paper/artefacts/` or `paper/notes/artefacts/`. It is
  build output. Fix the code and rebuild.
- Type a number from code or config into a `.tex` file. Emit a macro instead.
  A fixed convention, such as a significance level of 0.05, may be typed. A
  methods setting, such as a sample size or a number of repetitions, may not,
  because it changes with the code or the config. Name result macros
  `\resThing` in the paper and `\wipThing` in notes, and methods settings
  `\mthThing`. The `res` and `wip` prefixes are a habit for the reader, and
  the tools go by tier. The `mth` prefix is the one the tools read.
- Write to a tier except through the emit helpers (`emit_numbers`,
  `save_figure`, `save_table`), with the path taken from Snakemake's `output`.
- Build with `snakemake` directly. Use the `make` targets, which run the guard
  (`tools/build_guard.py`, the branch and tree check before a build).
  Read-only calls such as `snakemake -n` are fine.
- Reference anything under `scratch/` from a `.tex` file.

## Methods

- A tracked setting is a methods setting that the code records as an
  `\mthThing` macro. Record it from what ran, not from the config: the folds
  from the fitted search, the sample sizes and repetitions from the stored
  results. Emit it in the same `emit_numbers` call as the results it belongs
  to.
- The user chooses which settings are tracked, and which of those the text
  prints through its macro. Do not start tracking a setting, or replace typed
  text with a macro, unless asked. New methods text prints tracked settings
  through their macros.
- After a change to anything the methods section describes, run
  `make methods`, then fix the text or tell the user what no longer matches.
- `make methods-ok` records that the methods text was reviewed against the
  current values. Run it only after reading the whole methods section against
  `make methods`, and after every mismatch is fixed or reported.

## Checks

- `make pdf` compiles the manuscript, so the checks can see what it uses.
- `make status` classifies each artefact as current, stale (a dependency
  changed since the build), drifted (the file was edited after the build),
  orphan (the manuscript uses it, but no recorded build made it), or unused.
  The skill has one repair for each state.
- `make methods` shows the tracked settings, whether the text prints each
  one, and what changed since the review that `make methods-ok` recorded.
- `make check` fails when a paper artefact's stamp is not on `main`, a notes
  artefact's stamp no longer exists, the manuscript uses notes or scratch
  output, a file has drifted or is an orphan, or a macro name is defined twice.
  It also warns when a tracked setting changed after that review.
  `make push-paper` runs all of it first. The code repo's pre-push hook runs
  all but the methods warnings.

The `reproducible-paper-artefacts` skill has the procedures: making an
artefact, recording methods settings, the methods audit, promotion, and one
repair for each state. Load it when a task needs more than these rules.
