# ---------------------------------------------------------------------------
# Pilot check: can the design resolve the contrast the mockup promises?
#
# Every contrast a mockup displays reduces to a per-repetition difference d_i.
# The displayed quantity is mean(d); its Monte Carlo SE at n_sim repetitions is
# sd(d)/sqrt(n_sim). So to show a gap at k Monte Carlo SEs you need
#
#     n_sim >= (k * sd(d) / mean(d))^2
#
# This is a power calculation for the simulation itself. Run it on ~100-200
# pilot repetitions, BEFORE the full run, for every cell comparison the mockup
# promises. See references/piloting.md.
#
# Pairing matters: both methods see the same datasets, so d_i is formed within
# a repetition and sd(d) is usually far below either method's own spread.
#
# Input `results`: tidy pilot output with columns rep, DGP, est, se and a
# column naming the method (`method`, default "estimator"). Optional: lo, hi,
# p. Contrasts pair repetitions within each group of the `by` columns. When
# the design has factors beyond the DGP, such as sample size or learner
# library, name them in `by`, so that each group holds one row per repetition
# per method. To compare libraries for one estimator, set method = "library"
# and put "estimator" in `by`.
# Dependency-free base R.
# ---------------------------------------------------------------------------

pilot_contrast <- function(results,
                           measure = c("bias", "mse", "coverage", "rejection"),
                           a, b = NULL,
                           true_values = NULL,
                           k = 5,
                           n_sim_planned = NULL,
                           level = 0.95, alpha = 0.05,
                           by = "DGP", method = "estimator") {

  measure <- match.arg(measure)
  if (measure %in% c("bias", "mse", "coverage") && is.null(true_values))
    stop("`true_values` is required for measure '", measure,
         "': a named vector of the true estimand per DGP")

  groups <- split(results, results[by], drop = TRUE)
  out <- lapply(groups, function(g) {
    d <- .pilot_d(g, measure, a, b, true_values[[g$DGP[1]]], level, alpha, method)
    cbind(as.data.frame(g[1, by, drop = FALSE]),
          .pilot_verdict(d, measure, a, b, k, n_sim_planned))
  })
  res <- do.call(rbind, out)
  rownames(res) <- NULL
  res
}

# --- build the per-repetition difference d_i -------------------------------
.pilot_d <- function(g, measure, a, b, theta, level, alpha, method) {
  pick <- function(m) {
    r <- g[g[[method]] == m, , drop = FALSE]
    if (!nrow(r)) stop(method, " '", m, "' not found in DGP '", g$DGP[1], "'")
    # A repeated rep means another design factor varies inside the group, and
    # pairing on rep would silently match rows from different cells.
    if (anyDuplicated(r$rep))
      stop("`rep` repeats for ", method, " '", m, "' within one group. Name ",
           "the other design factors in `by`, e.g. by = c(\"DGP\", \"n_obs\", \"library\").")
    r[order(r$rep), , drop = FALSE]
  }
  A <- pick(a)
  B <- if (is.null(b)) NULL else pick(b)
  if (!is.null(B)) {
    keep <- intersect(A$rep, B$rep)          # pair strictly on rep
    A <- A[A$rep %in% keep, ]; B <- B[B$rep %in% keep, ]
  }

  covers <- function(r) {
    if (all(c("lo", "hi") %in% names(r))) {
      r$lo <= theta & theta <= r$hi
    } else {
      z <- qnorm(1 - (1 - level) / 2)
      (r$est - z * r$se <= theta) & (theta <= r$est + z * r$se)
    }
  }
  rejects <- function(r) {
    if ("p" %in% names(r)) r$p <= alpha
    else abs(r$est) >= qnorm(1 - alpha / 2) * r$se
  }

  stat <- switch(measure,
    bias      = function(r) r$est - theta,
    mse       = function(r) (r$est - theta)^2,
    coverage  = function(r) as.numeric(covers(r)),
    rejection = function(r) as.numeric(rejects(r)))

  dA <- stat(A)
  if (!is.null(B)) dA - stat(B)
  else if (measure == "coverage") dA - level     # against nominal
  else dA                                        # against zero
}

