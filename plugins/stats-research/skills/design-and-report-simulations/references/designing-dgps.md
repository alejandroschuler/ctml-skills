# Designing data-generating processes (DGPs) and settings

The governing principle: **being able to reason about a simulation and iterate on it matters more than making it realistic.** If you cannot predict roughly what should happen, you cannot tell a bug from a finding, and that confusion will eat most of your time. Realism is worth buying only after the reasoning is in place, and often it is not worth buying at all.

Every parameter value and every functional form in a DGP needs a reason. It shows a specific phenomenon, it prevents a specific problem, or it is an unobjectionable default.

## Sensible defaults

For the common causal-inference setup, these choices keep everything interpretable:

- **Covariates:** $X \sim \mathsf{Unif}([-1,1]^d)$ unless something requires otherwise. A bounded domain makes it easy to reason about the range of any function you build on top.
- **Treatment:** $A \sim \mathsf{Bern}(\mathrm{expit}(\rho(X)))$. Keep $\rho$ simple and sparse. Unless empirical positivity violations are the point of the study, aim for $\rho \in [-3, 3]$, which keeps propensities away from the boundary.
- **Outcome:** $Y \sim \mu(A, X) + \mathsf{N}(0, \sigma^2)$, with noise standard deviation $\sigma$. Keep $\mu$ simple and sparse.

Simple and sparse is not a limitation here. A DGP with two covariates and a hand-written mean function is one you can reason about completely, which is what lets you diagnose a surprising result in minutes instead of days.

## Diagnostics to run before trusting a DGP

Compute these on a single very large draw. They are cheap and they catch most DGP mistakes:

- **Overlap.** The distribution of $A \mid X$, and how close propensities get to 0 and 1. Accidental positivity violations are the most common way a DGP misbehaves without anyone noticing.
- **Variance explained.** The fraction of outcome variance explained by the conditional mean $\mu$, that is $\mathrm{Var}(\mu)/\mathrm{Var}(Y)$, or the population $R^2$. With the default additive noise of standard deviation $\sigma$ it equals $\mathrm{Var}(\mu)/(\mathrm{Var}(\mu)+\sigma^2)$, a monotone transform of the signal-to-noise ratio $\mathrm{Var}(\mu)/\sigma^2$ that always lies between 0 and 1. This governs how hard the estimation problem is, and a DGP that is trivially easy or hopelessly noisy will not discriminate between methods.
- **Nonlinearity.** The fraction of $\mathrm{Var}(\mu)$ captured by the best linear approximation to $\mu$. This says how much a flexible learner can actually gain over a linear model, which is often the thing a comparison is really about.
- **The true estimand value**, computed by brute force on a large draw if no closed form exists.

Report these alongside the DGP description. They tell the reader what the DGPs span far better than the generating equations alone.

These four fit the standard causal setup with a binary treatment. Other setups call for their own, such as the censoring rate for a survival outcome or the intraclass correlation for clustered data. Decide what they are while designing the DGPs, so that each DGP can be built to land at sensible values of them.

## Choosing the set of DGPs

The set exists to span the conditions in the claims, so derive it from the claims rather than from a sense of what looks reasonable.

A claim of the form "works well when X and not when Y" needs at least one DGP on each side, and the interesting design work is making each one an **archetype of its extreme** rather than a mild example. Edge cases are what sharpen a claim, and a sharpened claim is the more useful paper.

Three DGPs of increasing complexity is a common and workable default: one simple enough that everything should work, one moderate, one where the flexible methods should earn their keep. Keep the structure intelligible, for example a binary treatment with two covariates, unless the claim needs otherwise.

Watch for a DGP with no claim attached. It is either a claim you have not articulated or a run you do not need.

## Sample sizes

Start with three or four values spanning the range the claim is about, and add more once you see where the interesting behaviour is. Log spacing, for example 100 / 500 / 2000 / 10000, usually shows convergence behaviour better than linear spacing.

Most method comparisons reverse somewhere along $n$, so a claim that names no sample size range is usually hiding that reversal.

## Number of repetitions

Everything above stays provisional until the pilot in `piloting.md` shows the DGP can actually produce the mockup. The diagnostics catch a DGP that is not what you think it is. The pilot catches a DGP that is exactly what you think it is and still cannot resolve the contrast you built it for. Both failures are cheap here and expensive after the full run.

Ramp up rather than committing early:

- **2 repetitions** to find out whether the code runs at all.
- **~100 to 200 repetitions** for the pilot: check the output matches the mockup, then run the resolvability check in `piloting.md` on every contrast the mockup promises.
- **Scale up** only once the pilot clears, to the `n_sim` that check returned.

Every step runs the same code, and only the number of repetitions changes.

For claims about bias or coverage, `performance-measures.md` gives the calculation that turns a tolerable Monte Carlo error into a required number of repetitions. For claims about gross qualitative behaviour, a few hundred repetitions often settles the question and more is wasted compute.

## Choosing estimands

Prefer estimands that are computationally easy and that work with the same DGP, so one run serves several purposes. Having a second estimand helps support a generality claim, but stick to one for the first rounds of output and send the second to the appendix.
