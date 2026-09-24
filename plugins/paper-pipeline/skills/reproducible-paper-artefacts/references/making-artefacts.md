# Making artefacts

Everything needed to write a rule and its script: where the output goes, how
the rule is shaped, how the script emits, how numbers are named and rounded,
and what the provenance record can and cannot see. Methods settings, the list
and set helpers, and learner-grid tables are in `methods.md`.

## Layout

```
paper/
├── main.tex
├── artefacts.sty          defines \artefactdefine, logs macro use
├── artefacts/
│   ├── README.md          the do-not-edit notice, for coauthors
│   ├── BUILD.json         what produced each file, with hashes and commits
│   ├── artefacts.tex      inputs every numbers file
│   ├── figures/
│   ├── tables/
│   └── numbers/
└── notes/
    ├── 2026-09-14-overlap.tex   a notes document
    └── artefacts/         the same shape, for the notes tier
```

The manuscript preamble needs two lines, and then it never changes:

```latex
\usepackage{artefacts}
\input{artefacts/artefacts.tex}
```

`artefacts.tex` is generated and lists one `\input` per paper-tier numbers
file, so numbers can come and go without touching `main.tex`. It covers only
the paper tier.

### Notes documents

Notes documents live in `paper/notes/`, next to their artefacts, so the folder
collapses in Overleaf's file tree. A notes document inputs the notes numbers
files it needs itself. Write every path from the paper root, such as
`notes/artefacts/numbers/overlap.tex`, and start the preamble like this:

```latex
\documentclass{article}
\usepackage{graphicx}
% Paths are given from the paper root. These lines let them resolve the same
% way whether the compile runs in the paper root or in notes/.
\makeatletter
\def\input@path{{./}{../}}
\makeatother
\graphicspath{{./}{../}}
\usepackage{artefacts}
\input{notes/artefacts/numbers/overlap.tex}
```

Without the `\input@path` line, a compile that runs inside `notes/` cannot
find `artefacts.sty`. Do not use paths relative to `notes/` instead: from the
paper root, `artefacts/numbers/overlap.tex` names the paper-tier file of the
same name.

## The rule

### Two layers

This is the most important structural decision in the Snakefile, and getting it
wrong is what makes people abandon a pipeline. Every expensive computation
writes a results file that is itself a pipeline output. Figures, tables and
numbers then depend on that file plus the plotting helper code:

```python
rule simulate_primary:                    # expensive
    input:  dgp="config/dgp.yaml", helpers=SIM
    output: "results/sim-primary.parquet"
    threads: 8
    script: "py/simulate_primary.py"

rule fig_primary:                         # cheap
    input:  results="results/sim-primary.parquet", helpers=PLOT
    output: f"{ART}/figures/fig-primary.pdf"
    script: "R/fig_primary.R"
```

Without the split, fixing a typo in a plotting comment re-runs the Monte Carlo.
A pipeline that charges an hour for a cosmetic change is one you stop using,
and then every guarantee downstream stops being true. In the Snakefile, `ART`
and `NOTES` name the tier directories `paper/artefacts` and
`paper/notes/artefacts`. `results/` is gitignored, so the build's own output
never dirties the tree.

### The registry

The lists at the top of the Snakefile (`NUMBERS`, `FIGURES`, `TABLES`) are
`rule all`. A name there without a rule fails at once with
MissingRuleException, so the lists are safe to treat as the registry.
Exploratory rules go in the `NOTES_` lists, which feed `rule notes` and stay
out of `rule all`, so a manuscript build does not drag along months of
abandoned exploration. `make notes` builds with `--keep-going`, so one broken
exploratory rule does not block the rest.

### Code dependencies

Snakemake's `code` rerun trigger hashes the script file and nothing it sources
or imports. Change a function in `R/lib/estimate/ipw.R` and the script hashes
the same, so Snakemake reports the artefact as up to date when it is not. So
declare helper code by directory, with `lib()`:

