"""
Simulation scaffold: one pipeline from DGPs to every display.

Python counterpart of simulation-scaffold.R. In a real project these are
separate files: dgps.py, learners.py, estimators.py, run.py, and a summary
script per display. Kept together here so the whole pattern is visible.

The pipeline runs one way, data -> predictions -> estimates -> summaries, and
three properties keep it cheap to iterate on:
  * Any piece runs alone. run_sim() takes a subset of every factor, and each
    dataset's random stream comes from its name, so a partial run returns the
    same rows a full run would.
  * Every display reads the same fits. The library table and the estimator
    table below are two summaries of one set of predictions.
  * Expensive steps are cached. Each base learner's predictions are stored per
    dataset and split, so a new library or estimator refits nothing.

Run:  uv run --with numpy,pandas,scikit-learn,joblib python simulation-scaffold.py
"""

from __future__ import annotations

import os

# One thread per fit, since parallelism goes across cells (the
# supervised-learning skill has the reason). It has to be set before numpy
# and scikit-learn start their thread pools.
os.environ.setdefault("OMP_NUM_THREADS", "1")

import hashlib
import inspect
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, NamedTuple

import numpy as np
import pandas as pd

CACHE_DIR = Path("cache")   # local, and listed in .gitignore before the first run
BASE_SEED = 20260916

# =========================== 1. DGPs =======================================


@dataclass(frozen=True)
class DGP:
    """A data-generating process.

    Keeping rho, mu and sigma as fields rather than inlining them into a draw
    function is what makes the true estimand and the diagnostics below
    computable without writing anything DGP-specific.
    """

    rho: Callable[[np.ndarray, np.ndarray], np.ndarray]  # log-odds of treatment
    mu: Callable[[np.ndarray, np.ndarray, np.ndarray], np.ndarray]  # E[Y|A,W]
    sigma: float = 1.0

    def draw(self, n: int, rng: np.random.Generator) -> pd.DataFrame:
        w1 = rng.uniform(-1, 1, n)
        w2 = rng.uniform(-1, 1, n)
        a = rng.binomial(1, _expit(self.rho(w1, w2)))
        y = self.mu(a, w1, w2) + rng.normal(0, self.sigma, n)
        return pd.DataFrame({"W1": w1, "W2": w2, "A": a, "Y": y})

    def draw_intervene(
        self, n: int, treatment: Callable[[np.ndarray, np.ndarray], np.ndarray],
        rng: np.random.Generator,
    ) -> pd.DataFrame:
        """Draw under a fixed treatment rule.

        This is what gives the true estimand by brute force, with no closed
        form needed, and it costs almost nothing to write.
        """
        w1 = rng.uniform(-1, 1, n)
        w2 = rng.uniform(-1, 1, n)
        a = np.broadcast_to(np.asarray(treatment(w1, w2)), (n,)).astype(float)
        y = self.mu(a, w1, w2) + rng.normal(0, self.sigma, n)
        return pd.DataFrame({"W1": w1, "W2": w2, "A": a, "Y": y})

    # ---- diagnostics: run these before trusting a DGP, and report them -----

    def ate(self, n: int = 1_000_000, seed: int = 0) -> float:
        """Both arms start from the same seed, so they share covariates and
        noise and their difference carries no outcome noise. Arms drawn
        independently would put a Monte Carlo error of about 0.002 into the
        "truth" at this n, which is not small next to the Monte Carlo SE of a
        bias estimate."""
        mu1 = self.draw_intervene(n, _treat_all, np.random.default_rng(seed))["Y"].mean()
        mu0 = self.draw_intervene(n, _treat_none, np.random.default_rng(seed))["Y"].mean()
        return float(mu1 - mu0)

    def diagnose(self, n: int = 100_000, seed: int = 0) -> dict:
        """Overlap, variance explained, and how nonlinear the truth actually is.

        These say what the DGP spans far better than the generating equations,
        and they catch most DGP mistakes. Report them next to the DGP.
        """
        rng = np.random.default_rng(seed)
        d = self.draw(n, rng)
        mu_true = self.mu(d["A"].values, d["W1"].values, d["W2"].values)
        pi_true = _expit(self.rho(d["W1"].values, d["W2"].values))

        X = np.column_stack([np.ones(n), d["A"], d["W1"], d["W2"]])
        mu_lin = X @ np.linalg.lstsq(X, mu_true, rcond=None)[0]

        return {
            "ate": self.ate(n, seed),
            "pi_min": float(pi_true.min()),          # overlap
            "pi_max": float(pi_true.max()),
            "var_explained": float(mu_true.var() / d["Y"].var()),
            "linear_share": float(mu_lin.var() / mu_true.var()),
        }


