# Example study: aims, subclaims and scenarios

Section 5 of Højbjerre-Frandsen, van der Laan & Schuler (2025), "Powering RCTs for marginal effects with GLMs using prognostic score adjustment", arXiv:2503.22284, is a simulation study whose aims have the right scope. Each aim splits into subclaims that the DGP scenarios and comparators test, the scenarios have stated reasons, and the results follow the aims.

## Contents

- The method and what the theory predicts
- Aims (Stage 2)
- Subclaims and what tests each (Stages 2 and 4)
- DGP scenarios (Stage 4)
- Comparators (Stage 2)
- Displays and the results section (Stage 3 and the write-up)
- What could be sharper

## The method and what the theory predicts

A randomized trial with a count outcome estimates the marginal rate ratio. The proposed estimator fits a prognostic model on historical control data, predicts a prognostic score for each trial participant, and adds the score as a covariate, next to the baseline covariates, in a GLM plug-in estimator. The paper also gives a formula for the sample size that reaches a target power.

The theory makes three predictions, and the simulation tests each one in finite samples:

- The estimator is locally efficient when the treatment effect is additive on the link scale and the estimated score converges to the control-arm conditional mean in the trial. A score fit on a shifted historical population converges to a different function. So the gain may be largest with an additive effect and matched populations, and should shrink under a shift.
- In a randomized trial the estimator is consistent and its influence-function SE is asymptotically valid whatever prognostic model is used, so coverage and type I error should stay nominal even when the score is useless.
- The sample size formula takes the score's predictive accuracy from the historical data, so it should reach the target power when the two populations match, and can fail when they do not.

## Aims

The paper states three aims as questions:

1. How much does prognostic adjustment reduce standard errors, relative to covariate adjustment or no adjustment?
2. Does it keep nominal coverage, which checks both its bias and its SE estimate?
3. Does the sample size formula reach the target power when the historical and trial populations match, and how does it fail when they do not?

Each aim is a question that a trial statistician asks before using the method: will it make my trial smaller, is it safe, and can I plan the trial with it? Each aim has its own main figure, which covers all the scenarios. `ademp.md` gives the three aims as hypotheses.

## Subclaims and what tests each

The paper does not list subclaims. This table reconstructs them from the reasons in its Section 5.1 and from its results.

| Aim | Subclaim (expected result) | Tested by |
|---|---|---|
| 1 | With no shift and an additive effect, the gain is largest and close to that of the true prognostic score, as local efficiency predicts | No-shift column, additive row, oracle comparator |
| 1 | With a heterogeneous effect, the gain is smaller | Heterogeneous row |
| 1 | The gain shrinks as the historical population moves away from the trial population, more for large shifts than for small ones, and for unobserved as well as observed shifts | The four shift columns |
| 1 | With a score that carries no information, the SE is about that of covariate adjustment, and rarely much larger | Noise comparator |
| 1 | Adjusting for the score alone, without the covariates, can be much worse than covariate adjustment when the score is poor, down to the unadjusted SE | Score-only comparator in the shift columns, against the unadjusted one |
| 2 | Coverage is nominal for every estimator, sample size and scenario, including the noise score | Every cell of the coverage figure |
| 2 | Type I error is nominal for every estimator | Null row |
| 3 | The formula reaches 80% power when the populations match | No-shift column |
| 3 | The formula underestimates the sample size under a shift, more for a large shift | Shift columns |

Covariate adjustment is the reference for every aim 1 row.

## DGP scenarios

One scaffold generates both the trial data and the historical data. Two factors vary, crossed in a 3 × 5 design. The paper gives a reason for each trial scenario, and one reason for the shift factor as a whole: larger differences between the populations should reduce the efficiency gain and make the sample size unreliable. The reasons for the separate shift levels below are inferred from its discussion.

| Factor | Level | Reason |
|---|---|---|
| Trial scenario | Null effect, rate ratio 1 | Measures type I error |
| | Effect additive on the log scale, rate ratio 1.22 | The condition under which theory predicts larger efficiency gains and a more conservative sample size |
| | Heterogeneous effect, rate ratio 1.22 | Breaks that condition, to challenge the method. It keeps the rate ratio of the additive scenario, so that the two are as similar as possible apart from the heterogeneity |
| Historical shift | None | The populations match, as the sample size formula assumes |
| | Small or large shift in the mean of an observed covariate | A shift that an analyst can see by comparing covariate distributions |
| | Small or large shift in the mean of an unobserved covariate | Changes how the outcome depends on the observed covariates, which a comparison of covariate distributions does not show |

