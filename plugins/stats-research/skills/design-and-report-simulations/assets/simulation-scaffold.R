# ---------------------------------------------------------------------------
# Simulation scaffold: one pipeline from DGPs to every display.
#
# Shape follows "Simulations Done Right" (A. Schuler). In a real project these
# are separate files: dgps.R, learners.R, estimators.R, run.R, and a summary
# script per display. Kept together here so the whole pattern is visible.
#
# The pipeline runs one way, data -> predictions -> estimates -> summaries,
# and three properties keep it cheap to iterate on:
#   * Any piece runs alone. run_sim() takes a subset of every factor, and each
#     dataset's seed comes from its name, so a partial run returns the same
#     rows a full run would.
#   * Every display reads the same fits. The library table and the estimator
#     table below are two summaries of one set of predictions.
#   * Expensive steps are cached. Each base learner is fit once per dataset
#     and its predictions are stored, so a new library or estimator refits
#     nothing.
#
# Run as a script (Rscript simulation-scaffold.R) for a demo, or source() it.
# ---------------------------------------------------------------------------

library(tidyverse)
library(magrittr)

CACHE_DIR <- "cache"   # local, and listed in .gitignore before the first run

# =========================== 1. DGPs =======================================

simple_dgp <- structure(list(
    rho   = \(w1, w2) w1 + w2,
    mu    = \(a, w1, w2) w1 + w2 + a,
    sigma = 1
), class = "dgp")

complex_dgp <- structure(list(
    rho   = \(w1, w2) w1 + w2 + w1 * abs(w2),
    # heterogeneous effect: the a * (...) term is what makes the ATE nonzero.
    # Check this. A mean function with no treatment term is a silent ATE of 0.
    mu    = \(a, w1, w2) w1 + w2 + abs(w2) + 0.5 * w1 * w2 + a * (1 + 0.5 * w1),
    sigma = 1
), class = "dgp")

DGPS <- list(simple = simple_dgp, complex = complex_dgp)

draw <- function(x, ...) UseMethod("draw")
draw.dgp <- \(dgp, n) dgp %$% tibble(
    W1 = runif(n, -1, 1),
    W2 = runif(n, -1, 1),
    A  = rbinom(n, 1, plogis(rho(W1, W2))),
    Y  = mu(A, W1, W2) + rnorm(n, 0, sigma)
)

# Draw under a fixed treatment rule. This is what makes the true estimand
# computable by brute force, with no closed form needed.
draw_intervene <- function(x, ...) UseMethod("draw_intervene")
draw_intervene.dgp <- \(dgp, n, treatment) dgp %$% tibble(
    W1 = runif(n, -1, 1),
    W2 = runif(n, -1, 1),
    A  = treatment(W1, W2),
    Y  = mu(A, W1, W2) + rnorm(n, 0, sigma)
)

# =========================== 2. DGP diagnostics ============================
# Run these on every DGP before trusting it, and report them next to the DGP
# description. They tell a reader what the DGPs span far better than the
# generating equations do.

# Both arms start from the same seed, so they share covariates and noise and
# their difference carries no outcome noise. Arms drawn independently would
# put a Monte Carlo error of about 0.002 into the "truth" at this n, which is
# not small next to the Monte Carlo SE of a bias estimate.
ATE <- function(x, ...) UseMethod("ATE")
ATE.dgp <- \(dgp, n = 1e6, seed = 1) {
    arm <- \(a) {
        set.seed(seed, kind = "Mersenne-Twister")
        dgp |> draw_intervene(n, \(w1, w2) a) %$% mean(Y)
    }
    arm(1) - arm(0)
}

diagnose <- function(x, ...) UseMethod("diagnose")
diagnose.dgp <- \(dgp, n = 1e5, seed = 1) {
    set.seed(seed, kind = "Mersenne-Twister")
    pop <- dgp |> draw(n) |>
        mutate(mu_true = dgp$mu(A, W1, W2),
               pi_true = plogis(dgp$rho(W1, W2)))
    mu_lin <- lm(mu_true ~ A + W1 + W2, data = pop)
    tibble(
        ate           = ATE(dgp, n),
        pi_min        = min(pop$pi_true),       # overlap
        pi_max        = max(pop$pi_true),
        var_explained = var(pop$mu_true) / var(pop$Y),
        linear_share  = var(predict(mu_lin, pop)) / var(pop$mu_true)
    )
}

# =========================== 3. Learners and libraries =====================
# Placeholder learners that keep the pipeline running; set up real ones with
# the supervised-learning skill. The interface is what this scaffold fixes: a
# learner takes training covariates and a response and returns a prediction
# function, and everything that determines a fit lives in its definition, so
# it is part of the learner's source and so of its cache key.

