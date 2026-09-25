# Sharpening a claim into a simulation goal

A claim is ready when a skeptical reader could look at the planned output and agree it was met or not met. Most first drafts are not there. The way to get there is to interrogate every word that could mean more than one thing, then rewrite.

This worked example is from Alejandro Schuler's "Simulations Done Right". It is worth walking through in full the first time, because the move is easy to describe and easy to skip.

---

## The setup

> You wake up. It's 2006. You look in the mirror and you see you are Mark van der Laan. You've just invented targeted maximum likelihood estimation (TMLE).

What claims should the TMLE paper make, and which can be supported by theory rather than simulation?

## Round 1: candidate claims

**(theory)** TMLE is a general method for constructing efficient estimators of pathwise differentiable estimands.

Estimating equations already do this. So the claim needs to be shown, but showing it is not enough to establish that TMLE is useful. This is the first lesson: a true claim can still fail to be a *reason to care*.

**TMLE is in practice "better" than...**

- plug-in estimators? Augmented inverse probability weighting (AIPW) is already better than those.
- AIPW?

Which forces the question: **better in what sense, and when should it be better and when worse?** That question is the whole job.

**It works in the real world:** computationally tractable, handles mixed data types, can be prespecified. Usually addressable with theory plus a single real-data application, not with simulation.

## Round 2: simulation goals, first pass

1. Across the board, AIPW and TMLE behave similarly in large samples when they have access to the same learners.
2. TMLE is better than plug-in estimators, allowing for good coverage of Wald intervals.
3. There are cases where TMLE is better than AIPW in small samples.

These read like goals. None of them is answerable yet.

## Round 3: the interrogation

Take each goal and list what is unpinned. This is the core move.

**Goal 1.** Across the board, AIPW and TMLE behave similarly in large samples when they have access to the same learners.
- What learners?
- Similar *by what measure*?

**Goal 2.** TMLE is better than plug-in estimators, allowing for good coverage of Wald intervals.
- What learners?
- What should $n$ be here?
- Presumably using influence-function-based intervals. Say so.
- Better by what measure?
- Is there a way to get intervals for the plug-in estimators, as a naive baseline? Without one the comparison is unfair in the wrong direction.

**Goal 3.** There are cases where TMLE is better than AIPW in small samples.
- Can this be backed by theory, so the simulation confirms rather than fishes?
- In which data-generating processes (DGPs)? "There are cases" with no named case is unfalsifiable.

## Round 4: rewritten goals

1. Across the board, AIPW and TMLE behave similarly **in terms of point estimate and standard error (SE) estimate** in large samples when they have access to the same learners.
2. Like AIPW, TMLE **improves the mean squared error of plug-in estimators in moderate sample sizes** and allows for good coverage of **Wald intervals based on influence-function SEs**, even compared to the same SE put around the plug-in estimator.
3. TMLE is better than AIPW in small samples **when the outcome is bounded** (?).

Round 4 answers most of the round 3 questions inside the goal text. Two stay open. "What learners?" is a setting, chosen with the DGPs once the mockup exists, and whether theory backs goal 3 is still unknown. The trailing question mark on goal 3 is honest about the second: it marks a goal that may not survive contact with results, which is exactly the kind of goal worth running.

---

## The questions that do the work

When sharpening any goal, these are usually the ones that matter:

| Question | Why it matters |
|---|---|
| Better or worse **by what measure**? | Without it there is no possible table. |
| At **what sample size**? | Most method comparisons reverse somewhere along $n$. |
| Under **which DGPs**? | "There are cases" names no case and cannot be checked. |
| With **what nuisance estimators or tuning**? | A comparison of methods is often a comparison of learners in disguise. |
| Against **what baseline**? | A method beating a straw man has shown nothing. |
| Is there an **oracle or semi-oracle** (true nuisance functions, in whole or in part) to compare against? | It helps test ablation and mechanism-of-action claims and gives an idea of the best case. Whether one belongs depends on the claim. |
| Is there **theory** that predicts this? | A confirmed prediction is much stronger evidence than a found pattern. |

## Oracles and semi-oracles

An oracle is an estimator given the true values of its nuisance functions, such as the propensity score and the outcome regression. Only a simulation can supply them. A semi-oracle gets the true values of some of them and estimates the rest. Always consider one when choosing comparators, and let the claim or subclaim it would serve decide whether it belongs and in which display.

Goal 3 above says TMLE is better than AIPW in small samples when the outcome is bounded. A mechanism-of-action subclaim would say why. A plausible mechanism is that TMLE stays inside the bounds when some of the inverse probability weights are large. Large weights can come from estimating the propensity score or from poor overlap in the DGP. Semi-oracle versions of TMLE and AIPW, both given the true propensity score and an estimated outcome regression, tell the two apart. If TMLE's edge over AIPW survives with the true propensity score, estimating the score cannot be the whole story. An ablation claim, about how much each nuisance function contributes to the error, gets the same treatment: swap in the true value of one nuisance function at a time.

An oracle also gives an idea of best-case performance, but check the theory before calling it a ceiling. Inverse probability weighting is a case where it is not one: weighting by the true propensity score is, in general, asymptotically less efficient than weighting by a nonparametric estimate of it (Hirano, Imbens & Ridder 2003, *Econometrica*).

## What happens next

The sharpened goal determines the mockup, and the mockup determines the DGPs. Goal 3 above is a good illustration: "when the outcome is bounded" means one of the DGPs now needs a bounded outcome. That requirement did not come from a sense of what a realistic DGP looks like. It came from the claim.

This is also why goal 3's evidence can be a *subset* of goal 2's evidence. Once the DGP set includes a bounded-outcome configuration, supporting goal 3 may be a matter of pointing at the relevant rows of a table that already exists. Noticing that at the mockup stage saves an entire run.
