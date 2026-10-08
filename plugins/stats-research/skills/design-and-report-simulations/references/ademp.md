# ADEMP: describing the study before the results

From Morris, White & Crowther (2019), "Using simulation studies to evaluate statistical methods", *Statistics in Medicine* 38(11):2074-2102.

ADEMP is a structure for the part of the write-up that comes before any numbers: Aims, Data-generating processes, Estimands, Methods, Performance measures. It is the "tell 'em what you're going to tell 'em" part of the sandwich.

Aims is the important element. The other four exist to serve it, and a reader judges them by whether they make the aims answerable. You can go through ADEMP once for the whole study, or once per claim when the claims need different setups. The order of the elements matters less than completeness: a reader should be able to replicate the study from the text without the code.

Derive each element from the simulation code, not from what anyone says the code does, and raise any mismatch between the two.

---

## A: Aims

The claims the simulation is meant to support, stated specifically enough that they could turn out to be wrong.

**Weak:** "We conduct a simulation study to evaluate the proposed estimator."
**Strong:** "We evaluate the finite-sample bias and 95% interval coverage of the proposed estimator, relative to the standard approach, when the outcome model is misspecified and the propensity model is correct."

Properties a simulation can target include consistency, finite-sample unbiasedness, whether the method's own variance estimate recovers the true sampling variance, interval coverage, efficiency, and how each of these degrades under specific misspecification. Some aims are not about estimation: testing behavior, model selection, prediction accuracy, runtime.

Every performance measure below should trace back to an aim here. Drop a measure that answers no aim, and add a measure for any aim that has none.

## D: Data-generating processes

Enough detail that a reader could regenerate the data from the text alone, without opening the code. Morris et al. call these data-generating mechanisms; this skill calls each one a data-generating process (DGP).

State the generating equations and every parameter value. Say which factors vary and at what levels: sample size, effect size, censoring rate, degree of misspecification, correlation structure. Say whether the design is fully factorial, partially factorial, or one-at-a-time from a reference configuration, since that determines which interactions the study can speak to. A one-at-a-time design cannot detect interactions, so say so in the discussion.

If parameters came from a real analysis, say which. If the data are resampled from a dataset instead of drawn from a model, name the source dataset and say how the true value of the estimand was determined. Resampling keeps whatever effect is present in the source, and that effect is rarely zero and rarely known.

Check the code for these problems:

- **The analysis uses knowledge that only the simulator has.** If the DGP is used to construct the analysis in a way no applied analyst could replicate, the results are optimistic and do not transfer. Oracles and semi-oracles are the exception, because they use true values from the DGP on purpose and are reported as such (see Methods).
- **Bayesian and frequentist logic are mixed.** Drawing parameters from a prior in each repetition targets a different quantity from fixing them and drawing data repeatedly. Either design is valid, but say which one the study uses and do not mix them.
- **Generation shortcuts have side effects.** Tricks for inducing correlation, censoring, or missingness often change more than intended. Check the realized DGP against the intended one on one very large dataset.

## E: Estimands

The target quantity, its true value under each DGP, and how that true value was obtained.

Say whether the target is an estimand, a null hypothesis, a model, or a prediction. Estimands need to be nonparametrically defined unless the study is explicitly restricted to a parametric setting (e.g. the goal is to estimate the population-level logistic regression coefficient).

Say how the truth is known: analytically, by construction, or by numerical approximation. An approximated truth has its own error. Make that error small relative to the Monte Carlo error of interest, and report it.

If two methods target different estimands, they cannot be compared on bias. Say so, and do not put them in one table.

## M: Methods

Enough detail to reimplement without the code, plus software and version.

Tuning is part of the method definition: hyperparameters, the data split or the cross-validation scheme and its number of folds, bootstrap draws, convergence tolerance. So is the rule applied when a method fails to converge, because that rule changes what every downstream number means. For learners, report the setup that the `supervised-learning` skill records, including whether the selected settings fell inside their grids, and, for each edge they kept choosing, whether it was a hard limit or a plateau. Describe the data split too, as that skill records it. By default it is three independent draws of the full sample size in place of cross-validated cross-fitting.

Say why each method is in the comparison. A known-flawed method can belong in the comparison if practitioners use it, and the text should give that reason. Note whether each method is available in accessible software, since that decides whether readers can act on the findings.

If the study includes an oracle or semi-oracle (see `sharpening-goals.md`), say which nuisance functions take their true values from the DGP, and which claim or subclaim it helps test. Label each one as an oracle or semi-oracle in every table and figure, so that no reader takes it for a method they could run.

## P: Performance measures

Every measure, with its definition, and the aim it answers. See `performance-measures.md` for the standard estimator-accuracy set and their Monte Carlo standard errors, when the claim is of that kind.

State the number of repetitions and how it was chosen. State the alpha level for any rejection rate and the nominal level for any interval.

---

## Run-time practices that the write-up depends on

Raise these while the simulation is being built, not after:

- Keep the data-generating code and the analysis code in separate files.
- Seed each simulated dataset from its own identity (DGP, sample size, repetition), not once per run, so that any single repetition can be reproduced alone.
- Save **per-repetition** output: estimates, standard errors, interval limits, p-values, convergence flags, timings. Summaries computed at run time cannot be reanalyzed or given Monte Carlo errors afterwards.
- Use separate random streams when running in parallel, so results do not depend on scheduling.
- Publish the code and point to it from the paper.
