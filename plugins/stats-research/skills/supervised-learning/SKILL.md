---
name: supervised-learning
description: 'Chooses machine-learning learners, sets their hyperparameters, and builds and checks cross-validated libraries that take one learner type from each family, such as a super learner over an elastic net, MARS, tuned boosting and a small neural net, where a random forest would duplicate the boosting. Use whenever supervised machine learning, or similar loss-based learning such as Riesz regression, is in play, whatever the purpose: nuisance functions for TMLE, AIPW, double machine learning or other causal estimators, prediction models, learners inside a simulation, or checking a library someone else tuned. It covers how to split data for tuning and cross-fitting, with a simulation default of separate training, validation and estimation draws of the same size; how to set up and tune gradient boosting in xgboost; and the edge rule: when cross-validation keeps selecting a setting on the edge of a tuning grid, the grid has to move if the risk still falls toward that edge, and stays if the risk has flattened there.'
---

# Supervised learning: learners, hyperparameters, and cross-validated libraries

If a library holds a learner type only at poor settings, nothing in its output says so, and a comparison of estimators that use the library's predictions turns into a comparison of tuning.

The rest of this skill uses three terms. A **learner type** is a learning algorithm, such as gradient-boosted trees or MARS. A **setting** is one full choice of a learner type's hyperparameters. A **family** is a group of learner types whose fits are built from the same kind of pieces, such as all the learner types made of trees. The skill applies to any learner fit by minimizing a loss: regression and classification, and also Riesz regression, which learns a Riesz representer by minimizing the Riesz loss. Inside a simulation, `design-and-report-simulations` covers how to cache the fits across repetitions.

## Choosing learners

| Learner type | Speed | Notes |
|---|---|---|
| **MARS** (multivariate adaptive regression splines; `earth` in R, `pymars` in Python) | Very fast | Works well with one set of hyperparameters. Set the interaction degree high enough and keep pruning on. |
| **Random forests** (ranger) | Fast | Fine on defaults. Worse for smooth functions. Same family as gradient-boosted trees, which usually do better once tuned. |
| **Gradient-boosted trees** (xgboost; lightgbm if xgboost cannot be used) | Fast | Beats almost everything. Needs tuning over depth, number of trees and learning rate, as the section on boosting below says. |
| **Elastic net** | Fast (ridge) | Loses under moderate nonlinearity. Good as a baseline. Needs regularization tuning. Covers lasso, ridge and the main-terms generalized linear model (GLM). |
| **Kernel ridge** | Slow | Good for smooth functions and easy to analyze theoretically. Only for $n < 1000$. |
| **Small neural net** (one or two hidden layers) | Moderate | Same family as kernel ridge, and takes its place from 1000 observations up. Needs tuning over width and weight decay. |

For MARS in Python, use `pymars.EarthRegressor` or `pymars.EarthClassifier`, both scikit-learn estimators, installed with `pip install git+https://github.com/alejandroschuler/mars`. Install it from that repository and not from PyPI, where the `mars-earth` package is older upstream code with the same import name. Set `max_degree`, the interaction degree, since its default is 1, as in earth. For Riesz regression, a learner type qualifies only if its implementation can minimize the Riesz loss.

Deeper networks are worth avoiding unless you specifically need a differentiable model, a custom loss, or fine-tuning. They are hard to tune and gradient boosting wins on tabular data.

## Fixed and tuned hyperparameters

Every hyperparameter is either fixed or tuned, and each needs a reason. A fixed value is a default known to work, a value the analysis requires, or a value too expensive to vary. A tuned value comes from cross-validation over a grid. Record which is which. The fixed values and the grids are both part of the method, and a reader needs both to reimplement it.

A learner that tunes itself, such as `cv.glmnet` or a learner wrapped in its own cross-validation, has a grid too, even if nobody wrote it down. The edge rule below applies to it in the same way.

## Splitting the data