.pilot_verdict <- function(d, measure, a, b, k, n_planned) {
  d <- d[is.finite(d)]
  n_pilot <- length(d)
  gap <- mean(d); sd_d <- sd(d)

  # The pilot's own gap estimate is noisy, and sizing the full run on the point
  # estimate inherits that noise: a gap that happened to come out large gives
  # an n_sim that is too small, so the full run lands short of k MCSEs. Two
  # guards. First, report how well the PILOT itself resolves the gap. Second,
  # size the run on a conservative lower bound for |gap| rather than the point
  # estimate. n_sim_required is the optimistic number; use n_sim_safe.
  #
  # A d that never varies (every pilot rep covered, say) has an unknown SD,
  # not a zero one, and sizing on sd = 0 would advise n_sim >= 0.
  no_spread <- !is.finite(sd_d) || sd_d == 0
  se_gap  <- sd_d / sqrt(n_pilot)
  pilot_z <- if (no_spread) NA_real_ else abs(gap) / se_gap
  gap_lo  <- if (no_spread) NA_real_ else max(0, abs(gap) - qnorm(0.975) * se_gap)

  need  <- if (no_spread) NA_real_ else if (gap == 0) Inf else ceiling((k * sd_d / abs(gap))^2)
  safe  <- if (no_spread) NA_real_ else if (gap_lo <= 0) Inf else ceiling((k * sd_d / gap_lo)^2)
  mcse_planned <- if (is.null(n_planned) || no_spread) NA_real_ else sd_d / sqrt(n_planned)
  z_planned    <- if (is.null(n_planned) || no_spread) NA_real_ else abs(gap) / mcse_planned

  verdict <- if (no_spread) {
    sprintf(paste0("NO SPREAD: d took the same value in all %d pilot reps, so its SD is ",
                   "unknown rather than zero (common for coverage and rejection ",
                   "contrasts). Enlarge the pilot."), n_pilot)
  } else if (pilot_z < 2) {
    sprintf(paste0("PILOT TOO SMALL: the gap is not distinguishable from zero in the pilot ",
                   "itself (|z| = %.2f on %d reps), so any n_sim estimate here is noise. ",
                   "Enlarge the pilot%s, or treat the contrast as unresolvable."),
            pilot_z, n_pilot,
            if (gap == 0) "" else paste0(" to >= ", format(ceiling((2 * sd_d / abs(gap))^2),
                                                         big.mark = ",", scientific = FALSE),
                                         " reps"))
  } else if (!is.finite(safe)) {
    "DEAD: no gap the pilot can detect. Redesign or drop the cell."
  } else if (!is.null(n_planned) && safe <= n_planned) {
    sprintf("OK at planned n_sim = %d (gap is %.1f MCSEs; safe requirement %d)",
            n_planned, z_planned, safe)
  } else if (safe <= 50000) {
    sprintf("RAISE n_sim to >= %d (optimistic %d, planned %s)", safe, need,
            if (is.null(n_planned)) "unset" else as.character(n_planned))
  } else {
    sprintf(paste0("REDESIGN: needs n_sim >= %s. Amplify the signal in the DGP, ",
                   "change what the table displays, or change n_obs."),
            format(safe, big.mark = ",", scientific = FALSE))
  }

  data.frame(
    measure = measure,
    contrast = if (is.null(b)) a else paste(a, "-", b),
    n_pilot = n_pilot, gap = gap, sd_d = sd_d, pilot_z = pilot_z,
    mcse_at_planned = mcse_planned, mcse_multiples = z_planned,
    n_sim_required = need, n_sim_safe = safe, verdict = verdict,
    stringsAsFactors = FALSE
  )
}

# --- sweep every pair of methods -------------------------------------------
pilot_sweep <- function(results, measure, true_values, k = 5, n_sim_planned = NULL,
                        method = "estimator", ...) {
  ms <- unique(results[[method]])
  pairs <- utils::combn(ms, 2, simplify = FALSE)
  do.call(rbind, lapply(pairs, function(p)
    pilot_contrast(results, measure, p[1], p[2], true_values, k, n_sim_planned,
                   method = method, ...)))
}

# --- equivalence: for claims that two methods perform the SAME -------------
# A small gap with a large MCSE is an unresolvable design, not evidence of
# equivalence. State the largest difference `margin` that still counts as
# equivalent, then size the run so the interval for the gap fits inside it.
pilot_equivalence <- function(results, measure, a, b, true_values,
                              margin, k = 2, ...) {
  r <- pilot_contrast(results, measure, a, b, true_values, k = k, ...)
  r$margin <- margin
  spread <- is.finite(r$sd_d) & r$sd_d > 0
  r$n_sim_required <- ifelse(spread, ceiling((2 * k * r$sd_d / margin)^2), NA_real_)
  r$n_sim_safe <- r$n_sim_required
  r$verdict <- ifelse(spread,
                      sprintf("equivalence within %.4g needs n_sim >= %s", margin,
                              format(r$n_sim_required, big.mark = ",", scientific = FALSE)),
                      r$verdict)   # keeps the NO SPREAD message
  r
}
