---
name: design-and-report-simulations
description: 'Designs simulation studies and organizes their write-ups so a reader can see what was done and why. Emphasizes backwards design: a simulation exists to support a claim. The claims come first, followed by mockups of the tables and figures and finally code, and the write-up is organized claim by claim with the purpose of every artefact stated explicitly. Use whenever simulation or Monte Carlo work is in play: planning a simulation for a paper, choosing DGPs or settings, writing or restructuring simulation code (including how to rerun parts of it and what to cache), making tables or figures from simulation output, writing up simulation results in any form (a simulation section, a slide, a README or a chat reply), or answering "how did the methods compare". Also use when simulation results contradict the claim they were meant to support and the claim needs rescoping.'
---

# Designing and reporting simulation studies

A paper is claims and evidence for those claims. Simulations are one kind of evidence, next to theory and real-data applications. They have no value independent of the claim they support.

Most bad simulation work fails because the researcher did not state their hypotheses clearly enough, leading to a haphazard choice of data-generating processes, baselines, parameter settings, and metrics. The solution is to apply a backwards design loop.

## The workflow

```
                          ┌─ DGP or method changes ─┐
                          ↓                         │
1. Claims → 2. Goals → 3. Mockups → 4. DGPs & settings → 5. Build → 6. Pilot → full run
     ↑                       ↑          ↑                                │         │
     │                       └──────────┴──── design cannot show it ─────┘         │
     └───────────────────────── results reshape the claim ─────────────────────────┘
```

The pilot study in Stage 6 is a required gate. It is where we can quickly test hypotheses without consuming a lot of time and computational resources.

Find out where the user actually is and enter there. Someone arriving with results already in hand still needs stages 1 through 3 reconstructed before the write-up can be organized. Reconstructing a hypothesis from finished results is sometimes possible and you can help the user think through what their claims should be and how they align with theory.

When the work spans more than one stage, copy this checklist and check off an item only when it holds. For results already in hand, check items 1 to 3 when they are reconstructed. 

```
Simulation progress:
- [ ] 1. Claims: well-scoped, with an outline of the evidence that could support each claim
- [ ] 2. Goals: a skeptic could agree each was met or not; comparators pinned, oracle or semi-oracle considered
- [ ] 3. Mockups: every table and figure drawn with empty cells and a caption describing expected results, before any code
- [ ] 4. DGPs and settings: a reason for every parameter value and functional form; learners and split from supervised-learning skill; mockups redrawn to match
- [ ] 5. Build: one pipeline for pilot, full run and every display; any piece runs alone; expensive steps cached
- [ ] 6. Pilot: code runs; DGP diagnostics sane; every promised contrast resolvable; n_sim set
- [ ] Full run at that n_sim; raw per-repetition results saved
- [ ] Write-up: passes "Before calling a write-up done"
```

For a plan kept in a file, copy `assets/simulation-plan.md`, a fill-in template with one section per stage.

## Stage 1: claims

Ask what the paper is claiming, not what the simulation will compute. "We show our method works" is far from adequate.

A good claim has practical utility, builds insight, and is honest and well-scoped. Many claims are always possible, and less is more, so prioritize by relevance to the audience and by the potential to change what people do or think.

Simulation-supported claims usually take this shape:

> *[method] works [well] when [condition] and not when [other condition]*

The second half matters as much as the first. A claim with no stated boundary is usually overstated, and usually less useful, because a reader who cannot tell when the method fails cannot tell when to use it.

Sort the claims by what kind of evidence supports them. Theory usually supports asymptotic and structural claims. A single real-data application supports claims about practicality, runtime, and data-type handling. Simulations often support claims about finite-sample behavior under different operating conditions, and are best when they are supported by theory.

## Stage 2: simulation goals

Turn each claim into something a simulation can answer by recursively interrogating and splitting up ambiguous terms. `references/sharpening-goals.md` has a full worked example of this interrogation.