Two steps need data that a fit has not seen. Choosing among settings needs it, and cross-validation supplies it as held-out folds. An estimator that reads nuisance predictions, such as fitted propensity scores or outcome regressions, needs it too, and cross-fitting supplies it. Cross-fitting divides a dataset of $n$ observations into $K$ folds and predicts each fold from a fit to the other $K-1$. A real-data analysis that needs both runs a $V$-fold cross-validation inside each of the $K$ training sets. This skill calls that design the nested scheme. With the outer held-out fold used as a test set, the same design is nested cross-validation.

**In a simulation, use the three-draw split instead.** Give each simulated dataset three independent draws, each with the $n$ observations of the real-data analysis it stands for:

- a **training draw**, on which every setting of every learner type is fit once;
- a **validation draw**, on which each setting's **validation risk**, its average loss on that draw, is computed. The library chooses or weights its settings by validation risk, and the edge check of the edge rule below reads it;
- an **estimation draw**, on which the estimators run on the library's predictions. When the simulation's claim is about prediction, it is the test draw, and the library's error is measured on it.

The same fits that were evaluated on the validation draw predict the estimation draw. Do not refit on the training and validation draws together. The nested scheme does refit after its inner cross-validation, but on one training set of $(K-1)n/K$ observations, about $n$, while the training and validation draws together hold $2n$. In a simulation, validation risk takes the place of cross-validated risk, the average loss on held-out folds, and everything else this skill says about cross-validation, the edge rule included, applies to the validation draw.

**Why the three-draw split emulates the nested scheme.** Cross-fitting and cross-validation rotate the roles, so that each fit trains on most of the $n$ observations and the estimate averages over all of them. A simulation can draw new data at no cost, so it can give each role $n$ observations of its own. For an orthogonal estimator such as AIPW or TMLE, with nuisance fits that converge to the true functions fast enough, the two schemes then have the same sampling distribution to first order. The three-draw split also fits each setting once per dataset, where the nested scheme fits it $K(V+1)$ times: 30 with five folds at each level.

Two more rules go with the three-draw split.

- **Report $n$ as the size of one draw.** A dataset at $n = 500$ holds 1500 observations, and its results stand for a real-data analysis of 500. Cutting a draw of 500 into thirds would emulate an analysis of about 167.
- **Point a self-tuning learner at the validation draw.** A learner that tunes itself, such as `cv.glmnet` or boosting with early stopping, splits the training draw again unless told otherwise. Its final fit then trains on only part of the training draw, and the tuning happens where the edge check cannot see it. Score the learner's path on the validation draw instead. Each penalty on the elastic-net path, or each number of boosting rounds, is then a setting with a validation risk like any other.

**When to run the nested scheme.** With good nuisance fits, the three-draw split tracks cross-fitting closely. It can part from it in three cases:

- **The claim is about the scheme itself.** Examples are the number of folds, cross-fitting against a single sample split, and cross-validated TMLE, which cross-fits the nuisance fits that TMLE starts from, against ordinary TMLE.
- **The nuisance fits' errors move the estimate at first order.** This happens when a fit converges to the wrong function, since orthogonality removes the first-order effect of fit errors only near the true functions. It also happens for any estimator that is not orthogonal, such as inverse probability weighting or a plug-in.
- **A learner is noisy,** meaning its fits change a lot from one training sample to the next, as untuned boosting's do at $n = 500$.

When a claim about variance or coverage rests on fits like these, run the simulation cells that carry it, meaning those combinations of data-generating process and sample size, under the nested scheme as well, at pilot scale at least, and keep the three-draw split only where the two agree. Read `references/three-draw-split.md` before relying on the three-draw split for such a claim. It says how the two schemes part in each case, and it has the first-order argument step by step, the variances behind the second case, and the checks behind the numbers.

## The edge rule

When cross-validation chooses among settings of one learner type, the setting it chooses should not sit on the edge of the grid in any tuned hyperparameter while the risk still falls toward that edge. Such a choice says the best setting may lie beyond the grid, which means the library never tried that learner type at its best. An edge where the risk has flattened, which this skill calls a **plateau**, is fine. Past a plateau, a wider grid would gain less than the noise in the risk estimate.

