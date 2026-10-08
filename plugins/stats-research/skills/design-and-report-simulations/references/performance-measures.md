# Performance measures and their Monte Carlo standard errors

Use this file when the claim is about an estimator's accuracy or its intervals. It is a resource, not a checklist. Claims about runtime, model selection, prediction, or qualitative behavior need different measures, and a study whose claim does not concern estimator accuracy needs none of these.

## Contents

- Which measure answers which claim
- Notation
- The table: each measure's estimate and its Monte Carlo SE, from bias to rejection rate
- Choosing $n_{sim}$: worked numbers for bias and coverage
- Failures, non-convergence and missing estimates: what to report

## Which measure answers which claim

The measures below answer specific questions, so pick by question:

| The claim is about... | Measure |
|---|---|
| Finite-sample unbiasedness | Bias |
| Precision, absolute or relative to a competitor | Empirical standard error, relative % increase in precision |
| Overall accuracy, trading bias against variance | Mean squared error (MSE), relative efficiency |
| Whether the method's own variance estimate is accurate | Average model standard error (SE) vs empirical SE, relative % error in model SE |
| Frequentist interval validity | Coverage, with bias-eliminated coverage as a diagnostic |
| Type I error or power | Rejection rate |

Even when the rest of this file does not apply, report a Monte Carlo SE next to each headline number, so that noise is not over-read, and report how many repetitions failed, so that the other numbers can be interpreted.

Formulas follow Morris, White & Crowther (2019), Table 6, cross-checked against the `rsimsum` implementation.

## Notation

| Symbol | Meaning |
|---|---|
| $\theta$ | the estimand, the true population quantity targeted |
| $\hat\theta_i$ | the estimate from repetition $i$ |
| $\bar\theta$ | $\frac{1}{n_{sim}}\sum_i \hat\theta_i$, the mean estimate across repetitions |
| $\widehat{\mathrm{Var}}(\hat\theta_i)$ | the variance estimate reported by the method in repetition $i$ |
| $\hat\theta_{i,\text{low}}, \hat\theta_{i,\text{upp}}$ | confidence interval limits from repetition $i$ |
| $p_i$ | the p-value from repetition $i$ |
| $n_{sim}$ | number of repetitions **used**, after failures are excluded |
| $n_{obs}$ | sample size of each simulated dataset, a parameter of the data-generating process (DGP), not $n_{sim}$ |
| $\mathrm{MCSE}(\cdot)$ | the Monte Carlo standard error of an estimated performance measure, its standard deviation over reruns of the whole simulation at $n_{sim}$ repetitions |

Keep $n_{sim}$ and $n_{obs}$ typographically distinct in the write-up, because readers easily confuse them.

## The table

### Bias

$$\text{Bias} = E[\hat\theta] - \theta \qquad \widehat{\text{Bias}} = \frac{1}{n_{sim}}\sum_{i=1}^{n_{sim}} \hat\theta_i - \theta$$

$$\mathrm{MCSE}(\widehat{\text{Bias}}) = \sqrt{\frac{1}{n_{sim}(n_{sim}-1)}\sum_{i=1}^{n_{sim}}(\hat\theta_i - \bar\theta)^2} \;=\; \frac{\widehat{\text{EmpSE}}}{\sqrt{n_{sim}}}$$

Relative bias, $\widehat{\text{Bias}}/\theta$, is readable across estimands on different scales but is undefined at $\theta = 0$ and unstable near it. Use it only when $\theta$ is comfortably away from zero, and give absolute bias alongside.

### Empirical standard error

$$\text{EmpSE} = \sqrt{\mathrm{Var}(\hat\theta)} \qquad \widehat{\text{EmpSE}} = \sqrt{\frac{1}{n_{sim}-1}\sum_{i=1}^{n_{sim}}(\hat\theta_i - \bar\theta)^2}$$

$$\mathrm{MCSE}(\widehat{\text{EmpSE}}) = \frac{\widehat{\text{EmpSE}}}{\sqrt{2(n_{sim}-1)}}$$

This is the precision of the estimator. It needs no knowledge of $\theta$, so it is computable even when the true value is unknown.

### Relative % increase in precision, method B against reference A