The pattern: state the goal, list what is unpinned, rewrite. "Targeted maximum likelihood estimation (TMLE) is better than plug-in estimators" leaves *better by what measure*, *at what sample size*, *with what learners*, and *in which DGPs* all undetermined, which means no simulation can confirm or refute it. 

Pin down the comparators here too, and always consider an oracle or semi-oracle among them. An oracle is given something only the simulation knows, so no analyst could run it on real data. Oracles help test two kinds of claim. An ablation claim says how much one part of a method contributes to its performance, and a mechanism-of-action claim says why a method works. If one method's advantage disappears once every method gets the true propensity score, the advantage comes from how the methods cope with estimating it. An oracle also gives an idea of best-case performance. Whether to include one, and in which display, depends on the claim or subclaim it would serve. `references/sharpening-goals.md` works through a case and gives a reason an oracle is not always a ceiling.

Stop when a skeptical reader could look at the planned output and agree the goal was met or not met. If two people could read the goal and disagree about whether a given table supports it, keep going.

## Stage 3: mock up the tables and figures

Before writing simulation code, draw each table and figure with the cells empty, and write its caption. This is also where appropriate metrics can be sharpened or distilled down from higher level claims. 

The mockup answers questions that are expensive to answer later:

- If the numbers land where you expect, does this display convince a skeptic? If they land the other way, will you be able to tell?
- Which DGPs does this display require? Often the mockup reveals you need a configuration nobody had planned. That is the point.
- Do two claims share one display? Good, merge them. Does a display have no claim attached? Cut it, or find the claim.
- What goes in the appendix? Keep the main text as clean and to-the-point as possible. 1-3 claims are fine, prioritize and put any evidence for the rest in the appendix.

Layout follows from the comparison the reader cares about, which is usually between methods, so methods belong in adjacent rows or adjacent columns and the other factors vary along the other axis. Don't make a reader look across page breaks to compare two methods.

## Stage 4: DGPs and settings

Being able to *reason* about a DGP and *iterate* on it matters more than making it realistic. If you cannot predict roughly what should happen, you cannot tell a bug from a finding, and most of your time will go to that confusion.

Sensible defaults, and some diagnostics worth computing on any DGP, are in `references/designing-dgps.md`. The short version: bounded covariates, simple and sparse nuisance functions, and a check on overlap, variance explained, and how nonlinear the truth actually is.

Many simulations require supervised learning or generic regressions. See supervised-learning for suggestions on best practice.

Design DGPs to archetype different ends of spectra. Edge cases are what sharpen a claim from "works well" into "works well when [condition] and not when [other condition]", and that sharper claim is the more useful paper.

Every parameter value and every functional form in a DGP needs a reason. It shows a specific phenomenon, it prevents a specific problem, or it is an unobjectionable default.

Stages 3 and 4 form a loop. Adding, dropping or changing a DGP or method can change a mockup before any code exists. For example, a DGP for a new extreme adds a column or a panel, a new comparator, oracle or learner library adds a row, and a DGP that cannot vary a factor the mockup assumed removes that axis. When you make such a change, redraw the affected display and its caption, and ask the Stage 3 questions of it again.

Everything chosen here stays provisional until the pilot in Stage 6 confirms it can produce the mockup. 

## Stage 5: build

Write the code, shared between the pilot and full run. The pilot runs it at two and then a couple of hundred repetitions, the full run is the same code at the final number of repetitions `n_sim`.

Three properties decide how cheap the rest of the project will be:

