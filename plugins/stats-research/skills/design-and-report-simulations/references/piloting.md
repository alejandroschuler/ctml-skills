# Piloting: can this design show what the mockup promises?

A mockup predicts that certain cells of a table will differ by enough to see. The prediction can be wrong, and a pilot tests it cheaply.

If the design cannot resolve the contrast, the cells look alike, and the output looks the same as it would if the methods did perform alike. Nothing in the output shows that the study could not answer the question. So run the check before the full run. After the full run, the options are to report an ambiguous null, to rerun everything, or to change the claim after the fact to match the numbers.

## Contents

- Reducing any contrast to a per-repetition difference: `d_i` for each measure
- The calculation: the bound on $n_{sim}$, and how to choose $k$
- The pilot's own uncertainty: the two guards, the pilot's $|z|$ and `n_sim_safe`
- What to do when the answer is bad
- Cancellation
- Claims of no difference: sizing on an equivalence margin
- Reporting the pilot

## Reducing any contrast to a per-repetition difference

Every comparison between two means over repetitions can be written as the mean of a per-repetition quantity `d_i`, because over the same repetitions the difference of two averages is the average of the differences. That covers bias, mean squared error (MSE), coverage and rejection rate, and once a comparison is in that form, one formula covers all of them. A measure that is not a mean over repetitions, such as the empirical standard error (SE) or a variance ratio, needs a bootstrap instead, as in the last row of the table.

| What the mockup compares | `d_i` for repetition `i` |
|---|---|
| Bias of A vs bias of B | $\hat\theta_{A,i} - \hat\theta_{B,i}$ |
| MSE of A vs MSE of B | $(\hat\theta_{A,i} - \theta)^2 - (\hat\theta_{B,i} - \theta)^2$ |
| Coverage of A vs coverage of B | $\mathbf{1}(\text{A covers}_i) - \mathbf{1}(\text{B covers}_i)$ |
| Rejection rate of A vs B | $\mathbf{1}(p_{A,i} \le \alpha) - \mathbf{1}(p_{B,i} \le \alpha)$ |
| Bias of one method against zero | $\hat\theta_i - \theta$ |
| Coverage of one method against nominal | $\mathbf{1}(\text{covers}_i) - (1 - \alpha)$ |
| Variance ratio, A vs B | use the log ratio, $\log(\widehat{\text{EmpSE}}_A^2 / \widehat{\text{EmpSE}}_B^2)$, bootstrapped over repetitions |

The displayed quantity is $\bar d$. Repetitions are independent, so its Monte Carlo SE at $n_{sim}$ repetitions is $\mathrm{sd}(d)/\sqrt{n_{sim}}$.

Pairing makes the check more precise. Both methods see the same simulated datasets, so $d_i$ is computed within a repetition, and $\mathrm{sd}(d)$ is usually much smaller than either method's own spread. A design that looks hopeless when the two methods are treated as independent is often resolvable once paired, so run the check instead of guessing.

## The calculation

Displaying a gap of $\bar d$ at $k$ Monte Carlo SEs means the gap divided by its Monte Carlo SE is at least $k$:

$$\frac{|\bar d|}{\mathrm{sd}(d)/\sqrt{n_{sim}}} \;\ge\; k .$$

Multiplying both sides by the positive number $\mathrm{sd}(d)/|\bar d|$ gives $\sqrt{n_{sim}} \ge k \cdot \mathrm{sd}(d)/|\bar d|$. Both sides are nonnegative, so squaring keeps the inequality, and it removes the absolute value:

$$n_{sim} \;\ge\; \left( \frac{k \cdot \mathrm{sd}(d)}{\bar d} \right)^{2}$$

The left side of the first inequality grows with $n_{sim}$, so this bound is the smallest run that works, and any larger run works too. Round it up. There is no finite solution when $\bar d = 0$. When the mockup promises several comparisons, the full run has to satisfy all of them, so the largest bound sets $n_{sim}$. Throughout, $\bar d$ and $\mathrm{sd}(d)$ stand for the true gap and spread, which the pilot only estimates. The next section is about the error this causes.

