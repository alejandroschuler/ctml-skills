# Simulation write-up skeleton

Organized by claim, not by table. Each claim states its goal, presents its evidence, then says how the evidence supports the goal.

Delete the bracketed prompts as real content replaces them.

---

## Simulation study

### Aims

[State the claims this simulation supports. Specific enough to be wrong. This is the most important part of the setup; everything below serves it.]

We evaluate [PROPERTY] of [METHOD(S)], relative to [BASELINE], under [CONDITION]. [One sentence per additional claim.]

### Data-generating processes

[Generating equations with every parameter value. A reader should be able to regenerate the data from this section alone, without opening the code.]

We consider [K] data-generating processes (DGPs), chosen to span [WHAT THE CLAIMS REQUIRE]:

| DGP | Characterization | True estimand | Overlap | Variance explained | Linearity of $\mu$ |
|---|---|---|---|---|---|
| | | | | | |

[Say why these DGPs and what they span. Say what varies across them and what is held fixed. Name the factorial structure.]

Sample sizes [VALUES] were chosen because [REASON].

### Estimands

The estimand is [DEFINITION], a [marginal / conditional] quantity. Its true value is [VALUE / computed by MEANS] under each mechanism. [If approximated numerically, give the approximation error.]

[If a second estimand is in the appendix, say so and say why.]

### Methods

1. **[NAME]**: [enough to reimplement, including tuning, folds, tolerances]
2. **[NAME]**: ...
3. **[BASELINE]**: [why this is the right baseline]
4. **[ORACLE or SEMI-ORACLE, if one serves a claim]**: [which nuisance functions take their true values from the DGP (all of them for an oracle, some for a semi-oracle), and which claim or subclaim this comparison helps test]

Nuisance functions were estimated with [LEARNERS], chosen because [REASON]. All methods were implemented in [SOFTWARE, VERSION]. [Rule applied on non-convergence.]

### Performance measures

We report [MEASURES] because [WHICH CLAIM EACH ANSWERS]. [Definitions or a pointer.] Intervals are at [95]%; tests use alpha = [0.05]. We ran [N] repetitions [and how that was decided]. [Monte Carlo standard errors are reported alongside each estimate.]

---

## Results

[If any repetitions failed: how many, for which method, and why, before anything else.]

### [Claim 1, stated as a heading a reader can act on]

**Goal.** [Tell them what you're going to tell them. What is this about to show, and why does it matter?]

[TABLE or FIGURE. Caption names the claim it serves, not just the contents.]

**What it shows.** [Tell them what you've told them. Point at the specific rows or panels. Say how they support the goal. State clearly where the evidence is weaker than you would like.]

### [Claim 2 …]

**Goal.** ...

[Evidence]

**What it shows.** ...

---

## Discussion of the simulation

[Scope the conclusions to the DGPs simulated. Name the extrapolation a reader is likely to make and say whether the study supports it.]

[Report anything that went the other way, with the same prominence, and say what it means for the claim. A claim that gained a condition is a better claim.]
