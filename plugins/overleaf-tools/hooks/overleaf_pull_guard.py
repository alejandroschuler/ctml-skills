#!/usr/bin/env python3
"""PreToolUse hook that stops reads and edits of the files in an Overleaf clone
that are behind Overleaf.

The hook finds what a tool call touches: the file or folder of Read, Edit,
Write, NotebookEdit, Grep and Glob, and for Bash the working directory and each
word of the command. For each git repo among them with a remote on
git.overleaf.com, it compares the local HEAD with the commit on Overleaf. When
Overleaf has a commit that HEAD does not contain, the hook fetches it and lists
the files that Overleaf changed after the two histories split. The fetch
updates only the remote-tracking refs. It never changes HEAD or the files.
Then:

- The hook denies a call that names one of those files, and tells Claude how
  to pull. A Bash command names a file when its text has the file name with
  no other path characters next to it, or when one of its words is the path
  of the file, the end of that path, or a wildcard or {a,b} list that matches
  it.
- A call that covers a folder with one of those files in it, such as a Grep of
  the whole clone, goes through with a note that lists the files.
- A call that touches only other files goes through with no note.

Paths are compared without regard to case, as on the default macOS file
system. When the fetch fails, the hook cannot tell which files changed, so it
denies every call that touches the clone. It keeps the failure for five
minutes, so that a fetch that hangs delays only the first call.

A check of Overleaf (`git ls-remote`) takes about a second, so the hook makes
one at most every five minutes for each repo and keeps the answer in the
plugin's data folder. The fetch runs once for each new commit on Overleaf. The
comparison with HEAD runs on every call, so a pull clears the block at once. A
Bash command that pulls (`git pull`, `merge` or `rebase`, or `make
pull-paper`) passes without a check, so the pull itself is never blocked. In
other Bash commands, the hook leaves the git commands out of the check. Any
other failure (no network, no token, a timeout, input that does not parse)
lets the call through.
"""

import fnmatch
import glob
import hashlib
import itertools
import json
import os
import re
import shlex
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

try:
    import fcntl
except ImportError:  # not on Windows
    fcntl = None

OVERLEAF_HOST = "git.overleaf.com"
CHECK_INTERVAL = 5 * 60  # seconds between checks of Overleaf for one repo
LS_REMOTE_TIMEOUT = 10  # seconds
FETCH_TIMEOUT = 15  # seconds, including the wait for a fetch by another call
MAX_WORDS = 200  # words of a Bash command to look at
MAX_BRACES = 64  # words that one {a,b} expansion can give
MAX_MATCHES = 20  # paths of a Bash wildcard to look at
MAX_LISTED = 10  # changed files to name in a message
CACHE_MAX_AGE = 24 * 60 * 60  # seconds before a cache entry is dropped

PULL_COMMAND = re.compile(
    r"(^|[\s;&|(`/])git\s[^;&|\n]*\b(pull|merge|rebase)\b|\bpull-paper\b"
)
SEGMENT = re.compile(r"&&|\|\||[;|\n]")
GIT_SEGMENT = re.compile(r"^\s*(\w+=\S*\s+)*(\S*/)?git(\s|$)")
PAPER_DIR = re.compile(r'^\s*paper_dir\s*=\s*"([^"]+)"', re.M)
WILDCARD = re.compile(r"[*?\[]")
BRACES = re.compile(r"\{([^{}]*,[^{}]*)\}")
OPERATOR = "();<>|&"
PLAIN_WORD = re.compile(r"[^\s'\"`();<>|&]+")

# The clone is behind Overleaf, but the hook could not fetch the new commits
# to see which files they change.
UNKNOWN = object()


def run_git(root, *args, timeout=5):
    """Run git in root. Return the finished process, or None if git failed to run."""
    env = dict(os.environ, GIT_TERMINAL_PROMPT="0")
    try:
        proc = subprocess.Popen(
            ["git", "-C", str(root), *args],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            env=env,
            start_new_session=True,
        )
    except (OSError, ValueError):
        return None
    try:
        out, _ = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        # Kill the whole process group, so that a remote helper that git
        # started does not live on.
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except (AttributeError, OSError):
            proc.kill()
        proc.wait()
        return None
    return subprocess.CompletedProcess(proc.args, proc.returncode, out)


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


