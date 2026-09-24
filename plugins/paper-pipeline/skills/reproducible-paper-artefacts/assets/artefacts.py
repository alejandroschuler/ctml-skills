"""Emit artefacts from Python. Import this at the top of every analysis script.

    import artefacts as art

    fit = estimate(data)
    art.emit_numbers(
        snakemake.output[0],
        resPrimaryAte   = art.num(fit.estimate, 2),
        resPrimaryCi    = art.ci(fit.lo, fit.hi, 2),
        resPrimaryN     = art.int(fit.n),
        mthPrimaryFolds = art.int(search.n_splits_),
    )

The import works under Snakemake because the Snakefile puts py/lib on
PYTHONPATH. A scratch script run by hand needs the same:
`PYTHONPATH=py/lib python3 scratch/look.py`.

Four things happen that would otherwise be left to memory.

Rounding happens once, here, in code. Numbers in a paper go inconsistent when
each use site rounds by hand, and they stay consistent when the digit count is
an argument to one function. Changing a precision policy across the manuscript
becomes an edit to one call rather than a search through prose.

Every write is checked before it happens: the tier's branch rule, a clean code
tree, and macro names LaTeX will accept. A refused write leaves nothing on disk,
so a mistake stays local instead of breaking the Overleaf compile for every
coauthor.

Provenance is recorded for every file written: the content hash, the commit,
and each file the build read, with its hash. The commit is read from git at
write time rather than passed in, because passing it through Snakemake `params`
would make every artefact in the project stale on every commit.

Methods settings use the same machinery. A macro whose name starts with `mth`
is a methods setting, recorded from what ran, and `make methods` tracks it.
The helpers in the methods sections below format lists, sets and learner grids
for that purpose.
"""

from __future__ import annotations

import numbers
import sys
from pathlib import Path

MARKER = ".artefacts.toml"


def _find_root() -> Path:
    here = Path.cwd().resolve()
    for candidate in [here, *here.parents]:
        if (candidate / MARKER).is_file():
            return candidate
    raise RuntimeError(
        f"No {MARKER} found above {here}. artefacts.py only works inside a "
        "reproducible-paper-artefacts project."
    )


_ROOT = _find_root()
_TOOLS = _ROOT / "tools"
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))

from _common import load_config  # noqa: E402
import record_provenance  # noqa: E402

_CFG = load_config(_ROOT)
_DATA_READS: set[str] = set()


# --------------------------------------------------------------------------
# Formatting. Round once, here.
# --------------------------------------------------------------------------


def num(value: float, digits: int = 2) -> str:
    """A rounded number, formatted through siunitx.

    Fixed-point formatting is deliberate: `round(0.40, 2)` drops the trailing
    zero and the paper ends up with 0.4 in one sentence and 0.42 in the next.
    """
    return rf"\num{{{value:.{digits}f}}}"


def int(value) -> str:  # noqa: A001
    """A count. siunitx supplies the thousands separator.

    Named to match the R front-end, where this cannot be called integer()
    without masking base::integer(). round() returns a Python int on its own,
    so nothing here needs the shadowed builtin.
    """
    return rf"\num{{{round(value)}}}"


def ci(lo: float, hi: float, digits: int = 2) -> str:
    return rf"(\num{{{lo:.{digits}f}}}, \num{{{hi:.{digits}f}}})"


def pct(value: float, digits: int = 1) -> str:
    """A percentage. Pass 42.0 for 42%, not 0.42."""
    return rf"\qty{{{value:.{digits}f}}}{{\percent}}"


def pval(value: float, digits: int = 3) -> str:
    """A p-value, with a floor so tiny values read as an inequality."""
    floor = 10.0 ** (-digits)
    if value < floor:
        return rf"\(<\)\num{{{floor:.{digits}f}}}"
    return rf"\num{{{value:.{digits}f}}}"


# --------------------------------------------------------------------------
# Methods: text, lists and sets
# --------------------------------------------------------------------------

_LATEX_SPECIAL = {
    "\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#",
    "_": r"\_", "{": r"\{", "}": r"\}", "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
}


def text(value) -> str:
    """Any value as LaTeX text, with the special characters escaped.

    Learner and package names are full of underscores, and one unescaped
    underscore stops the compile.
    """
    return "".join(_LATEX_SPECIAL.get(ch, ch) for ch in str(value))


def words(items, conj: str = "and", escape: bool = True) -> str:
    """A list for prose: "a", "a and b", "a, b, and c".

    Pass readable names, such as a mapping from estimator class to the name the
    text uses, rather than code identifiers.
    """
    xs = [text(x) if escape else str(x) for x in items]
    if not xs:
        raise ValueError("words() needs at least one item.")
    if len(xs) == 1:
        return xs[0]
    if len(xs) == 2:
        return f"{xs[0]} {conj} {xs[1]}"
    return ", ".join(xs[:-1]) + f", {conj} " + xs[-1]


