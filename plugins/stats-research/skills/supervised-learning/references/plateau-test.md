# The plateau test: why one standard error

The edge rule in `SKILL.md` extends a grid only while the risk still falls toward the edge that cross-validation keeps choosing. Its plateau test averages, over the fits, the drop in cross-validated risk from the setting one extension inside the edge to the edge setting. It calls the edge a plateau when that average is less than one standard error of one fit's cross-validated risk at the edge setting. This file gives the reason for that tolerance, and the check behind the two stopping signals that fail on a plateau.

## Why one standard error

One standard error is the tolerance of the one-standard-error rule, which treats settings whose cross-validated risks differ by less than one standard error as equally good, and which `cv.glmnet` applies for `lambda.1se`. Near a plateau the risk curve flattens, so the next extension would gain less than the drop, and a drop below one standard error bounds that gain.

## Why the other stopping signals fail

The share of edge choices does not fall on a plateau, because noise decides among nearly equal settings, and the edge keeps winning however far the grid extends. In a check with a lasso whose best penalty was close to 0, at $n = 500$, the smallest penalty on the path won in about half of 400 repetitions, whether the path ended at $10^{-3}$ or at $10^{-8}$ times the largest penalty. The plateau test would have stopped the path at $10^{-2}$.

A significance test of the drop fails as well. The standard error of the average drop shrinks as fits are added, so the test finds ever smaller falls, and the number of extensions it calls for grows with the number of repetitions.
