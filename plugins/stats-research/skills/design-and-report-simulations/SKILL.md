---
name: design-and-report-simulations
description: How to design a simulation study and how to organize its write-up so a reader can see what was done and why. Use whenever simulation or Monte Carlo work is in play: planning a simulation for a paper, choosing DGPs or settings, writing or restructuring simulation code (including how to rerun parts of it and what to cache), making tables or figures from simulation output, writing a simulation section, or answering "how did the methods compare". The core move is backwards design: a simulation exists to support a claim, so the claim comes first, the mockup of the tables and figures comes before any code, and the write-up is organized claim by claim with the purpose of every table stated out loud. Also use when simulation results contradict the claim they were meant to support and the claim needs rescoping.
---

# Designing and reporting simulation studies

A paper is claims plus evidence. Simulations are one kind of evidence, next to theory and real-data applications, and they have no value apart from the claim they support. Everything in this skill follows from that.

Two failures account for most bad simulation work, and they are the same failure seen from two ends.

**At the write-up end:** a results section that presents output without saying what any of it is for. Tables appear, numbers are described, and the reader is left to reverse-engineer why each table exists and what it proves. Even correct, well-executed simulations fail here, because the reader cannot follow an argument that was never stated.

**At the design end:** a simulation built before anyone decided what it needed to show. The data-generating processes (DGPs) were picked because they seemed reasonable, the settings because they seemed standard. Output like that cannot be organized well afterwards, because there is no argument to organize it around.

The fix for both is backwards design: decide the claim, mock up the table that would prove it, then build the simulation that fills the mockup.

## The workflow

```
1. Claims → 2. Goals → 3. Mockups → 4. DGPs & settings → 5. Build → 6. Pilot → full run
     ↑                       ↑          ↑                                │         │
     │                       └──────────┴──── design cannot show it ─────┘         │
     └───────────────────────── results reshape the claim ─────────────────────────┘
```

Stage 6 is a gate, not a formality. It is where a mockup that cannot be filled in gets caught, while fixing it still costs minutes.

Three things drive quality at different stages, and it helps to know which one you are serving:

- **Thoughtful goals give direction.** Practical utility, real insight, a specific audience.
- **Communication gives focus.** Structure and organize; minimize the reader's cognitive load.
- **Clean, fast sims give productivity.** Simple DGPs, minimal compute, modular code.

Find out where the user actually is and enter there. Someone arriving with results already in hand still needs stages 1 through 3 reconstructed before the write-up can be organized, because the write-up is organized by claim and there is nothing to organize without one. Reconstructing a claim from finished results is legitimate and common. Pretending the claim was prespecified when it was not is not.

## Stage 1: claims

Ask what the paper is claiming, not what the simulation will compute. If the answer is "we show our method works", the claim does not exist yet.

A good claim has practical utility, builds insight, and is honest and well-scoped. Many claims are always possible, and less is more, so prioritize by relevance to the audience and by the potential to change what people do or think.

Simulation-supported claims usually take this shape:

> *[method] works [well] when [condition] and not when [other condition]*

The second half matters as much as the first. A claim with no stated boundary is usually overstated, and usually less useful, because a reader who cannot tell when the method fails cannot tell when to use it.

Sort the claims by what kind of evidence can carry them. Theory carries asymptotic and structural claims. A single real-data application carries claims about practicality, runtime, and data-type handling. Simulations carry claims about finite-sample behaviour under a known truth, which is exactly the thing no other evidence can reach.

## Stage 2: simulation goals

Turn each claim into something a simulation can actually answer, by interrogating every word that could mean more than one thing. `references/sharpening-goals.md` has a full worked example of this interrogation, and it is worth reading the first time you do it, because the move is easy to describe and easy to skip.

The pattern: state the goal, list what is unpinned, rewrite. "Targeted maximum likelihood estimation (TMLE) is better than plug-in estimators" leaves *better by what measure*, *at what sample size*, *with what learners*, and *in which DGPs* all undetermined, which means no simulation can confirm or refute it. The rewrite names all four.

