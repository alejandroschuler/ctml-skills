# ADEMP performance measures with Monte Carlo standard errors.
# Formulas: Morris, White & Crowther (2019), Stat Med 38:2074-2102, Table 6.
#
# Dependency-free base R. If the `rsimsum` package is available, prefer it.
#
# Input: a long data frame with one row per repetition x method x DGM x estimand.
#   est   numeric, the per-repetition point estimate theta_hat_i
#   se    numeric, the per-repetition standard error (optional but strongly wanted)
#   true  numeric, the true value of the estimand, constant within a `by` group
#   lo,hi numeric, CI limits (optional; Wald limits are used if absent and `se` is present)
#   p     numeric, p-value (optional; a Wald test is used if absent and `se` is present)
#
# Failed repetitions must be present as rows with NA in `est`, so that they are
# counted rather than silently dropped.

ademp_perf <- function(d,
                       est  = "est",
                       se   = "se",
                       true = "true",
                       lo   = NULL,
                       hi   = NULL,
                       p    = NULL,
                       by   = NULL,
                       level = 0.95,
                       alpha = 0.05) {

  stopifnot(is.data.frame(d), est %in% names(d), true %in% names(d))
  if (!is.null(se) && !(se %in% names(d))) se <- NULL

  groups <- if (is.null(by)) list(d) else split(d, d[by], drop = TRUE)

  out <- lapply(seq_along(groups), function(k) {
    g <- groups[[k]]
    row <- .ademp_one(g, est, se, true, lo, hi, p, level, alpha)
    if (!is.null(by)) {
      key <- as.data.frame(g[1, by, drop = FALSE], stringsAsFactors = FALSE)
      rownames(key) <- NULL
      row <- cbind(key, row)
    }
    row
  })
  res <- do.call(rbind, out)
  rownames(res) <- NULL
  res
}

.ademp_one <- function(g, est, se, true, lo, hi, p, level, alpha) {

  theta_vals <- unique(g[[true]][!is.na(g[[true]])])
  if (length(theta_vals) != 1L)
    stop("`true` must take exactly one value within each `by` group; got ",
         length(theta_vals))
  theta <- theta_vals

  e <- g[[est]]
  n_attempted <- length(e)
  ok <- !is.na(e)
  if (!is.null(se)) ok <- ok & !is.na(g[[se]])
  n_missing <- sum(!ok)
  n <- sum(ok)
  if (n < 2L)
    stop("fewer than 2 usable repetitions in a group; nothing can be estimated")

  e <- e[ok]
  ebar <- mean(e)

  # --- bias -----------------------------------------------------------------
  bias      <- ebar - theta
  empse     <- sd(e)                                   # sqrt(sum((e-ebar)^2)/(n-1))
  bias_mcse <- empse / sqrt(n)

  # --- empirical SE ---------------------------------------------------------
  empse_mcse <- empse / sqrt(2 * (n - 1))

  # --- MSE ------------------------------------------------------------------
  sq       <- (e - theta)^2
  mse      <- mean(sq)
  mse_mcse <- sqrt(sum((sq - mse)^2) / (n * (n - 1)))

  modse <- modse_mcse <- relerr <- relerr_mcse <- NA_real_
  if (!is.null(se)) {
    v <- (g[[se]][ok])^2
    # root of the MEAN VARIANCE, not the mean of the SEs
    modse      <- sqrt(mean(v))
    var_v      <- var(v)
    modse_mcse <- sqrt(var_v / (4 * n * modse^2))
    relerr     <- 100 * (modse / empse - 1)
    relerr_mcse <- 100 * (modse / empse) *
      sqrt(var_v / (4 * n * modse^4) + 1 / (2 * (n - 1)))
  }

  # --- coverage -------------------------------------------------------------
  cov <- cov_mcse <- becov <- becov_mcse <- NA_real_
  lower <- upper <- NULL
  if (!is.null(lo) && !is.null(hi) && all(c(lo, hi) %in% names(g))) {
    lower <- g[[lo]][ok]; upper <- g[[hi]][ok]
  } else if (!is.null(se)) {
    z <- qnorm(1 - (1 - level) / 2)
    lower <- e - z * g[[se]][ok]; upper <- e + z * g[[se]][ok]
  }
  if (!is.null(lower)) {
    cov        <- mean(lower <= theta & theta <= upper)
    cov_mcse   <- sqrt(cov * (1 - cov) / n)
    becov      <- mean(lower <= ebar & ebar <= upper)
    becov_mcse <- sqrt(becov * (1 - becov) / n)
  }

  # --- rejection rate -------------------------------------------------------
  rej <- rej_mcse <- NA_real_
  if (!is.null(p) && p %in% names(g)) {
    pv  <- g[[p]][ok]
    rej <- mean(pv <= alpha, na.rm = TRUE)
  } else if (!is.null(se)) {
    z   <- qnorm(1 - alpha / 2)
    rej <- mean(abs(e) >= z * g[[se]][ok])
  }
  if (!is.na(rej)) rej_mcse <- sqrt(rej * (1 - rej) / n)

  data.frame(
    n_attempted = n_attempted, n_missing = n_missing, n_sim = n,
    bias = bias,   bias_mcse = bias_mcse,
    empse = empse, empse_mcse = empse_mcse,
    mse = mse,     mse_mcse = mse_mcse,
    modse = modse, modse_mcse = modse_mcse,
    relerr_modse = relerr, relerr_modse_mcse = relerr_mcse,
    coverage = cov,   coverage_mcse = cov_mcse,
    becoverage = becov, becoverage_mcse = becov_mcse,
    rejection = rej,  rejection_mcse = rej_mcse,
    stringsAsFactors = FALSE
  )
}