1. **Check within each learner type.** Among that type's settings, take the one with the smallest cross-validated risk, meaning its average loss on held-out folds, whatever loss the learner minimizes. Then see whether any of its tuned hyperparameters sits at the smallest or the largest value in its grid. The check is the same whether the library then picks one setting or weights several, as a super learner does.
2. **Read it across fits.** In a simulation that means across repetitions, and in a real-data analysis across cross-fitting folds, outcomes or nuisance functions. An occasional edge choice is noise. A consistent one calls for the plateau test.
3. **Test for a plateau.** Compare the edge setting with the setting that lies as far inside the grid as the next extension would reach past the edge, with the other hyperparameters at their chosen values. Examples are a penalty ten times the smallest on the path, the round at half the cap on the number of trees, and a depth one less than the largest. The **drop** is that setting's cross-validated risk minus the edge setting's. Average the drop over the fits, and compare the average with the standard error of one fit's cross-validated risk at the edge setting: the standard deviation of that fit's held-out losses divided by the square root of their number. `cv.glmnet` reports this standard error as `cvsd`. If the average drop is less than one standard error, the edge is a plateau and the grid stays where it is. If not, the grid is too narrow in that direction and has to extend there.
4. **Extend the grid without raising the runtime much.** Shift the grid rather than only widening it: drop settings at the end that cross-validation never chooses, and add the same number past the edge it keeps choosing. When two hyperparameters trade compute against each other, move along the trade instead.

Three more rules go with the check.

- **Two other stopping signals fail on a plateau.** The share of edge choices does not fall, because noise decides among nearly equal settings, and the edge keeps winning however far the grid extends. A significance test of the drop fails as well. The standard error of the average drop shrinks as fits are added, so the test finds ever smaller falls, and the number of extensions it calls for grows with the number of repetitions. Read `references/plateau-test.md` when the user questions the test or proposes another stopping signal, or when a write-up must justify the tolerance. It has the reason for the tolerance of one standard error, and the lasso check behind the first failure.
- **Treat early stopping as a grid.** If the number of trees keeps hitting its cap and the loss has no plateau there, the learner wants more trees than it was given. Raise the learning rate rather than the cap: a larger learning rate reaches a given training loss in fewer trees, so it covers more of the boosting path at the same cost. The section on gradient-boosted trees below has the rest of the boosting grid.
- **Two kinds of edge are exempt.** Fixed hyperparameters are exempt by definition. So is an edge that is a hard limit of the hyperparameter, such as a tree depth of 1, an elastic-net mixing weight of 0 (ridge) or 1 (lasso), or the largest penalty on an elastic-net path, which sets every coefficient to zero. The grid cannot extend past such a limit, and a choice there is a finding about the data. A plateau at the smallest penalty on a path is the same kind of finding. The path runs toward the hard limit of no penalty, which a logarithmic path never reaches, and the plateau says the data want almost no penalty.

The check costs almost nothing if each fit stores the cross-validated risk of every setting, with its standard error, next to its predictions. Then no refitting is needed to run it, or to run it again after the grid moves.

## Gradient-boosted trees

Use xgboost through its scikit-learn interface, `xgboost.XGBRegressor` and `xgboost.XGBClassifier`, whenever it can minimize the loss. The rules below set it up. The values are those of xgboost 3.4.

**Keep the xgboost defaults for every hyperparameter that is not tuned.** These are no row or column subsampling (`subsample=1` and `colsample_bytree=1`), an L2 penalty of 1 on the leaf values (`reg_lambda=1`), no minimum loss reduction to split (`gamma=0`), and histogram split finding with 256 bins.

**Set no minimum number of observations per leaf.** In `XGBClassifier`, set `min_child_weight=0`. The default of 1 is a lower bound on the sum, over the observations in a child, of the second derivative of the loss. Under squared-error loss each observation adds 1, so the bound asks for one observation. Under logistic loss an observation with fitted probability $p$ adds only $p(1-p)$, at most $1/4$. The same default then asks for at least 4 observations in each leaf, and for about 100 where $p$ is near 0.01, so it holds back splits where a propensity score is near 0 or 1. Those are the regions where an error in the propensity score moves AIPW and TMLE the most. The L2 penalty keeps the leaf values finite.

