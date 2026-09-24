"""Shared helpers for the artefact tooling.

Everything here is deliberately boring. These functions are the trusted base
that check_artefacts, artefact_status, build_guard and record_provenance all
rest on, so they are written to be read in one sitting rather than to be clever.

Two rules hold throughout:

  - Anything ambiguous raises instead of guessing. A provenance tool that
    quietly skips what it cannot parse is worse than no tool, because it
    teaches you to stop checking.
  - Git state is read, never written. Only build_guard (auto-commit on a wip
    branch) and methods.py (the review record, in the paper repo) commit, and
    both do so explicitly.

Run as a script, it prints settings from .artefacts.toml, so the Makefile reads
them instead of repeating them:

    python3 tools/_common.py main_branch main_tex paper_dir
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    sys.exit("This tooling needs Python 3.11 or newer (for tomllib).")

MARKER = ".artefacts.toml"


class ArtefactError(RuntimeError):
    """Raised for any condition the caller should stop on."""


# --------------------------------------------------------------------------
# Project discovery and configuration
# --------------------------------------------------------------------------


@dataclass
class Config:
    root: Path
    paper_dir: Path
    main_branch: str
    main_tex: Path
    tiers: dict[str, Path]
    max_file_mb: float
    secret_patterns: list[str] = field(default_factory=list)
    methods_strict: bool = False
    methods_prefix: str = "mth"
    methods_table_prefix: str = "methods-"

    @property
    def prov_dir(self) -> Path:
        """Per-artefact provenance sidecars. Lives in the code repo, gitignored.

        Sidecars are written one per artefact so parallel Snakemake jobs never
        race on a shared file. They are merged into BUILD.json afterwards.
        """
        return self.root / ".artefacts" / "prov"

    def tier_of(self, path: Path) -> str | None:
        """Which tier a path belongs to, or None if it is outside all of them."""
        p = self._abs(path)
        best: tuple[int, str] | None = None
        for name, tier_root in self.tiers.items():
            tr = self._abs(tier_root)
            if p == tr or tr in p.parents:
                depth = len(tr.parts)
                if best is None or depth > best[0]:
                    best = (depth, name)
        return best[1] if best else None

    def _abs(self, path: Path) -> Path:
        path = Path(path)
        return path if path.is_absolute() else (self.root / path)

    def build_json(self, tier: str) -> Path:
        return self._abs(self.tiers[tier]) / "BUILD.json"

    @property
    def methods_ledger(self) -> Path:
        """The values the methods text was last reviewed against.

        It lives in the paper repo, because the review is about the manuscript,
        and that repo has one branch however many the code repo has.
        """
        return self.root / self.paper_dir / "methods-reviewed.json"

    def is_methods_macro(self, name: str) -> bool:
        """A methods setting: a generated macro whose name starts with `mth`.

        This is the one place a macro name means something to the tools.
        """
        return name.startswith(self.methods_prefix)

    def is_methods_table(self, path) -> bool:
        """A methods table: tables/methods-*.tex in a tier."""
        p = Path(path)
        return p.parent.name == "tables" and p.name.startswith(self.methods_table_prefix)


def find_root(start: Path | None = None) -> Path:
    """Walk up from `start` looking for the project marker."""
    here = (start or Path.cwd()).resolve()
    for candidate in [here, *here.parents]:
        if (candidate / MARKER).is_file():
            return candidate
    raise ArtefactError(
        f"No {MARKER} found in {here} or any parent. "
        "This is not a reproducible-paper-artefacts project."
    )


def load_config(start: Path | None = None) -> Config:
    root = find_root(start)
    with (root / MARKER).open("rb") as fh:
        raw = tomllib.load(fh)

    project = raw.get("project", {})
    tiers_raw = raw.get("tiers", {})
    guard = raw.get("guard", {})
    methods = raw.get("methods", {})

    missing = [k for k in ("scratch", "notes", "paper") if k not in tiers_raw]
    if missing:
        raise ArtefactError(f"{MARKER} is missing [tiers] entries: {', '.join(missing)}")

    paper_dir = Path(project.get("paper_dir", "paper"))
    return Config(
        root=root,
        paper_dir=paper_dir,
        main_branch=project.get("main_branch", "main"),
        main_tex=Path(project.get("main_tex", str(paper_dir / "main.tex"))),
        tiers={k: Path(v) for k, v in tiers_raw.items()},
        max_file_mb=float(guard.get("max_file_mb", 20)),
        secret_patterns=list(
            guard.get(
                "secret_patterns",
                [
                    "*.pem", "*.key", "*.p12", "*.pfx",
                    ".env", ".env.*", "*_rsa", "*_ed25519",
                    "id_rsa", "credentials.json", "*.secret",
                ],
            )
        ),
        methods_strict=bool(methods.get("strict", False)),
    )


# --------------------------------------------------------------------------
# Git
# --------------------------------------------------------------------------


def _git_env() -> dict[str, str]:
    # Snakemake jobs record provenance in parallel. Without this, `git status`
    # and `git diff` may take index.lock to refresh the index, and two jobs
    # recording at the same moment make one of them fail.
    return {**os.environ, "GIT_OPTIONAL_LOCKS": "0"}


def git(*args: str, cwd: Path, check: bool = True) -> str:
    proc = subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        env=_git_env(),
    )
    if check and proc.returncode != 0:
        raise ArtefactError(
            f"git {' '.join(args)} failed in {cwd}:\n{proc.stderr.strip()}"
        )
    return proc.stdout.strip()


def git_ok(*args: str, cwd: Path) -> bool:
    """Run a git command purely for its exit status."""
    proc = subprocess.run(
        ["git", *args], cwd=str(cwd), capture_output=True, text=True, env=_git_env()
    )
    return proc.returncode == 0


def head_commit(cwd: Path) -> str:
    return git("rev-parse", "HEAD", cwd=cwd)


def branch_name(cwd: Path) -> str | None:
    """The checked-out branch, or None when HEAD is detached.

    During a rebase, a bisect, or after checking out a commit to look at
    something, `git rev-parse --abbrev-ref HEAD` prints the literal string HEAD.
    Treating that as a branch is how work gets committed somewhere that becomes
    unreachable the moment anything else is checked out, so detached is None.
    """
    if not git_ok("symbolic-ref", "-q", "HEAD", cwd=cwd):
        return None
    return git("rev-parse", "--abbrev-ref", "HEAD", cwd=cwd)


def dirty_paths(cwd: Path, pathspec: str | None = None) -> list[str]:
    """Paths that differ from HEAD, plus untracked files git would add.

    Deliberately avoids parsing `git status --porcelain`. That format puts a
    two-character status in front of the path, and any helper that strips
    whitespace from the output eats the leading space of the first line and
    shifts every offset by one. Asking for bare filenames removes the whole
    class of bug.
    """
    spec = ["--", pathspec] if pathspec else []
    out: list[str] = []
    if git_ok("rev-parse", "--verify", "HEAD", cwd=cwd):
        out += git("diff", "--name-only", "HEAD", *spec, cwd=cwd).splitlines()
    else:
        # No commits yet, so everything staged counts as pending.
        out += git("diff", "--name-only", "--cached", *spec, cwd=cwd).splitlines()
    out += git(
        "ls-files", "--others", "--exclude-standard", *spec, cwd=cwd
    ).splitlines()
    return sorted({p for p in out if p.strip()})


def commit_exists(commit: str, cwd: Path) -> bool:
    return git_ok("cat-file", "-e", f"{commit}^{{commit}}", cwd=cwd)


def is_ancestor(commit: str, ref: str, cwd: Path) -> bool:
    """True when `commit` is reachable from `ref`.

    This is the paper-tier invariant. It is stronger than a clean-tree check
    because it also catches an artefact built from a pristine tree on a branch
    that was later abandoned.
    """
    return git_ok("merge-base", "--is-ancestor", commit, ref, cwd=cwd)


def is_reachable(commit: str, cwd: Path) -> bool:
    """True when some branch, tag or remote ref contains `commit`."""
    if not commit_exists(commit, cwd):
        return False
    out = git(
        "for-each-ref", f"--contains={commit}", "--count=1", "--format=%(refname)",
        cwd=cwd, check=False,
    )
    return bool(out.strip())


# --------------------------------------------------------------------------
# Records: what produced each file
# --------------------------------------------------------------------------


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_build_json(cfg: Config, tier: str) -> dict:
    path = cfg.build_json(tier)
    if not path.is_file():
        return {"artefacts": {}}
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise ArtefactError(f"Corrupt {path}: {exc}") from exc


def load_sidecars(cfg: Config) -> list[dict]:
    if not cfg.prov_dir.is_dir():
        return []
    out = []
    for sc in sorted(cfg.prov_dir.glob("*.json")):
        try:
            out.append(json.loads(sc.read_text()))
        except json.JSONDecodeError as exc:
            raise ArtefactError(f"Corrupt provenance sidecar {sc}: {exc}") from exc
    return out


def load_records(cfg: Config, tier: str) -> dict[str, dict]:
    """What produced each file in a tier, keyed by path from the project root.

    BUILD.json is the published record, and it can lag behind the files. A
    build that stops part way leaves sidecars that were never merged, and a
    clone on another machine has BUILD.json but none of this machine's
    sidecars. So both are read. For each file, the record whose hash matches
    the file on disk wins; failing that, the newer one does, so a file that
    matches neither is judged against its latest build. Records for files that
    no longer exist are dropped.

    Every reader uses this, so the guard, the checks and the status report all
    see the same thing, and the next merge writes exactly that.
    """
    records = dict(load_build_json(cfg, tier).get("artefacts", {}))
    for rec in load_sidecars(cfg):
        if rec.get("tier") != tier:
            continue
        old = records.get(rec["path"])
        if old is None or _prefer_sidecar(cfg, rec, old):
            records[rec["path"]] = rec
    return {k: v for k, v in records.items() if (cfg.root / k).is_file()}


def _prefer_sidecar(cfg: Config, new: dict, old: dict) -> bool:
    path = cfg.root / new["path"]
    if not path.is_file():
        return True
    actual = sha256_file(path)
    if new.get("sha256") == actual:
        return True
    if old.get("sha256") == actual:
        return False
    return new.get("built_at", "") >= old.get("built_at", "")


def drifted(cfg: Config, tier: str) -> list[str]:
    """Files whose content differs from the hash recorded when they were built.

    This is how an edit after the build shows up, whoever made it: a coauthor
    uploading a replacement through the Overleaf file menu, or someone fixing a
    number in the .tex by hand. It is a comparison with the recorded hash, so it
    never confuses a fresh build that has not been pushed with a hand edit.
    """
    out = []
    for key, rec in load_records(cfg, tier).items():
        recorded = rec.get("sha256")
        if recorded and sha256_file(cfg.root / key) != recorded:
            out.append(key)
    return sorted(out)


def rel(cfg: Config, path: Path) -> str:
    """Path relative to the project root, for stable keys and readable output."""
    p = Path(path)
    p = p if p.is_absolute() else (cfg.root / p)
    try:
        return str(p.resolve().relative_to(cfg.root.resolve()))
    except ValueError:
        return str(p)


# --------------------------------------------------------------------------
# Output
# --------------------------------------------------------------------------

_COLOR = sys.stdout.isatty() and os.environ.get("NO_COLOR") is None


def _paint(code: str, text: str) -> str:
    return f"\033[{code}m{text}\033[0m" if _COLOR else text


def ok(msg: str) -> None:
    print(f"{_paint('32', 'ok')}      {msg}")


def warn(msg: str) -> None:
    print(f"{_paint('33', 'warning')} {msg}")


def fail(msg: str) -> None:
    # stdout, not stderr. These lines are part of a report that has to read in
    # order, and a caller deciding pass or fail reads the exit code.
    print(f"{_paint('31', 'FAIL')}    {msg}")


def info(msg: str) -> None:
    print(f"        {msg}")


if __name__ == "__main__":
    try:
        _cfg = load_config()
    except ArtefactError as exc:
        sys.exit(str(exc))
    _settings = {
        "main_branch": _cfg.main_branch,
        "main_tex": str(_cfg.main_tex),
        "paper_dir": str(_cfg.paper_dir),
    }
    print(" ".join(_settings[name] for name in sys.argv[1:]))