def _expit(x):
    return 1.0 / (1.0 + np.exp(-x))


def _treat_all(w1, w2):
    return 1.0


def _treat_none(w1, w2):
    return 0.0


# Module-level named functions, not lambdas. A DGP gets shipped to worker
# processes when you parallelize, and lambdas do not pickle, so lambdas here
# work fine serially and then break the moment you set n_jobs > 1.


def _simple_rho(w1, w2):
    return w1 + w2


def _simple_mu(a, w1, w2):
    return w1 + w2 + a


def _complex_rho(w1, w2):
    return w1 + w2 + w1 * np.abs(w2)


def _complex_mu(a, w1, w2):
    # heterogeneous effect: the a * (...) term is what makes the ATE nonzero.
    # Check this. A mean function with no treatment term is a silent ATE of 0.
    return w1 + w2 + np.abs(w2) + 0.5 * w1 * w2 + a * (1 + 0.5 * w1)


SIMPLE_DGP = DGP(rho=_simple_rho, mu=_simple_mu, sigma=1.0)
COMPLEX_DGP = DGP(rho=_complex_rho, mu=_complex_mu, sigma=1.0)
DGPS = {"simple": SIMPLE_DGP, "complex": COMPLEX_DGP}

# =========================== 2. Learners and libraries =====================
# Placeholder learners that keep the pipeline running; set up real ones with
# the supervised-learning skill. The interface is what this scaffold fixes: a
# learner takes training covariates and a response and returns a prediction
# function, and everything that determines a fit lives in its definition, so
# it is part of the learner's source and so of its cache key.


def linear(X: np.ndarray, y: np.ndarray, binary: bool) -> Callable:
    from sklearn.linear_model import LinearRegression, LogisticRegression

    if binary:
        fit = LogisticRegression(C=np.inf).fit(X, y)     # C=inf: unpenalized
        return lambda Xn: fit.predict_proba(Xn)[:, 1]
    return LinearRegression().fit(X, y).predict


def gbt(X: np.ndarray, y: np.ndarray, binary: bool) -> Callable:
    from sklearn.ensemble import (
        HistGradientBoostingClassifier,
        HistGradientBoostingRegressor,
    )

    Model = HistGradientBoostingClassifier if binary else HistGradientBoostingRegressor
    fit = Model(max_iter=100, max_depth=3, learning_rate=0.1, random_state=0).fit(X, y)
    return (lambda Xn: fit.predict_proba(Xn)[:, 1]) if binary else fit.predict


LEARNERS = {"linear": linear, "gbt": gbt}

# A library is a set of base learners. One learner is used as it is. Several
# are combined per nuisance by picking the learner with the smallest
# cross-validated risk, the discrete super learner. The convex weights of a
# full super learner would slot into library_preds() and read the same folds.
LIBRARIES = {"linear": ["linear"], "gbt": ["gbt"], "select": ["linear", "gbt"]}
N_FOLDS = 5

# =========================== 3. Seeds and cache ============================


def cell_rng(dgp_name: str, n_obs: int, rep: int) -> np.random.Generator:
    """A dataset's random stream comes from its name, never from its place in
    a loop, so it draws the same data alone as it does in the full grid. One
    stream per repetition shared across DGPs would give the complex DGP
    different data depending on whether the simple one ran first. crc32
    rather than hash(), which Python salts differently in every process."""
    return np.random.default_rng(
        [BASE_SEED, zlib.crc32(dgp_name.encode()), int(n_obs), int(rep)])


def digest(*parts) -> str:
    """Hash of everything that determines a cache entry: data frames by
    content, functions by source text, anything else by repr."""
    h = hashlib.sha256()
    for p in parts:
        if isinstance(p, pd.DataFrame):
            h.update(pd.util.hash_pandas_object(p, index=False).to_numpy().tobytes())
            h.update(repr(list(p.columns)).encode())
        elif callable(p):
            h.update(inspect.getsource(p).encode())
        else:
            h.update(repr(p).encode())
    return h.hexdigest()[:16]


