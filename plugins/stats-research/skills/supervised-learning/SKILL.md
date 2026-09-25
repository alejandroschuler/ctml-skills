---
name: supervised-learning
description: How to choose machine-learning learners, set their hyperparameters, and build and check cross-validated libraries that take one learner type from each family, such as a super learner over an elastic net, MARS, tuned boosting and a small neural net, where a random forest would duplicate the boosting. Use whenever any supervised machine learning is done, or similar loss-based learning such as Riesz regression, whatever the purpose: nuisance functions for TMLE, AIPW, double machine learning or other causal estimators, prediction models, learners inside a simulation, or checking a library someone else tuned. It sets how to split data for tuning and cross-fitting, with a simulation default of separate training, validation and estimation draws of the same size. It also holds the edge rule: the setting that cross-validation selects within each learner type must not sit on the edge of its tuning grid, and when it does, the grid is too narrow in that direction and has to move.
---

# Supervised learning: learners, hyperparameters, and cross-validated libraries

A learner's performance depends on its hyperparameters as much as on its type. If a library holds a learner type only at poor settings, nothing in its output says so, and a comparison of estimators that use the library's predictions turns into a comparison of tuning.

The rest of this skill uses three terms. A **learner type** is a learning algorithm, such as gradient-boosted trees or MARS. A **setting** is one full choice of a learner type's hyperparameters. A **family** is a group of learner types whose fits are built from the same kind of pieces, such as all the learner types made of trees. The skill applies to any learner fit by minimizing a loss: regression and classification, and also Riesz regression, which learns a Riesz representer by minimizing the Riesz loss. It covers which learner types to use, which hyperparameters to fix and which to tune, how to split the data for fitting, tuning and estimation, how to check a tuning grid after the fits, and what keeps a library's runtime sane. Inside a simulation, `design-and-report-simulations` covers how to cache the fits across repetitions.

## Choosing learners

| Learner type | Speed | Notes |
|---|---|---|
| **MARS** (multivariate adaptive regression splines, `earth`) | Very fast | Works well with one set of hyperparameters. Set the interaction degree high enough and keep pruning on. |
| **Random forests** (ranger) | Fast | Fine on defaults. Worse for smooth functions. Same family as gradient-boosted trees, which usually do better once tuned. |
| **Gradient-boosted trees** (lightgbm, xgboost) | Fast | Beats almost everything. Needs tuning over number of trees, depth, learning rate. Use early stopping. |
| **Elastic net** | Fast (ridge) | Loses under moderate nonlinearity. Good as a baseline. Needs regularization tuning. Covers lasso, ridge and the main-terms generalized linear model (GLM). |
| **Kernel ridge** | Slow | Good for smooth functions and easy to analyze theoretically. Only for $n < 1000$. |
| **Small neural net** (one or two hidden layers) | Moderate | Same family as kernel ridge, and takes its place from 1000 observations up. Needs tuning over width and weight decay. |

In Python, `HistGradientBoosting{Regressor,Classifier}` from scikit-learn is the fast tabular default and needs no extra dependency. MARS has no maintained Python implementation. A generalized additive model from `pygam` can stand in for it there, but it fits interactions only through tensor-product terms that you add by hand, while MARS searches for them. For Riesz regression, a learner type qualifies only if its implementation can minimize the Riesz loss.

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

**Why the three-draw split emulates the nested scheme.** Cross-fitting and cross-validation rotate the roles. Each observation is held out of one of the $K$ fits and trains the other $K-1$, so the estimate averages over all $n$ observations and each fit trains on most of them. The inner cross-validation does the same inside each training set. A simulation can draw new data at no cost, so it can give each role $n$ observations of its own and skip the rotation.

Take an orthogonal estimator, such as augmented inverse probability weighting (AIPW) or targeted maximum likelihood estimation (TMLE). Orthogonal means that small errors in the nuisance fits, near the true functions, have no first-order effect on the estimate. If its nuisance fits converge to the true functions fast enough, both schemes give the true value, plus an average over $n$ independent observations of the efficient influence function, a fixed function of one observation, plus terms that shrink faster than $1/\sqrt{n}$. The two estimators then have the same sampling distribution to first order. Training on $n$ observations instead of the $(K-1)n/K$ in each cross-fitting training set changes only the smaller terms.