$$100\left[\left(\frac{\widehat{\text{EmpSE}}_A}{\widehat{\text{EmpSE}}_B}\right)^2 - 1\right]$$

$$\mathrm{MCSE} \simeq 200\left(\frac{\widehat{\text{EmpSE}}_A}{\widehat{\text{EmpSE}}_B}\right)^2 \sqrt{\frac{1-\hat\rho_{AB}^2}{n_{sim}-1}}$$

where $\hat\rho_{AB} = \mathrm{Corr}(\hat\theta_A, \hat\theta_B)$ across repetitions. The correlation term is there because both methods saw the same simulated datasets, so the comparison is more precise than two independent estimates would be. Without the term, the MCSE is too large and can hide differences.

Percent increase in precision is asymmetric in the direction of comparison. State which method is the reference.

### Mean squared error

$$\text{MSE} = E[(\hat\theta - \theta)^2] \qquad \widehat{\text{MSE}} = \frac{1}{n_{sim}}\sum_{i=1}^{n_{sim}}(\hat\theta_i - \theta)^2$$

$$\mathrm{MCSE}(\widehat{\text{MSE}}) = \sqrt{\frac{\sum_{i=1}^{n_{sim}}\left[(\hat\theta_i - \theta)^2 - \widehat{\text{MSE}}\right]^2}{n_{sim}(n_{sim}-1)}}$$

MSE combines bias and variance: $\text{MSE} = \text{Bias}^2 + \mathrm{Var}(\hat\theta)$. Report it when the aim is overall accuracy, and report its two components alongside so the reader can see which one drives it. Relative efficiency of B against A is $\widehat{\text{MSE}}_A / \widehat{\text{MSE}}_B$.

### Average model-based standard error

$$\text{ModSE} = \sqrt{E[\widehat{\mathrm{Var}}(\hat\theta)]} \qquad \widehat{\text{ModSE}} = \sqrt{\frac{1}{n_{sim}}\sum_{i=1}^{n_{sim}}\widehat{\mathrm{Var}}(\hat\theta_i)}$$

$$\mathrm{MCSE}(\widehat{\text{ModSE}}) \simeq \sqrt{\frac{\widehat{\mathrm{Var}}\left[\widehat{\mathrm{Var}}(\hat\theta_i)\right]}{4\, n_{sim}\, \widehat{\text{ModSE}}^2}}$$

This is the root of the *mean variance*, not the mean of the SEs. Averaging SEs instead of variances is a common coding error, and it biases the result downward.

### Relative % error in model SE

$$100\left(\frac{\widehat{\text{ModSE}}}{\widehat{\text{EmpSE}}} - 1\right)$$

$$\mathrm{MCSE} \simeq 100\left(\frac{\widehat{\text{ModSE}}}{\widehat{\text{EmpSE}}}\right)\sqrt{\frac{\widehat{\mathrm{Var}}\left[\widehat{\mathrm{Var}}(\hat\theta_i)\right]}{4\, n_{sim}\, \widehat{\text{ModSE}}^4} + \frac{1}{2(n_{sim}-1)}}$$

This tests directly whether the method's own variance estimator is accurate. A negative value means the method understates its uncertainty, which drives undercoverage. A positive value means it overstates it, which drives overcoverage and lost power.

### Coverage

$$\text{Coverage} = \Pr(\hat\theta_{\text{low}} \le \theta \le \hat\theta_{\text{upp}}) \qquad \widehat{\text{Cov}} = \frac{1}{n_{sim}}\sum_{i=1}^{n_{sim}} \mathbf{1}(\hat\theta_{i,\text{low}} \le \theta \le \hat\theta_{i,\text{upp}})$$

$$\mathrm{MCSE}(\widehat{\text{Cov}}) = \sqrt{\frac{\widehat{\text{Cov}}\,(1-\widehat{\text{Cov}})}{n_{sim}}}$$

There are two standards. Neyman's *randomization validity* requires exactly $100(1-\alpha)\%$ of intervals to contain $\theta$, and *confidence validity* requires at least that. Say which one you judge against, because a method with 98% coverage passes the second and fails the first.