- **Share whatever can be shared.** When two claims need overlapping computation, they get it from the same code and the same stored outputs. If one table compares learner libraries by the root mean squared error (RMSE) of their nuisance predictions and another reports TMLE built on some of those libraries, the TMLE code should read the predictions the RMSE table came from, and nothing gets refit in a second script. A fix then reaches every display at once, and the displays stay paired on the same datasets.
- **Let any piece run alone.** The run function takes a subset of every factor: DGPs, sample sizes, repetitions, learners, estimators. That is what lets you rerun one DGP, add one estimator, or run one learner library across every estimator without touching the rest. It works only if each dataset's seed comes from its name (DGP, sample size, repetition) and never from its position in a loop.
- **Cache the expensive steps.** Learner predictions are the usual example. For an ensemble, keep each base learner's predictions on the validation draw too, so that a new learner library is a cheap recombination of stored fits. Keep the cache in a local directory that git ignores. Key each entry on everything that determines it so it is clear when things need to be recomputed.

Beyond those three, simulation code is written to be run and rewritten, not maintained. Fast, modular, and disposable beats polished. Everything should be smoke-tested on corner case inputs, but writing formal tests for all but the most complex parts of the code is likely overkill, and the user should consider turning anything with that complexity into a separate package with its own tests.

`references/implementation.md` has the architecture, the caching rules, what keeps runtime sane, and what to save. `assets/simulation-scaffold.R` and `assets/simulation-scaffold.py` are working skeletons in that shape, to read and adapt. Their learners are placeholders: set up the real ones with the `supervised-learning` skill.

## Stage 6: pilot, and check the design can show what the mockup promises

A mockup is a hypothesis. It says that once this table is filled in, particular cells will differ, in a particular direction, by enough to see. A pilot tests that hypothesis for a few minutes of compute, before the full run spends hours either confirming it or quietly failing to.

The failure this catches is specific and expensive. When the contrast a table was built to display is less than about three Monte Carlo standard errors (SEs) of the difference between its cells at the planned number of repetitions, the cells cannot be reliably told apart, and **an unresolvable design produces a null result that looks exactly like a true null.** You cannot tell "these methods really do perform the same" from "this simulation could never have told them apart", and neither can a reader.

Three checks, in increasing cost:

1. **Does it run?** Two repetitions.
2. **Are the DGPs what you think they are?** One large draw, computing appropriate diagnostics such as those in `references/designing-dgps.md`: true estimand value, overlap, variance explained, and how nonlinear the truth is. 
3. **Is the designed contrast resolvable?** Roughly 100 to 200 repetitions.

Unexpected results from the pilot can sometimes indicate obvious bugs with the code, or clear misunderstandings about the methods or DGPs. Besides this, pilots also help size the final simulation run.

A contrast between two means over repetitions (bias, mean squared error, coverage, rejection rate) is itself the mean of a per-repetition difference `d_i`, since the difference of two averages is the average of the differences. Repetitions are independent, so that mean has Monte Carlo SE `sd(d)/sqrt(n_sim)`. Requiring `|mean(d)|` to be at least `k` of those SEs and solving for `n_sim` gives

```
n_sim  >=  ( k * sd(d) / mean(d) )^2        k = 3 to see it, 5 to be comfortable
```

The pilot only estimates `mean(d)` and `sd(d)`, and plugging in the estimates is optimistic exactly when the pilot was lucky. `references/piloting.md` has two guards for that: size on a lower bound for the gap (the tools report it as `n_sim_safe`), and treat a pilot whose own `|z|` is below 2 as too small to size anything. Run the check for every cell comparison the mockup promises, and let the largest requirement set `n_sim`. The same file has the derivation step by step, what `d_i` is for each performance measure, the bootstrap for measures that are not means, what to do when the answer comes back bad, and what to report about the pilot. For a claim of no difference, use that file's equivalence section instead of this formula. `assets/pilot_check.R` (base R) and `assets/pilot_check.py` (numpy, pandas, scipy) implement the check as functions to call on the pilot's results.

If the pilot cannot tell the gap from zero, the `n_sim` it implies is noise: enlarge the pilot, or, for a bias contrast, measure the gap directly on one very large draw as `references/piloting.md` describes. If the gap is still indistinguishable from zero, the design is dead as drawn. The fix is then upstream, in Stage 3 or Stage 4: amplify the signal by changing the DGP, or change what the table displays. That is exactly why this gate sits before the full run instead of after it.