The three-draw split is also cheaper. It fits each setting once per dataset. The nested scheme fits it $K(V+1)$ times: in each of the $K$ training sets, $V$ times for the inner cross-validation and once more on the whole training set. With five folds at each level, that is 30 fits.

Two more rules go with the three-draw split.

- **Report $n$ as the size of one draw.** A dataset at $n = 500$ holds 1500 observations, and its results stand for a real-data analysis of 500. Cutting a draw of 500 into thirds would emulate an analysis of about 167.
- **Point a self-tuning learner at the validation draw.** A learner that tunes itself, such as `cv.glmnet` or boosting with early stopping, splits the training draw again unless told otherwise. Its final fit then trains on only part of the training draw, and the tuning happens where the edge check cannot see it. Score the learner's path on the validation draw instead. Each penalty on the elastic-net path, or each number of boosting rounds, is then a setting with a validation risk like any other.

**When to run the nested scheme.** With good nuisance fits, the three-draw split tracks cross-fitting closely. It can part from it in three cases:

- **The claim is about the scheme itself.** Examples are the number of folds, cross-fitting against a single sample split, and cross-validated TMLE, which cross-fits the nuisance fits that TMLE starts from, against ordinary TMLE.
- **The nuisance fits' errors move the estimate at first order.** This happens when a fit converges to the wrong function, since orthogonality removes the first-order effect of fit errors only near the true functions. It also happens for any estimator that is not orthogonal, such as inverse probability weighting or a plug-in. Under cross-fitting, those errors come from the same observations as the estimate and can partly cancel its own error. An independent training draw removes the cancellation, so the errors add variance instead. With a correct logistic propensity model and an outcome regression that left out a confounder, the spread of the three-draw split's AIPW estimates across repetitions, its empirical standard error, was twice that of cross-fitting, and its 95% intervals covered 87% of the time, against 99.8% under cross-fitting.
- **A learner is noisy,** meaning its fits change a lot from one training sample to the next, as untuned boosting's do at $n = 500$. Cross-fitting's smaller training sets raise the standard error it reports, and its average over $K$ fits lowers the actual spread of its estimates. With untuned boosting, 5-fold cross-fitting's intervals covered 98% of the time and the three-draw split's 95%.

When a claim about variance or coverage rests on fits like these, run the simulation cells that carry it, meaning those combinations of data-generating process and sample size, under the nested scheme as well, at pilot scale at least, and keep the three-draw split only where the two agree. Read `references/three-draw-split.md` before relying on the three-draw split for such a claim. It has the first-order argument step by step, the variances behind the second case, and the checks behind these numbers.

## The edge rule

When cross-validation chooses among settings of one learner type, the setting it chooses should never sit on the edge of the grid in any tuned hyperparameter. A choice on the edge says the best setting may lie beyond the grid, which means the library never tried that learner type at its best.

- **Check within each learner type.** Among that type's settings, take the one with the smallest cross-validated risk, meaning its average loss on held-out folds, whatever loss the learner minimizes. Then see whether any of its tuned hyperparameters sits at the smallest or the largest value in its grid. The check is the same whether the library then picks one setting or weights several, as a super learner does.
- **Read it across fits.** In a simulation that means across repetitions, and in a real-data analysis across cross-fitting folds, outcomes or nuisance functions. An occasional edge choice is noise. A consistent one means the grid is too narrow in that direction and has to extend there.
- **Extend the grid without raising the runtime much.** Shift the grid rather than only widening it: drop settings at the end that cross-validation never chooses, and add the same number past the edge it keeps choosing. When two hyperparameters trade compute against each other, move along the trade instead. In boosting, a larger learning rate reaches a given training loss in fewer trees, so raising it covers more of the boosting path at the same cost.
- **Treat early stopping as a grid.** If the number of trees keeps hitting its cap, the learner wants more trees than it was given. Raise the learning rate rather than the cap, so the runtime stays flat.
- **Two kinds of edge are exempt.** Fixed hyperparameters are exempt by definition. So is an edge that is a hard limit of the hyperparameter, such as a tree depth of 1, an elastic-net mixing weight of 0 (ridge) or 1 (lasso), or the largest penalty on an elastic-net path, which sets every coefficient to zero. The grid cannot extend past such a limit, and a choice there is a finding about the data.

