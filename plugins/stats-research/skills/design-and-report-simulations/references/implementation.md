# Implementing simulations

Simulation code is written to be run and rewritten, not maintained. Fast, modular, and disposable beats polished, because the thing that determines quality is how many times you can go around the loop before the deadline. Three properties make each trip around the loop cheap, and all three are easier to build in from the first line than to retrofit: any piece of the design can run alone, one shared path leads from the data to every display, and the expensive steps are cached.

This guidance is written for R but the same ideas apply in Python or other languages, although the implementation will look slightly different.

Two working skeletons in the shape described here, pick by language:

- `../assets/simulation-scaffold.R` (tidyverse, S3 classes, `furrr` for parallelism)
- `../assets/simulation-scaffold.py` (numpy/pandas, dataclasses, `joblib` for parallelism)

Both build the same pipeline and produce the same two tidy results frames, so the R snippets below describe the pattern regardless of which you use. Run as a script, each prints the diagnostics of its data-generating processes (DGPs) first, which is the habit worth copying, then runs a small grid and reruns one piece of it from the cache.

## Architecture

The pipeline runs one way: datasets, then learner predictions, then estimates, then summaries. Each layer reads the one below it and knows nothing about the ones above.

**DGPs** are objects carrying their nuisance functions and noise level, with a `draw` method. Keeping the treatment log-odds $\rho$, the outcome regression $\mu$ and the noise SD $\sigma$ as named fields rather than inlining them means you can compute the true estimand, run diagnostics, and add a new DGP by changing three lines.

```r
simple_dgp <- structure(list(
    rho   = \(w1, w2) w1 + w2,
    mu    = \(a, w1, w2) w1 + w2 + a,
    sigma = 1
), class = "dgp")

complex_dgp <- structure(list(
    rho   = \(w1, w2) w1 + w2 + w1 * abs(w2),
    mu    = \(a, w1, w2) w1 + w2 + abs(w2) + 0.5 * w1 * w2 + a * (1 + 0.5 * w1),
    sigma = 1
), class = "dgp")
```

A companion `draw_intervene` method, which draws under a fixed treatment rule, gives you the true estimand by brute force and costs almost nothing to write. Draw both arms from the same seed. They then share covariates and noise, and the brute-force truth carries no outcome noise.

**Learners** take training data and return a prediction function. Everything that determines a fit, hyperparameters and seed included, is written into the learner's definition, which puts it in the learner's source and so in its cache key. A **library** combines several learners into one prediction. Which learners, which settings, and how to combine them is learner setup, and it comes from the `supervised-learning` skill.

**Estimators** are functions with a uniform signature: take a data frame with consistently named columns plus the nuisance predictions at its rows, return `list(est = ..., est_se = ...)`. The uniform signature is what lets the run stay a plain map. Write for the simulation, not for a human user; this is not a package.

Estimators never fit anything. Factoring the learning of shared nuisances out of them means methods differing only in what they do with the same nuisance estimates are compared on that difference alone, and it means a new estimator reruns nothing upstream.

**The run** maps over the cells of the design. A cell is one simulated dataset, named by its DGP, sample size and repetition. It is made of three draws of that size: a training draw that the learners are fit on, a validation draw that scores them, and an estimation draw that the estimators see. The `supervised-learning` skill gives the reasons for this split, and the cases that need cross-fitting instead. The run returns tidy data frames. For the estimates that is one row per cell per library per estimator, with columns `est` and `se` for the estimate and its standard error (SE). Tidy output is what makes the analysis step a single `group_by |> summarize`.

**Files:** DGPs, learners, estimators and the run each in a file of their own, and the summary behind each display in another.

## One pipeline serves every claim

When two claims need some of the same computation, they get it from the same code, and where it is expensive, from the same stored output.

Take a paper that compares learner libraries by how well they estimate the nuisance functions and also reports how targeted maximum likelihood estimation (TMLE) performs when built on some of those libraries. That is one simulation with two summaries. One pipeline draws the datasets and fits the learners. The library table summarizes the predictions against the true nuisance values, which a simulation knows exactly. The TMLE table summarizes estimates computed from those same predictions. No second script redraws the data or refits a learner.