def cached(label: str, key: str, compute: Callable[[], pd.DataFrame]) -> pd.DataFrame:
    """One file per entry, named by a hash of everything that determines it,
    so a hit returns exactly what recomputing would. The readable prefix shows
    what is stored and makes selective deletion easy (rm -r cache/complex/gbt)."""
    path = CACHE_DIR / f"{label}_{key}.pkl"
    if path.exists():
        return pd.read_pickle(path)
    value = compute()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.tmp{os.getpid()}")
    value.to_pickle(tmp)
    os.replace(tmp, path)   # atomic, so a killed run leaves no half-written entry
    return value


# =========================== 4. Datasets and predictions ===================


@dataclass(frozen=True)
class CellData:
    """Everything random about one dataset, from its own stream: the training
    draw the learners see, the evaluation draw the estimators see (a single
    sample split on a separate draw), and the fold labels for
    cross-validation. Cheap to redraw, so never cached."""

    dgp_name: str
    n_obs: int
    rep: int
    train: pd.DataFrame
    eval: pd.DataFrame
    folds: np.ndarray


def cell_data(dgp_name: str, n_obs: int, rep: int) -> CellData:
    rng = cell_rng(dgp_name, n_obs, rep)
    dgp = DGPS[dgp_name]
    train, eval_ = dgp.draw(n_obs, rng), dgp.draw(n_obs, rng)
    folds = rng.permutation(np.arange(n_obs) % N_FOLDS)
    return CellData(dgp_name, n_obs, rep, train, eval_, folds)


def fit_predict(learner: Callable, train: pd.DataFrame, test: pd.DataFrame) -> pd.DataFrame:
    """One fit of one learner, returning every prediction any downstream step
    reads: the propensity, and the outcome regression at the observed arm and
    at both counterfactual arms. Predictions rather than models, because they
    are smaller and they are all that estimators and accuracy summaries need."""
    pi_hat = learner(train[["W1", "W2"]].to_numpy(), train["A"].to_numpy(), binary=True)
    mu_hat = learner(train[["A", "W1", "W2"]].to_numpy(), train["Y"].to_numpy(), binary=False)
    W = test[["W1", "W2"]].to_numpy()

    def arm(a: float) -> np.ndarray:
        return np.column_stack([np.full(len(test), a), W])

    return pd.DataFrame({
        "pi": pi_hat(W),
        "mu": mu_hat(test[["A", "W1", "W2"]].to_numpy()),
        "mu1": mu_hat(arm(1.0)),
        "mu0": mu_hat(arm(0.0)),
    })


def learner_preds(d: CellData, learner_name: str, split: str | int = "eval") -> pd.DataFrame:
    """The expensive step, cached. split="eval" fits on the whole training draw
    and predicts the evaluation draw; split=k holds out fold k, which is what
    an ensemble needs. The key is the data itself plus the code, so a changed
    DGP, seed or fold can never pair a stored fit with the wrong dataset, and
    editing one learner invalidates only that learner's entries. A learner
    that calls helpers of your own needs them in the digest too."""
    if split == "eval":
        train, test = d.train, d.eval
    else:
        train, test = d.train[d.folds != split], d.train[d.folds == split]
    learner = LEARNERS[learner_name]
    return cached(
        label=f"{d.dgp_name}/{learner_name}/n{d.n_obs}_rep{d.rep}_{split}",
        key=digest(train, test, learner, fit_predict),
        compute=lambda: fit_predict(learner, train, test),
    )


def library_preds(d: CellData, library: list[str]) -> pd.DataFrame:
    """Predictions from one library on the evaluation draw. A single learner is
    read straight from the cache. Several are compared on cross-validated risk
    over the training draw, and each nuisance takes the learner that wins for
    it. Every fit involved is cached, so a new library is a recombination of
    stored predictions and costs no refitting."""
    if len(library) == 1:
        return learner_preds(d, library[0])
    held_out = pd.concat([d.train[d.folds == k] for k in range(N_FOLDS)])
    risk = {}
    for name in library:
        cv = pd.concat([learner_preds(d, name, k) for k in range(N_FOLDS)])
        risk[name] = {
            "pi": np.mean((cv["pi"].to_numpy() - held_out["A"].to_numpy()) ** 2),
            "mu": np.mean((cv["mu"].to_numpy() - held_out["Y"].to_numpy()) ** 2),
        }
    pi_from = learner_preds(d, min(library, key=lambda m: risk[m]["pi"]))
    mu_from = learner_preds(d, min(library, key=lambda m: risk[m]["mu"]))
    return pd.DataFrame({"pi": pi_from["pi"], "mu": mu_from["mu"],
                         "mu1": mu_from["mu1"], "mu0": mu_from["mu0"]})


