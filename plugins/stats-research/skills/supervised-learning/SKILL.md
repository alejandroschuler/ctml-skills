---
name: supervised-learning
description: How to choose machine-learning learners, set their hyperparameters, and build and check cross-validated libraries, such as a super learner over tuned boosting, MARS, random forests and elastic nets. Use whenever any supervised machine learning is done, or similar loss-based learning such as Riesz regression, whatever the purpose: nuisance functions for TMLE, AIPW, double machine learning or other causal estimators, prediction models, learners inside a simulation, or checking a library someone else tuned. It also holds the edge rule: the setting that cross-validation selects within each learner type must not sit on the edge of its tuning grid, and when it does, the grid is too narrow in that direction and has to move.
---

# Supervised learning: learners, hyperparameters, and cross-validated libraries

A learner's performance depends on its hyperparameters as much as on its type. If a library holds a learner type only at poor settings, nothing in its output says so, and a comparison of estimators that use the library's predictions turns into a comparison of tuning.

The rest of this skill uses two terms. A **learner type** is a family such as gradient-boosted trees or MARS. A **setting** is one full choice of a learner type's hyperparameters. The skill applies to any learner fit by minimizing a loss: regression and classification, and also Riesz regression, which learns a Riesz representer by minimizing the Riesz loss. It covers which learner types to use, which hyperparameters to fix and which to tune, how to check a tuning grid after the fits, and what keeps a library's runtime sane. Inside a simulation, `design-and-report-simulations` decides whether cross-validation belongs in the study at all and how to cache its fits across repetitions.

## Choosing learners

| Learner type | Speed | Notes |
|---|---|---|
| **MARS** (multivariate adaptive regression splines, `earth`) | Very fast | Works well with one set of hyperparameters. Set the interaction degree high enough and keep pruning on. |
| **Random forests** (ranger) | Fast | Fine on defaults. Worse for smooth functions. |
| **Gradient-boosted trees** (lightgbm, xgboost) | Fast | Beats almost everything. Needs tuning over number of trees, depth, learning rate. Use early stopping. |
| **Elastic net** | Fast (ridge) | Loses under moderate nonlinearity. Good as a baseline. Needs regularization tuning. |
| **Kernel ridge** | Slow | Good for smooth functions and easy to analyze theoretically. Only for $n < 1000$. |

In Python, `HistGradientBoosting{Regressor,Classifier}` from scikit-learn is the fast tabular default and needs no extra dependency. MARS has no maintained Python implementation, so gradient-boosted trees take its place there. For Riesz regression, a learner type qualifies only if its implementation can minimize the Riesz loss.

Deep learning is worth avoiding unless you specifically need a differentiable model, a custom loss, or fine-tuning. It is hard to tune and gradient boosting wins on tabular data.

## Fixed and tuned hyperparameters

Every hyperparameter is either fixed or tuned, and each needs a reason. A fixed value is a default known to work, a value the analysis requires, or a value too expensive to vary. A tuned value comes from cross-validation over a grid. Record which is which. The fixed values and the grids are both part of the method, and a reader needs both to reimplement it.

A learner that tunes itself, such as `cv.glmnet` or a learner wrapped in its own cross-validation, has a grid too, even if nobody wrote it down. The rule below applies to it in the same way.

## The edge rule

When cross-validation chooses among settings of one learner type, the setting it chooses should never sit on the edge of the grid in any tuned hyperparameter. A choice on the edge says the best setting may lie beyond the grid, which means the library never tried that learner type at its best.

- **Check within each learner type.** Among that type's settings, take the one with the smallest cross-validated risk, meaning its average loss on held-out folds, whatever loss the learner minimizes. Then see whether any of its tuned hyperparameters sits at the smallest or the largest value in its grid. The check is the same whether the library then picks one setting or weights several, as a super learner does.
- **Read it across fits.** In a simulation that means across repetitions, and in a real-data analysis across cross-fitting folds, outcomes or nuisance functions. An occasional edge choice is noise. A consistent one means the grid is too narrow in that direction and has to extend there.
- **Extend the grid without raising the runtime much.** Shift the grid rather than only widening it: drop settings at the end that cross-validation never chooses, and add the same number past the edge it keeps choosing. When two hyperparameters trade compute against each other, move along the trade instead. In boosting, a larger learning rate reaches a given training loss in fewer trees, so raising it covers more of the boosting path at the same cost.
- **Treat early stopping as a grid.** If the number of trees keeps hitting its cap, the learner wants more trees than it was given. Raise the learning rate rather than the cap, so the runtime stays flat.
- **Two kinds of edge are exempt.** Fixed hyperparameters are exempt by definition. So is an edge that is a hard limit of the hyperparameter, such as a tree depth of 1, or an elastic-net mixing weight of 0 (ridge) or 1 (lasso). The grid cannot extend past such a limit, and a choice there is a finding about the data.

The check costs almost nothing if each fit stores the cross-validated risk of every setting next to its predictions. Then no refitting is needed to run it, or to run it again after the grid moves.

## Building a library

- Give every setting in the library the same cross-validation folds. Their cross-validated predictions are then comparable, and the rule that combines them can use them together.
- Include a simple parametric learner, such as a main-terms GLM, as a floor.
- Enter each setting of a tuned learner type into the library separately. That is what makes each setting's cross-validated risk available to the edge check.

## Compute

- When an outer loop already runs fits in parallel (cross-fitting folds, simulation repetitions, bootstrap draws), give each fit one thread. xgboost, lightgbm and scikit-learn's gradient boosting use all cores by default, and ranger uses two. On small datasets the threads spend their time contending for cores. In the Python scaffold of `design-and-report-simulations`, the default thread count ran about 16 times slower.
- Give each learner with internal randomness a fixed seed, so a fit depends on its data and nothing else. scikit-learn's `HistGradientBoosting` learners in particular need a fixed `random_state`, since above 10,000 rows they turn on early stopping, which draws a random validation split.