This is a power calculation for the simulation itself. The effect is the gap the table is built to show, and the noise is Monte Carlo error, which more repetitions reduce.

Choosing $k$: 2 is the minimum and leaves a gap a reader can dispute, 3 makes the gap visible, and 5 is a comfortable default for a headline table. These labels come from a simple calculation. At the bound, the full run's gap divided by its Monte Carlo SE is roughly normal with mean $k$ and SD 1, so it clears 1.96 with probability about $\Phi(k - 1.96)$, where $\Phi$ is the standard normal distribution function: 52% at $k = 2$, 85% at $k = 3$, and 99.9% at $k = 5$. For a claim of *no* difference, use the equivalence section below instead.

## The pilot's own uncertainty

Both $\bar d$ and $\mathrm{sd}(d)$ come from the pilot, so the required $n_{sim}$ is an estimate. The error in the spread is the smaller problem: 100 repetitions pin $\mathrm{sd}(d)$ to about 7% when $d$ is close to normal, and to about 15% for heavy-tailed differences such as squared-error contrasts.

The error in the gap matters more. Plugging the pilot's $\bar d$ into the formula sizes a study on an effect estimated from a small sample. If the pilot's gap happened to come out large, the formula gives a small $n_{sim}$, and a full run of that size falls short of the $k$ you asked for. So sizing on the point estimate is optimistic exactly when the pilot was lucky.

There are two guards, both implemented in `../assets/pilot_check.R` and `.py`.

**Check whether the pilot can see the gap at all.** Compute the pilot's own $|z| = |\bar d| / (\mathrm{sd}(d)/\sqrt{n_{pilot}})$. Below about 2, the pilot cannot distinguish the gap from zero, so any $n_{sim}$ it implies is noise. Report that the pilot is too small to size the run, and do not report an $n_{sim}$. Then enlarge the pilot, or accept that the contrast cannot be resolved.

**Size on a lower bound, not the point estimate.** Use $|\bar d|_{\text{lo}} = \max(0,\, |\bar d| - 1.96\,\mathrm{sd}(d)/\sqrt{n_{pilot}})$ in place of $|\bar d|$. The tools report this as `n_sim_safe` alongside the optimistic `n_sim_required`; use the safe one. In a 500-study check, sizing on the point estimate delivered a median of 3.3 Monte Carlo SEs against a target of 5, while the lower bound delivered 5.2.

One identity shows how the two guards interact. Substituting $|\bar d| = |z| \cdot \mathrm{sd}(d)/\sqrt{n_{pilot}}$ into the bound, and $|\bar d|_{\text{lo}} = (|z| - 1.96)\,\mathrm{sd}(d)/\sqrt{n_{pilot}}$ for the lower bound, writes both requirements in terms of the pilot's own $|z|$:

$$n_{sim} \;\ge\; n_{pilot}\left(\frac{k}{|z|}\right)^{2} \;\text{ on the point estimate,} \qquad n_{sim} \;\ge\; n_{pilot}\left(\frac{k}{|z| - 1.96}\right)^{2} \;\text{ on the lower bound.}$$

A pilot that clears $|z| \ge 2$ never asks for more than $n_{pilot}(k/2)^2$ on the point estimate, which is 1,250 repetitions at $n_{pilot} = 200$ and $k = 5$. The safe requirement grows without limit as $|z|$ falls toward 1.96: at 150 pilot repetitions, $k = 5$ and $|z| = 2.01$, it is about 1.5 million.

Power calculations based on pilot effect sizes have the same problem and the same fix. It is a form of the winner's curse.

## What to do when the answer is bad

Look at the pilot's $|z|$ first. A huge `n_sim_safe` from a pilot whose $|z|$ is just above 2 says only that the lower bound on the gap is near zero. A larger pilot is the cheaper way to find out whether the gap itself is near zero. Then compare the required $n_{sim}$ with what you can afford.