# =========================== 5. Estimators =================================
# Uniform signature: (data, preds) -> Estimate, where preds holds the nuisance
# predictions at the rows of data. Estimators never fit anything, so adding
# one reruns nothing upstream. Trimming lives here rather than in the
# learners, so a different trimming rule needs no refit either.


class Estimate(NamedTuple):
    est: float
    est_se: float


def _clip(p: np.ndarray, trim: float = 0.01) -> np.ndarray:
    return np.clip(p, trim, 1 - trim)


def _aipw_if(data: pd.DataFrame, preds: pd.DataFrame) -> np.ndarray:
    a, y = data["A"].to_numpy(), data["Y"].to_numpy()
    pi = _clip(preds["pi"].to_numpy())
    alpha = a / pi - (1 - a) / (1 - pi)
    return alpha * (y - preds["mu"].to_numpy()) + (preds["mu1"] - preds["mu0"]).to_numpy()


def plugin(data: pd.DataFrame, preds: pd.DataFrame) -> Estimate:
    """AIPW's influence-function SE put around the plug-in: the naive baseline."""
    phi = _aipw_if(data, preds)
    return Estimate(est=float((preds["mu1"] - preds["mu0"]).mean()),
                    est_se=float(phi.std(ddof=1) / np.sqrt(len(phi))))


def aipw(data: pd.DataFrame, preds: pd.DataFrame) -> Estimate:
    phi = _aipw_if(data, preds)
    return Estimate(est=float(phi.mean()), est_se=float(phi.std(ddof=1) / np.sqrt(len(phi))))


def tmle(data: pd.DataFrame, preds: pd.DataFrame) -> Estimate:
    a, y = data["A"].to_numpy(), data["Y"].to_numpy()
    pi = _clip(preds["pi"].to_numpy())
    a1, a0 = 1 / pi, -1 / (1 - pi)
    alpha = np.where(a == 1, a1, a0)
    mu = preds["mu"].to_numpy()

    # one-step fluctuation: no-intercept least squares of residual on alpha
    eps = float(alpha @ (y - mu) / (alpha @ alpha))

    mu1 = preds["mu1"].to_numpy() + eps * a1
    mu0 = preds["mu0"].to_numpy() + eps * a0
    phi = alpha * (y - (mu + eps * alpha)) + (mu1 - mu0)
    return Estimate(est=float((mu1 - mu0).mean()),
                    est_se=float(phi.std(ddof=1) / np.sqrt(len(phi))))


ESTIMATORS = {"plugin": plugin, "aipw": aipw, "tmle": tmle}

# =========================== 6. Run ========================================
# The design is a grid. A DGP, a sample size and a repetition name a dataset;
# every requested library is fit to it, and every requested estimator reads
# each library's predictions. run_sim() takes a subset of any factor, with the
# full grid as the default, so one DGP, one estimator, or one library across
# all estimators runs on its own and returns exactly the rows a full run
# would.

REPS = 20     # 2 to check the code runs, ~100 for the shape, then scale
N_OBS = 500


def run_cell(dgp_name: str, n_obs: int, rep: int,
             libraries: list[str], estimators: list[str]) -> tuple[list[dict], list[dict]]:
    d = cell_data(dgp_name, n_obs, rep)
    dgp = DGPS[dgp_name]
    w1, w2, a = (d.eval[c].to_numpy() for c in ("W1", "W2", "A"))
    truth = {"pi": _expit(dgp.rho(w1, w2)), "mu": dgp.mu(a, w1, w2)}
    ids = dict(DGP=dgp_name, n_obs=n_obs, rep=rep)
    estimates, accuracy = [], []
    for lib in libraries:
        preds = library_preds(d, LIBRARIES[lib])
        for name in estimators:
            try:
                est, se = ESTIMATORS[name](d.eval, preds)
            except Exception:
                est, se = np.nan, np.nan   # count failures, do not crash the run
            estimates.append(dict(ids, library=lib, estimator=name, est=est, se=se))
        for nuisance in ("pi", "mu"):
            err = preds[nuisance].to_numpy() - truth[nuisance]
            accuracy.append(dict(ids, library=lib, nuisance=nuisance,
                                 rmse=float(np.sqrt(np.mean(err ** 2)))))
    return estimates, accuracy


def _levels(x, default) -> list:
    """Accept one level or several, so run_sim(dgps="complex") works."""
    if x is None:
        return list(default)
    return [x] if isinstance(x, (str, int)) else list(x)


