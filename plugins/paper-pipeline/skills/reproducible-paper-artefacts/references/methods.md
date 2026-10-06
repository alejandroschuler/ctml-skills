# Methods

Many mismatches between a paper and its code sit in the methods, not in the
results: the learners, the tuning grids, the cross-validation folds, the sample
sizes, the number of repetitions. This file covers how to keep those in step,
one setting at a time, and how to check the parts that stay prose.

## Contents

- Record what ran: where to read each setting from
- Three levels, chosen per setting: manual, tracked, generated
- Recording a setting: `mth` macros, for a model fit and for a simulation
- Formatting helpers: `words`, `numlist`, `numset`, `pkg_version`, `text`
- Methods tables: `grid_table()` and `rows_from_search()`
- The sheet and the review: `make methods`, `make methods-ok`, and the
  methods check
- The methods audit: the steps for what stays prose
- With the other skills

## Record what ran

A methods description goes wrong in three ways:

- The code changes and the prose does not. A learner is dropped, or a grid
  moves.
- A default changes. The text says "100 boosting iterations", but that was a
  package default, and the default changed between versions.
- What ran differs from what was planned. The config asks for 1,000
  repetitions and 37 fail, or a script overrides a config value.

A value read from the fitted object, or from the stored results, catches all
three. A value read from the config catches only the first. So record each
setting from what ran:

- the number of folds from the fitted search (`search.n_splits_`), not from
  the `cv` argument you meant to pass;
- a fixed hyperparameter from the estimator's own parameters
  (`search.estimator.get_params()`), so a default is reported as it was. In
  xgboost, also set it in the constructor, as the section on methods tables
  says;
- sample sizes, repetitions and failures from the stored per-repetition
  results, not from the config;
- package versions from the running interpreter, with `pkg_version()`.

## Three levels, chosen per setting

| Level | Text | Code | What catches a mismatch |
|---|---|---|---|
| manual | typed by hand | nothing | the methods audit, at the end of this file |
| tracked | typed by hand | records the value | `make methods` and `make check` |
| generated | prints the value through its macro, or inputs a methods table | records the value | nothing needed: the text cannot drift |

To start controlling a setting, add one line of code; that makes it tracked.
To generate it, replace the typed text with its macro. To stop, delete the
line.

## Recording a setting

A methods setting is a macro whose name starts with `mth`. Emit it in the same
`emit_numbers` call as the results of the computation that used it:

```python
import artefacts as art
from sklearn.model_selection import GridSearchCV, KFold
from xgboost import XGBRegressor

search = GridSearchCV(
    XGBRegressor(reg_lambda=1, min_child_weight=1, random_state=1),
    {"max_depth": [1, 2, 3, 4, 5], "learning_rate": [0.1, 0.3],
     "n_estimators": [125, 250, 500]},
    cv=KFold(n_splits=5, shuffle=True, random_state=1),
    scoring="neg_mean_squared_error",
).fit(X, y)

art.emit_numbers(snakemake.output.numbers,
    resPrimaryAte   = art.num(ate, 2),
    mthPrimaryFolds = art.int(search.n_splits_),
    mthXgboost      = art.pkg_version("xgboost"))
```

The learner and its grid follow the `supervised-learning` skill. A grid over
`n_estimators` fits the model again for each number of trees.
`supervised-learning` shows how to score every round of one fit instead.

The settings then carry the same stamp as the results, the commit that built
them, and go stale with them. A numbers file that holds only methods settings
is fine: `make status` never reports it as unused, because tracking a value
that the text types by hand is the point.

In the text, `\mthPrimaryFolds-fold cross-validation` renders as "5-fold
cross-validation".

For a simulation, read the design from the stored per-repetition results:

```python
res = pd.read_parquet(art.track_read(snakemake.input.results))
art.emit_numbers(snakemake.output.design,
    mthSimN      = art.numset(sorted(res["n"].unique())),
    mthSimReps   = art.int(res["rep"].nunique()),
    mthSimFailed = art.int(res["failed"].sum()))
```

Emit the diagnostics of each data-generating process (DGP) the same way, from
the one large draw used to check it: the true value of the estimand, the
overlap, and the signal-to-noise ratio.

## Formatting helpers

The helpers exist in Python, with the `art.` prefix, and in R. The names are
the same, except for the last row.

| Helper | Output | Use |
|---|---|---|
| `words(x)` | a, b, and c | a prose list, with LaTeX characters escaped |
| `numlist(x)` | 250, 500 and 1000 | numbers in prose, through siunitx |
| `numset(x)` | {250, 500, 1000} | a set, in math mode only, such as the sample sizes: `$n \in \mthSimN$` |
| `pkg_version(name)` | 1.5.2 | the version the running interpreter loaded |
| `text(x)` in Python, `latex_text(x)` in R | escaped text | any other string |