The check costs almost nothing if each fit stores the cross-validated risk of every setting next to its predictions. Then no refitting is needed to run it, or to run it again after the grid moves.

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

A super learner gains from learners whose errors differ. Two learner types from one family make similar predictions, so the second adds little accuracy. It hardly harms the super learner either: by the super learner's oracle inequality, its risk stays close to that of the best learner in its library, and the gap widens only slowly as the library grows. What a duplicate costs is runtime, since it brings its own grid of fits and its own edge check.

Within each family, the learner type in the last column usually does best.

- An elastic net covers the other linear learners. Its mixing weight runs from ridge to lasso, and its penalty path runs down to almost no penalty, which is the main-terms GLM. If cross-validation keeps picking the smallest penalty, extend the path down toward zero, as the edge rule says. When the covariates are few for the sample size, a main-terms GLM fits nearly the same and can be the floor instead.
- Among spline learners, MARS is very fast and works with one setting. HAL's family depends on its smoothness order. With order 1, the `hal9001` default, it fits piecewise-linear functions like MARS, far more slowly.
- Among tree learners, tuned boosting usually matches or beats a random forest, and both beat a single tree. A forest does well on its defaults, so it can stand in for boosting when there is no budget to tune boosting. With smoothness order 0, HAL fits sums of the same step functions that boosted trees add up.
- Kernel ridge and Gaussian process regression give the same predictions: the posterior mean of Gaussian process regression is the kernel ridge fit, with the process's covariance as the kernel and its noise variance as the penalty. A small neural net fits the same kind of smooth function and scales to larger $n$.

Keep a second learner type from a family only for a reason you can state. The usual reason is a property the analysis needs and the first lacks. HAL's root-mean-squared error, for example, shrinks faster than $n^{-1/4}$ for every true function in a large nonparametric class. That is the rate that the standard conditions for orthogonal estimators such as TMLE and AIPW ask of nuisance fits, and a super learner with HAL in its library keeps the guarantee. When it is unclear whether two learner types duplicate each other, compare the super learner's risk on held-out data with and without the second one, across fits as for the edge rule. If the risk barely moves, drop it.

An elastic net, MARS, tuned boosting and a small neural net cover all four families. HAL with smoothness order 0, boosting, a single tree and a random forest cover the tree family four times and nothing else. Two implementations of one learner type, such as xgboost and lightgbm, count as one. More settings of a learner type widen its grid, which the edge rule checks, and cover no new family.

- Give every setting in the library the same cross-validation folds. Their cross-validated predictions are then comparable, and the rule that combines them can use them together.
- Enter each setting of a tuned learner type into the library separately. That is what makes each setting's cross-validated risk available to the edge check.

## Compute

- When an outer loop already runs fits in parallel (cross-fitting folds, simulation repetitions, bootstrap draws), give each fit one thread. xgboost, lightgbm and scikit-learn's gradient boosting use all cores by default, and ranger uses two. On small datasets the threads spend their time contending for cores. In the Python scaffold of `design-and-report-simulations`, the default thread count ran about 16 times slower.
- Give each learner with internal randomness a fixed seed, so a fit depends on its data and nothing else. scikit-learn's `HistGradientBoosting` learners in particular need a fixed `random_state`, since above 10,000 rows they turn on early stopping, which holds out a random part of the training data. In a simulation, set `early_stopping=False` and score the boosting rounds on the validation draw instead, with `staged_predict`.