LEARNERS <- list(
    glm = function(x, y, binary) {
        fit <- glm(y ~ ., data = cbind(x, y = y),
                   family = if (binary) binomial() else gaussian())
        \(newx) unname(predict(fit, newx, type = "response"))
    },
    mars = function(x, y, binary) {
        fit <- earth::earth(x, y, degree = 3, nprune = 50,
                            glm = if (binary) list(family = binomial()))
        \(newx) as.numeric(predict(fit, newx, type = "response"))
    }
)

# A library is a set of base learners. One learner is used as it is. Several
# are combined per nuisance by picking the learner with the smallest risk on
# the validation draw, the discrete super learner. The convex weights of a
# full super learner would slot into library_preds() and be fit to the same
# validation-draw predictions.
LIBRARIES <- list(glm = "glm", mars = "mars", select = c("glm", "mars"))

# =========================== 4. Seeds and cache ============================

# A dataset's seed comes from its name, never from its place in a loop, so it
# draws the same data alone as it does in the full grid. One seed per
# repetition shared across DGPs would give the complex DGP different data
# depending on whether the simple one ran first. The hash is plain base R, so
# the seeds, and the data with them, survive package upgrades; format() makes
# 1e5 and 100000L name the same cell.
seed_for <- function(...) {
    key <- map_chr(list(...), format, scientific = FALSE, trim = TRUE)
    chars <- utf8ToInt(paste(key, collapse = "|"))
    reduce(chars, \(h, ch) (31 * h + ch) %% 2147483647, .init = 0)
}

# The generator is named as well as the seed. A parallel backend can switch
# it (furrr with seed = TRUE moves workers to L'Ecuyer-CMRG), and the same
# seed under another generator is a different dataset.
set_cell_seed <- \(...) set.seed(seed_for(...), kind = "Mersenne-Twister")

# One file per entry, named by a hash of everything that determines it, so a
# hit returns exactly what recomputing would. The readable prefix shows what
# is stored and makes selective deletion easy (rm -r cache/complex/mars).
cached <- function(label, key, compute) {
    path <- file.path(CACHE_DIR, paste0(label, "_", rlang::hash(key), ".rds"))
    if (file.exists(path)) return(readRDS(path))
    value <- compute()
    dir.create(dirname(path), recursive = TRUE, showWarnings = FALSE)
    tmp <- paste0(path, ".tmp", Sys.getpid())
    saveRDS(value, tmp)
    file.rename(tmp, path)   # atomic, so a killed run leaves no half-written entry
    value
}

# Source text of the code on the path, so editing a learner changes its key.
# deparse() drops comments and source references, so a cosmetic edit or a new
# session does not.
code_of <- \(...) map(list(...), deparse)

# =========================== 5. Datasets and predictions ===================

# Everything random about one dataset, from its own seed: three draws of the
# same size. Learners are fit on the training draw and scored on the
# validation draw, and estimators run on the estimation draw. The three draws
# stand in for cross-validated cross-fitting at n_obs; the supervised-learning
# skill gives the reasons and the limits. Cheap to redraw, so never cached.
cell_data <- function(dgp_name, n_obs, rep) {
    set_cell_seed(dgp_name, n_obs, rep)
    dgp <- DGPS[[dgp_name]]
    list(dgp_name = dgp_name, n_obs = n_obs, rep = rep,
         training   = draw(dgp, n_obs),
         validation = draw(dgp, n_obs),
         estimation = draw(dgp, n_obs))
}

# One fit of one learner on the training draw, and on each draw in `draws`
# every prediction any downstream step reads: the propensity, and the outcome
# regression at the observed arm and at both counterfactual arms. Predictions
# rather than models, because they are smaller and they are all that
# estimators and accuracy summaries need.
fit_predict <- function(learner, train, draws) {
    pi_hat <- learner(select(train, W1, W2), train$A, binary = TRUE)
    mu_hat <- learner(select(train, A, W1, W2), train$Y, binary = FALSE)
    map(draws, \(new) {
        arm <- \(a) new |> mutate(A = a) |> select(A, W1, W2)
        tibble(pi  = pi_hat(select(new, W1, W2)),
               mu  = mu_hat(select(new, A, W1, W2)),
               mu1 = mu_hat(arm(1)),
               mu0 = mu_hat(arm(0)))
    })
}