Pin down the comparators here too, and always consider an oracle or semi-oracle among them. An oracle is given something only the simulation knows, so no analyst could run it on real data. Usually that is the true value of each nuisance function, such as the propensity score or the outcome regression. A semi-oracle gets the true values of some nuisance functions and estimates the rest.

Both help test two kinds of claim. An ablation claim says how much one part of a method contributes to its performance, and a mechanism-of-action claim says why a method works. If one method's advantage disappears once every method gets the true propensity score, the advantage comes from how the methods cope with estimating it. An oracle also gives an idea of best-case performance. Whether to include one, and in which display, depends on the claim or subclaim it would serve. `references/sharpening-goals.md` works through a case and gives a reason an oracle is not always a ceiling.

Stop when a skeptical reader could look at the planned output and agree the goal was met or not met. If two people could read the goal and disagree about whether a given table supports it, keep going.

## Stage 3: mock up the tables and figures

This is the stage people skip, and skipping it is what produces disorganized output. Before writing simulation code, draw each table and figure with the cells empty, and write its caption.

The mockup answers questions that are expensive to answer later:

- If the numbers land where you expect, does this display convince a skeptic? If they land the other way, will you be able to tell?
- Which DGPs does this display require? Often the mockup reveals you need a configuration nobody had planned. That is the point.
- Do two claims share one display? Good, merge them. Does a display have no claim attached? Cut it, or find the claim.
- What goes in the appendix? A second estimand usually does. The main text carries one thing well rather than three things thinly.

Layout follows from the comparison the reader cares about, which is usually between methods, so methods belong in adjacent rows or adjacent columns and the other factors vary along the other axis. A reader who has to look across a page break to compare two methods will not do it.

Mockups are also the cheapest possible feedback. Show them to a coauthor before a single line of simulation code exists.

## Stage 4: DGPs and settings

Being able to *reason* about a DGP and *iterate* on it matters more than making it realistic. If you cannot predict roughly what should happen, you cannot tell a bug from a finding, and most of your time will go to that confusion.

Sensible defaults, and the diagnostics worth computing on any DGP before trusting it, are in `references/designing-dgps.md`. The short version: bounded covariates, simple and sparse nuisance functions, and a check on overlap, variance explained, and how nonlinear the truth actually is.

Learners and their tuning are settings too, and so is the way each dataset is split between fitting the learners, validating them and computing the estimators. Set all of these up with the `supervised-learning` skill. By default each dataset is three independent draws, each with the dataset's full sample size: a training draw to fit the learners, a validation draw to tune and choose them, and an estimation draw for the estimators. The three draws are a cheap stand-in for cross-validated cross-fitting at that sample size, and the skill also lists the cases where the stand-in fails.

Design DGPs to archetype the extremes. Edge cases are what sharpen a claim from "works well" into "works well when [condition] and not when [other condition]", and that sharper claim is the more useful paper.

Every parameter value and every functional form in a DGP needs a reason. It shows a specific phenomenon, it prevents a specific problem, or it is an unobjectionable default.

Everything chosen here stays provisional until the pilot in Stage 6 confirms it can produce the mockup. Do not freeze the DGPs, and do not start the full run, on the strength of the equations looking right.

## Stage 5: build

Write the code once, in the shape every later step reuses. The pilot runs it at two and then a couple of hundred repetitions, the full run is the same code at the final number of repetitions `n_sim`, and every claim's display is a summary of what it stores. A pilot written as a separate script checks the wrong code.

Three properties decide how cheap the rest of the project will be:

- **Share whatever can be shared.** When two claims need overlapping computation, they get it from the same code and the same stored outputs. If one table compares learner libraries by the root mean squared error (RMSE) of their nuisance predictions and another reports TMLE built on some of those libraries, the TMLE code reads the predictions the RMSE table came from, and nothing gets refit in a second script. A fix then reaches every display at once, and the displays stay paired on the same datasets.
- **Let any piece run alone.** The run function takes a subset of every factor: DGPs, sample sizes, repetitions, learners, estimators. That is what lets you rerun one DGP, add one estimator, or run one learner library across every estimator without touching the rest. It works only if each dataset's seed comes from its name (DGP, sample size, repetition) and never from its position in a loop.
- **Cache the expensive steps.** Learner predictions are the usual example. For an ensemble, keep each base learner's predictions on the validation draw too, so that a new learner library is a cheap recombination of stored fits. Keep the cache in a local directory that git ignores. Key each entry on everything that determines it, so that a hit always equals what recomputing would give and deleting the cache changes nothing but runtime.

