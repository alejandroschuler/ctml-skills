# Designing data-generating processes (DGPs) and settings

Being able to reason about a simulation and iterate on it matters more than making it realistic. If you cannot predict roughly what should happen, you cannot tell a bug from a finding, and most of your time goes to that confusion. Add realism only after you can reason about the DGP. Often it is not needed at all.

Every parameter value and every functional form in a DGP needs a reason. It shows a specific phenomenon, it prevents a specific problem, or it is an unobjectionable default.

## Sensible defaults

For the common causal-inference setup, these choices keep everything interpretable:

- **Covariates:** $X \sim \mathsf{Unif}([-1,1]^d)$ unless something requires otherwise. With a bounded domain, it is easy to reason about the range of any function you build on top.
- **Treatment:** $A \sim \mathsf{Bern}(\mathrm{expit}(\rho(X)))$. Keep $\rho$ simple and sparse. Unless empirical positivity violations are the point of the study, aim for $\rho \in [-3, 3]$, which keeps propensities away from the boundary.
- **Outcome:** $Y \sim \mu(A, X) + \mathsf{N}(0, \sigma^2)$, with noise standard deviation $\sigma$. Keep $\mu$ simple and sparse.

You can reason completely about a DGP with two covariates and a hand-written mean function, so a surprising result takes minutes to diagnose instead of days.

## Diagnostics to run before trusting a DGP

Compute these on a single very large draw. They are cheap, and they catch many DGP mistakes:

- **Overlap.** The distribution of $A \mid X$, and how close propensities get to 0 and 1. An accidental positivity violation is a common way for a DGP to go wrong without anyone noticing.
- **Variance explained.** The fraction of outcome variance explained by the conditional mean $\mu$, that is $\mathrm{Var}(\mu)/\mathrm{Var}(Y)$, or the population $R^2$. With the default additive noise of standard deviation $\sigma$ it equals $\mathrm{Var}(\mu)/(\mathrm{Var}(\mu)+\sigma^2)$, a monotone transform of the signal-to-noise ratio $\mathrm{Var}(\mu)/\sigma^2$ that always lies between 0 and 1. It sets how hard the estimation problem is. A DGP that is trivially easy or hopelessly noisy will not discriminate between methods.
- **Nonlinearity.** The fraction of $\mathrm{Var}(\mu)$ captured by the best linear approximation to $\mu$. It says how much a flexible learner can gain over a linear model, which is often what a comparison is about.
- **The true estimand value**, computed by brute force on a large draw if no closed form exists.

You can set targets for these when you build a DGP. For example, the DGP in `example-study.md` was built so that the covariates explain about half of the outcome variance and a linear model about 0.3 of it. The linear figure is in the range expected for a trial, and the gap leaves room for a nonlinear prognostic model to help.

Report these with the DGP description. They show the reader the range the DGPs cover more clearly than the generating equations do.

These four fit the standard causal setup with a binary treatment. Other setups call for their own, such as the censoring rate for a survival outcome or the intraclass correlation for clustered data. Decide what they are while you design the DGPs, so that you can build each DGP to land at sensible values of them.

## Choosing the set of DGPs

The set of DGPs has to cover the conditions in the claims, so derive it from the claims.

A claim of the form "works well when X and not when Y" needs at least one DGP on each side. Make each one an **archetype of its extreme**, not a mild example. Edge cases are what sharpen a claim, and a sharper claim makes a more useful paper.

Three DGPs of increasing complexity is a common default: one simple enough that everything should work, one moderate, and one where the flexible methods should do better than the simple ones. Keep the structure easy to follow, for example a binary treatment with two covariates, unless the claim needs otherwise.

If a DGP has no claim attached, either there is a claim you have not stated or you do not need that run.

It often helps to arrange the scenarios as factors and give each level the subclaim it tests. The study in `example-study.md` crosses a trial factor (null, additive or heterogeneous effect) with a historical-shift factor (none, or a small or large shift in an observed or an unobserved covariate), and gives a reason for each trial level and for the shift factor.

Within a factor, change one thing at a time where you can. In that study the heterogeneous scenario keeps the rate ratio of the additive one, so that the two are as similar as possible apart from the heterogeneity.

When many real-world failure modes act on the method through the same channel, it is often enough to simulate the channel and its worst case, instead of each mode. In that study, a misspecified prognostic model, covariates defined differently in the two datasets, a covariate missing from the historical data, and a population shift all reduce how well the prognostic score predicts in the trial. The study simulates a few covariate shifts, and adds as the worst case a score with no predictive power, made by shuffling the in-trial scores.

## Sample sizes

Start with three or four values across the range the claim is about, and add more once you see where the interesting behavior is. Log spacing, for example 100 / 500 / 2000 / 10000, usually shows convergence better than linear spacing.

Many method comparisons reverse somewhere along $n$. If a claim names no range of sample sizes, check whether it hides such a reversal.

## Number of repetitions

Everything above stays provisional until the pilot in `piloting.md` shows that the DGP can produce the mockup. The diagnostics catch a DGP that is not what you think it is. The pilot catches a DGP that is what you think it is but still cannot resolve the contrast you built it for. Both problems are cheap to fix before the full run and expensive to fix after it.

Increase the number of repetitions in steps:

- **2 repetitions** to find out whether the code runs at all.
- **~100 to 200 repetitions** for the pilot: check that the output matches the mockup, then run the resolvability check in `piloting.md` on every contrast the mockup promises.
- **The full run**, only after the pilot passes, at the `n_sim` that check returned.

Every step runs the same code. Only the number of repetitions changes.

For claims about bias or coverage, `performance-measures.md` shows how to turn a tolerable Monte Carlo error into a required number of repetitions. For claims about gross qualitative behavior, a few hundred repetitions are often enough.

## Choosing estimands

Prefer estimands that are easy to compute and that work with the same DGP, so that one run serves several purposes. A second estimand helps support a claim of generality, but use only one for the first rounds of output, and put the second in the appendix.