**Other libraries do not share these defaults.** lightgbm and scikit-learn's `HistGradientBoosting` learners ask for at least 20 observations in each leaf (`min_child_samples` and `min_samples_leaf`), grow each tree to at most 31 leaves with no limit on its depth, and put no L2 penalty on the leaf values. `HistGradientBoosting` also turns on early stopping by itself above 10,000 rows, on a random part of the training data. If one of them has to stand in for xgboost, set its leaf minimum to 1, its depth limit to the tuned depth $d$ (with `num_leaves` $= 2^d$ in lightgbm and `max_leaf_nodes=None` in scikit-learn), and its L2 penalty to 1. In R, the SuperLearner wrapper `SL.xgboost` asks for 10 observations in each leaf (`minobspernode`, which it passes to xgboost as `min_child_weight`), and the sl3 learner `Lrnr_xgboost` stops at 20 trees. Set these values explicitly.

**Tune three hyperparameters: depth, number of trees and learning rate.**

- **Depth.** Cap it low, at about 5, with a grid such as 1 to 5. Boosting adds many trees together, and shallow trees already fit most functions. xgboost's default depth of 6 does not apply, since depth is tuned. Raise the cap only when the edge rule calls for it, which is when cross-validation keeps choosing depth 5 and the risk has no plateau there. Then shift the grid up, and drop the depths that it never chooses.
- **Number of trees.** Each depth and learning rate needs only one fit to each training set, with a cap on the number of trees (`n_estimators`). Pass the held-out data to `fit` as `eval_set`: the validation draw in a simulation, or the held-out fold in cross-validation. `evals_result()` then holds the held-out loss after every round, and `predict(X, iteration_range=(0, m))` predicts from the first $m$ trees. The round with the smallest held-out risk sets the number of trees. In the nested scheme, average the loss of each round across the inner folds, take the round with the smallest average, and refit on the whole training set with that many trees. Early stopping (`early_stopping_rounds`, an argument of the constructor) only ends a fit before the cap, and `predict` then uses the best round by itself. In the library, enter each depth and learning rate once, at its best round, and keep the loss of every round with the fit for the edge check.
- **Learning rate.** It trades against the number of trees. A smaller learning rate needs about proportionally more trees to reach the same fit, and the runtime grows with the number of trees. Set the cap from the compute budget, and then choose learning rates whose best round falls inside the cap. If the best round keeps hitting the cap and the loss has no plateau there, raise the learning rate rather than the cap, so the runtime stays flat. If the best round comes within the first few tens of trees, the steps are too coarse for the path to stop near its best point. Lower the learning rate then. A smaller rate often fits a little better, and the cap still bounds its cost.

In a simulation, one setting of the propensity score fits like this:

```python
import numpy as np
from xgboost import XGBClassifier

fit = XGBClassifier(max_depth=d, learning_rate=lr, n_estimators=500,
                    min_child_weight=0, n_jobs=1, random_state=0)
fit.fit(X_train, a_train, eval_set=[(X_val, a_val)], verbose=False)
risk = fit.evals_result()["validation_0"]["logloss"]  # one value per round
m = int(np.argmin(risk)) + 1                          # best number of trees
pi_hat = fit.predict_proba(X_est, iteration_range=(0, m))[:, 1]
```

The default held-out metrics, `rmse` for `XGBRegressor` and `logloss` for `XGBClassifier`, rank the rounds on one held-out set in the same order as the loss does. Set `eval_metric` when the library minimizes another loss.

A first grid is depths 1 to 5, learning rates 0.1 and 0.3 (the xgboost default), and a cap of 500 trees. That is 10 fits for each nuisance function. The edge rule then reads all three hyperparameters: the depth against its grid, the best round against the cap, and the learning rate against its grid. Depth 1 is a hard limit, a fit with no interactions.

## Building a library

**Take one learner type from each family.** A learner type's family depends on the pieces its fits are built from:

