# Status and repair

`make status` joins three sources: the build records (`BUILD.json`, plus any
sidecars, the per-artefact records a build writes before it merges them), the
compile record (what the manuscript actually opened and expanded), and
Snakemake (what would re-run now).

## Reading the manuscript by observation

Grepping `.tex` for `\includegraphics` finds text that looks like a reference,
including inside commented-out blocks and branches of `\if` that never fire.
That produces confident, wrong answers. LaTeX already knows. `make pdf`
compiles with `-recorder`, which writes `main.fls`, a list of every file the
compiler opened. And `artefacts.sty` makes each generated macro log its own
name when it expands, into `main.artefactuse`. A figure inside a commented
block appears in neither.

Together these two files are the compile record. `make status` says when the
compile record cannot be trusted, and why:

- no compile yet: `unused` (built, but not used by the manuscript) and
  `orphan` (used, but never built) are not reported at all, because an
  approximation would flag every figure in a paper that has only ever been
  compiled on Overleaf;
- the last compile stopped on an error: the compile record is truncated, so
  everything after the error would look unused;
- `main.tex`, or a `.tex` file it inputs, changed after the compile, for
  example after `make pull-paper`: the compile record describes the old
  manuscript.

The fix in each case is `make pdf`, which rewrites the compile record. The
other three states, defined below, are not affected, because they come from
the build records and from Snakemake.

## The five states

### current

Matches its recorded hash, and nothing upstream changed. No action.

### stale

Snakemake says a dependency changed since this was built, or the output does
not exist yet. `snakemake -n` shows the reason for each job. The repair is
`make build`, or `make notes` for the notes tier.

Stale is a warning, and it does not fail `make check`. On a wip branch, paper
artefacts go stale as soon as the branch changes helper code they depend on;
that is the expected state, and every stale artefact still carries the stamp
of the commit that built it.

If something is stale and you expected it not to be, the topic directory it
depends on is probably too broad. Splitting it narrows what invalidates.

### drifted

The file differs from the hash recorded when it was built, so it was edited or
replaced after the fact. The usual cause is a coauthor uploading a replacement
figure through Overleaf's file menu, or someone fixing a number in a generated
`.tex` by hand. `make build` refuses to run while a paper-tier file has
drifted.

First find out what they were trying to fix. Drift is usually a correct
complaint in the wrong place, and the number is wrong in the analysis. Then
delete the file and rebuild:

```
rm paper/artefacts/figures/fig-primary.pdf
make build
```

Deleting is necessary. The file's inputs did not change, so Snakemake sees
nothing to do and would leave the edited file in place. The coauthor's version
stays in the paper repo's history.

The drift check compares against the hash written at build time. It does not
predict what a rebuild would produce, which would require the rebuild.
`stale` carries that meaning.

### orphan

The manuscript uses it, and no recorded build produced it. Either a figure was
placed before its rule was written, or a file was added to the paper repo by
hand. The repair is to write its Snakemake rule. The orphan list is a to-do queue
generated from the manuscript.

Orphan macros need no check here. A macro the manuscript uses but nothing
emits is undefined, and LaTeX stops with "undefined control sequence", which is
louder and earlier than anything this tool could say.

### unused

A paper-tier artefact that a rule produces and the manuscript does not use.
It is a warning and never fails a build, because a rule for a figure not yet
placed is the normal state of a paper in progress. Before submission, delete
the rule or place the figure. Notes artefacts are never reported as unused,
because notes documents read them and the manuscript must not.

## Methods warnings

`make check` also runs the methods check, which warns and does not fail unless
`[methods] strict = true`. A setting warning names a tracked methods setting
that the text types by hand and that changed since the last review, is new, or
is no longer recorded. The repair: run `make methods`, read the methods
section against it, fix the text or the code, then run `make methods-ok`. A
grid warning says that a learner's best setting sits on the edge of its grid
in at least half of the fits; move the grid in that direction.
`methods.md` has the details.

## Repairs that span both repos

The paper repo always looks dirty. It holds `main.aux`, `main.pdf` and similar
files between compiles, and a build leaves regenerated artefacts there until
the next push. That is why the rule that nothing is built from a dirty tree
applies to the code repo only, and why the guard asks the paper tier a
narrower question: does any file differ from the hash its build recorded?

A push failed part way. See `promotion-and-recovery.md`. `make push-paper`
pushes the code first, then the paper, and running it again is safe.

An old paper commit needs inspecting. Check it out and read its `BUILD.json`,
which names the code commit for every artefact in that version, with each
macro's rendered value. That works with no access to the code repo. Inside the
paper repo, `git log -p artefacts/BUILD.json` gives the history of every number
in the paper, with the code commit that changed it. The checkout rewrites
modification times, and `snakemake --touch` reconciles them afterwards without
rebuilding anything.

## ARTEFACTS.md

`make package` writes it, in the Social Science Data Editors README schema:
"List of tables and programs", with columns `Figure/Table #`, `Program`,
`Output file` and `Note`. Several journals ask for this at submission, so the
build records double as part of the replication package.

It is generated by `make package` rather than by every build, because the
schema also expects data availability statements that a methods paper does not
have until submission time.