Pass `words()` the names the text uses, such as a mapping from estimator class
to "gradient boosting", rather than code identifiers. `numlist` and `numset`
take `digits=` for fixed-point values; without it, whole numbers stay whole and
others keep six significant digits.

## Methods tables

A long list belongs in a table, not a macro. A table named
`tables/methods-*.tex` is a methods table: `make methods` compares it by
content hash, and `make status` never reports it as unused.

`grid_table()` writes a learner library's hyperparameters as such a table,
from the configurations the fits used:

```python
rows = art.rows_from_search(search, "gradient boosting",
                            fixed=["reg_lambda", "min_child_weight"])
rows += [{"learner": "main-terms GLM"}]
art.grid_table(snakemake.output.library, rows, label="tab:library")
```

The search's estimator sets `reg_lambda` and `min_child_weight` to their
xgboost defaults. Without that, xgboost's scikit-learn wrapper keeps `None` for
them, and the table would show `None`. Here "main-terms GLM" is a generalized
linear model with one term per covariate.

```latex
\begin{table}
  \caption{Learners and hyperparameters.}\label{tab:library}
  \input{artefacts/tables/methods-library.tex}
\end{table}
```

The manuscript needs the booktabs package.

Each row is one configuration of a learner, that is, one combination of its
hyperparameter values. A row is a dict or a DataFrame row with:

- `learner`: the learner type, as the table names it;
- one entry per hyperparameter.

`rows_from_search()` builds these rows from a fitted `GridSearchCV` or
`RandomizedSearchCV`. It drops pipeline prefixes such as `model__`, and it
reads the values of the untuned hyperparameters listed in `fixed` from the
search's estimator. Rows for other learners can be added by hand. A learner
with no hyperparameters needs only its type name, `learner`. Rows from several
fits, such as the repetitions of a simulation, can go in together. In R,
`grid_table()` takes a data frame, or a list of data frames, with the same
columns.

Within a learner type, a hyperparameter with one value is fixed, and one with
several is tuned. The table lists each with its value or its grid; a grid with
more than six values is shown by its size and range.

`grid_table()` does not check whether a grid is wide enough. That check is the
edge rule of the `supervised-learning` skill. Apply it where the learners are
tuned, while a wider grid can still change the results. Earlier versions of
`grid_table()` ran a grid check, so older code may pass `cv_risk` and `fit`
columns, a `limits` argument, or `fit` and `metric` to `rows_from_search()`.
That code still runs, and those values are ignored.

## The sheet and the review

`make methods` shows the methods sheet:

- each setting and methods table, with its current value;
- whether the text prints it through its macro (`macro`) or not (`by hand`).
  This comes from the compile record, the files and macros that the last
  `make pdf` saw, so run `make pdf` first;
- whether it changed since the last review.

`make methods-ok` records the current values as reviewed, in
`paper/methods-reviewed.json`, and commits that file in the paper repo. The
next `make push-paper` sends it to Overleaf. Run it only after the whole
methods section has been read against the sheet, and every mismatch has been
fixed in the text or in the code, or reported to the user.

`make check` runs the methods check, and so does `make push-paper`. The
methods check warns when:

- a setting that the text does not print through its macro changed since the
  review, is new, or is no longer recorded;
- the methods text has never been reviewed against the recorded settings.

A printed setting that changed gets a note instead of a warning: its text
updates itself, but the sentence around it may need rereading. With
`[methods] strict = true` in `.artefacts.toml`, the warnings fail `make check`
and `make push-paper`. The code repo's pre-push hook does not run the methods
check.

## The methods audit

Some things stay prose: the DGP formulas, the estimand definitions, the
descriptions of the estimators, and every reason. For these, Claude runs an
audit when a notes result is promoted to the paper, before submission, and
when the user asks:

1. Run `make methods`, and read the sheet.
2. Read the methods section of the manuscript, and any appendix that holds
   methods.
3. For each claim about what was done, find the code or the recorded value
   that confirms it, and cite it as `file:line` or as a macro name. Claims
   include a formula, a parameter value, a learner, a grid, a fold count, a
   sample size, the way seeds are set, and a software version.
4. Report each mismatch with both sides. Fix none silently, because the error
   can be in the text or in the code.
5. After the text is fixed, run `make methods-ok`.

This answers the question from `design-and-report-simulations`, "could a
reader reimplement this from the text alone?", against the real code.

## With the other skills

- `design-and-report-simulations` asks for ADEMP (aims, data-generating
  mechanisms, estimands, methods, performance measures) before the results,
  for the DGP diagnostics in the paper, and for the number of repetitions and
  failures. Emit the numbers from the diagnostic draw and the stored results.
  The aims, the formulas and the reasons stay prose, and the audit checks them.
- `supervised-learning` chooses the learners and their grids, and says that the
  fixed values and the grids are both part of the method. Its edge rule checks,
  at tuning time, that each grid is wide enough. `grid_table()` reports the
  fixed values and the grids in the paper.