def _is_number(value) -> bool:
    return (
        isinstance(value, numbers.Real)
        and not isinstance(value, bool)
        and value == value
    )


def _is_nan(value) -> bool:
    return isinstance(value, float) and value != value


def _plain(value, digits: int | None = None) -> str:
    """A number as siunitx input: integers whole, others to six significant digits."""
    if digits is not None:
        return f"{float(value):.{digits}f}"
    if float(value).is_integer():
        return str(round(float(value)))
    return f"{float(value):g}"


def _numbers_only(values, helper: str) -> list:
    values = list(values)
    if not values or not all(_is_number(v) for v in values):
        raise ValueError(f"{helper}() needs one or more numbers.")
    return values


def numlist(values, digits: int | None = None) -> str:
    """Numbers as a prose list, through siunitx: "250, 500 and 1000"."""
    values = _numbers_only(values, "numlist")
    return r"\numlist{" + ";".join(_plain(v, digits) for v in values) + "}"


def numset(values, digits: int | None = None) -> str:
    r"""Numbers as a set, for math mode: $n \in \mthSimN$ gives n ∈ {250, 500, 1000}.

    Use it inside math only. siunitx's \numlist writes "250, 500 and 1000",
    which is right in prose and wrong inside a set.
    """
    values = _numbers_only(values, "numset")
    return r"\{" + ", ".join(rf"\num{{{_plain(v, digits)}}}" for v in values) + r"\}"


def pkg_version(name: str) -> str:
    """The version of an installed package, as the running interpreter sees it."""
    from importlib.metadata import version

    return text(version(name))


# --------------------------------------------------------------------------
# Methods: learner grids
# --------------------------------------------------------------------------

_RESERVED = ("learner", "cv_risk", "fit")


def rows_from_search(search, learner: str, fixed=(), fit=None, metric=None) -> list[dict]:
    """One row per candidate configuration of a fitted scikit-learn search, for grid_table().

    Works with GridSearchCV and RandomizedSearchCV, and reads only their
    documented attributes, so this module does not import scikit-learn.

    `learner` is the learner type's name in the table. `fixed` lists the
    hyperparameters that were set rather than tuned and that the methods should
    report, such as ["learning_rate"]; their values come from the search's
    estimator, so defaults are reported as they were, not as remembered. `fit`
    marks which fit the rows come from (a repetition, a fold, an outcome), so
    the grid check can read across fits. `metric` picks the scorer when the
    search used several and `refit` names none.

    cv_risk is the negated mean test score. scikit-learn scorers are all
    greater-is-better, so the configuration with the smallest cv_risk is the one the
    search ranked best. Pipeline prefixes such as "model__" are dropped from the
    hyperparameter names.
    """
    results = search.cv_results_
    if metric is not None:
        key = f"mean_test_{metric}"
    elif "mean_test_score" in results:
        key = "mean_test_score"
    elif isinstance(getattr(search, "refit", None), str):
        key = f"mean_test_{search.refit}"
    else:
        raise ValueError("The search used several scorers and refit names none, so pass metric=.")
    if key not in results:
        raise ValueError(f"cv_results_ has no {key!r}.")

    def short(name: str) -> str:
        return name.split("__")[-1]

    base = search.estimator.get_params() if fixed else {}
    rows = []
    for params, score in zip(results["params"], results[key]):
        row = {"learner": learner}
        for name, value in params.items():
            s = short(name)
            if s in row:
                raise ValueError(f"Two hyperparameters of {learner} shorten to {s!r}.")
            row[s] = value
        for name in fixed:
            if name not in base:
                raise ValueError(f"The estimator of the {learner} search has no parameter {name!r}.")
            row.setdefault(short(name), base[name])
        row["cv_risk"] = -float(score)
        if fit is not None:
            row["fit"] = fit
        rows.append(row)
    return rows


def _distinct(values) -> list:
    seen: dict[str, object] = {}
    for v in values:
        seen.setdefault(repr(v), v)
    unique = list(seen.values())
    if all(_is_number(v) for v in unique):
        return sorted(unique, key=float)
    return sorted(unique, key=lambda v: (not _is_number(v), float(v) if _is_number(v) else 0.0, str(v)))


def _grid_cell(values: list, digits: int | None, max_listed: int) -> str:
    if all(_is_number(v) for v in values):
        if len(values) == 1:
            return rf"\num{{{_plain(values[0], digits)}}}"
        if len(values) <= max_listed:
            return f"${numset(values, digits)}$"
        return (
            rf"\num{{{len(values)}}} values from \num{{{_plain(values[0], digits)}}}"
            rf" to \num{{{_plain(values[-1], digits)}}}"
        )
    shown = [rf"\num{{{_plain(v, digits)}}}" if _is_number(v) else text(v) for v in values]
    if len(shown) == 1:
        return shown[0]
    return r"\{" + ", ".join(shown) + r"\}"