def is_dir(path):
    try:
        return path.is_dir()
    except (OSError, ValueError):
        return False


def literal_part(path):
    """The folders of path above its first wildcard."""
    parts = path.parts
    for i, part in enumerate(parts):
        if WILDCARD.search(part):
            return Path(*parts[:i])
    return path


def matches(pattern):
    """Up to MAX_MATCHES paths that the wildcard pattern matches."""
    try:
        return list(itertools.islice(glob.iglob(str(pattern)), MAX_MATCHES))
    except (OSError, ValueError, re.error):
        return []


def bash_words(command):
    """Words of a Bash command, with operators such as && and > as words of their own."""
    lexer = shlex.shlex(command, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    lexer.commenters = ""  # a # inside a word, as in s#a#b#, is not a comment
    try:
        return list(lexer)
    except ValueError:
        # An unclosed quote, such as an apostrophe in a heredoc. Treat quotes
        # and operators as spaces.
        return PLAIN_WORD.findall(command)


def without_git(command):
    """The command with its git commands left out."""
    return "\n".join(
        part for part in SEGMENT.split(command) if not GIT_SEGMENT.match(part)
    )


def expand_braces(word):
    """The words that Bash makes from word by {a,b} expansion."""
    words = [word]
    for _ in range(MAX_BRACES):
        for i, item in enumerate(words):
            match = BRACES.search(item)
            if match:
                words[i:i + 1] = [
                    item[:match.start()] + part + item[match.end():]
                    for part in match.group(1).split(",")
                ]
                break
        else:
            break
    return words[:MAX_BRACES]


def targets(payload):
    """What the tool call touches, as far as the input shows.

    Returns (found, text). Each target in found is (kind, path, word). kind is
    "file" for a file that the call reads or writes, "folder" for a folder that
    it searches or works in, and "pattern" for a word with a wildcard. word is
    the Bash word or Grep glob that gave the target, or None. text is the Bash
    command without its git commands, or None for other tools.
    """
    cwd = str(payload.get("cwd") or os.getcwd())
    tool = payload.get("tool_name") or ""
    tool_input = payload.get("tool_input") or {}

    if tool == "Bash":
        command = str(tool_input.get("command") or "")
        if PULL_COMMAND.search(command):
            return [], None
        text = without_git(command)
        found = [("folder", Path(cwd), None)]
        for token in bash_words(text)[:MAX_WORDS]:
            # Look at the value of --opt=value and NAME=value too. The name of
            # an option is not a path.
            tokens = [token]
            if "=" in token:
                tokens.append(token.split("=", 1)[1])
            if token.startswith("-"):
                tokens = tokens[1:]
            for word in (w for t in tokens for w in expand_braces(t)):
                if not word.strip(OPERATOR) or "://" in word:
                    continue
                path = as_path(cwd, word)
                if WILDCARD.search(word):
                    found.append(("pattern", path, word))
                elif is_dir(path):
                    found.append(("folder", path, word))
                else:
                    found.append(("file", path, word))
        return found, text

    if tool == "Glob":
        # Glob lists file names and reads no content, so it only covers folders.
        folder = tool_input.get("path")
        if not isinstance(folder, str) or not folder:
            folder = cwd
        found = [("folder", as_path(cwd, folder), None)]
        pattern = tool_input.get("pattern")
        if isinstance(pattern, str) and os.path.isabs(os.path.expanduser(pattern)):
            found.append(("folder", literal_part(as_path(cwd, pattern)), None))
        return found, None

    values = [tool_input.get(key) for key in ("file_path", "notebook_path", "path")]
    if isinstance(tool_input.get("paths"), list):
        values += tool_input["paths"]
    found = []
    for value in values:
        if isinstance(value, str) and value:
            path = as_path(cwd, value)
            found.append(("folder" if is_dir(path) else "file", path, None))
    if tool == "Grep":
        if not found:
            found.append(("folder", Path(cwd), None))
        # A glob with no wildcard, such as sections/intro.tex, names the file
        # that the Grep reads. A glob with a wildcard only narrows a folder.
        name_filter = tool_input.get("glob")
        if isinstance(name_filter, str) and name_filter:
            base = found[0][1]
            for word in expand_braces(name_filter):
                if not WILDCARD.search(word):
                    found.append(("file", as_path(str(base), word), word))
    return found, None


def repo_root(path):
    """Top of the git work tree that holds path, or None."""
    for folder in [path, *path.parents]:
        if exists(folder / ".git"):
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


def data_folder():
    return Path(
        os.environ.get("CLAUDE_PLUGIN_DATA")
        or os.path.join(tempfile.gettempdir(), "overleaf-pull-guard")
    )


def cache_file():
    return data_folder() / "overleaf-heads.json"


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


def has_commit(root, sha):
    """True or False, or None if git failed to run."""
    done = run_git(root, "cat-file", "-e", f"{sha}^{{commit}}")
    return None if done is None else done.returncode == 0


def open_lock(root):
    name = hashlib.sha1(str(root).encode()).hexdigest()[:16]
    try:
        data_folder().mkdir(parents=True, exist_ok=True)
        return open(data_folder() / f"fetch-{name}.lock", "w")
    except OSError:
        return None


def failed_recently(key):
    entry = load_cache().get(key)
    return isinstance(entry, dict) and time.time() - entry.get("t", 0) < CHECK_INTERVAL


def fetch(root, remote, sha):
    """Fetch from remote so that sha is in the local repo. True when it is there.

    Parallel tool calls each run this hook. A lock lets one of them fetch while
    the others wait, so that they do not fight over the ref locks. A failed
    fetch is cached for CHECK_INTERVAL, so that a fetch that hangs does not
    delay every call.
    """
    key = f"fetch|{root}|{sha}"
    if failed_recently(key):
        return bool(has_commit(root, sha))
    deadline = time.time() + FETCH_TIMEOUT
    lock = open_lock(root)
    try:
        while lock is not None and fcntl is not None:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.time() > deadline:
                    return bool(has_commit(root, sha))
                time.sleep(0.2)
            except OSError:
                break  # no lock on this file system, so fetch without one
        if has_commit(root, sha) or failed_recently(key):
            return bool(has_commit(root, sha))
        run_git(
            root,
            "fetch",
            "--quiet",
            "--no-tags",
            "--no-write-fetch-head",
            remote,
            timeout=max(1, deadline - time.time()),
        )
        if has_commit(root, sha):
            return True
        cache = load_cache()
        cache[key] = {"t": time.time()}
        save_cache(cache)
        return False
    finally:
        if lock is not None:
            lock.close()


def changed_on_overleaf(root):
    """Files that changed on Overleaf and that root does not have yet.

    Returns None if root is not an Overleaf clone or is not behind, a list of
    paths relative to root if it is behind, and UNKNOWN if it is behind but
    the commits from Overleaf could not be fetched.
    """
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
    known = has_commit(root, sha)
    if known is None:
        return None
    if known:
        # If Overleaf's commit is in the local history, the copy is up to date
        # or ahead with commits that are not pushed yet.
        contained = run_git(root, "merge-base", "--is-ancestor", sha, head)
        if contained is None or contained.returncode == 0:
            return None
    elif not fetch(root, remote, sha):
        return UNKNOWN
    # HEAD...sha compares sha with the last commit that both histories share,
    # so only the changes made on Overleaf count. --no-renames lists both
    # names of a moved file.
    out = git_out(root, "diff", "--name-only", "--no-renames", "-z", f"HEAD...{sha}")
    if out is None:
        return UNKNOWN
    return sorted(name for name in out.split("\0") if name)


def fold(path):
    """path as a string to compare without regard to case."""
    return str(path).casefold()


def ends_path(tail, word):
    """True if word, as written in a command, is the end of the path tail."""
    word = fold(os.path.normpath(word))
    if word == "." or word.startswith(("/", "..", "~")):
        return False
    return tail.endswith("/" + word)


def names(target, path, tail):
    """True if the target names the file at path, whose path in the clone is tail.

    Both path and tail are folded.
    """
    kind, where, word = target
    if kind == "file":
        return fold(where) == path or (word is not None and ends_path(tail, word))
    if kind == "pattern":
        return fnmatch.fnmatchcase(path, fold(where)) or fnmatch.fnmatchcase(
            tail, "*/" + fold(os.path.normpath(word))
        )
    return False


def covers(target, path):
    """True if the target is a folder that holds the file at path, which is folded."""
    kind, where, _ = target
    where = fold(where).rstrip("/")
    return kind == "folder" and (path == where or path.startswith(where + "/"))


def mentions(text, name):
    """True if text has the file name of name with no path characters next to it."""
    base = re.escape(name.rsplit("/", 1)[-1])
    return re.search(rf"(?<![\w.-]){base}(?![\w.-])", text, re.I) is not None


def sort_out(root, changed, found, text):
    """Split the changed files into those the call names and those it only covers."""
    named, covered = [], []
    for name in changed:
        path = fold(root / name)
        tail = fold("/" + name)
        if (text is not None and mentions(text, name)) or any(
            names(target, path, tail) for target in found
        ):
            named.append(name)
        elif any(covers(target, path) for target in found):
            covered.append(name)
    return named, covered


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


def pull_command(root):
    code = pipeline_root(root)
    if code:
        return f"`make -C {shlex.quote(str(code))} pull-paper`"
    return f"`git -C {shlex.quote(str(root))} pull --rebase --autostash`"


def listed(names):
    shown = ", ".join(f"`{name}`" for name in names[:MAX_LISTED])
    if len(names) > MAX_LISTED:
        shown += f" and {len(names) - MAX_LISTED} more"
    return shown


def unknown_message(root):
    return (
        f"Blocked: {root} is behind Overleaf, and the hook could not fetch the "
        "new commits to see which files they change. What you read or edit "
        f"here can be out of date. Pull first with {pull_command(root)}, then "
        "retry. If the pull reports a conflict, stop and show it to the user. "
        "If you cannot run git (for example, you are a subagent without Bash), "
        "stop and report this block to your caller."
    )


def named_message(root, names):
    files = "this file" if len(names) == 1 else "these files"
    return (
        f"Blocked: {listed(names)} changed on Overleaf, and the copy in {root} "
        f"is out of date. Pull first with {pull_command(root)}, then retry. If "
        "the pull reports a conflict, stop and show it to the user. If you "
        "cannot run git (for example, you are a subagent without Bash), stop "
        f"the work that needs {files} and report this block to your caller. "
        "The hook blocks only the files that changed on Overleaf, so you can "
        "still read and edit the others."
    )


def covered_message(root, names):
    files, them = ("that file", "it") if len(names) == 1 else ("those files", "them")
    return (
        f"Note: {listed(names)} changed on Overleaf, and the copy in {root} is "
        f"out of date. The results of this call from {files} can be out of "
        f"date. Before you rely on {them} or edit {them}, pull with "
        f"{pull_command(root)}. If you cannot run git (for example, you are a "
        "subagent without Bash), tell your caller."
    )


def main():
    try:
        payload = json.load(sys.stdin)
    except ValueError:
        return
    if not isinstance(payload, dict):
        return
    found, text = targets(payload)
    roots = []
    for kind, path, _ in found:
        paths = [path]
        if kind == "pattern":
            # The wildcard can stand for the clone itself, as in pap*/main.tex.
            paths = [literal_part(path), *map(Path, matches(path))]
        for root in map(repo_root, paths):
            if root and root not in roots:
                roots.append(root)
    denials, notes = [], []
    for root in roots:
        changed = changed_on_overleaf(root)
        if not changed:
            continue
        if changed is UNKNOWN:
            denials.append(unknown_message(root))
            continue
        named, covered = sort_out(root, changed, found, text)
        if named:
            denials.append(named_message(root, named))
        elif covered:
            notes.append(covered_message(root, covered))
    if denials:
        output = {
            "permissionDecision": "deny",
            "permissionDecisionReason": "\n\n".join(denials),
        }
    elif notes:
        output = {"additionalContext": "\n\n".join(notes)}
    else:
        return
    json.dump(
        {"hookSpecificOutput": {"hookEventName": "PreToolUse", **output}},
        sys.stdout,
    )


if __name__ == "__main__":
    try:
        main()
    except Exception:
        # The hook must never get in the way when it fails.
        pass