Causes of undercoverage, in the order to check them: nonzero bias; $\widehat{\text{ModSE}} < \widehat{\text{EmpSE}}$; a non-normal sampling distribution of $\hat\theta$ when the interval is Wald-type; a variance estimator that is itself too variable. Overcoverage usually means $\widehat{\text{ModSE}} > \widehat{\text{EmpSE}}$.

Undercoverage from bias gets worse as $n_{obs}$ grows, unless the bias shrinks at least as fast as the standard error, which is usually proportional to $1/\sqrt{n_{obs}}$. Intervals narrow around the wrong value. A study run at a single sample size can therefore look much better than the method is.

### Bias-eliminated coverage

$$\widehat{\text{BECov}} = \frac{1}{n_{sim}}\sum_{i=1}^{n_{sim}} \mathbf{1}(\hat\theta_{i,\text{low}} \le \bar\theta \le \hat\theta_{i,\text{upp}}) \qquad \mathrm{MCSE} = \sqrt{\frac{\widehat{\text{BECov}}\,(1-\widehat{\text{BECov}})}{n_{sim}}}$$

Coverage of $\bar\theta$ instead of $\theta$, which removes bias from the calculation. Use it as a diagnostic, not as a performance measure, and say so in the write-up. It shows whether a coverage problem comes from bias or from the width of the intervals. A method with poor coverage and good bias-eliminated coverage still has poor intervals.

### Rejection rate: type I error and power

$$\Pr(p_i \le \alpha) \qquad \widehat{\text{Rej}} = \frac{1}{n_{sim}}\sum_{i=1}^{n_{sim}} \mathbf{1}(p_i \le \alpha) \qquad \mathrm{MCSE} = \sqrt{\frac{\widehat{\text{Rej}}\,(1-\widehat{\text{Rej}})}{n_{sim}}}$$

Under a null DGP this estimates type I error; under a non-null DGP it estimates power. Say which, state $\alpha$, and do not compare power across methods whose type I errors differ.

When p-values are not stored, the Wald equivalent is $\mathbf{1}\left(|\hat\theta_i| \ge z_{\alpha/2}\sqrt{\widehat{\mathrm{Var}}(\hat\theta_i)}\right)$. Say which one was used.

## Choosing $n_{sim}$

Run the calculation backwards from the Monte Carlo SE you can tolerate on the measure that matters most to the aim.

**Bias.** $\mathrm{MCSE}(\text{Bias}) = \sqrt{\mathrm{Var}(\hat\theta)/n_{sim}}$, so

$$n_{sim} = \frac{\mathrm{Var}(\hat\theta)}{\mathrm{MCSE}_{\text{req}}^2}$$

With an anticipated $\mathrm{SD}(\hat\theta) \le 0.2$ and a required MCSE below 0.005: $n_{sim} = 0.04/0.005^2 = 1600$.

**Coverage**, with coverage on the percentage scale:

$$n_{sim} = \frac{E(\text{Cov})\,(100 - E(\text{Cov}))}{\mathrm{MCSE}_{\text{req}}^2}$$

Anticipated 95% coverage with a required MCSE of 0.5%: $n_{sim} = 95 \times 5 / 0.5^2 = 1900$. At 1.5%: 211. The worst case over all possible coverages is 50%, which at 0.5% requires $50 \times 50/0.5^2 = 10{,}000$.

The anticipated values are guesses, so check the realized MCSEs after the run. In a simulation, more repetitions are usually the cheapest way to get more precision.

## Failures, non-convergence and missing estimates

Report the number of missing $\hat\theta_i$ and missing $\widehat{\mathrm{Var}}(\hat\theta_i)$ for each method and cell, because it changes how to read every other measure.

Estimates go missing because of features of the simulated dataset, such as separation in a logistic model or a boundary variance component, so the missingness is informative and the complete cases are a biased subpopulation. In the write-up:

- Report attempted and completed repetition counts per cell, per method.
- When the missing fraction is not small, label every downstream measure as conditional on convergence, and say that a comparison between methods that lost different numbers of repetitions is not like for like.
- Consider reporting performance for a realistic fallback procedure. In practice, an analyst facing non-convergence switches methods instead of reporting nothing, so the combined procedure is often the one to evaluate.
- Store the random number generator state per repetition during the run, so failing repetitions can be reproduced and diagnosed. Use `try()` in R or `capture` in Stata so one failure does not end the run.
