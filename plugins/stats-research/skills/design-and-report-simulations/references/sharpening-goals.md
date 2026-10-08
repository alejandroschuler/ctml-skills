# Sharpening a claim into a simulation goal

A claim is ready when a skeptical reader could look at the planned output and agree it was met or not met. Most first drafts are not there yet. To get there, question every word that could mean more than one thing, then rewrite.

This worked example is from Alejandro Schuler's "Simulations Done Right".

---

## The setup

> You wake up. It's 2006. You look in the mirror and you see you are Mark van der Laan. You've just invented targeted maximum likelihood estimation (TMLE).

What claims should the TMLE paper make, and which can be supported by theory rather than simulation?

## Round 1: candidate claims

**(theory)** TMLE is a general method for constructing efficient estimators of pathwise differentiable estimands.

Estimating equations already do this. The claim has to be shown, but showing it does not establish that TMLE is useful. A true claim can still give a reader no reason to care.

**TMLE is in practice "better" than...**

- plug-in estimators? Augmented inverse probability weighting (AIPW) is already better than those.
- AIPW?

This raises the main question: better in what sense, and when should it be better and when worse?

**It works in the real world:** computationally tractable, handles mixed data types, can be prespecified. Theory plus a single real-data application usually covers this, without a simulation.

## Round 2: simulation goals, first pass

1. Across the board, AIPW and TMLE behave similarly in large samples when they have access to the same learners.
2. TMLE is better than plug-in estimators, allowing for good coverage of Wald intervals.
3. There are cases where TMLE is better than AIPW in small samples.

No simulation can answer these yet.

## Round 3: questioning each goal

For each goal, list what is unpinned.

**Goal 1.** Across the board, AIPW and TMLE behave similarly in large samples when they have access to the same learners.
- What learners?
- Similar *by what measure*?

**Goal 2.** TMLE is better than plug-in estimators, allowing for good coverage of Wald intervals.
- What learners?
- What should $n$ be here?
- Presumably using influence-function-based intervals. Say so.
- Better by what measure?
- Is there a way to get intervals for the plug-in estimators, as a naive baseline? Without one, the comparison favors TMLE unfairly.

**Goal 3.** There are cases where TMLE is better than AIPW in small samples.
- Can theory back this, so that the simulation tests a prediction instead of searching for a pattern?
- In which data-generating processes (DGPs)? "There are cases" names no case, so nobody can check it.

## Round 4: rewritten goals

1. Across the board, AIPW and TMLE behave similarly **in terms of point estimate and standard error (SE) estimate** in large samples when they have access to the same learners.
2. Like AIPW, TMLE **improves the mean squared error of plug-in estimators in moderate sample sizes** and allows for good coverage of **Wald intervals based on influence-function SEs**, even compared to the same SE put around the plug-in estimator.
3. TMLE is better than AIPW in small samples **when the outcome is bounded** (?).

The rewritten goals answer most of the Round 3 questions in their own text. Two stay open. "What learners?" is a setting, chosen with the DGPs once the mockup exists. Whether theory backs goal 3 is still unknown, and the question mark on goal 3 shows that. A goal that could turn out false is a good one to test.

---

## Questions to ask of any goal

| Question | Why it matters |
|---|---|
| Better or worse **by what measure**? | Without a measure, you cannot draw the table. |
| At **what sample size**? | Many method comparisons reverse somewhere along $n$. |
| Under **which DGPs**? | "There are cases" names no case and cannot be checked. |
| With **what nuisance estimators or tuning**? | A comparison of methods is often a comparison of learners. |
| Against **what baseline**? | Beating a weak baseline shows little. |
| Is there an **oracle or semi-oracle** (true nuisance functions, in whole or in part) to compare against? | It helps test ablation and mechanism-of-action claims and shows roughly what the best case looks like. Whether one belongs depends on the claim. |
| Is there **theory** that predicts this? | A confirmed prediction is stronger evidence than a pattern found after the fact. |

## Oracles and semi-oracles

An oracle is an estimator given the true values of its nuisance functions, such as the propensity score and the outcome regression. Only a simulation can supply them. A semi-oracle gets the true values of some of them and estimates the rest. Always consider one when you choose comparators, and let the claim or subclaim it would serve decide whether it belongs and in which display.

Goal 3 above says TMLE is better than AIPW in small samples when the outcome is bounded. A mechanism-of-action subclaim would say why. One possible mechanism is that TMLE stays inside the bounds when some of the inverse probability weights are large. Large weights can come from estimating the propensity score or from poor overlap in the DGP. Semi-oracle versions of TMLE and AIPW, both given the true propensity score and an estimated outcome regression, tell the two apart. If TMLE's advantage over AIPW remains with the true propensity score, estimating the score cannot be the whole explanation. An ablation claim, about how much each nuisance function contributes to the error, works the same way: swap in the true value of one nuisance function at a time.

An oracle also shows roughly what the best case looks like, but check the theory before you call it a ceiling. Inverse probability weighting is a case where it is not one: weighting by the true propensity score is, in general, asymptotically less efficient than weighting by a nonparametric estimate of it (Hirano, Imbens & Ridder 2003, *Econometrica*).

## What happens next

The sharpened goal determines the mockup, and the mockup determines the DGPs. In goal 3, "when the outcome is bounded" means that one of the DGPs needs a bounded outcome. That requirement comes from the claim, not from an idea of what a realistic DGP looks like.

The evidence for one goal can be a subset of the evidence for another. Once the DGP set includes a bounded-outcome configuration, the evidence for goal 3 may be some rows of the table built for goal 2. If you see this at the mockup stage, you do not need a separate run for goal 3.
