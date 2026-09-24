# ADEMP: describing the study before the results

From Morris, White & Crowther (2019), "Using simulation studies to evaluate statistical methods", *Statistics in Medicine* 38(11):2074-2102.

ADEMP is a structure for the part of the write-up that comes before any numbers: Aims, Data-generating mechanisms, Estimands, Methods, Performance measures. It is the "tell 'em what you're going to tell 'em" slice of the sandwich.

Aims is the important element. The other four exist to serve it, and a reader judges them by whether they make the aims answerable. It is fine to run through ADEMP once for the whole study, or once per claim when the claims need different setups.

Derive each element from the simulation code rather than from what anyone says the code does, and raise any mismatch between the two.

---

## A: Aims

The claims the simulation is meant to support, stated specifically enough to be wrong.

**Weak:** "We conduct a simulation study to evaluate the proposed estimator."
**Strong:** "We evaluate the finite-sample bias and 95% interval coverage of the proposed estimator, relative to the standard approach, when the outcome model is misspecified and the propensity model is correct."

Properties a simulation can target include consistency, finite-sample unbiasedness, whether the method's own variance estimate recovers the true sampling variance, interval coverage, efficiency, and how each of these degrades under specific misspecification. Non-estimation aims exist too: testing behaviour, model selection, prediction accuracy, runtime.

Every performance measure below should trace back to an aim here. A measure with no aim is padding; an aim with no measure is unanswered.

## D: Data-generating mechanisms

Enough detail that a reader could regenerate the data from the text alone, without opening the code.

State the generating equations and every parameter value. Say which factors vary and at what levels: sample size, effect size, censoring rate, degree of misspecification, correlation structure. Say whether the design is fully factorial, partially factorial, or one-at-a-time from a reference configuration, since that determines which interactions the study can speak to. A one-at-a-time design cannot detect interactions, and saying so in the discussion is better than letting a reader assume otherwise.

If parameters came from a real analysis, say which. If the data are resampled rather than drawn from a model, say what the source dataset is and how the true value of the estimand was determined, because resampling preserves whatever effect is present in the source and that effect is rarely zero and rarely known.

Pitfalls worth checking for in the code:

- **Giving the analyst knowledge only the simulator has.** If the DGP is used to construct the analysis in a way no applied analyst could replicate, the results are optimistic and do not transfer.
- **Mixing Bayesian and frequentist logic.** Drawing parameters from a prior each repetition targets a different quantity from fixing them and drawing data repeatedly. Both are legitimate; conflating them is not.
- **Side effects of generation shortcuts.** Tricks for inducing correlation, censoring, or missingness often change more than intended. Check the realized DGP against the intended one on one very large dataset.

## E: Estimands

The target quantity, its true value under each DGP, and how that true value was obtained.

Say whether the target is an estimand, a null hypothesis, a model, or a prediction. Estimands need to be nonparametrically defined unless the study is explicitly restricted to a parametric setting (e.g. the goal is to estimate the population-level logistic regression coefficient).

Say how the truth is known: analytically, by construction, or by numerical approximation. An approximated truth carries its own error, which should be made small relative to the Monte Carlo error of interest and reported.

If two methods target different estimands, they cannot be compared on bias. Say so rather than tabulating them together.

## M: Methods

Enough detail to reimplement without the code, plus software and version.

Tuning is part of the method definition: hyperparameters, cross-validation scheme, number of folds, bootstrap draws, convergence tolerance. For learners, report the setup that the `supervised-learning` skill records, including whether the selected settings fell inside their grids. So is the rule applied when a method fails to converge, which is a design decision rather than an implementation detail because it changes what every downstream number means.

Say why each method is in the comparison. Methods should be plausible candidates or in genuine practical use; including a known-flawed method is defensible when practitioners use it, and the reason belongs in the text. Note whether each is available in accessible software, since that governs whether readers can act on the findings.

## P: Performance measures

Every measure, with its definition, and why it answers an aim. See `performance-measures.md` for the standard estimator-accuracy set and their Monte Carlo standard errors, when the claim is of that kind.

State the number of repetitions and where that number came from. State the alpha level for any rejection rate and the nominal level for any interval.

---

## Practices at run time that the write-up depends on

These are design-phase decisions, so raise them when a simulation is being built rather than after:

- Keep the data-generating code and the analysis code in separate files.
- Seed each simulated dataset from its own identity (DGP, sample size, repetition) rather than once per run, so any single repetition can be reproduced in isolation.
- Save **per-repetition** output: estimates, standard errors, interval limits, p-values, convergence flags, timings. Summaries computed at run time cannot be reanalyzed or given Monte Carlo errors afterwards.
- Use separate random streams when running in parallel, so results do not depend on scheduling.
- Publish the code and point to it from the paper.
