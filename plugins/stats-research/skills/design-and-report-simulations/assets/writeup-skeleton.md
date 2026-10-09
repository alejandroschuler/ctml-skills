# Simulation write-up skeleton

Organized by claim, not by table. One subsection per aim: state the aim, present its evidence, then say how the evidence supports each subclaim.

Delete the bracketed prompts as real content replaces them.

---

## Simulation study

### Aims

[State the Stage 2 aims, from the plan or reconstructed from the results, as hypotheses that could turn out to be wrong, each with its subclaims. This is the most important part of the setup, and everything below serves it. The Aims section of `references/ademp.md` has an example.]

1. *[SHORT NAME].* [METHOD] gives [a smaller / larger / no worse] [MEASURE] than [COMPARATOR] when [CONDITION], as [THEORY] predicts. [Or: METHOD keeps MEASURE at TARGET when CONDITION.] [Under SCENARIO, EXPECTED RESULT. Under SCENARIO, EXPECTED RESULT. One sentence per subclaim.]
2. *[SHORT NAME].* ...

### Data-generating processes

[Generating equations with every parameter value. A reader should be able to regenerate the data from this section alone, without opening the code.]

We consider [K] data-generating processes (DGPs), chosen to span [WHAT THE CLAIMS REQUIRE]:

| DGP | Characterization | True estimand | Overlap | Variance explained | Linearity of $\mu$ |
|---|---|---|---|---|---|
| | | | | | |

[Say why these DGPs and what they span: name the subclaim that each one tests. Say what varies across them and what is held fixed. Name the design: a base case with one-at-a-time deviations, or which factors are crossed and the subclaim that needs the cross.]

Sample sizes [VALUES] were chosen because [REASON].

### Estimands

The estimand is [DEFINITION], a [marginal / conditional] quantity. Its true value is [VALUE / computed by MEANS] under each mechanism. [If approximated numerically, give the approximation error.]

[If a second estimand is in the appendix, say so and say why.]

### Methods

1. **[NAME]**: [enough to reimplement, including tuning, the data split or folds, tolerances]
2. **[NAME]**: ...
3. **[BASELINE]**: [why this is the right baseline]
4. **[ORACLE or SEMI-ORACLE, if one serves a claim]**: [which nuisance functions take their true values from the DGP (all of them for an oracle, some for a semi-oracle), and which claim or subclaim this comparison helps test]

Nuisance functions were estimated with [LEARNERS], chosen because [REASON]. Each dataset consisted of three independent draws of size [n]: the learners were fit on the first and validated on the second, and the estimators were computed on the third. This stands in for cross-validated cross-fitting at [n]. [Or describe the cross-fitting scheme and its folds, if a claim needed it.] All methods were implemented in [SOFTWARE, VERSION]. [Rule applied on non-convergence.]

### Performance measures

We report [MEASURES] because [WHICH CLAIM EACH ANSWERS]. [Definitions or a pointer.] Intervals are at [95]%; tests use alpha = [0.05]. We ran [N] repetitions [and how that was decided]. [Monte Carlo standard errors are reported alongside each estimate.] [If any repetitions failed: how many, for which method, and why.]

---

## Results

### [Aim 1, stated as a heading a reader can act on]

**What it tests.** [Tell them what you're going to tell them. What is this about to show, how is it measured, and why does it matter?]

[TABLE or FIGURE. Caption names the claim it serves, not just the contents.]

**What it shows.** [Tell them what you've told them. Go through the subclaims in turn, and point at the rows or panels for each. Say how they support the aim. State clearly where the evidence is weaker than you would like.]

### [Aim 2 …]

**What it tests.** ...

[Evidence]

**What it shows.** ...

---

## Discussion of the simulation

[Scope the conclusions to the DGPs simulated. Name the extrapolation a reader is likely to make and say whether the study supports it.]

[Report anything that went the other way, with the same prominence, and say what it means for the claim. A claim that gained a condition is usually a better claim.]