```python
EST  = lib("R/lib/estimate", "R/lib/artefacts.R")
PLOT = lib("R/lib/plot", "R/lib/artefacts.R")
SIM  = lib("py/lib/sim", "py/lib/artefacts.py")
```

`lib()` takes directories and single files, and skips `__pycache__`, compiled
bytecode and hidden files. A new helper file is picked up with no edit.
Invalidation is coarse in the safe direction: editing any estimation helper
marks every fit stale, and nothing that was read is ever missed. If
`R/lib/estimate` is too blunt, split it into `estimate/ipw` and
`estimate/tmle`, and have each rule depend on what it uses.

### Software

Python rules run under Snakemake's own interpreter, so the packages a Python
script imports must be installed there. With a uv install of Snakemake, that is
`uv tool install snakemake --with pandas --with matplotlib`. The other way is a
per-rule `conda:` environment with `--use-conda`, which also makes a dependency
bump mark the affected artefacts stale, because `software-env` is a rerun
trigger. R rules run `Rscript` from PATH, with its usual library.

### Two traps

The first trap is threading the git commit into a rule as a `params` value. It
looks natural, since the script needs the commit for the stamp, the commit
recorded for each artefact. Do not do it. `params` is a rerun trigger, so a
commit that changes on every commit would mark every artefact stale, forever.
The emit helpers read the commit from git at write time, which keeps it out of
the dependency graph.

The second trap is listing an exploratory rule in `rule all`. Every manuscript
build then runs it, and a broken one blocks the paper. Keep exploration in the
`NOTES_` lists.

## The script

R scripts source the emit helpers first; Python scripts import them. The
Snakefile puts `py/lib` on `PYTHONPATH`, so `import artefacts` works in any
script that Snakemake runs.

```r
source("R/lib/artefacts.R")
data <- readRDS(track_read(snakemake@input[["data"]]))
fit <- estimate(data)
emit_numbers(
    snakemake@output[["numbers"]],
    resPrimaryAte = num(fit$estimate, 2),
    resPrimaryCi  = ci(fit$lo, fit$hi, 2),
    resPrimaryN   = int(fit$n)
)
```

```python
import artefacts as art
data = pd.read_csv(art.track_read(snakemake.input.data))
art.emit_numbers(snakemake.output.numbers, resPrimaryAte=art.num(fit.estimate, 2))
art.save_figure(snakemake.output.figure, fig, label="fig:primary")
```

Take every output path from Snakemake's `output`, never from a string in the
script. A script that writes to a tier then cannot run outside the pipeline by
accident, and the rule's declared output is the file that gets written.

Before each write, the emit helpers check that the tier allows it. If not, they
refuse, and nothing is written:

- a paper-tier path when the branch is not `main`,
- a notes-tier path on `main`,
- any paper or notes write from a detached HEAD or a dirty code tree,
- a macro name LaTeX will not accept.

`make notes` commits on a wip branch before it builds and `make build` refuses
a dirty `main`, so a build through `make` passes these checks. A script run by
hand usually does not, and that is deliberate.

## Numbers

### Grain

One file per computation. The estimate, its standard error, its interval and
its n all come out of one fit. They change together and go stale together, so
they live in `numbers/primary-fit.tex` together. A number with its own
expensive computation is its own file, because under this rule it is its own
target anyway.

### Macro names

LaTeX accepts letters in a macro name and nothing else: no digits, no hyphens,
no underscores. So use camelCase: `resPrimaryAte`, never `res_primary_ate` or
`resTable2N`. The emit helpers check this before writing, because a bad name
would produce a `.tex` file that breaks the Overleaf compile for every
coauthor.

Naming manuscript numbers `\resThing` and exploratory ones `\wipThing` helps
the reader, and the tools deliberately do not enforce it. What decides which
guarantee a number carries is the directory it was written to, which
`BUILD.json` records. Rename at promotion anyway: renaming at every use site
makes you reread each sentence whose claim now rests on that number.

