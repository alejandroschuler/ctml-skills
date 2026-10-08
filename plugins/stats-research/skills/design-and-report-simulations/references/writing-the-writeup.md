# Organizing the write-up

Write for a reader who is seeing the design for the first time and does not know why any part of it exists.

## Contents

- Organize by claim
- Sandwich every piece of evidence
- ADEMP is the "tell 'em what you're going to tell 'em"
- Captions: weak and better
- Making displays easy to read: layout, naming, rounding, table size
- Say what was done and why: the questions a reader will ask
- Reporting results that went the wrong way
- Common failure modes: symptoms and what they mean
- Choosing the display: distribution plots, matched scatters, lollipop, zip and nested loop plots, and the caption checklist

## Organize by claim

The section structure mirrors the claims, as the aims state them. State each claim, put its evidence next to it, and tell the reader how the evidence supports the claim before moving on.

Many simulation sections are ordered by output instead: Table 1, Table 2, Figure 1, and then a discussion that says what they were for. The reader then has to remember every number until the end.

When several claims share one display, present it once and point to the relevant rows from each claim's paragraph.

The results in `example-study.md` follow this structure, with one subsection per aim. Their figures have one DGP factor in the rows and the other in the columns, so each subclaim is a region of a figure that the text can point to.

When one aim answers an objection to another, it usually reads best right after that aim. In the example, coverage comes right after efficiency, because an estimator that underestimates its own SE would look efficient.

## Sandwich every piece of evidence

For each piece of evidence, in this order:

1. **State the goal.** What is this about to show?
2. **Give the evidence.** The table, the figure, the numbers.
3. **Say how the evidence supports the goal.** Say it in words.

> In the first part I tell 'em what I am going to tell 'em; in the second part, well, I tell 'em; in the third part I tell 'em what I've told 'em.

Be prosaic and direct. Here it is correct to state the obvious, because it is obvious only to the person who designed the study.

The same sandwich works for evidence other than simulations. For a real-data application of targeted maximum likelihood estimation (TMLE):

> The point of this application is to show how fast TMLE is on a real-world dataset of size *n*, to demonstrate that it works with mixed data types, to show it can be prespecified, and to confirm it produces plausible results.

A sentence like this tells the reader what to look for. Put it before the application.

## ADEMP is the "tell 'em what you're going to tell 'em"

Before any results, describe Aims, Data-generating processes (DGPs), Estimands, Methods, and Performance measures. See `ademp.md` for what each element needs. Aims is the most important one; everything else exists to serve it.

DGPs must be fully described. Methods must be described with enough detail to reimplement without code, including hyperparameter tuning, grids, etc. Similarly, performance measures must be clearly described so someone with the raw results file could recompute them without code.

Do this once for the whole study when the claims share a setup, or separately per claim when they do not.

## Captions

Every table and figure caption names the claim it serves. The reader can see what a display contains; the caption has to say what it is for.

Weak: "Table 2: Performance of three estimators across three DGPs."
Better: "Table 2: TMLE and augmented inverse probability weighting achieve comparable mean squared error and near-nominal coverage at n = 300, while the plug-in estimator's intervals undercover badly. Supports the claim that debiasing is necessary for valid inference at moderate n."

If you cannot state the purpose or purposes of a display in one sentence, cut it or split it.

## Making displays easy to read

- **One table per claim** where the claims allow it.
- **Comparisons side by side.** The comparison is usually between methods, so put methods in adjacent rows or columns, and vary DGPs or sample sizes along the other axis.
- **A short main text.** Keep one to three claims and one estimand in the main text. Put the evidence for the other claims, and any second estimand, in the appendix.
- **Consistent orientation.** If methods are columns in Table 1, they are columns everywhere. Readers learn the layout from the first table.
- **Consistent naming.** A method or DGP has the same name in the code, the tables and the prose.
- **Rounding.** Report only the precision that the Monte Carlo error supports. `fmt_mcse()` in `../assets/performance_measures.R` rounds an estimate to match its Monte Carlo SE.
- **Table size.** Readers rarely read a table with more than about 40 numbers. Use a figure, and put the full table in the supplementary material.
- **Caption checklist.** Every simulation display states (as relevant) the estimand and its true value, the DGP or a pointer to it, the number of repetitions and the sample size, what any uncertainty marks represent, and the claim(s) it serves.

## Say what was done and why

Every choice a reader might question gets a reason in the text:

- Why these DGPs, and what range do they cover?
- Why this range of sample sizes?
- Why these learners or tuning parameters?
- Why each oracle or semi-oracle (a method given the true nuisance functions, in whole or in part), and which claim or subclaim does it help test?
- Why this estimand?
- Why these performance measures, for this claim?
- Why this many repetitions?

To check, give the draft to someone and ask them to mark each place where they wondered why you did something. Each mark needs a sentence of explanation.

## Reporting results that went the wrong way

Report them as prominently as the results that went your way, and say what they mean. A claim that gains a condition from a negative result is usually a better claim, because the reader needs to know that condition. In `example-study.md`, the sample size subsection reports that the formula is slightly anti-conservative for two of the baselines, suggests a cause, and says what is still unclear.

Scope every conclusion to the DGPs actually simulated. If a reader is likely to extrapolate past them, name the extrapolation and say whether the study supports it.

## Common failure modes

| Symptom | What it means |
|---|---|
| A table nobody refers to in the text | No claim needs it. Cut it. |
| "Results are shown in Table 3" and nothing more | The text does not say how the table supports the goal (the third part of the sandwich). |
| The reader cannot tell why a DGP was included | The DGP was not derived from a claim. |
| Every number to four decimals | More precision than the number of repetitions supports. |
| Methods split across separate tables | The reader cannot compare the methods directly. |
| The purpose of each table appears only in the discussion | The section is ordered by output, not by claim. |


