# Sharpening a claim into a simulation goal

A claim is ready when a skeptical reader could look at the planned output and agree it was met or not met. Most first drafts are not there. The way to get there is to interrogate every word that could mean more than one thing, then rewrite.

This worked example is from Alejandro Schuler's "Simulations Done Right". It is worth walking through in full the first time, because the move is easy to describe and easy to skip.

---

## The setup

> You wake up. It's 2006. You look in the mirror and you see you are Mark van der Laan. You've just invented TMLE.

What claims should the TMLE paper make, and which can be supported by theory rather than simulation?

## Round 1: candidate claims

**(theory)** TMLE is a general method for constructing efficient estimators of pathwise differentiable estimands.

Estimating equations already do this. So the claim needs to be shown, but showing it is not enough to establish that TMLE is useful. This is the first lesson: a true claim can still fail to be a *reason to care*.

**TMLE is in practice "better" than...**

- plug-in estimators? AIPW is already better than those.
- AIPW?

Which forces the question: **better in what sense, and when should it be better and when worse?** That question is the whole job.

**It works in the real world:** computationally tractable, handles mixed data types, can be prespecified. Usually addressable with theory plus a single real-data application, not with simulation.

## Round 2: simulation goals, first pass

1. Across the board, AIPW and TMLE behave similarly in large samples when they have access to the same learners.
2. TMLE is better than plugins, allowing for good coverage of Wald intervals.
3. There are cases where TMLE is better than AIPW in small samples.

These read like goals. None of them is answerable yet.

## Round 3: the interrogation

Take each goal and list what is unpinned. This is the core move.

**Goal 1.** Across the board, AIPW and TMLE behave similarly in large samples when they have access to the same learners.
- What learners?
- Similar *by what metric*?

**Goal 2.** TMLE is better than plugins, allowing for good coverage of Wald intervals.
- What learners?
- What should $n$ be here?
- Presumably using influence-function-based intervals. Say so.
- Better by what metric?
- Is there a way to get intervals for the plugins, as a naive baseline? Without one the comparison is unfair in the wrong direction.

**Goal 3.** There are cases where TMLE is better than AIPW in small samples.
- Can this be backed by theory, so the simulation confirms rather than fishes?
- In which DGPs? "There are cases" with no named case is unfalsifiable.

## Round 4: rewritten goals

1. Across the board, AIPW and TMLE behave similarly **in terms of point estimate and SE estimate** in large samples when they have access to the same learners.
2. Like AIPW, TMLE **improves the MSE of plugins in moderate sample sizes** and allows for good coverage of **Wald intervals based on IF SEs**, even compared to the same SE put around the plugin.
3. TMLE is better than AIPW in small samples **when the outcome is bounded** (?).

Every question from round 3 is now answered inside the goal text. The trailing question mark on goal 3 is honest: it marks a goal that may not survive contact with results, which is exactly the kind of goal worth running.

---

## The questions that do the work

When sharpening any goal, these are usually the ones that matter:

| Question | Why it matters |
|---|---|
| Better or worse **by what metric**? | Without it there is no possible table. |
| At **what sample size**? | Most method comparisons reverse somewhere along $n$. |
| Under **which DGPs**? | "There are cases" names no case and cannot be checked. |
| With **what nuisance estimators or tuning**? | A comparison of methods is often a comparison of learners in disguise. |
| Against **what baseline**? | A method beating a straw man has shown nothing. |
| Is there **theory** that predicts this? | A confirmed prediction is much stronger evidence than a found pattern. |

## What happens next

The sharpened goal determines the mockup, and the mockup determines the DGPs. Goal 3 above is a good illustration: "when the outcome is bounded" means one of the DGPs now needs a bounded outcome. That requirement did not come from a sense of what a realistic DGP looks like. It came from the claim.

This is also why goal 3's evidence can be a *subset* of goal 2's evidence. Once the DGP set includes a bounded-outcome configuration, supporting goal 3 may be a matter of pointing at the relevant rows of a table that already exists. Noticing that at the mockup stage saves an entire run.