**Within about 3x of affordable.** Raise $n_{sim}$. More repetitions are usually the cheapest fix in a simulation.

**10x to 1000x over.** Change the design. There are three places to change it.

- *Amplify the signal in the data-generating process (DGP).* This is usually the best option. If the grid exists to show that misspecification hurts, make the misspecification larger: more nonlinearity, stronger confounding, worse overlap, a sharper interaction. Say in the paper that the DGP was chosen to make the mechanism visible. That is what it means to archetype an extreme.
- *Change what the table displays.* A contrast on one scale may be far easier to resolve on another. Ratios often work better than differences for variance-type quantities, and a single well-chosen sample size often works better than a grid in which every cell is underpowered.
- *Change the sample size $n_{obs}$.* Many contrasts grow or shrink with the size of each simulated dataset. A comparison invisible at $n_{obs} = 5000$ can be obvious at 200, and the reverse can hold for undercoverage caused by bias.

**Beyond about 1000x.** The contrast is too small to show. Either the two methods agree in this configuration, which is a finding to report once, or the design cannot ask the question. Use theory to decide which; more compute will not help.

## Cancellation

A common reason for a designed contrast to vanish is that errors cancel, so suspect this before you conclude that the true gap is small.

For example, take a grid meant to show that a misspecified outcome model produces bias. The estimator targets a contrast between the arms' conditional mean outcomes, $\mu(1, X) - \mu(0, X)$. A working model that is wrong about both arms *in the same direction and by similar amounts* is barely wrong about their difference. The bias that the grid was built to display is then a small residual, not the full error, and it can be smaller than any affordable Monte Carlo SE.

The fix is effect heterogeneity in the covariate that the misspecification corrupts. If the model is wrong about a covariate $X_3$, give the treatment effect an $A \times X_3$ interaction, of a shape the working model cannot represent, so that the error cannot cancel across arms. To check before any repetitions, compute the plug-in's asymptotic bias directly: fit the working model on one very large dataset and compare its estimate to the truth. If that number is near zero, no $n_{sim}$ will make the cell show the bias.

The same cancellation can happen whenever an estimand is a contrast or an average. Errors that are large at each point can vanish when they are aggregated.

## Claims of no difference

A small $\bar d$ with a large Monte Carlo SE does not show that two methods perform equivalently. That is the unresolvable design again. A claim of equivalence needs an equivalence margin: state the largest difference $\Delta$ that would still count as equivalent, then choose $n_{sim}$ so the Monte Carlo SE is small enough that the confidence interval for $\bar d$ fits inside $\pm\Delta$. Roughly $n_{sim} \ge (2 k \cdot \mathrm{sd}(d) / \Delta)^2$. The factor 2 leaves room for a true gap of up to half the margin: the interval $\bar d \pm k \cdot \mathrm{sd}(d)/\sqrt{n_{sim}}$ stays inside $\pm\Delta$ whenever $|\bar d| \le \Delta/2$ and $k \cdot \mathrm{sd}(d)/\sqrt{n_{sim}} \le \Delta/2$, and solving the second condition for $n_{sim}$ gives the bound. To choose $\Delta$, you have to decide how close counts as close. `pilot_equivalence` in `../assets/pilot_check.R` and `.py` computes this bound.

## Reporting the pilot

Give the pilot a sentence or two in the paper:

- The DGP diagnostics (true estimand, overlap, variance explained, nonlinearity) go in the DGP description regardless.
- The $n_{sim}$ justification becomes concrete. For a comparison of targeted maximum likelihood estimation (TMLE) with augmented inverse probability weighting (AIPW), it could read: "$n_{sim} = 2000$, chosen from a 150-repetition pilot so that the TMLE-AIPW MSE difference under the complex DGP is resolved at 5 Monte Carlo SEs."
- If a DGP was tuned to make a mechanism visible, say so and say why. A reader who later finds out that the configuration was chosen to produce the result will trust the paper less.

Do not tune the DGP until a claim comes out true. Tune it before the full run, only to make a mechanism visible, and disclose that you did.