# The expensive step, cached: one fit per learner and dataset, stored as its
# predictions on the validation and estimation draws. The key is the data
# itself plus the code, so a changed DGP or seed can never pair a stored fit
# with the wrong dataset, and editing one learner invalidates only that
# learner's entries. A learner that calls helpers of your own needs them in
# code_of() too.
learner_preds <- function(d, learner_name) {
    learner <- LEARNERS[[learner_name]]
    draws <- list(validation = d$validation, estimation = d$estimation)
    cached(
        label   = sprintf("%s/%s/n%d_rep%d", d$dgp_name, learner_name, d$n_obs, d$rep),
        key     = list(d$training, draws, code_of(learner, fit_predict)),
        compute = \() fit_predict(learner, d$training, draws)
    )
}

# Predictions from one library on the estimation draw. A single learner is
# read straight from the cache. Several are compared on their risk over the
# validation draw, and each nuisance takes the learner that wins for it, so
# the estimation draw plays no part in the choice. Every fit involved is
# cached, so a new library is a recombination of stored predictions and
# costs no refitting.
library_preds <- function(d, library) {
    preds <- map(setNames(nm = library), \(l) learner_preds(d, l))
    if (length(library) == 1) return(preds[[1]]$estimation)
    risk <- map(preds, \(p) c(pi = mean((p$validation$pi - d$validation$A)^2),
                              mu = mean((p$validation$mu - d$validation$Y)^2)))
    best <- \(nuisance) preds[[which.min(map_dbl(risk, nuisance))]]$estimation
    pi_from <- best("pi")
    mu_from <- best("mu")
    tibble(pi = pi_from$pi, mu = mu_from$mu, mu1 = mu_from$mu1, mu0 = mu_from$mu0)
}

# =========================== 6. Estimators =================================
# Uniform signature: (data, preds) -> list(est, est_se), where preds holds the
# nuisance predictions at the rows of data. Estimators never fit anything, so
# adding one reruns nothing upstream. Trimming lives here rather than in the
# learners, so a different trimming rule needs no refit either.

clip <- \(p, trim = 0.01) pmin(pmax(p, trim), 1 - trim)

aipw_if <- function(data, preds) {
    pi <- clip(preds$pi)
    alpha <- data$A / pi - (1 - data$A) / (1 - pi)
    alpha * (data$Y - preds$mu) + preds$mu1 - preds$mu0
}

plugin <- function(data, preds) {
    # AIPW's influence-function SE put around the plug-in: the naive baseline
    list(est    = mean(preds$mu1 - preds$mu0),
         est_se = sd(aipw_if(data, preds)) / sqrt(nrow(data)))
}

aipw <- function(data, preds) {
    phi <- aipw_if(data, preds)
    list(est = mean(phi), est_se = sd(phi) / sqrt(nrow(data)))
}

tmle <- function(data, preds) {
    pi <- clip(preds$pi)
    a1 <- 1 / pi
    a0 <- -1 / (1 - pi)
    a  <- ifelse(data$A == 1, a1, a0)
    eps <- sum(a * (data$Y - preds$mu)) / sum(a^2)   # least-squares fluctuation
    mu1 <- preds$mu1 + eps * a1
    mu0 <- preds$mu0 + eps * a0
    phi <- a * (data$Y - (preds$mu + eps * a)) + mu1 - mu0
    list(est = mean(mu1 - mu0), est_se = sd(phi) / sqrt(nrow(data)))
}

ESTIMATORS <- list(plugin = plugin, aipw = aipw, tmle = tmle)

# =========================== 7. Run ========================================
# The design is a grid. A DGP, a sample size and a repetition name a dataset;
# every requested library is fit to it, and every requested estimator reads
# each library's predictions. run_sim() takes a subset of any factor, with the
# full grid as the default, so one DGP, one estimator, or one library across
# all estimators runs on its own and returns exactly the rows a full run
# would.

REPS  <- 20     # 2 to check the code runs, ~100 for the shape, then scale
N_OBS <- 500

run_cell <- function(dgp_name, n_obs, rep, libraries, estimators) {
    d <- cell_data(dgp_name, n_obs, rep)
    dgp <- DGPS[[dgp_name]]
    truth <- with(d$estimation, tibble(pi = plogis(dgp$rho(W1, W2)), mu = dgp$mu(A, W1, W2)))
    per_library <- map(libraries, \(lib) {
        preds <- library_preds(d, LIBRARIES[[lib]])
        estimates <- map(estimators, \(e) {
            # a failure records NA and gets counted; it does not end the run
            res <- try(ESTIMATORS[[e]](d$estimation, preds), silent = TRUE)
            if (inherits(res, "try-error")) res <- list(est = NA_real_, est_se = NA_real_)
            tibble(estimator = e, est = res$est, se = res$est_se)
        }) |> bind_rows()
        accuracy <- tibble(
            nuisance = c("pi", "mu"),
            rmse     = c(sqrt(mean((preds$pi - truth$pi)^2)),
                         sqrt(mean((preds$mu - truth$mu)^2))))
        ids <- \(x) mutate(x, DGP = dgp_name, n_obs = n_obs, rep = rep,
                           library = lib, .before = 1)
        list(estimates = ids(estimates), accuracy = ids(accuracy))
    })
    list(estimates = map(per_library, "estimates") |> bind_rows(),
         accuracy  = map(per_library, "accuracy")  |> bind_rows())
}

