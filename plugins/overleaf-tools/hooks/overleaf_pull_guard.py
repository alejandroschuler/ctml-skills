#!/usr/bin/env python3
"""PreToolUse hook that stops reads and edits of an Overleaf clone that is
behind Overleaf.

The hook finds the git repos that a tool call touches: the file or folder of
Read, Edit, Write, NotebookEdit, Grep and Glob, and for Bash the working
directory and each word of the command that names a path. For each repo with a
remote on git.overleaf.com, it compares the local HEAD with the commit on
Overleaf. When Overleaf has a commit that HEAD does not contain, the hook
denies the call and tells Claude how to pull.

A check of Overleaf (`git ls-remote`) takes about a second, so the hook makes
one at most every five minutes for each repo and keeps the answer in the
plugin's data folder. The comparison with HEAD runs on every call, so a pull
clears the block at once. A Bash command that runs git or `make pull-paper`
passes without a check, so the pull itself is never blocked. Any failure (no
network, no token, a timeout, input that does not parse) lets the call
through.
"""

import json
import os
import re
import shlex
import subprocess
import sys
import tempfile
import time
from pathlib import Path

OVERLEAF_HOST = "git.overleaf.com"
CHECK_INTERVAL = 5 * 60  # seconds between checks of Overleaf for one repo
LS_REMOTE_TIMEOUT = 10  # seconds
MAX_WORDS = 50  # words of a Bash command to look at
CACHE_MAX_AGE = 24 * 60 * 60  # seconds before a cache entry is dropped

PULL_COMMAND = re.compile(r"(^|[\s;&|(`/])(git(\s|$)|pull-paper\b)")
PAPER_DIR = re.compile(r'^\s*paper_dir\s*=\s*"([^"]+)"', re.M)


def run_git(root, *args, timeout=5):
    """Run git in root. Return the finished process, or None if git failed to run."""
    env = dict(os.environ, GIT_TERMINAL_PROMPT="0")
    try:
        return subprocess.run(
            ["git", "-C", str(root), *args],
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )
    except (OSError, subprocess.SubprocessError):
        return None


def git_out(root, *args, timeout=5):
    """Stdout of a git command that succeeded, or None."""
    done = run_git(root, *args, timeout=timeout)
    if done is None or done.returncode != 0:
        return None
    return done.stdout.strip()


def as_path(cwd, text):
    return Path(os.path.abspath(os.path.join(cwd, os.path.expanduser(text))))


def exists(path):
    try:
        return path.exists()
    except (OSError, ValueError):
        return False


def candidate_paths(payload):
    """Paths that the tool call reads or writes, as far as the input shows."""
    cwd = str(payload.get("cwd") or os.getcwd())
    tool = payload.get("tool_name") or ""
    tool_input = payload.get("tool_input") or {}

    if tool == "Bash":
        command = str(tool_input.get("command") or "")
        if PULL_COMMAND.search(command):
            return []
        try:
            words = shlex.split(command)
        except ValueError:
            words = command.split()
        paths = [Path(cwd)]
        for word in words[:MAX_WORDS]:
            if word.startswith("-"):
                if "=" not in word:
                    continue
                word = word.split("=", 1)[1]
            if not word or "://" in word:
                continue
            path = as_path(cwd, word)
            if "/" in word or exists(path):
                paths.append(path)
        return paths

    paths = []
    keys = ["file_path", "notebook_path", "path"]
    if tool == "Glob":
        keys.append("pattern")
    for key in keys:
        value = tool_input.get(key)
        if isinstance(value, str) and value:
            paths.append(as_path(cwd, value))
    value = tool_input.get("paths")
    if isinstance(value, list):
        paths += [as_path(cwd, v) for v in value if isinstance(v, str) and v]
    if not paths and tool in ("Grep", "Glob"):
        paths.append(Path(cwd))
    return paths


def repo_root(path):
    """Top of the git work tree that holds path, or None."""
    for folder in [path, *path.parents]:
        if (folder / ".git").exists():
            return folder
    return None


def overleaf_config(root):
    """Remote URLs and branch upstreams of root, or None if no remote is on Overleaf."""
    dot_git = root / ".git"
    if dot_git.is_dir():
        # Most tool calls are in repos with no Overleaf remote. Reading the
        # config file is faster than starting git.
        try:
            if OVERLEAF_HOST not in (dot_git / "config").read_text(errors="replace"):
                return None
        except OSError:
            return None
    out = git_out(
        root,
        "config",
        "--get-regexp",
        r"^(remote\..*\.url|branch\..*\.(remote|merge))$",
    )
    config = {}
    for line in (out or "").splitlines():
        key, _, value = line.partition(" ")
        config[key] = value
    if not any(
        k.startswith("remote.") and OVERLEAF_HOST in v for k, v in config.items()
    ):
        return None
    return config


