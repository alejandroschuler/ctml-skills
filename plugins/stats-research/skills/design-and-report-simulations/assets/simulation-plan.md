# Simulation plan

Fill this out **before writing simulation code**. It is the backwards-design artifact: the claims determine the mockups, and the mockups determine the DGPs (data-generating processes). Work top to bottom, and expect to revise upward as lower sections expose problems.

---

## 1. Claims

The claims the paper makes. Not what the simulation computes.

| # | Claim | Evidence type | Priority |
|---|---|---|---|
| 1 | | theory / simulation / application | |
| 2 | | | |
| 3 | | | |

Check each: does it have practical utility? Does it build insight? Is it honest and well-scoped, with a stated boundary condition? Would the audience care enough to change what they do?

Simulation-supported claims usually read: *[method] works [well] when [condition] and not when [other condition].*

---

## 2. Simulation goals

For each claim assigned to simulation, sharpen until a skeptic could agree it was met or not met.

### Goal 1

**First pass:** [the claim, roughly]

**Unpinned:**
- By what measure?
- At what sample size?
- Under which DGPs?
- With what nuisance estimators or tuning?
- Against what baseline?
- Would an oracle or semi-oracle (true values for all or some of the nuisance functions) help test this goal, and in which display?
- Does theory predict this?

**Sharpened:** [rewrite with every question above answered inside the sentence]

*(Repeat per goal.)*

---

## 3. Mockups

For each goal, draw the display with empty cells and write the caption now.

### Evidence for Goal 1

**Caption (written first):** [what this shows and which claim it serves]

**Display:** [sketch the table with empty cells, or describe the figure: what is on each axis, what is faceted, what is a color]

**Checks:**
- If the numbers land where expected, does this convince a skeptic?
- If they land the other way, will it be visible?
- Which DGPs does this require? → feeds section 4
- Which settings (sample size, estimand, learners) does this require? → feeds section 4
- Does this display overlap with another goal's? Merge if so.

*(Repeat per goal.)*

**Main text vs appendix:** [what gets cut to the appendix, usually the second estimand]

---

## 4. DGPs and settings

Derived from section 3, not chosen independently.

Notation as in `references/designing-dgps.md`: covariates $X$, a binary treatment $A$ with log-odds $\rho(X)$ and propensity $\pi(X) = \mathrm{expit}(\rho(X))$, and an outcome $Y$ with conditional mean $\mu(A,X)$ and noise SD $\sigma$.

| DGP | Purpose / which claim | $\rho(X)$ | $\mu(A,X)$ | $\sigma$ | Notes |
|---|---|---|---|---|---|
| simple | | | | | |
| moderate | | | | | |
| complex | | | | | |

Diagnostics to compute on a large draw, and report:

| DGP | True estimand | Overlap (range of $\pi$) | Variance explained $\mathrm{Var}(\mu)/\mathrm{Var}(Y)$ | Linear-approximable share of $\mathrm{Var}(\mu)$ |
|---|---|---|---|---|
| | | | | |

- **Sample sizes:** [values, and why this range]
- **Estimand(s):** [primary, and what goes to the appendix]
- **Methods / estimators:** [list, including the baseline and any oracle or semi-oracle, with the claim each oracle serves]
- **Learners:** [which, and why these; set up with the `supervised-learning` skill]
- **Repetitions:** [2 → 100 to 200 → final count, and what determined the final count]

Does every DGP trace to a claim? A DGP with no claim is either an unarticulated claim or a run you do not need.

---

## 5. Build

One codebase serves the pilot, the full run, and every display. Plan what it runs and what it stores before writing it.

- **Grid:** [factors and levels: DGPs, sample sizes $n_{obs}$, repetitions, learners (or libraries built from them), estimators]
- **Shared computation:** [which displays read which stored outputs, e.g. "Table 1, the root mean squared error of each library's nuisance predictions, and Table 2, the coverage of targeted maximum likelihood estimation (TMLE) and augmented inverse probability weighting (AIPW), both read the same library predictions"]
- **Cached:** [which steps, at what grain, estimated size; cache directory already in `.gitignore`]
- **Seeds:** [each dataset seeded from its DGP, sample size and repetition]
- **Parallelization:** [plan and workers; thread settings from the `supervised-learning` skill]

Can any single DGP, estimator, or learner library be rerun alone, and return the same rows as the full run?

---

## 6. Pilot: can this design show what section 3 promises?

Run before the full run and before freezing anything above, with the code from section 5. 2 reps that it runs, one large draw for the diagnostics in section 4, then 100 to 200 reps for the check below. Use `assets/pilot_check.R` or `.py`.

Each contrast reduces to a per-repetition difference $d$ between the two methods (defined per measure in `references/piloting.md`). The pilot gap is the mean of $d$, and the pilot $|z|$ is that gap divided by its Monte Carlo standard error (SE). n_sim safe is the number of repetitions that shows the gap at the target number of Monte Carlo SEs, sized on a lower bound for the gap so that a lucky pilot does not undersize the run.

| Mockup cell | Measure | Contrast | Pilot gap | sd(d) | Pilot \|z\| | n_sim safe | Verdict |
|---|---|---|---|---|---|---|---|
| Table 2, complex | coverage | TMLE vs AIPW | | | | | |
| | | | | | | | |

A pilot \|z\| below 2 means the pilot cannot size the run; enlarge it or treat the contrast as unresolvable. Size on `n_sim_safe`, not the optimistic number.

- **Contrasts that failed, and what changed upstream:** [which DGP, mockup, or n_obs was revised, and why]
- **Final n_sim:** [value, and which contrast bound it]
- **Was any DGP tuned to make a mechanism visible?** [if yes, this must be disclosed in the paper]