### Collisions

`artefacts.tex` inputs every paper-tier numbers file, so two computations that
emit the same macro name would resolve to whichever file loaded last, silently.
`\artefactdefine` claims the name with `\newcommand` first, so LaTeX stops with
"command already defined", and `make check` reports the collision before a
coauthor's compile finds it. Names are compared within a tier, because a tier
is what loads together. A promoted number may keep the name its notes copy had.

### Rounding and formatting

Rounding happens once, in code, through a digits argument:

```python
art.num(fit.estimate, 2)      # \num{0.42}
art.ci(fit.lo, fit.hi, 2)     # (\num{0.21}, \num{0.65})
art.int(fit.n)                # \num{1284}
art.pct(42.0, 1)              # \qty{42.0}{\percent}
art.pval(0.0002, 3)           # \(<\)\num{0.001}
```

The R functions have the same names and arguments. For lists, sets and
package versions, see the formatting helpers in `methods.md`. Fixed-point formatting is
deliberate: `round(0.40, 2)` gives `0.4`, and a paper with `0.4` in one
sentence and `0.42` three sentences later looks careless. Values go through
siunitx, so minus signs, thousands separators and unit spacing stay consistent,
and a change of precision policy is an edit to one call.

### In the text

`\artefactdefine` appends `\xspace`, so `\resPrimaryAte was significant`
renders with its space. In math mode `\xspace` does nothing, which is harmless.
Directly before `\footnote` and inside `\MakeUppercase` it can misfire, so
write `\resPrimaryAte{}` there. Macros work in captions and section titles,
because the definitions are robust commands.

## What the provenance record sees

Each artefact's record in `BUILD.json` lists the files the build read, each
with its content hash. The commit pins the code; the hashes pin the data, which
is usually gitignored.

- Python: after the script body runs, `sys.modules` is scanned for modules
  under the project root. The running script, the checkers in `tools/`, and Snakemake's copies in `.snakemake/` are left out, because no rule declares them.
- R: sourcing `R/lib/artefacts.R` installs a wrapper over `source()` and
  `sys.source()` that logs what they load.
- Data, in both: wrap the path with `track_read(path)`. It returns the path, so
  it drops into any reader.

The instrumentation misses:

- `library()` of a locally installed package, in R,
- `box::use()`, `Rcpp::sourceCpp()`, and anything loaded through a namespace,
- modules reached through `importlib` rather than a normal import, in Python,
- every data file opened directly, without `track_read`.

So the list of reads is a lint that catches the common case, and it is not a
proof. The `lib()` declarations are what guarantee that nothing read is missed;
the record checks that the declarations were enough for the branch of the code
that ran. `make deps` does that check. It compares each artefact's recorded
reads with the transitive closure of its declared inputs, from `snakemake -n
--forceall all notes`, and fails on anything read but not declared, because a
change to that file would leave the artefact looking fresh. A declared input
that the build never read is safe, and it is not reported.

## BUILD.json

It lives next to the artefacts, in the paper repo, so checking out any commit
of the paper tells you what produced that version with no access to the code
repo at all.

```json
{
  "artefacts": {
    "paper/artefacts/numbers/primary-fit.tex": {
      "tier": "paper",
      "sha256": "3a7f...",
      "commit": "8b2c1a0...",
      "built_at": "2026-09-14T09:31:00Z",
      "rule": "fit_primary",
      "macros": {"resPrimaryAte": "\\num{0.42}", "resPrimaryN": "\\num{1284}"},
      "reads": {"R/lib/estimate/ipw.R": "91c0...", "data/analysis.rds": "e5d2..."}
    }
  }
}
```

The file carries no timestamp of its own and is rewritten only when a record
changes. So `git log -p artefacts/BUILD.json` in the paper repo is a changelog
of every number in the paper: when the primary estimate moved from 0.42 to
0.39, and which commit did it.