def _as_json_number(value):
    value = float(value)
    return round(value) if value.is_integer() else value


def _edge_counts(rows: list[dict], param: str, exempt) -> dict | None:
    """The edge rule for one tuned hyperparameter of one learner type, across fits."""
    groups: dict[str, list[dict]] = {}
    for r in rows:
        if param in r and _is_number(r[param]) and _is_number(r.get("cv_risk")):
            groups.setdefault(repr(r.get("fit")), []).append(r)
    lower = upper = fits = 0
    low = high = None
    for group in groups.values():
        grid = sorted({float(r[param]) for r in group})
        if len(grid) < 3:
            # With two values every choice is an edge, so the rule says nothing.
            continue
        best = min(group, key=lambda r: r["cv_risk"])
        value = float(best[param])
        lo, hi = grid[0], grid[-1]
        lower += value == lo and lo not in exempt
        upper += value == hi and hi not in exempt
        fits += 1
        low = lo if low is None else min(low, lo)
        high = hi if high is None else max(high, hi)
    if fits == 0:
        return None
    return {"lower": lower, "upper": upper, "fits": fits,
            "low": _as_json_number(low), "high": _as_json_number(high)}


def grid_table(path, rows, limits=None, label: str | None = None,
               digits: int | None = None, max_listed: int = 6) -> Path:
    """Write a learner library's hyperparameters as a methods table, and check its grids.

    `rows` has one row per learner configuration and fit, as a list of dicts or
    a DataFrame: a `learner` column (the learner type), one column per
    hyperparameter, `cv_risk` (that configuration's cross-validated risk in that fit),
    and optionally `fit` (which fit the row is from). rows_from_search()
    builds these rows from a fitted search. Rows for other learners can be
    added by hand; a learner with no hyperparameters needs only `learner`, and
    `cv_risk` matters only for the grid check.

    Within a learner type, a hyperparameter with one value is fixed and one with
    several is tuned. The table lists each with its value or its grid; a grid
    longer than `max_listed` is shown by its size and range. Name the path
    tables/methods-*.tex, so `make methods` tracks it. The manuscript needs the
    booktabs package.

    The grid check is the edge rule: within each learner type and fit, take the
    configuration with the smallest cv_risk, and see whether a tuned hyperparameter
    sits at the smallest or the largest value of its grid. The counts go into
    the table's provenance record, and `make methods` reports them. A grid of
    two values is reported as such instead, because there every choice is an
    edge and the rule can say nothing. `limits`
    maps a hyperparameter to values that are hard limits of the parameter, such
    as {"max_depth": [1]}; an edge choice at a hard limit is exempt.
    """
    out = _target(path)
    record_provenance.validate_write(_CFG, out)
    limits = limits or {}
    source = rows.to_dict("records") if hasattr(rows, "to_dict") else rows
    rows = [dict(r) for r in source]
    if not rows:
        raise ValueError("grid_table() needs at least one row.")
    for r in rows:
        if "learner" not in r:
            raise ValueError("Every row of grid_table() needs a 'learner'.")

    params: list[str] = []
    learners: list = []
    for r in rows:
        if r["learner"] not in learners:
            learners.append(r["learner"])
        for k in r:
            if k not in _RESERVED and k not in params:
                params.append(k)

    lines = [
        "% Generated. Do not edit; edit the code that produces it.",
        r"\begin{tabular}{llll}",
        r"\toprule",
        r"Learner & Hyperparameter & Value or grid & Tuned \\",
        r"\midrule",
    ]
    edges = []
    for learner in learners:
        mine = [r for r in rows if r["learner"] == learner]
        cells = []
        for p in params:
            values = _distinct(r[p] for r in mine if p in r and not _is_nan(r[p]))
            if not values:
                continue
            tuned = len(values) > 1
            cells.append((p, values, tuned))
            if tuned and all(_is_number(v) for v in values):
                if len(values) == 2:
                    edges.append({"learner": str(learner), "param": p, "two_values": True})
                    continue
                exempt = {float(v) for v in limits.get(p, ())}
                counts = _edge_counts(mine, p, exempt)
                if counts:
                    edges.append({"learner": str(learner), "param": p, **counts})
        if not cells:
            lines.append(rf"{text(learner)} & none & & \\")
            continue
        for i, (p, values, tuned) in enumerate(cells):
            name = text(learner) if i == 0 else ""
            cell = _grid_cell(values, digits, max_listed)
            lines.append(rf"{name} & {text(p)} & {cell} & {'yes' if tuned else 'no'} \\")
    lines += [r"\bottomrule", r"\end{tabular}"]

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    _record(out, macros=None, label=label, extra={"edges": edges})
    return out