def run_sim(dgps=None, n_obs=None, reps=None, libraries=None, estimators=None,
            n_jobs: int = 1) -> dict[str, pd.DataFrame]:
    cells = [(g, n, r)
             for g in _levels(dgps, DGPS)
             for n in _levels(n_obs, [N_OBS])
             for r in _levels(reps, range(REPS))]
    libraries, estimators = _levels(libraries, LIBRARIES), _levels(estimators, ESTIMATORS)
    if n_jobs == 1:
        out = [run_cell(*c, libraries, estimators) for c in cells]
    else:
        from joblib import Parallel, delayed
        out = Parallel(n_jobs=n_jobs)(
            delayed(run_cell)(*c, libraries, estimators) for c in cells)
    return {
        "estimates": pd.DataFrame([row for est, _ in out for row in est]),
        "accuracy": pd.DataFrame([row for _, acc in out for row in acc]),
    }


# Parallelize across cells, not within them. Test with reps=range(5) first.

# =========================== 7. Summaries ==================================
# One summary per display, all reading the same run. The library table and
# the estimator table come from the same predictions on the same datasets, so
# they can be compared repetition by repetition. Save the results themselves
# to disk; everything below is derived and regenerable.


def summarize_learners(accuracy: pd.DataFrame) -> pd.DataFrame:
    g = accuracy.groupby(["DGP", "n_obs", "library", "nuisance"])["rmse"]
    return pd.DataFrame({
        "mean_rmse": g.mean(),
        "mcse": g.std(ddof=1) / np.sqrt(g.count()),
    }).reset_index()


def summarize_estimators(estimates: pd.DataFrame, dgps: dict | None = None,
                         z: float = 1.96) -> pd.DataFrame:
    dgps = dgps or DGPS
    true_ate = {k: v.ate() for k, v in dgps.items()}

    def _one(g: pd.DataFrame) -> pd.Series:
        theta = true_ate[g.name[0]]
        n_failed = int(g.est.isna().sum())
        g = g.dropna(subset=["est", "se"])
        return pd.Series({
            "n_failed": n_failed,
            "bias": g.est.mean() - theta,
            "empirical_se": g.est.std(ddof=1),
            "model_se": np.sqrt((g.se ** 2).mean()),   # root of the mean variance
            "rmse": np.sqrt(((g.est - theta) ** 2).mean()),
            "coverage": ((g.est - theta).abs() <= z * g.se).mean(),
        })

    return estimates.groupby(["DGP", "n_obs", "library", "estimator"]).apply(
        _one, include_groups=False
    ).reset_index()


# Monte Carlo SEs for these summaries: see assets/performance_measures.R, or
# note that MCSE(bias) = empirical_se / sqrt(n_sim) and
# MCSE(coverage) = sqrt(coverage * (1 - coverage) / n_sim).
# Pilot check on this output: assets/pilot_check.py, with the other design
# factors named in `by`, e.g.
#   pilot_contrast(results["estimates"], "mse", "tmle", "aipw",
#                  {k: v.ate() for k, v in DGPS.items()},
#                  by=["DGP", "n_obs", "library"])


# =========================== Demo ==========================================
# Writes its cache to a temporary directory, runs a small full grid, then
# reruns one piece of it from the cache.

if __name__ == "__main__":
    import tempfile
    import time

    CACHE_DIR = Path(tempfile.mkdtemp()) / "cache"

    print("=== DGP diagnostics ===")
    print(pd.DataFrame({k: v.diagnose(n=20_000) for k, v in DGPS.items()}).T.round(3))

    print("\n=== full grid, 6 reps: every fit computed and cached ===")
    t0 = time.perf_counter()
    results = run_sim(reps=range(6))
    print(f"{time.perf_counter() - t0:.1f}s, {len(results['estimates'])} estimate rows")
    print(summarize_learners(results["accuracy"]).round(4).to_string(index=False))
    print(summarize_estimators(results["estimates"]).round(4).to_string(index=False))

    print("\n=== one DGP, one library, one estimator: every fit is a cache hit ===")
    t0 = time.perf_counter()
    part = run_sim(dgps="complex", libraries="select", estimators="tmle", reps=range(6))
    elapsed = time.perf_counter() - t0
    full = results["estimates"].query(
        "DGP == 'complex' and library == 'select' and estimator == 'tmle'")
    same = part["estimates"].reset_index(drop=True).equals(full.reset_index(drop=True))
    print(f"{elapsed:.2f}s; same rows as the full run: {same}")