Beyond those three, simulation code is written to be run and rewritten, not maintained. Fast, modular, and disposable beats polished. `references/implementation.md` has the architecture, the caching rules, what keeps runtime sane, and what to save. `assets/simulation-scaffold.R` and `assets/simulation-scaffold.py` are working skeletons in that shape. The learners in that code come from the `supervised-learning` skill.

## Stage 6: pilot, and check the design can show what the mockup promises

A mockup is a hypothesis. It says that once this table is filled in, particular cells will differ, in a particular direction, by enough to see. A pilot tests that hypothesis for a few minutes of compute, before the full run spends hours either confirming it or quietly failing to.

The failure this catches is specific and expensive. When the contrast a table was built to display is less than about three Monte Carlo standard errors (SEs) of the difference between its cells at the planned number of repetitions, the cells cannot be reliably told apart, and **an unresolvable design produces a null result that looks exactly like a true null.** You cannot tell "these methods really do perform the same" from "this simulation could never have told them apart", and neither can a reader. The discovery also arrives after the compute is spent and the deadline is near, when every remaining fix is a bad one.

Three checks, in increasing cost:

1. **Does it run?** Two repetitions. Catches the errors that are embarrassing rather than interesting.
2. **Are the DGPs what you think they are?** One large draw, computing the diagnostics in `references/designing-dgps.md`: true estimand value, overlap, variance explained, and how nonlinear the truth is. These belong in the paper, so the work is not wasted.
3. **Is the designed contrast resolvable?** Roughly 100 to 200 repetitions. This is the check that gets skipped, and the one that saves whole runs.

The third check, briefly. A contrast between two means over repetitions (bias, mean squared error, coverage, rejection rate) is itself the mean of a per-repetition difference `d_i`, since the difference of two averages is the average of the differences. Repetitions are independent, so that mean has Monte Carlo SE `sd(d)/sqrt(n_sim)`. Requiring `|mean(d)|` to be at least `k` of those SEs and solving for `n_sim` gives

```
n_sim  >=  ( k * sd(d) / mean(d) )^2        k = 3 to see it, 5 to be comfortable
```

The pilot only estimates `mean(d)` and `sd(d)`, and plugging in the estimates is optimistic exactly when the pilot was lucky. `references/piloting.md` has two guards for that: size on a lower bound for the gap (the tools report it as `n_sim_safe`), and treat a pilot whose own `|z|` is below 2 as too small to size anything. Run the check for every cell comparison the mockup promises, and let the largest requirement set `n_sim`. The same file has the derivation step by step, what `d_i` is for each performance measure, the bootstrap for measures that are not means, and what to do when the answer comes back bad. `assets/pilot_check.R` and `assets/pilot_check.py` implement it.

A requirement in the millions is a verdict only when the pilot can see the gap at all. If the pilot cannot tell the gap from zero, the `n_sim` it implies is noise: enlarge the pilot, or, for a bias contrast, measure the gap directly on one very large draw as `references/piloting.md` describes. If the gap is still indistinguishable from zero, the design is dead as drawn. The fix is then upstream, in Stage 3 or Stage 4: amplify the signal by changing the DGP, or change what the table displays. That is exactly why this gate sits before the full run instead of after it.

**The trap worth knowing by name.** Designed contrasts vanish through cancellation far more often than by being genuinely small. An outcome model that misses the treated-arm mean `mu(1, X)` and the control-arm mean `mu(0, X)` in the same direction and by similar amounts is barely wrong about their difference `mu(1, X) - mu(0, X)`, so a grid built to show that misspecification hurts can end up showing almost nothing. The usual cure is effect heterogeneity in the very covariate the misspecification corrupts, in a form the working model cannot fit. This is close to invisible on paper and obvious after twenty seconds of pilot.