# --------------------------------------------------------------------------
# Reads
# --------------------------------------------------------------------------


def track_read(path: str | Path) -> Path:
    """Register a data file as an input of whatever is being built.

    Module imports are observed automatically. Data reads are not, because
    nothing in the interpreter announces them, so wrap the path:

        data = pd.read_csv(art.track_read("data/analysis.csv"))

    It returns the path, so it drops into any reader rather than covering a
    short list of pre-wrapped ones that will never match what you actually use.
    """
    p = Path(path)
    p = p if p.is_absolute() else (_ROOT / p)
    try:
        _DATA_READS.add(str(p.resolve().relative_to(_ROOT)))
    except ValueError:
        pass
    return p


def _observed_reads() -> list[str]:
    """Project-local modules the interpreter actually loaded, plus data reads.

    This is observation, not inference, so it cannot be wrong about what ran.
    It is also not complete: a module reached through importlib, and any file
    opened without going through track_read, will be missing. Treat the result
    as a lint that catches the common case rather than as a proof.

    Three kinds of file are left out, because no rule declares them and none
    should: the running script, which Snakemake tracks through its code
    trigger; the tooling under tools/; and Snakemake's own copies under
    .snakemake/.
    """
    skip = (_TOOLS, _ROOT / ".snakemake")
    # By identity, not by name: multiprocessing registers the same module a
    # second time as __mp_main__.
    main = sys.modules.get("__main__")
    found = set(_DATA_READS)
    for module in list(sys.modules.values()):
        if module is main:
            continue
        f = getattr(module, "__file__", None)
        if not f:
            continue
        try:
            p = Path(f).resolve()
            if any(s == p or s in p.parents for s in skip):
                continue
            found.add(str(p.relative_to(_ROOT)))
        except (ValueError, OSError):
            continue
    return sorted(found)


def _rule_name() -> str | None:
    """The rule being run, when Snakemake is driving."""
    import __main__

    sm = getattr(__main__, "snakemake", None)
    return getattr(sm, "rule", None) if sm is not None else None


def _target(path: str | Path) -> Path:
    out = Path(path)
    return out if out.is_absolute() else (_ROOT / out)


def _record(path: Path, macros: dict[str, str] | None, label: str | None,
            extra: dict | None = None) -> None:
    record_provenance.record(
        _CFG,
        path,
        macros=macros,
        reads=_observed_reads(),
        label=label,
        rule=_rule_name(),
        extra=extra,
    )


# --------------------------------------------------------------------------
# Emitters
# --------------------------------------------------------------------------


def emit_numbers(path: str | Path, **macros: str) -> Path:
    """Write one numbers file. All the numbers from one computation belong here.

    Grain matters: the estimate, its standard error, its interval and its n all
    come out of one fit and always go stale together, so they share a file.
    Splitting them would create four things that pretend to be independent and
    never are. The methods settings of the same computation, the `mth` macros,
    belong here too, for the same reason.
    """
    out = _target(path)
    tier = record_provenance.validate_write(_CFG, out)
    record_provenance.validate_macros(_CFG, tier, dict(macros))

    out.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "% Generated. Do not edit; edit the code that produces it.",
        "% Rebuild with: make build",
        "",
    ]
    for name in sorted(macros):
        lines.append(rf"\artefactdefine{{{name}}}{{{macros[name]}}}")
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")

    _record(out, macros=dict(macros), label=None)
    return out


def save_figure(path: str | Path, figure=None, label: str | None = None, **kwargs) -> Path:
    """Save a matplotlib figure and record it.

    `figure` defaults to the current figure. Extra keyword arguments go to
    savefig, with bbox_inches set tight unless overridden.
    """
    out = _target(path)
    record_provenance.validate_write(_CFG, out)
    out.parent.mkdir(parents=True, exist_ok=True)

    if figure is None:
        import matplotlib.pyplot as plt
        figure = plt.gcf()
    kwargs.setdefault("bbox_inches", "tight")
    figure.savefig(out, **kwargs)

    _record(out, macros=None, label=label)
    return out


def save_table(path: str | Path, frame, label: str | None = None, **kwargs) -> Path:
    """Write a dataframe as a LaTeX fragment and record it.

    The fragment is meant for \\input inside a table environment, so it carries
    no float wrapper and no caption. Those belong in the manuscript, where the
    caption can say what the table is for.
    """
    out = _target(path)
    record_provenance.validate_write(_CFG, out)
    out.parent.mkdir(parents=True, exist_ok=True)

    kwargs.setdefault("index", False)
    body = frame.to_latex(**kwargs)
    header = "% Generated. Do not edit; edit the code that produces it.\n"
    out.write_text(header + body, encoding="utf-8")

    _record(out, macros=None, label=label)
    return out