Three things follow:

- A fix to a DGP or a learner reaches every display at once, so the displays cannot drift apart.
- Each expensive fit is paid for once.
- Every display is computed on the same datasets, so the displays can be compared repetition by repetition. A bad TMLE estimate can be traced to the nuisance fit in the same repetition, and a contrast between two libraries is paired, which usually makes it far more precise than the libraries' separate Monte Carlo errors suggest.

The pilot and the full run are this same pipeline at different repetition counts. A pilot with a script of its own has bugs the full run does not share, so it checks the wrong code.

This is the code-level version of what the mockup stage does on paper. Two claims that share a display, or a goal whose evidence is a subset of another goal's, should share computation as well.

## Any piece runs alone

The design is a grid of cells. Each cell gets a fit from every learner in play, and each fit feeds every estimator. The run function takes a subset of each factor, with the full grid as the default:

```r
run_sim(dgps = "complex", libraries = "select", estimators = c("aipw", "tmle"), reps = 1:200)
```

Here `select` is the scaffolds' library that picks between two learners by their risk on the validation draw. One call like this reruns a DGP after changing it, adds an estimator without touching the others, or runs one learner library across every estimator.

For a partial run to return exactly the rows a full run would, two things have to hold.

- **Seeds come from the cell's name.** A dataset's seed is a function of its DGP, sample size and repetition, and never of its position in a loop. A seed set once per repetition and then consumed DGP after DGP gives the complex DGP different data depending on whether the simple one ran first, so rerunning one DGP silently breaks its pairing with everything else. Name the random number generator along with the seed, because a parallel backend can switch it (`furrr` with `seed = TRUE` moves workers to L'Ecuyer-CMRG), and the same seed under another generator is a different dataset. Learners with internal randomness need fixed seeds as well, which the `supervised-learning` skill covers.
- **Results are stored per cell.** A partial run adds rows to what exists. Together with the cache, this means a rerun of the whole grid after a change recomputes only what the change touched.

## Cache what is expensive

Most simulations spend nearly all their compute in one place. When the simulation fits learners, that place is the learner fits, and everything computed from their predictions is cheap. Store the output of the expensive steps on local disk, so that no rerun and no new summary computes them a second time.

- **Store predictions rather than fitted models.** Predictions are smaller and simpler to serialize, and they are all an estimator or an accuracy summary reads. Store them at every point a planned estimator will ask for; for the average treatment effect (ATE) that means the propensity score, and the outcome regression at each unit's observed treatment and at both treatment values.
- **Store the finest grain that fits on disk.** For an ensemble that means each base learner's predictions on the validation draw and on the estimation draw. The ensemble is then a cheap combination of stored predictions. A new library costs no refitting, and neither does a new combining rule or the root mean squared error of a single base learner. Stored for each setting of a tuned learner, the same predictions give that setting's validation risk in every repetition, which is what the edge check in the `supervised-learning` skill reads. Check the size first, as stored values per dataset times datasets times 8 bytes. Ten learners that each store four values per observation on both draws, at a sample size of 1000 and 3000 datasets, come to about 2 GB. When the finest grain will not fit, store library-level predictions instead.
- **Key each entry on everything that determines it.** A hit has to return exactly what recomputing would. Hash the inputs themselves, the three draws, together with the source code of the learner and of the fitting function. Hashing the data rather than the seed or the DGP's name means a changed DGP or seed can never pair a stored fit with the wrong dataset. Hashing each learner's own source means editing one learner invalidates its entries and no others. A key that includes too much costs a recomputation, while a key that misses a dependency serves stale results with no sign of it, so when unsure, put it in the key. The usual misses are your own helper functions called from inside a learner, and package upgrades.
- **Keep the cache local and out of git.** Put it in a directory listed in `.gitignore` before the first run, so it never shows up as a change and never gets committed.
- **Write each entry atomically.** Write to a temporary name, then rename, so a run killed mid-write leaves no truncated entry behind.

Datasets are cheap to redraw from their seed, so the scaffolds do not cache them. Estimates are usually cheap given predictions, so the run recomputes them every time. An estimator that is expensive in its own right, one that bootstraps for instance, gets its own cache entry keyed the same way.

The cache is never the record; the raw per-repetition results are. Deleting the cache should change how long the next run takes and nothing else. If deleting it changes a result, some key missed a dependency, so one run from an empty cache is the check to make before a result is final.

## Speed

Compute is the binding constraint on iteration, so spend it deliberately.

- **Parallelize across cells.** In R, `furrr::future_pmap` is a drop-in replacement for `pmap` once you set a `plan()`; every cell sets its own seed, so pass `furrr_options(seed = NULL)`. Test with a handful of repetitions before scaling. The fits inside each cell then need the thread settings from the `supervised-learning` skill.
- **Use the three draws in place of cross-fitting and nested cross-validation.** Each learner is then fit once per cell, where cross-validated cross-fitting with five folds at each level would fit it 5 × (5 + 1) = 30 times: five inner fits and one refit in each of the five outer folds. The answer rarely changes, and the `supervised-learning` skill lists the cases where it can. Keep the library to one or two good learners unless the claim is about ensembles or learner libraries. When it is, the cache is what makes them affordable, since every library is a recombination of stored predictions.
- **Set up learners with the `supervised-learning` skill.** A method comparison is often a learner comparison in disguise, so learner setup is part of the design. The checks in that skill have the most data in a simulation, since every repetition refits the library.

The scaffolds' learners are placeholders that keep the pipeline running: MARS and a GLM in R, gradient boosting and a linear model in Python.

## What to save

Two things go to disk, and they do different jobs.

The **raw per-repetition results** are the record. For each cell they hold one row per library and estimator, with the estimates, standard errors, interval limits and convergence flags, plus the accuracy measures a display needs in a frame of their own. Every table and figure is derived from them and can be regenerated, which is what makes it possible to answer a reviewer's question about a different performance measure without re-running anything.

The **cache** holds the expensive intermediates and exists only for speed.

A fast simulation needs less of both, since regenerating is cheap, which is one more argument for keeping the simulation fast.

## Testing and documentation

Keep both light. Simulation code gets rewritten constantly, and elaborate test suites and docstrings are rewritten with it.

- Comments where something is non-obvious, not everywhere.
- When you write a new function, exercise it a few times in a notebook and look at the output. Does the difference-in-means estimator recover the truth on a DGP with no confounding? Does the estimated SE shrink like $1/\sqrt{n}$?
- Clear claims are themselves a debugging tool. Knowing what *should* happen is how you notice that it did not.

## Analysis

The summarize step turns the tidy results into the mockup's tables, one summary per display. Compute the true estimand values once per DGP, then group and summarize:

```r
true_ATEs <- DGPS |> map_dbl(ATE)

results$estimates |>
    mutate(theta = true_ATEs[DGP]) |>
    group_by(DGP, n_obs, library, estimator) |>
    summarize(
        bias         = mean(est - theta),
        empirical_se = sd(est),
        model_se     = sqrt(mean(se^2)),
        rmse         = sqrt(mean((est - theta)^2)),
        coverage     = mean(abs(est - theta) <= 1.96 * se)
    )
```

Here `DGPS` is the named list of DGP objects, and `ATE()` computes each one's true effect by brute force with `draw_intervene`. The library table is the same operation on `results$accuracy`, grouped by library and nuisance. From there, `tidyr`, `kable` and `ggplot` produce the tables and figures that the mockup specified. The Python scaffold's `summarize_estimators` and `summarize_learners` are the same operations as pandas `groupby`, feeding `matplotlib` or `plotnine`.

Wrap each estimator call so a failure records `NA` and gets counted, rather than ending the run.