Trial sample size, from 100 to 400, is a third factor. There are 1000 repetitions for each combination.

Other choices in the DGP also have stated reasons:

- The conditional mean is mostly hinge functions, plus a square term and an interaction. Hinge functions keep the mean positive, and one offset makes a term nearly linear or clearly nonlinear.
- The covariates explain about half of the outcome variance, and a linear model explains about 0.3 of it, a figure that comes from a regression on one very large draw. The linear figure is in the range expected for a trial, and the gap leaves room for a nonlinear prognostic model to help.
- Each historical dataset has 2,500 records, to reflect a setting with about ten times more historical data than trial data.
- Under a shift, the historical population has more explainable variance than the trial population, so the sample size formula underestimates. The paper says that it chose this direction to show the underestimate.

The study does not simulate each way that a prognostic score can go wrong in practice: a misspecified model, covariates defined differently in the two datasets, a covariate missing from the historical data, or bad imputation. All of these reduce how well the score predicts in the trial. So the study simulates a few covariate shifts, and adds the worst case, a score with no predictive power (the noise comparator below).

## Comparators

The paper lists the estimators in one table with a motivation column. All six are the same GLM plug-in estimator with different adjustment sets:

| Adjustment set | Motivation |
|---|---|
| None | Simplest baseline |
| Covariates | Strong baseline that is commonly used |
| Noise + covariates | Worst case. The in-trial scores, shuffled across participants, keep their distribution and lose all predictive power |
| True prognostic score + covariates | Oracle and best case. The true control-arm conditional mean in the trial |
| Estimated score only | A variant for an analyst who trusts the score |
| Estimated score + covariates | The proposal. The covariates protect against a poor score |

The oracle and the noise score give the best and the worst case to compare the proposal with. The method settings have stated reasons too. The working model is a negative binomial GLM with its dispersion fixed at 3. The true outcome is Poisson, so the model is mildly misspecified on purpose. The pilot showed that the dispersion value made little difference. The prognostic model is one MARS fit, not an ensemble, so that the study runs on a laptop. MARS suits a conditional mean made mostly of hinge functions, although the square term leaves it slightly misspecified.

## Displays and the results section

There is one main figure for each aim. Each figure has the trial scenarios in rows and the historical shifts in columns, so each subclaim is a region of a figure that the text can point to.

- Figure 1, aim 1: the estimated SE of each estimator divided by that of covariate adjustment, per repetition, as box plots at n = 250. The shift columns show only the estimators that use historical data, because the others do not change with the shift.
- Figure 2, aim 2: the coverage of each estimator against trial sample size.
- Figure 3, aims 2 and 3: the rejection rate against trial sample size, with a vertical line at each method's average estimated sample size. The null row gives the type I error. The caption says that the observed-shift columns are left out because they show the same pattern.

The results section has one subsection for each aim, in the order efficiency, coverage, sample size. Each subsection opens with its question and how it was measured, shows the figure, and then goes through the subclaims in turn. In the efficiency subsection the order is the gain with no shift, the oracle, the noise score, the shifts, the score-only estimator, and heterogeneity. The coverage subsection opens with its reason: an estimator that underestimates its own SE would look efficient in Figure 1.

Results that went the other way are in the same subsections as the others. The sample size formula is slightly anti-conservative for the unadjusted and covariate-adjusted estimators. The paper suggests a cause, notes a result that argues against it, and says that the rest is not clear to the authors. Coverage drops slightly for the estimators that adjust for all the covariates when the SEs are not cross-fitted. That result is in an appendix, and the paper turns it into a recommendation to cross-fit.

## What could be sharper

- The aims are stated as questions ("to what extent"), and the expected directions are spread through Section 5.1, next to the scenarios. The hypothesis form in `ademp.md` puts the direction in the aim, so the reader knows before the results which outcomes would confirm the theory and which would contradict it.
- The figure captions say what each figure contains but not which aim it serves. A caption such as "Prognostic adjustment with covariates rarely increases the SE relative to covariate adjustment, even with a useless score (aim 1)" would meet the caption rule in `writing-the-writeup.md`.
