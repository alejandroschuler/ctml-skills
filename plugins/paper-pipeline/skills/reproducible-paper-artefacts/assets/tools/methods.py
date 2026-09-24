#!/usr/bin/env python3
"""The methods sheet, and the values the methods text was last reviewed against.

A methods setting is a generated macro whose name starts with `mth`, emitted by
the computation that used it. A methods table is tables/methods-*.tex. Both
live in the paper tier, so they carry stamps and go stale like results.

    methods.py           print the methods sheet
    methods.py --ok      record the current values as reviewed, and commit that
                         record in the paper repo
    methods.py --check   warn about settings that changed since the review; fail
                         instead when [methods] strict = true in .artefacts.toml

The review record says nothing about the text itself. It records which values
the text was read against, so that a later change to a value the text types by
hand gets caught. A value the text prints through its macro updates itself. The
sheet says so, but the sentence around it may still need rereading.

The grid counts come from grid_table() and follow the edge rule: the best
configuration of a learner type should not sit on the edge of its tuning grid. They
are warnings only, and never fail a check.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone

from _common import (
    ArtefactError,
    Config,
    fail,
    git,
    info,
    load_config,
    load_records,
    ok,
    warn,
)
from artefact_status import read_fls, read_macro_log

NOTE = (
    "Values the methods text was last reviewed against. Written by "
    "`make methods-ok`. Do not edit by hand."
)


# --------------------------------------------------------------------------
# What is recorded, and what was reviewed
# --------------------------------------------------------------------------


def current(cfg: Config) -> tuple[dict[str, str], dict[str, str], list[dict]]:
    """Methods settings and tables in the paper tier, and grid counts in both tiers."""
    settings: dict[str, str] = {}
    tables: dict[str, str] = {}
    for key, rec in sorted(load_records(cfg, "paper").items()):
        for name, value in rec.get("macros", {}).items():
            if cfg.is_methods_macro(name):
                settings[name] = value
        if cfg.is_methods_table(key):
            tables[key] = rec.get("sha256")
    grids = []
    for tier in ("paper", "notes"):
        for key, rec in sorted(load_records(cfg, tier).items()):
            for entry in rec.get("edges") or []:
                grids.append({**entry, "artefact": key, "tier": tier})
    return settings, tables, grids


def load_review(cfg: Config) -> dict | None:
    path = cfg.methods_ledger
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise ArtefactError(f"Corrupt {path}: {exc}") from exc


def plain(value: str) -> str:
    """A rendered value made readable. For the sheet only; the text gets the LaTeX."""
    s = re.sub(r"\\qty\{([^}]*)\}\{\\percent\}", r"\1%", value)
    s = re.sub(r"\\numlist\{([^}]*)\}", lambda m: m.group(1).replace(";", ", "), s)
    s = re.sub(r"\\num\{([^}]*)\}", r"\1", s)
    s = s.replace(r"\(<\)", "<")
    for escaped, char in ((r"\{", "{"), (r"\}", "}"), (r"\_", "_"), (r"\&", "&"),
                          (r"\%", "%"), (r"\$", "$"), (r"\#", "#")):
        s = s.replace(escaped, char)
    return s


def evaluate(cfg: Config):
    """Compare what is recorded with what was reviewed and what the text prints."""
    settings, tables, grids = current(cfg)
    review = load_review(cfg)
    used_macros, used_files = read_macro_log(cfg), read_fls(cfg)
    rows = [_row("setting", name, value, review, used_macros) for name, value in settings.items()]
    rows += [_row("table", key, digest, review, used_files) for key, digest in tables.items()]
    removed = []
    if review:
        removed += [n for n in review.get("settings", {}) if n not in settings]
        removed += [k for k in review.get("tables", {}) if k not in tables]
    return rows, removed, review, grids


def _row(kind: str, name: str, value: str, review: dict | None, used: set[str] | None) -> dict:
    printed = None if used is None else name in used
    old = None
    if review is None:
        state = "not reviewed"
    else:
        old = review.get("settings" if kind == "setting" else "tables", {}).get(name)
        state = "new" if old is None else ("same" if old == value else "changed")
    return {"kind": kind, "name": name, "value": value, "printed": printed,
            "state": state, "old": old}


# --------------------------------------------------------------------------
# Findings
# --------------------------------------------------------------------------


def text_findings(rows: list[dict], removed: list[str], review: dict | None) -> list[str]:
    """Changes the text might not reflect: the ones it does not print through a macro."""
    if not rows and not removed:
        return []
    if review is None:
        return [
            f"The methods text has never been reviewed against the {len(rows)} "
            "recorded methods setting(s) and table(s)."
        ]
    findings = []
    for r in rows:
        if r["state"] not in ("changed", "new") or r["printed"] is True:
            continue
        label = r["name"] if r["kind"] == "setting" else f"The table {r['name']}"
        if r["state"] == "changed":
            what = "changed since the review"
            if r["kind"] == "setting":
                what += f" (was {plain(r['old'])}, now {plain(r['value'])})"
        else:
            what = "is new since the review"
        if r["printed"] is False:
            how = ("the text does not print it through its macro" if r["kind"] == "setting"
                   else "the manuscript does not input it")
        else:
            how = "the manuscript has not been compiled here, so run `make pdf` to see whether the text prints it"
        findings.append(f"{label} {what}, and {how}.")
    for name in removed:
        findings.append(f"{name} was reviewed but is no longer recorded; the text may still describe it.")
    return findings


def _number(value) -> str:
    return f"{value:g}" if isinstance(value, float) else str(value)


def grid_findings(grids: list[dict]) -> tuple[list[str], list[str]]:
    """(warnings, notes) from the grid counts. A warning means at least half the fits."""
    warnings, notes = [], []
    for g in grids:
        if g.get("two_values"):
            notes.append(
                f"{g['learner']} {g['param']}: a grid of two values puts every choice on "
                "an edge, so the edge rule cannot be checked. Add a third value."
            )
            continue
        for side, count, edge in (("upper", g.get("upper", 0), g.get("high")),
                                  ("lower", g.get("lower", 0), g.get("low"))):
            if not count:
                continue
            where = (
                f"{g['learner']} {g['param']}: the best configuration sits at the {side} "
                f"edge of its grid ({_number(edge)}) in {count} of {g['fits']} fit(s)"
            )
            if count * 2 >= g["fits"]:
                direction = "upward" if side == "upper" else "downward"
                warnings.append(f"{where}. The grid is too narrow there; move it {direction}.")
            else:
                notes.append(f"{where}. That is occasional, so probably noise.")
    return warnings, notes


# --------------------------------------------------------------------------
# Output
# --------------------------------------------------------------------------


def _clip(s: str, width: int = 44) -> str:
    return s if len(s) <= width else s[: width - 3] + "..."


def print_sheet(rows: list[dict], removed: list[str], review: dict | None, grids: list[dict]) -> None:
    n_settings = sum(r["kind"] == "setting" for r in rows)
    print(f"methods:   {n_settings} setting(s) and {len(rows) - n_settings} table(s) in the paper tier")
    if review is None:
        print("reviewed:  never. Read the methods section against this sheet, then run `make methods-ok`.")
    else:
        print(f"reviewed:  {review.get('reviewed_at', 'unknown')}")
    print()

    if rows:
        labels = {
            ("setting", True): "macro", ("setting", False): "by hand",
            ("table", True): "input", ("table", False): "not input",
        }
        body = []
        for r in rows:
            value = plain(r["value"]) if r["kind"] == "setting" else "(table)"
            printed = labels.get((r["kind"], r["printed"]), "unknown")
            state = r["state"]
            if state == "changed":
                state = f"changed, was {_clip(plain(r['old']), 24)}" if r["kind"] == "setting" else "changed"
                if r["printed"]:
                    state += "; the text updates itself"
            body.append((r["name"], _clip(value), printed, state))
        head = ("item", "value", "in text", "since review")
        widths = [max(len(head[i]), *(len(b[i]) for b in body)) for i in range(3)]
        for line in [head, *body]:
            print("  " + "  ".join(line[i].ljust(widths[i]) for i in range(3)) + "  " + line[3])
    else:
        print("  No methods settings are recorded. Name a macro mth... and emit it with its results.")
    for name in removed:
        print(f"  {name}: reviewed, but no longer recorded")
    if any(r["printed"] is None for r in rows):
        print("\n  Run `make pdf` so the sheet can see which settings the text prints.")

    if grids:
        print("\ngrids (the edge rule, from grid_table() and the recorded cross-validated risks):")
        warnings, notes = grid_findings(grids)
        if not warnings and not notes:
            print("  No learner's best configuration sits on the edge of its grid.")
        for w in warnings:
            warn(w)
        for n in notes:
            info(n)


# --------------------------------------------------------------------------
# Actions
# --------------------------------------------------------------------------


def record_review(cfg: Config) -> int:
    settings, tables, _ = current(cfg)
    if not settings and not tables:
        warn("No methods settings or tables are recorded yet, so there is nothing to review.")
        return 0
    review = load_review(cfg)
    if review and review.get("settings") == settings and review.get("tables") == tables:
        ok("The review record already matches the recorded settings.")
        return 0

    paper = cfg.root / cfg.paper_dir
    if not (paper / ".git").exists():
        raise ArtefactError(f"{cfg.paper_dir}/ is not a git repo, so the review cannot be recorded.")
    payload = {
        "note": NOTE,
        "reviewed_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "settings": settings,
        "tables": tables,
    }
    path = cfg.methods_ledger
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    name = str(path.relative_to(paper))
    git("add", "--", name, cwd=paper)
    git("commit", "-q", "-m", "Record that the methods text was reviewed against the code",
        "--", name, cwd=paper)
    ok(f"Recorded {len(settings)} setting(s) and {len(tables)} table(s) as reviewed, and "
       f"committed {cfg.paper_dir}/{name}. It goes to Overleaf with the next `make push-paper`.")
    return 0


def check(cfg: Config) -> int:
    rows, removed, review, grids = evaluate(cfg)
    findings = text_findings(rows, removed, review)
    grid_warnings, _ = grid_findings(grids)
    for f in findings:
        warn(f)
    printed = [r["name"] for r in rows if r["state"] == "changed" and r["printed"]]
    if printed:
        info(f"Changed since the review, and printed through a macro, so the text updates "
             f"itself: {', '.join(printed)}. Reread the sentence around each.")
    for w in grid_warnings:
        warn(w)
    if findings:
        info("Read the methods section against `make methods`, fix the text or the code, "
             "then run `make methods-ok`.")
        if cfg.methods_strict:
            fail("[methods] strict = true in .artefacts.toml, so this fails the check.")
            return 1
    elif rows:
        ok(f"methods: {len(rows)} setting(s) and table(s) match the last review")
    else:
        ok("methods: none recorded")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--ok", action="store_true", help="record the current values as reviewed")
    mode.add_argument("--check", action="store_true", help="warn about changes since the review")
    args = ap.parse_args(argv)
    try:
        cfg = load_config()
        if args.ok:
            return record_review(cfg)
        if args.check:
            return check(cfg)
        print_sheet(*evaluate(cfg))
    except ArtefactError as exc:
        fail(str(exc))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