run_sim <- function(dgps = names(DGPS), n_obs = N_OBS, reps = seq_len(REPS),
                    libraries = names(LIBRARIES), estimators = names(ESTIMATORS),
                    parallel = FALSE) {
    cells <- expand_grid(dgp_name = dgps, n_obs = n_obs, rep = reps)
    one <- \(dgp_name, n_obs, rep) run_cell(dgp_name, n_obs, rep, libraries, estimators)
    # Every cell sets its own seed, so the backend is told to leave the
    # generator alone rather than to seed it.
    out <- if (parallel) {
        furrr::future_pmap(cells, one, .options = furrr::furrr_options(seed = NULL))
    } else {
        pmap(cells, one)
    }
    list(estimates = map(out, "estimates") |> bind_rows(),
         accuracy  = map(out, "accuracy")  |> bind_rows())
}

# For parallel runs:
#   library(furrr); plan(multicore, workers = 10)
#   results <- run_sim(parallel = TRUE)
# Test with reps = 1:5 first. Parallelize across cells, not within them.
# Forked workers (multicore) see everything this script defined. Separate
# sessions (multisession, the only choice on Windows or inside RStudio) do not
# find S3 methods defined in a script, such as draw.dgp, so there the code
# has to be loaded in each worker, for example from a package.

# =========================== 8. Summaries ==================================
# One summary per display, all reading the same run. The library table and
# the estimator table come from the same predictions on the same datasets, so
# they can be compared repetition by repetition. Save `results` itself to
# disk; everything below is derived and regenerable.

summarize_learners <- function(accuracy) {
    accuracy |>
        group_by(DGP, n_obs, library, nuisance) |>
        summarize(mean_rmse = mean(rmse), mcse = sd(rmse) / sqrt(n()),
                  .groups = "drop")
}

summarize_estimators <- function(estimates, dgps = DGPS) {
    true_ATEs <- map_dbl(dgps, ATE)
    estimates |>
        mutate(theta = true_ATEs[DGP]) |>
        group_by(DGP, n_obs, library, estimator) |>
        summarize(
            n_failed     = sum(is.na(est)),
            bias         = mean(est - theta, na.rm = TRUE),
            empirical_se = sd(est, na.rm = TRUE),
            model_se     = sqrt(mean(se^2, na.rm = TRUE)),   # root of the mean variance
            rmse         = sqrt(mean((est - theta)^2, na.rm = TRUE)),
            coverage     = mean(abs(est - theta) <= 1.96 * se, na.rm = TRUE),
            .groups = "drop"
        )
}

# Monte Carlo SEs for these summaries: see assets/performance_measures.R.
# Pilot check on this output: assets/pilot_check.R, with the other design
# factors named in `by`, e.g.
#   pilot_contrast(results$estimates, "mse", "tmle", "aipw", map_dbl(DGPS, ATE),
#                  by = c("DGP", "n_obs", "library"))

# =========================== Demo ==========================================
# Runs only as a script. It writes its cache to a temporary directory, runs a
# small full grid, then reruns one piece of it from the cache.

if (sys.nframe() == 0L) {
    CACHE_DIR <- file.path(tempdir(), "cache")

    cat("=== DGP diagnostics ===\n")
    print(map(DGPS, diagnose, n = 2e4) |> bind_rows(.id = "DGP"))

    cat("\n=== full grid, 6 reps: every fit computed and cached ===\n")
    t_full <- system.time(results <- run_sim(reps = 1:6))[["elapsed"]]
    cat(sprintf("%.1fs, %d estimate rows\n", t_full, nrow(results$estimates)))
    print(summarize_learners(results$accuracy), n = Inf)
    print(summarize_estimators(results$estimates), n = Inf, width = Inf)

    cat("\n=== one DGP, one library, one estimator: every fit is a cache hit ===\n")
    t_part <- system.time(
        part <- run_sim(dgps = "complex", libraries = "select", estimators = "tmle", reps = 1:6)
    )[["elapsed"]]
    same <- results$estimates |>
        filter(DGP == "complex", library == "select", estimator == "tmle")
    cat(sprintf("%.2fs; same rows as the full run: %s\n",
                t_part, isTRUE(all.equal(part$estimates, same))))
}