# ---------------------------------------------------------------------------
# Relative % increase in precision of method B over reference method A.
# est_a, est_b are the per-repetition estimates from the SAME repetitions, in the
# same order. The correlation term is what makes this comparison precise; the
# two methods saw the same simulated datasets.
rel_precision <- function(est_a, est_b) {
  ok <- !is.na(est_a) & !is.na(est_b)
  a <- est_a[ok]; b <- est_b[ok]; n <- length(a)
  if (n < 2L) stop("need at least 2 complete pairs")
  se_a <- sd(a); se_b <- sd(b)
  ratio <- (se_a / se_b)^2
  rho   <- cor(a, b)
  data.frame(
    n_sim = n,
    rel_pct_increase_precision = 100 * (ratio - 1),
    mcse = 200 * ratio * sqrt((1 - rho^2) / (n - 1)),
    corr = rho
  )
}

# Monte Carlo SE of the DIFFERENCE in a mean-type performance measure between
# two methods run on the same repetitions. Use this, not the two separate MCSEs,
# whenever the write-up claims one method beats another.
mcse_diff <- function(x_a, x_b) {
  ok <- !is.na(x_a) & !is.na(x_b)
  d  <- x_a[ok] - x_b[ok]; n <- length(d)
  if (n < 2L) stop("need at least 2 complete pairs")
  data.frame(n_sim = n, diff = mean(d), mcse = sd(d) / sqrt(n))
}

# ---------------------------------------------------------------------------
# Required n_sim for a target Monte Carlo SE.
nsim_for_bias <- function(sd_est, mcse_req) sd_est^2 / mcse_req^2
# coverage arguments are PERCENTAGES, e.g. expected = 95, mcse_req = 0.5
nsim_for_coverage <- function(expected = 95, mcse_req) {
  expected * (100 - expected) / mcse_req^2
}

# ---------------------------------------------------------------------------
# Round an estimate to the precision its Monte Carlo SE supports:
# give the MCSE `sig` significant figures, then match the estimate to that
# decimal place. Returns a character vector "est (mcse)".
# sig = 1 is the default and the stricter choice; sig = 2 is also defensible.
fmt_mcse <- function(est, mcse, sig = 1) {
  dp <- pmax(0, ceiling(-log10(abs(mcse))) + sig - 1)
  dp[!is.finite(dp)] <- 3
  mapply(function(e, m, k) sprintf("%.*f (%.*f)", k, e, k, m),
         est, mcse, dp, USE.NAMES = FALSE)
}