Scale up only once all three checks clear: the code runs, the DGP diagnostics are sane, and the contrast is resolvable at the number of repetitions `n_sim` you are about to pay for. The full run is the Stage 5 code at that `n_sim`. Save its raw per-repetition results to disk, since every table and figure is derived from them.

## Iterating when results disagree with the claim

Results that contradict the claim are the normal case, not a disaster, and a clear goal is what makes the contradiction legible in the first place. Without one you cannot tell whether an outcome is good or bad.

The first step is to check for a bug, although the pilot should have caught most of them. Then revisit the theory to try and understand the result, and iterate on the claim. A claim that gains or corrects a condition is usually a better claim, so this is progress! Burying the result, or quietly dropping the DGP that produced it, is bad. Flag this explicitly when it comes up. A user looking at a disappointing simulation often wants help making the result go away, and the useful help is the opposite.

## Writing it up

Read `references/writing-the-writeup.md` before drafting. For a paper section, `assets/writeup-skeleton.md` is a fill-in skeleton in this shape. At a high level:

**Organize by claim, not by output.** The section structure mirrors the claims, and each claim gets its evidence next to it.

**Sandwich every piece of evidence.** Tell the reader the goal, give the evidence, then say how the evidence supports the goal. Be direct and prosaic about it; this is one place where spelling out the obvious is correct, because what is obvious to the author is not obvious to a reader meeting the design for the first time.

**Use ADEMP for the "tell 'em what you're going to tell 'em".** Before results, describe Aims, Data-generating processes, Estimands, Methods, and Performance measures. Aims is the important one and the rest exist to serve it. The exact order is not as important as making sure that all the required detail is present for a reader to reasonably replicate the results without code. Element-by-element guidance, including what a reader needs in order to reimplement, is in `references/ademp.md`. Do this once for the whole study, or separately per claim when the claims need different setups.

**Every table and figure names its purpose.** The caption says which claim it serves. A display whose purpose(s) cannot be stated in one sentence is a display to cut.

**Say what was done and why it was done that way.** Every choice a reader might question gets a reason: why these DGPs, why this sample size, why these learners, why this estimand. 

## Performance measures

Which measures to compute depends entirely on the claim. Bias, empirical SE, mean squared error, coverage, and rejection rate are the standard set for claims about estimator accuracy and interval calibration, and `references/performance-measures.md` gives their definitions, their Monte Carlo standard errors, and how to pick the number of repetitions. That file is a resource, not a checklist. Claims about runtime, about model selection, about prediction, or about qualitative behavior need different measures or none of these. Reach for it when the claim is about an estimator's accuracy or its intervals; skip it otherwise.

Reporting a Monte Carlo SE alongside a headline number keeps you from over-reading noise, and saying how many repetitions failed keeps the rest of the numbers interpretable.

`assets/performance_measures.R` computes the standard set and their Monte Carlo SEs in base R, as functions to call on the raw per-repetition results. 

## Before calling a write-up done

The question to answer is whether a reader can follow the argument, so read the draft as someone meeting it for the first time and check:

- Can you state, for every table and figure, which claim it supports? Can the reader, from the text alone?
- Does each claim have its evidence next to it, rather than scattered across the section?
- Is every design choice a reader might question given a reason?
- Could someone reimplement the DGPs, the methods, and the performance measures from the text alone, without opening the code?
- Are the claims scoped to what the evidence shows, including the conditions where things failed?
- Is anything in the results section that no claim needs?

Then, if the write-up is a LaTeX (`.tex`) file, hand the prose to `readable-math` for notation and derivations. If `avoid-ai-writing` (github.com/conorbronsdon/avoid-ai-writing) is installed, hand the prose to it for voice.
