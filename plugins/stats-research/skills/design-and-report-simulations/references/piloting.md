# Piloting: can this design show what the mockup promises?

A mockup asserts that certain cells of a table will differ by enough to see. That assertion can be false, and it is cheap to test and expensive to leave untested.

The reason it matters is that failure is silent. A design that cannot resolve its own contrast returns cells that look alike, which is indistinguishable from the methods genuinely performing alike. Nothing in the output says "this study was never able to answer the question". So the check has to happen before the full run, because afterwards the remaining options are to publish an ambiguous null, to re-run everything late, or to quietly change the claim to whatever the numbers did show.

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

Pairing is doing real work here. Both methods see the same simulated datasets, so $d_i$ is computed within a repetition and $\mathrm{sd}(d)$ is usually far smaller than either method's own spread. A design that looks hopeless when the two methods are treated as independent is often perfectly resolvable once paired, which is one more reason to run the check rather than reason about it.

## The calculation

Displaying a gap of $\bar d$ at $k$ Monte Carlo SEs means the gap divided by its Monte Carlo SE is at least $k$:

$$\frac{|\bar d|}{\mathrm{sd}(d)/\sqrt{n_{sim}}} \;\ge\; k .$$

Multiplying both sides by the positive number $\mathrm{sd}(d)/|\bar d|$ gives $\sqrt{n_{sim}} \ge k \cdot \mathrm{sd}(d)/|\bar d|$. Both sides are nonnegative, so squaring keeps the inequality, and it removes the absolute value:

$$n_{sim} \;\ge\; \left( \frac{k \cdot \mathrm{sd}(d)}{\bar d} \right)^{2}$$

The left side of the first inequality grows with $n_{sim}$, so this bound is the smallest run that works, and any larger run works too. Round it up. There is no finite solution when $\bar d = 0$. When the mockup promises several comparisons, the full run has to satisfy all of them, so the largest bound sets $n_{sim}$. Throughout, $\bar d$ and $\mathrm{sd}(d)$ stand for the true gap and spread, which the pilot only estimates; the next section is about the error that brings.

This is a power calculation for the simulation itself. The "effect" is the gap the table is built to show; the "noise" is Monte Carlo error, which is the one kind of noise you can buy your way out of.

Choosing $k$: 2 is the bare minimum and leaves a gap a reader can argue with, 3 makes it visible, 5 makes it comfortable and is the right default for a headline table. Those labels have a concrete reading. At the bound, the full run's gap divided by its Monte Carlo SE is roughly normal with mean $k$ and SD 1, so it clears 1.96 with probability about $\Phi(k - 1.96)$, where $\Phi$ is the standard normal distribution function: 52% at $k = 2$, 85% at $k = 3$, and 99.9% at $k = 5$. For a claim of *no* difference, this calculation is the wrong tool; see equivalence below.

## The pilot's own uncertainty, which is the easy way to fool yourself

Both $\bar d$ and $\mathrm{sd}(d)$ come from the pilot, so the required $n_{sim}$ is an estimate. The spread is the minor problem: 100 repetitions pin $\mathrm{sd}(d)$ to about 7% when $d$ is close to normal, and to about 15% for heavy-tailed differences such as squared-error contrasts.

The gap is the real problem. Plugging the pilot's $\bar d$ into the formula is sizing a study on an effect estimate from a small sample, and it fails in the familiar direction. A gap that happened to come out large gives a small $n_{sim}$, you run exactly that many, and the full study lands short of the $k$ you asked for. Sizing on the point estimate is optimistic precisely when the pilot was lucky.

Two guards, both implemented in `../assets/pilot_check.R` and `.py`.

**Check whether the pilot can see the gap at all.** Compute the pilot's own $|z| = |\bar d| / (\mathrm{sd}(d)/\sqrt{n_{pilot}})$. Below about 2, the pilot cannot distinguish the gap from zero, so every $n_{sim}$ it implies is noise dressed as a number, and the honest output is "this pilot is too small to size the run" rather than a figure someone will act on. The fix is a bigger pilot, or accepting that the contrast is unresolvable.

**Size on a lower bound, not the point estimate.** Use $|\bar d|_{\text{lo}} = \max(0,\, |\bar d| - 1.96\,\mathrm{sd}(d)/\sqrt{n_{pilot}})$ in place of $|\bar d|$. The tools report this as `n_sim_safe` alongside the optimistic `n_sim_required`; use the safe one. In a 500-study check, sizing on the point estimate delivered a median of 3.3 Monte Carlo SEs against a target of 5, while the lower bound delivered 5.2.

One identity shows how the two guards interact. Substituting $|\bar d| = |z| \cdot \mathrm{sd}(d)/\sqrt{n_{pilot}}$ into the bound, and $|\bar d|_{\text{lo}} = (|z| - 1.96)\,\mathrm{sd}(d)/\sqrt{n_{pilot}}$ for the lower bound, writes both requirements in terms of the pilot's own $|z|$:

$$n_{sim} \;\ge\; n_{pilot}\left(\frac{k}{|z|}\right)^{2} \;\text{ on the point estimate,} \qquad n_{sim} \;\ge\; n_{pilot}\left(\frac{k}{|z| - 1.96}\right)^{2} \;\text{ on the lower bound.}$$

A pilot that clears $|z| \ge 2$ never asks for more than $n_{pilot}(k/2)^2$ on the point estimate, which is 1,250 repetitions at $n_{pilot} = 200$ and $k = 5$. The safe requirement grows without limit as $|z|$ falls toward 1.96: at 150 pilot repetitions, $k = 5$ and $|z| = 2.01$, it is about 1.5 million.

This is the same winner's curse that afflicts power calculations built on pilot effect sizes, and it has the same fix.

## What to do when the answer is bad

Read the requirement against the pilot's $|z|$ first. A huge `n_sim_safe` from a pilot whose $|z|$ sits just above 2 says only that the lower bound on the gap is near zero, and a larger pilot is the cheaper way to find out whether the gap itself is. Then read the required $n_{sim}$ against what you can afford.

**Within about 3x of affordable.** Raise $n_{sim}$. Monte Carlo error is the cheapest thing in a simulation to fix, and this is the happy case.

**10x to 1000x over.** The design needs changing, and there are three places to change it.

- *Amplify the signal in the data-generating process (DGP).* Usually the best move. If the grid exists to show that misspecification hurts, make the misspecification bite harder: more nonlinearity, stronger confounding, worse overlap, a sharper interaction. Say in the paper that the DGP was chosen to make the mechanism visible, which is honest and is what archetyping extremes means.
- *Change what the table displays.* A contrast on one scale may be far more resolvable on another. Ratios often beat differences for variance-type quantities, and a single well-chosen sample size often beats a grid where every cell is underpowered.
- *Change the sample size $n_{obs}$.* Many contrasts grow or shrink with the size of each simulated dataset. A comparison invisible at $n_{obs} = 5000$ can be obvious at 200, and vice versa for bias-driven undercoverage.

**Beyond about 1000x.** The contrast is not there. Either the two methods really do agree in this configuration, which is a finding worth reporting once, or the design cannot ask the question at all. Distinguishing these two takes theory, not more compute.

## Cancellation, the usual culprit

Contrasts disappear through cancellation more often than by being small to begin with.

The canonical case: a grid meant to show that a misspecified outcome model produces bias. The estimator targets a contrast between the arms' conditional mean outcomes, $\mu(1, X) - \mu(0, X)$. A working model that is wrong about both arms *in the same direction and by similar amounts* is barely wrong about their difference, so the bias the grid was built to display is a small residual rather than the full error, and it can sit below any affordable Monte Carlo SE.

The cure is effect heterogeneity in the covariate the misspecification corrupts. If the model is wrong about a covariate $X_3$, give the treatment effect a real $A \times X_3$ interaction, of a shape the working model cannot represent, so the error cannot cancel across arms. A quick diagnostic on a large draw, before any repetitions: compute the plug-in's asymptotic bias directly by fitting the working model on one huge dataset and comparing its estimate to the truth. If that number is near zero, no $n_{sim}$ will save the cell.

The same cancellation shows up whenever an estimand is a contrast or an average. Errors that survive pointwise can vanish on aggregation.

## Claims of no difference

"These two methods perform equivalently" is not established by a small $\bar d$ with a large Monte Carlo SE, which is exactly the unresolvable design. It needs an equivalence margin: state the largest difference $\Delta$ that would still count as equivalent, then choose $n_{sim}$ so the Monte Carlo SE is small enough that the confidence interval for $\bar d$ fits inside $\pm\Delta$. Roughly $n_{sim} \ge (2 k \cdot \mathrm{sd}(d) / \Delta)^2$. The factor 2 leaves room for a true gap of up to half the margin: the interval $\bar d \pm k \cdot \mathrm{sd}(d)/\sqrt{n_{sim}}$ stays inside $\pm\Delta$ whenever $|\bar d| \le \Delta/2$ and $k \cdot \mathrm{sd}(d)/\sqrt{n_{sim}} \le \Delta/2$, and solving the second condition for $n_{sim}$ gives the bound. Saying what $\Delta$ is forces the useful question of how close counts as close.

## Reporting the pilot

The pilot earns a sentence or two in the paper, and they are load-bearing:

- The DGP diagnostics (true estimand, overlap, variance explained, nonlinearity) go in the DGP description regardless.
- The $n_{sim}$ justification becomes concrete. For a comparison of targeted maximum likelihood estimation (TMLE) with augmented inverse probability weighting (AIPW), it could read: "$n_{sim} = 2000$, chosen from a 150-repetition pilot so that the TMLE-AIPW MSE difference under the complex DGP is resolved at 5 Monte Carlo SEs."
- If a DGP was tuned to make a mechanism visible, say so and say why. A reader who finds out later that the configuration was chosen to produce the result will not be charitable about it.

A pilot used to tune the DGP until the result appears, with nothing reported, is a different activity with a worse name. The line is that you tune the DGP to make a mechanism *visible*, disclosed, before the full run; you do not tune it until a claim comes out true.
