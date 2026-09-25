# Organizing the write-up

The reader is meeting this design for the first time and has no idea why any of it exists. Everything here follows from taking that seriously.

## The spine: organize by claim

Section structure mirrors the claims. Each claim is stated, its evidence sits next to it, and the reader is told how the one supports the other before moving on.

The alternative, which is what most simulation sections do, is to order the section by output: here is Table 1, here is Table 2, here is Figure 1, and then a discussion that finally explains what they were all for. That forces the reader to hold every number in working memory until the payoff arrives. Most readers stop holding.

When several claims genuinely share one display, present the display once and refer back to specific rows from each claim's paragraph. Pointing at rows is cheap; making the reader re-read a table is not.

## Sandwich every piece of evidence

For each unit of evidence, in order:

1. **State the goal.** What is this about to show?
2. **Give the evidence.** The table, the figure, the numbers.
3. **Say how the evidence supports the goal.** Explicitly. In words.

> In the first part I tell 'em what I am going to tell 'em; in the second part, well, I tell 'em; in the third part I tell 'em what I've told 'em.

Be prosaic and direct. This is one of the few places in academic writing where stating the obvious is correct, because it is only obvious to the person who designed the study.

The same sandwich works for non-simulation evidence. For a real-data application of targeted maximum likelihood estimation (TMLE):

> The point of this application is to show how fast TMLE is on a real-world dataset of size *n*, to demonstrate that it works with mixed data types, to show it can be prespecified, and to confirm it produces plausible results.

That sentence tells the reader exactly what to look for before they see anything. Write it before the application, not after.

## ADEMP is the "tell 'em what you're going to tell 'em"

Before any results, describe Aims, Data-generating processes (DGPs), Estimands, Methods, and Performance measures. See `ademp.md` for what each element needs. Aims is the most important one; everything else exists to serve it.

DGPs must be fully described. Methods must be described with enough detail to reimplement without code, including hyperparameter tuning, grids, etc. Similarly, performance measures must be clearly described so someone with the raw results file could recompute them without code.

Do this once for the whole study when the claims share a setup, or separately per claim when they do not.

## Captions

Every table and figure caption names the claim it serves. Not just what the table contains, which the reader can see, but what it is *for*.

Weak: "Table 2: Performance of three estimators across three DGPs."
Better: "Table 2: TMLE and augmented inverse probability weighting achieve comparable mean squared error and near-nominal coverage at n = 300, while the plug-in estimator's intervals undercover badly. Supports the claim that debiasing is necessary for valid inference at moderate n."

If the purpose cannot be stated in one sentence, that is a signal the display should be cut or split.

## Minimizing cognitive load

- **One table per claim** where the claims allow it.
- **Comparison side by side.** Methods usually are the comparison, so put methods in adjacent rows or columns, and vary DGPs or sample sizes along the other axis.
- **One estimand in the main text.** Send the second to the appendix. A paper that carries one thing well beats one that carries three thinly.
- **Consistent orientation.** If methods are columns in Table 1, they are columns everywhere. Readers build a habit from the first table and every deviation costs them.
- **Consistent naming.** The name in the code, the name in the table, and the name in the prose are the same name.
- **Round hard.** Trailing digits that carry no information are noise the reader has to filter. Report the precision the simulation actually supports.
- **A table past roughly 40 numbers stops being read.** Move to a figure and keep the full table in supplementary material.

## Say why, not only what

The "why" is the part that gets dropped, and it is what separates a report from a list of numbers. Every choice a reader might question gets a reason in the text:

- Why these DGPs, and what do they span?
- Why this range of sample sizes?
- Why these learners or tuning parameters?
- Why each oracle or semi-oracle (a method given the true nuisance functions, in whole or in part), and which claim or subclaim does it help test?
- Why this estimand?
- Why these performance measures, for this claim?
- Why this many repetitions?

A useful test: hand the draft to someone and ask them to mark every sentence where they thought "why did they do that?". Each mark is a missing sentence.

## Reporting results that went the wrong way

Report them with the same prominence as the ones that went your way, and then say what they mean. A claim narrowed by an honest negative result is a better claim, because the condition it gained is information the reader needs.

Scope every conclusion to the DGPs actually simulated. If a reader is likely to extrapolate past them, name the extrapolation and say whether the study supports it.

## Common failure modes

| Symptom | What it means |
|---|---|
| A table nobody refers to in the text | No claim needs it. Cut it. |
| "Results are shown in Table 3" and nothing more | The sandwich is missing its third slice. |
| The reader cannot tell why a DGP was included | The DGP came from taste, not from a claim. |
| Every number to four decimals | Precision that the number of repetitions does not support. |
| Methods split across separate tables | The comparison the reader wants is the one you made hardest. |
| The discussion is where the purpose of each table is finally revealed | The section is ordered by output rather than by claim. |

## Choosing the display

Pick by the question the display answers, not by habit.

**Distribution of the per-repetition estimates.** A histogram or box plot of the raw $\hat\theta_i$, per DGP and method. At least one of these belongs somewhere in the paper, because summaries hide skew, bimodality and outliers. An estimator that looks unbiased because two catastrophic repetitions cancel is invisible in a table of means and obvious here.

**Method against method on matched repetitions.** A scatter of one method's estimates against another's, over the same repetitions, with the line of equality. Both methods saw the same data, so this shows per-dataset agreement, which comparing two marginal distributions cannot. The Bland-Altman variant, difference against mean, works when one method is the reference.

**Lollipop plot.** Performance estimates as points with their Monte Carlo intervals, methods stacked within each DGP. Puts many methods on one readable axis with uncertainty visible.

**Zip plot** (Morris et al. 2019), for explaining why coverage is off. Compute $z_i = (\hat\theta_i - \theta)/\widehat{\mathrm{SE}}(\hat\theta_i)$, the distance from repetition $i$'s estimate $\hat\theta_i$ to the true value $\theta$, in units of the standard error (SE) that the method reports for that repetition. Rank repetitions by $|z_i|$ into fractional centiles for the vertical axis, and draw each interval as a horizontal segment coloured by whether it covers $\theta$. For 95% intervals with correct coverage, the colour switches at 95. With Wald intervals the switch is always clean, because such an interval misses the true value $\theta$ if and only if the standardized distance $|z_i|$ exceeds 1.96, so the diagnosis comes from two other features. The height of the switch is the coverage. Misses mostly on one side of the true value $\theta$ point to bias, while misses on both sides with the switch below 95 point to intervals that are too narrow, and a switch above 95 to intervals that are too wide. The centile scale keeps it legible at any number of repetitions.

**Nested loop plot**, for factorial designs too large to tabulate. Nested factors run along the horizontal axis with methods overplotted as lines. Carries a four- or five-factor design that no table could hold.

In R, `rsimsum` implements the standard performance measures along with zip, lollipop and nested loop plots.

**Caption checklist.** Every simulation display states the estimand and its true value, the DGP or a pointer to it, the number of repetitions and the sample size, what any uncertainty marks represent, and the claim it serves.