| Family | Fits are built from | Learner types | Use |
|---|---|---|---|
| Linear | Linear terms in the covariates | Elastic net (lasso and ridge are two of its settings), main-terms GLM | Elastic net |
| Splines | Hinge functions or smooth curves of single covariates, and their products | MARS, generalized additive models, the highly adaptive lasso (HAL) with smoothness order 1 | MARS |
| Trees | Step functions of single covariates, and their products | Gradient-boosted trees, random forests, Bayesian additive regression trees, a single tree, HAL with smoothness order 0 | Gradient-boosted trees |
| Kernels and nets | Smooth functions of all the covariates at once | Kernel ridge, Gaussian process regression, support vector machines, neural nets | Kernel ridge if $n < 1000$, else a small neural net |

Cover every family the true function might need, which means all four when nothing is known about it. The linear family goes into every library, as a floor.

Nearly every flexible learner can fit almost any function, given enough data. The families differ in what they fit well from the $n$ observations at hand, and that follows from their pieces. A sum of step functions needs many of them to follow a smooth curve, and a smooth fit needs many pieces to follow a jump. Tree and spline learners build their fits from functions of single covariates, so they need many pieces to follow a smooth function of a weighted sum of covariates, which kernels and nets fit easily.

Two learner types from one family make similar predictions, so the second adds little accuracy to a super learner. It hardly harms the super learner either: by the super learner's oracle inequality, its risk stays close to that of the best learner in its library, and the gap widens only slowly as the library grows. What a duplicate costs is runtime, since it brings its own grid of fits and its own edge check.

Within each family, the learner type in the last column usually does best.

- An elastic net covers the other linear learners. Its mixing weight runs from ridge to lasso, and its penalty path runs down to almost no penalty, which is the main-terms GLM. If cross-validation keeps picking the smallest penalty and the risk has no plateau there, extend the path down toward zero, as the edge rule says. When the covariates are few for the sample size, a main-terms GLM fits nearly the same and can be the floor instead.
- Among spline learners, MARS is very fast and works with one setting. HAL's family depends on its smoothness order. With order 1, the `hal9001` default, it fits piecewise-linear functions like MARS, far more slowly.
- Among tree learners, tuned boosting usually matches or beats a random forest, and both beat a single tree. A forest does well on its defaults, so it can stand in for boosting when there is no budget to tune boosting. With smoothness order 0, HAL fits sums of the same step functions that boosted trees add up.
- Kernel ridge and Gaussian process regression give the same predictions, since the posterior mean of Gaussian process regression is a kernel ridge fit. A small neural net fits the same kind of smooth function and scales to larger $n$.

Keep a second learner type from a family only for a reason you can state. The usual reason is a property the analysis needs and the first lacks. HAL's root-mean-squared error, for example, shrinks faster than $n^{-1/4}$ for every true function in a large nonparametric class. That is the rate that the standard conditions for orthogonal estimators such as TMLE and AIPW ask of nuisance fits, and a super learner with HAL in its library keeps the guarantee. When it is unclear whether two learner types duplicate each other, compare the super learner's risk on held-out data with and without the second one, across fits as for the edge rule. If the risk barely moves, drop it.

An elastic net, MARS, tuned boosting and a small neural net cover all four families. HAL with smoothness order 0, boosting, a single tree and a random forest cover the tree family four times and nothing else. Two implementations of one learner type, such as xgboost and lightgbm, count as one. More settings of a learner type widen its grid, which the edge rule checks, and cover no new family.

- Give every setting in the library the same cross-validation folds. Their cross-validated predictions are then comparable, and the rule that combines them can use them together.
- Enter each setting of a tuned learner type into the library separately. That is what makes each setting's cross-validated risk available to the edge check.

## Compute

- When an outer loop already runs fits in parallel (cross-fitting folds, simulation repetitions, bootstrap draws), give each fit one thread. xgboost, lightgbm and scikit-learn's gradient boosting use all cores by default, and ranger uses two. In xgboost, set `n_jobs=1`. On small datasets the threads spend their time contending for cores. In the Python scaffold of `design-and-report-simulations`, the default thread count ran about 16 times slower.
- Give each learner with internal randomness a fixed seed, so a fit depends on its data and nothing else. In xgboost that is `random_state`, which matters once rows or columns are subsampled. If scikit-learn's `HistGradientBoosting` learners are used, give them a fixed `random_state`, set `early_stopping=False`, and score the boosting rounds on the validation draw with `staged_predict`.