def upstream(config, branch):
    """The Overleaf remote and ref that branch tracks, or the Overleaf HEAD."""
    remotes = [
        k[len("remote."):-len(".url")]
        for k, v in config.items()
        if k.startswith("remote.") and OVERLEAF_HOST in v
    ]
    if branch.startswith("refs/heads/"):
        name = branch[len("refs/heads/"):]
        remote = config.get(f"branch.{name}.remote")
        ref = config.get(f"branch.{name}.merge")
        if remote in remotes and ref:
            return remote, ref
    return remotes[0], "HEAD"


def cache_file():
    folder = os.environ.get("CLAUDE_PLUGIN_DATA") or os.path.join(
        tempfile.gettempdir(), "overleaf-pull-guard"
    )
    return Path(folder) / "overleaf-heads.json"


def load_cache():
    try:
        data = json.loads(cache_file().read_text())
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def save_cache(cache):
    path = cache_file()
    now = time.time()
    cache = {
        k: v
        for k, v in cache.items()
        if isinstance(v, dict) and now - v.get("t", 0) < CACHE_MAX_AGE
    }
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
        with os.fdopen(fd, "w") as f:
            json.dump(cache, f)
        os.replace(tmp, path)
    except OSError:
        pass


def overleaf_head(root, remote, ref):
    """Commit at ref on Overleaf, from the cache when it is recent, or None."""
    key = f"{root}|{remote}|{ref}"
    cache = load_cache()
    entry = cache.get(key)
    if isinstance(entry, dict) and time.time() - entry.get("t", 0) < CHECK_INTERVAL:
        return entry.get("sha")
    out = git_out(root, "ls-remote", remote, ref, timeout=LS_REMOTE_TIMEOUT)
    sha = out.split()[0] if out else None
    # A failed check is cached too, so that a lost network costs one timeout
    # every five minutes and not one on every call.
    cache[key] = {"t": time.time(), "sha": sha}
    save_cache(cache)
    return sha


def pipeline_root(root):
    """Code repo of a reproducible-paper-artefacts project whose paper is root."""
    for folder in list(root.parents)[:3]:
        try:
            text = (folder / ".artefacts.toml").read_text()
        except OSError:
            continue
        match = PAPER_DIR.search(text)
        paper = folder / (match.group(1) if match else "paper")
        if os.path.realpath(paper) == os.path.realpath(root):
            return folder
    return None


def stale_message(root):
    code = pipeline_root(root)
    if code:
        pull = f"`make -C {shlex.quote(str(code))} pull-paper`"
    else:
        pull = f"`git -C {shlex.quote(str(root))} pull --rebase --autostash`"
    return (
        f"Blocked: {root} is behind Overleaf. Overleaf has commits that this "
        "copy does not have, so what you read or edit here can be out of date. "
        f"Pull first with {pull}, then retry. If the pull reports a conflict, "
        "stop and show it to the user. If you cannot run git (for example, you "
        "are a subagent without Bash), stop and report this block to your caller."
    )


def check(root):
    """A message if root is an Overleaf clone that is behind Overleaf, else None."""
    config = overleaf_config(root)
    if not config:
        return None
    out = git_out(root, "rev-parse", "HEAD", "--symbolic-full-name", "HEAD")
    lines = (out or "").splitlines()
    if len(lines) != 2:
        return None
    head, branch = lines
    remote, ref = upstream(config, branch)
    sha = overleaf_head(root, remote, ref)
    if not sha or sha == head:
        return None
    # Overleaf's commit is in the local history, so the copy is up to date or
    # ahead with commits that are not pushed yet.
    known = run_git(root, "cat-file", "-e", f"{sha}^{{commit}}")
    if known is None:
        return None
    if known.returncode == 0:
        contained = run_git(root, "merge-base", "--is-ancestor", sha, head)
        if contained is None or contained.returncode == 0:
            return None
    return stale_message(root)


def main():
    try:
        payload = json.load(sys.stdin)
    except ValueError:
        return
    if not isinstance(payload, dict):
        return
    roots = []
    for path in candidate_paths(payload):
        root = repo_root(path)
        if root and root not in roots:
            roots.append(root)
    problems = [m for m in map(check, roots) if m]
    if not problems:
        return
    json.dump(
        {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": "\n\n".join(problems),
            }
        },
        sys.stdout,
    )


if __name__ == "__main__":
    try:
        main()
    except Exception:
        # The hook must never get in the way when it fails.
        pass