Scale up only once all three checks clear: the code runs, the DGP diagnostics are sane, and the contrast is resolvable at the number of repetitions `n_sim` you are about to pay for. The full run is the Stage 5 code at that `n_sim`. Save its raw per-repetition results to disk, since every table and figure is derived from them.

## Iterating when results disagree with the claim

Results that contradict the claim are the normal case, not a disaster, and a clear goal is what makes the contradiction legible in the first place. Without one you cannot tell whether an outcome is good or bad.

The honest response runs: check for a bug, then understand the theory well enough to know why the result happens, then narrow the claim to what is true. A claim that gains a condition is usually a better claim, because the condition is information the reader needs. Burying the result, or quietly dropping the DGP that produced it, is the thing to refuse.

Flag this explicitly when it comes up. A user looking at a disappointing simulation often wants help making the result go away, and the useful help is the opposite.

## Writing it up

Read `references/writing-the-writeup.md` before drafting. It carries the detail; the spine is here.

**Organize by claim, not by output.** The section structure mirrors the claims, and each claim gets its evidence next to it. A results section ordered by table number forces the reader to hold every table in mind until the discussion finally explains what they were for.

**Sandwich every piece of evidence.** Tell the reader the goal, give the evidence, then say how the evidence supports the goal. Be direct and prosaic about it; this is one place where spelling out the obvious is correct, because what is obvious to the author is not obvious to a reader meeting the design for the first time.

> In the first part I tell 'em what I am going to tell 'em; in the second part, well, I tell 'em; in the third part I tell 'em what I've told 'em.

**Use ADEMP for the "tell 'em what you're going to tell 'em".** Before results, describe Aims, Data-generating processes, Estimands, Methods, and Performance measures. Aims is the important one and the rest exist to serve it. Element-by-element guidance, including what a reader needs in order to reimplement, is in `references/ademp.md`. Do this once for the whole study, or separately per claim when the claims need different setups.

**Every table and figure names its purpose.** The caption says which claim it serves. A display whose purpose cannot be stated in one sentence is a display to cut.

**Say what was done and why it was done that way.** Every choice a reader might question gets a reason: why these DGPs, why this sample size, why these learners, why this estimand. Each oracle or semi-oracle gets one too, and its reason is the claim or subclaim it helps test. "Why" is the part that gets dropped, and it is the part that separates a report from a list of numbers.

## Performance measures

Which measures to compute depends entirely on the claim. Bias, empirical SE, mean squared error, coverage, and rejection rate are the standard set for claims about estimator accuracy and interval calibration, and `references/performance-measures.md` gives their definitions, their Monte Carlo standard errors, and how to pick the number of repetitions.

That file is a resource, not a checklist. Claims about runtime, about model selection, about prediction, or about qualitative behaviour need different measures or none of these. Reach for it when the claim is about an estimator's accuracy or its intervals; skip it otherwise.

Two habits from that file are worth carrying everywhere, cheaply: reporting a Monte Carlo SE alongside a headline number keeps you from over-reading noise, and saying how many repetitions failed keeps the rest of the numbers interpretable. Neither needs to dominate the write-up.

## Before calling a write-up done

The question to answer is whether a reader can follow the argument, so read the draft as someone meeting it for the first time and check:

- Can you state, for every table and figure, which claim it supports? Can the reader, from the text alone?
- Does each claim have its evidence next to it, rather than scattered across the section?
- Is every design choice a reader might question given a reason?
- Could someone reimplement the DGPs, the methods, and the performance measures from the text alone, without opening the code?
- Are the claims scoped to what the evidence shows, including the conditions where things failed?
- Is anything in the results section that no claim needs?

Then, if the write-up is a LaTeX (`.tex`) file, hand the prose to `readable-math` for notation and derivations. If `avoid-ai-writing` (github.com/conorbronsdon/avoid-ai-writing) is installed, hand the prose to it for voice.
