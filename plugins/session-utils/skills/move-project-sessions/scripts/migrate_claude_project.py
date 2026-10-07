#!/usr/bin/env python3
"""
Migrate Claude Code's metadata after a project folder has been moved or
renamed on disk, so the desktop-app sidebar and `claude --resume` keep working.

Moving a project breaks Claude Code because the project's *old absolute path*
is recorded in several stores. When that path no longer exists, the sidebar
drops the project and the CLI can't find its history. This script rewrites the
old path to the new one in four stores.

The move covers the old path and every path under it. A project inside the
moved folder, such as a worktree under .claude/worktrees/, moves in the same
run: a path under the old path becomes the same path under the new path.

Stores handled (macOS paths shown; see app_support_dir() for other OSes):

  1. CLI transcripts:  ~/.claude/projects/<encoded-path>/
       - one folder per project path, named after the path: every character
         other than an ASCII letter or digit becomes "-", and a name longer
         than 200 characters is cut and gets a hash (the rule of Claude Code 2.1)
       - each *.jsonl record (incl. subagents/) has an internal "cwd" plus
         file references that point at the old path
       - if a folder's new name exists already (a session already ran at the
         new path), the old folder merges into it
  2. Global config:    ~/.claude.json
       - the "projects" object is keyed by absolute path; if a new key exists
         already, the old entry merges into it
       - the paths in each entry's "activeWorktreeSession", and the top-level
         "githubRepoPaths" lists
  3. Desktop sidebar:  ~/Library/Application Support/Claude/claude-code-sessions/**/local_*.json
       - "cwd", "originCwd", "worktreePath", "gitAnchors",
         "gitAnchorsFolderRealpath", "planPath", "worktreeLazy",
         "keptWorktreeLeftover", the directories in "sessionPermissionUpdates"
         and the paths in "writtenBranches"; the sidebar groups by "cwd"
  4. Desktop worktrees: ~/Library/Application Support/Claude/git-worktrees.json
       - the app's list of the worktrees it made: "path", "baseRepo",
         "originTopLevel", "placementRoot" and "anchors" of each entry

The git anchors in stores 3 and 4 are the desktop app's record of the
repositories it trusts, so the trust moves with the project.

Usage:
    # dry run (default): shows exactly what would change, touches nothing
    python3 migrate_claude_project.py --from /old/abs/path --to /new/abs/path

    # apply the changes (makes a timestamped backup first)
    python3 migrate_claude_project.py --from /old/abs/path --to /new/abs/path --apply

Exit codes:
    0  done, dry run printed, or nothing to migrate
    1  a write failed during --apply, or the check after it found a transcript
       that is not as planned; the message names the backup to restore
    2  bad arguments
    3  ABORT: a check needs a person (see the message); nothing was changed
    4  REFUSING: the Claude desktop app is running (see --force)

Safety notes:
  - Quit the Claude desktop app before running with --apply. It caches the
    session list in memory and rewrites its store on activity, so edits made
    while it runs can be clobbered and won't appear until a restart anyway.
  - Transcripts change only in the transcript folders of the moved projects,
    because the path can appear incidentally in unrelated projects'
    transcripts. In the JSON stores, only the fields listed above change, and
    only where they hold a path at or under the old path.
  - Every check runs before the first change, in a dry run and with --apply
    alike, and the backup is complete before the first change.
"""

import argparse
import copy
import filecmp
import functools
import json
import os
import platform
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import unicodedata
from datetime import datetime

EXIT_OK = 0
EXIT_ERROR = 1        # a write failed during --apply
# 2 is argparse's code for bad arguments
EXIT_ABORT = 3        # a check needs a person; nothing was changed
EXIT_APP_RUNNING = 4  # the desktop app is running and --force was not passed


# ---------------------------------------------------------------------------
# Path encoding (path -> ~/.claude/projects directory name)
# ---------------------------------------------------------------------------
# Claude Code 2.1 derives the projects/ subdirectory name from the absolute path
# with path.replace(/[^a-zA-Z0-9]/g, "-"). A name longer than 200 characters is
# cut to its first 200, followed by "-" and a base-36 hash of the path. The new
# directory always gets this name, because it is the one Claude Code reads.
# Older versions replaced fewer characters (only "/", or "/" and "."), so the
# old directory may carry an older name. We check which candidate reproduces
# the most existing (path -> directory) pairs on THIS machine and look for the
# old directory by that rule as well. A tie, or a machine with no evidence,
# goes to the current rule, which is first in ENCODERS.

MAX_NAME_LEN = 200

def js_string_hash(s):
    """Claude Code's 32-bit string hash, h = (h << 5) - h + charCode | 0, over
    the UTF-16 code units of s, as JavaScript computes it."""
    units = s.encode("utf-16-le", "surrogatepass")
    h = 0
    for i in range(0, len(units), 2):
        h = (h * 31 + units[i] + (units[i + 1] << 8)) & 0xFFFFFFFF
    return h - 0x100000000 if h & 0x80000000 else h

def to_base36(n):
    digits = "0123456789abcdefghijklmnopqrstuvwxyz"
    out = ""
    while True:
        n, r = divmod(n, 36)
        out = digits[r] + out
        if n == 0:
            return out

def enc_nonalnum(p):
    # JavaScript replaces UTF-16 code units, so a character outside the Basic
    # Multilingual Plane (an emoji, say) becomes two dashes.
    name = re.sub(r"[^A-Za-z0-9]", lambda m: "-" * (2 if ord(m.group()) > 0xFFFF else 1), p)
    if len(name) <= MAX_NAME_LEN:
        return name
    return f"{name[:MAX_NAME_LEN]}-{to_base36(abs(js_string_hash(p)))}"

def enc_slash_dot(p):
    return p.replace("/", "-").replace(".", "-")

def enc_slash(p):
    return p.replace("/", "-")

ENCODERS = [("nonalnum", enc_nonalnum), ("slash+dot", enc_slash_dot), ("slash", enc_slash)]


def detect_encoder(projects_dir, config_path):
    """Pick the encoder that best maps real .claude.json project keys to real
    projects/ directory names on this machine. Ties go to the earlier encoder.
    Also return each encoder's score, for the plan."""
    keys = []
    if os.path.isfile(config_path):
        try:
            with open(config_path, encoding="utf-8") as fh:
                keys = list(json.load(fh).get("projects", {}).keys())
        except Exception:
            keys = []
    try:
        dirs = set(os.listdir(projects_dir))
    except OSError:
        dirs = set()
    scores = {name: sum(1 for k in keys if fn(k) in dirs) for name, fn in ENCODERS}
    best_name, best_fn = ENCODERS[0]
    for name, fn in ENCODERS[1:]:
        if scores[name] > scores[best_name]:
            best_name, best_fn = name, fn
    return best_name, best_fn, scores


# ---------------------------------------------------------------------------
# Locations
# ---------------------------------------------------------------------------

def app_support_dir():
    home = os.path.expanduser("~")
    sysname = platform.system()
    if sysname == "Darwin":
        return os.path.join(home, "Library", "Application Support", "Claude")
    if sysname == "Windows":
        return os.path.join(os.environ.get("APPDATA", os.path.join(home, "AppData", "Roaming")), "Claude")
    # Linux / other
    return os.path.join(home, ".config", "Claude")

# the desktop app's list of the worktrees it made, in app_support_dir()
REGISTRY_FILE = "git-worktrees.json"


# ---------------------------------------------------------------------------
# Scope of the move
# ---------------------------------------------------------------------------
# The move covers the old path and every path under it. In the JSON stores a
# path field changes when its whole value is such a path; the rest of the
# value after the old path stays as it is.

_DOT_SEGMENT = re.compile(r"(^|/)\.\.?(/|$)")

def moved_path(p, old, new):
    """The path that p has after the move, or None when p is not part of it.
    p is part of the move when it is the old path or lies under it. When the
    new path lies inside the old one, a path at or under the new path counts
    as moved already, so it is not rewritten a second time."""
    if not isinstance(p, str):
        return None
    if _DOT_SEGMENT.search(p):
        # "/old/../old-backup" names a folder beside the old path, so a path
        # with "." or ".." segments counts by its normal form, which also
        # replaces it
        p = os.path.normpath(p)
    if not (p == old or p.startswith(old + "/")):
        return None
    if new.startswith(old + "/") and (p == new or p.startswith(new + "/")):
        return None
    return new + p[len(old):]

def _fold(p):
    return unicodedata.normalize("NFC", p).lower()

def case_variant(p, old):
    """The start of p if it spells the old path in another way that names the
    same folder on a disk that ignores letter case and Unicode form, as the
    disks of macOS do, and p is that path or lies under it; else None. The
    script changes only the exact spelling; the plan names these others."""
    if not isinstance(p, str) or p.startswith(old + "/") or p == old:
        return None
    key = _fold(old)
    for i in [j for j, c in enumerate(p) if c == "/" and j > 0] + [len(p)]:
        head = p[:i]
        if _fold(head) == key:
            return head
        if len(head) > 2 * len(old) + 8:
            break
    return None

def same_dir(a, b):
    """True if paths a and b are one real folder, as two names that differ
    only in case are on a disk that ignores case. A symlink is never the same."""
    try:
        return (not os.path.islink(a) and not os.path.islink(b)
                and os.path.isdir(a) and os.path.isdir(b) and os.path.samefile(a, b))
    except OSError:
        return False


# ---------------------------------------------------------------------------
# Boundary-safe path matching inside transcripts
# ---------------------------------------------------------------------------
# When we string-replace the old path inside a .jsonl, we must not catch a
# sibling like "/a/b/proj-backup" when migrating "/a/b/proj". A genuine
# occurrence of the project path is always followed by a path separator or a
# string delimiter, never by another name character.

def _name_char(c):
    return c.isalnum() or c in "-_"

def _ends_path(text, j):
    """True if a path that stops at index j of text ends there: no name
    character (a letter, a digit, '-' or '_') follows, not even after dots.
    Any other character is a boundary, such as a '.' or '?' that ends a
    sentence."""
    while j < len(text) and text[j] == ".":
        j += 1
    return not (j < len(text) and _name_char(text[j]))

def split_mentions(text, path):
    """Split text into (part, is_mention) pairs, where a mention is an
    occurrence of path that ends a path (see _ends_path)."""
    out, start = [], 0
    i = text.find(path)
    while i != -1:
        j = i + len(path)
        if _ends_path(text, j):
            out.append((text[start:i], False))
            out.append((path, True))
            start = j
            i = text.find(path, j)
        else:
            i = text.find(path, i + 1)
    out.append((text[start:], False))
    return out

def risky_occurrences(text, old, protect=None):
    """Return count of occurrences of `old` that do not end a path, i.e. where
    `old` is a prefix of a longer final path component such as proj-backup or
    proj.bak. Those would be wrong to replace. The mentions of `protect` (the
    new path, when it contains the old one) are skipped."""
    if protect:
        return sum(risky_occurrences(part, old) for part, mention in split_mentions(text, protect)
                   if not mention)
    risky = 0
    i = text.find(old)
    while i != -1:
        if not _ends_path(text, i + len(old)):
            risky += 1
        i = text.find(old, i + 1)
    return risky


def json_text(s):
    """s as it appears inside a JSON string written by JSON.stringify. It is s
    itself unless s holds a backslash, a quote or a control character."""
    return json.dumps(s, ensure_ascii=False)[1:-1]

def _parses(line):
    try:
        json.loads(line)
        return True
    except (ValueError, RecursionError):
        return False

def rewrite_lines(text, old, new):
    """Replace old with new, line by line. Return the new text and the number
    of lines that were valid JSON before the change but are not after it.
    If new contains old, as in a move from thesis to thesis-final, a mention
    of new (see split_mentions) stays as it is, so it is not rewritten a
    second time. Lines split on "\\n" only: str.splitlines() also splits at
    characters such as U+2028, which JSON strings may hold."""
    lines = text.split("\n")
    broken = 0
    for i, line in enumerate(lines):
        if old in line:
            if old in new:
                changed = "".join(part if mention else part.replace(old, new)
                                  for part, mention in split_mentions(line, new))
            else:
                changed = line.replace(old, new)
            if changed == line:
                continue
            if not _parses(changed) and _parses(line):
                broken += 1
            lines[i] = changed
    return "\n".join(lines), broken

def is_line_prefix(a, b):
    """True if text a is the start of text b and ends where a line of b ends,
    as when b is a longer copy of the same transcript."""
    return b.startswith(a) and (a == "" or a.endswith("\n") or len(a) == len(b) or b[len(a)] in "\r\n")


# ---------------------------------------------------------------------------
# Files
# ---------------------------------------------------------------------------
# Transcripts are read and written with surrogateescape and newline="", so a
# file keeps its exact bytes and line endings apart from the replaced path.

def read_text(path):
    with open(path, encoding="utf-8", errors="surrogateescape", newline="") as fh:
        return fh.read()

def write_atomic(path, text, like=None):
    """Write text to path through a temporary file in the same folder, so a
    failed write leaves the old file whole. A symlink is followed to its
    target. The result takes the permissions and times of the file `like`;
    without it, an existing file keeps its permissions and gets a new time."""
    path = os.path.realpath(path)
    ref = like or (path if os.path.exists(path) else None)
    st = os.stat(ref) if ref else None
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), prefix=".migrate-tmp-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", errors="surrogateescape", newline="") as fh:
            fh.write(text)
        if st:
            os.chmod(tmp, stat.S_IMODE(st.st_mode))
            if like:
                os.utime(tmp, ns=(st.st_atime_ns, st.st_mtime_ns))
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise

def rewrite_file(src, dst, old, new):
    """Write src to dst with old replaced by new. dst keeps src's times, so the
    session keeps its place in `claude --resume`."""
    text, broken = rewrite_lines(read_text(src), old, new)
    if broken:
        raise ValueError(f"{src}: replacing the old path breaks {broken} JSON line(s)")
    write_atomic(dst, text, like=src)

def _raise(err):
    raise err

def list_entries(root):
    """Relative paths of the files under root. A symlink counts as a file, even
    one that points at a folder, and is not followed. An unreadable folder
    raises OSError."""
    out = []
    for r, dirs, files in os.walk(root, onerror=_raise):
        out += [os.path.relpath(os.path.join(r, d), root) for d in dirs if os.path.islink(os.path.join(r, d))]
        out += [os.path.relpath(os.path.join(r, f), root) for f in files]
    return sorted(out)

def remove_empty_dirs(root):
    """Remove root and the folders under it, which should all be empty by now.
    Return the files that are still there, if any."""
    for r, _, _ in os.walk(root, topdown=False):
        try:
            os.rmdir(r)
        except OSError:
            pass
    return list_entries(root) if os.path.exists(root) else []

def blocked_parent(root, rel):
    """True if a folder that rel needs under root exists there as a file or a
    symlink."""
    parent = os.path.dirname(rel)
    while parent:
        p = os.path.join(root, parent)
        if os.path.lexists(p) and (os.path.islink(p) or not os.path.isdir(p)):
            return True
        parent = os.path.dirname(parent)
    return False

# chflags flags that stop a file or folder from being replaced or removed
_LOCK_FLAGS = (getattr(stat, "UF_IMMUTABLE", 0) | getattr(stat, "SF_IMMUTABLE", 0)
               | getattr(stat, "UF_APPEND", 0) | getattr(stat, "SF_APPEND", 0))

_IMMUTABLE_FLAGS = getattr(stat, "UF_IMMUTABLE", 0) | getattr(stat, "SF_IMMUTABLE", 0)

def is_locked(path, flags=_LOCK_FLAGS):
    """True if a file flag (immutable or append-only, set with chflags) on
    path, or on what a symlink at path leads to, stops the apply run from
    replacing or removing path or entries in it."""
    for get in (os.lstat, os.stat):
        try:
            if getattr(get(path), "st_flags", 0) & flags:
                return True
        except OSError:
            pass
    return False

def load_json(path):
    """Return (object, error) for the JSON file at path, or (None, None) when
    there is no such file."""
    if not os.path.isfile(path):
        return None, None
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh), None
    except Exception as e:
        return None, e


# Auto memory keeps one index file per project, with one line per memory. If
# both transcript folders have one, the old index's lines are added to the new.
MEMORY_INDEX = os.path.join("memory", "MEMORY.md")

def memory_index_extra(new_text, old_text):
    """Lines of the old index that the new index lacks, in order, without blank
    lines or repeats."""
    have = {line.rstrip() for line in new_text.split("\n")}
    extra = []
    for line in old_text.split("\n"):
        line = line.rstrip()
        if line.strip() and line not in have:
            have.add(line)
            extra.append(line)
    return extra

def append_lines(text, lines):
    sep = "" if not text or text.endswith("\n") else "\n"
    return text + sep + "\n".join(lines) + "\n"


def merge_kind(rel, src, dst, new_dir, rewrite=None):
    """Decide how one file of the old dir goes into the new dir:
      "move"      the new dir lacks it
      "drop"      the new dir holds it already, or a longer copy of the same transcript
      "replace"   the new dir holds a raw copy, or a shorter copy of the same transcript
      "join"      memory/MEMORY.md: the lines the new copy lacks go to its end
      "conflict"  anything else
    `rewrite` maps a transcript's text to its text after the path rewrite; it
    is None for a file that is not a transcript. A symlinked folder on the way
    to dst, or a dst that is the same file as src, is a conflict: it can lead
    back into the old dir, where a "drop" would delete the only copy."""
    if blocked_parent(new_dir, rel):
        return "conflict"
    if not os.path.lexists(dst):
        return "move"
    if os.path.islink(src) or os.path.islink(dst):
        same = os.path.islink(src) and os.path.islink(dst) and os.readlink(src) == os.readlink(dst)
        return "drop" if same else "conflict"
    if not (os.path.isfile(src) and os.path.isfile(dst)) or os.path.samefile(src, dst):
        return "conflict"
    if os.path.basename(rel) == ".DS_Store":
        return "drop"
    if rewrite:
        raw, dst_text = read_text(src), read_text(dst)
        src_new = rewrite(raw)
        if is_line_prefix(src_new, dst_text):
            return "drop"
        if dst_text == raw or is_line_prefix(dst_text, src_new):
            return "replace"
        return "conflict"
    if filecmp.cmp(src, dst, shallow=False):
        return "drop"
    if rel == MEMORY_INDEX:
        return "join" if memory_index_extra(read_text(dst), read_text(src)) else "drop"
    return "conflict"


# ---------------------------------------------------------------------------
# Backups
# ---------------------------------------------------------------------------

def _short(name, limit=60):
    """name cut to at most limit bytes of UTF-8, so that a backup folder name
    stays within the 255 that a disk allows"""
    return name.encode("utf-8", "surrogateescape")[:limit].decode("utf-8", "ignore")

# In ~/.claude/projects, the records of the finished moves whose old and new
# paths overlap (one is a folder above the other). Such a move must not run
# twice, and the records stay when the user clears the backups.
RECORDS_DIR = "_move-records"

def read_move_records(records_dir):
    """Return (records, problem): records lists (file, object) for each record
    in records_dir; problem names what cannot be read, else None."""
    if not os.path.lexists(records_dir):
        return [], None
    try:
        names = sorted(os.listdir(records_dir))
    except OSError as e:
        return [], f"{records_dir} ({e.strerror})"
    out = []
    for n in names:
        if n.endswith(".json") and not n.startswith("."):
            p = os.path.join(records_dir, n)
            o, err = load_json(p)
            if not isinstance(o, dict):
                return [], f"{p} ({err or 'not a record'})"
            out.append((p, o))
    return out, None

def make_backup_root(projects_dir, old, new):
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    tag = f"{_short(os.path.basename(old)) or 'root'}-to-{_short(os.path.basename(new)) or 'root'}-{stamp}"
    base = os.path.join(projects_dir, "_move-backups", tag)
    root, n = base, 1
    while True:  # a fresh folder even for two runs in the same second
        try:
            os.makedirs(root)
            return root
        except FileExistsError:
            n += 1
            root = f"{base}-{n}"


# ---------------------------------------------------------------------------
# Path fields of the JSON stores
# ---------------------------------------------------------------------------
# Each migrate_* function below changes its object in place and reports what
# changed. The plan runs it on a copy, and the apply run on the file as it is
# then, so the two take the same decisions.

# desktop-app session file (local_*.json): fields that hold one path
SESSION_FIELDS = ("cwd", "originCwd", "worktreePath", "gitAnchorsFolderRealpath", "planPath")
# a git anchor, in a session file or in git-worktrees.json
ANCHOR_FIELDS = ("gitRoot", "commonDir", "gitDir")
# an entry of git-worktrees.json
REGISTRY_FIELDS = ("path", "baseRepo", "originTopLevel", "placementRoot")
# "activeWorktreeSession" of a ~/.claude.json projects entry
WORKTREE_SESSION_FIELDS = ("originalCwd", "preEnterOriginalCwd", "worktreePath")

def _as_list(v):
    return v if isinstance(v, list) else []

def _slot(container, key, move, changed, field, nul=False):
    """Replace the path at container[key] by move(path), unless that is None.
    Add field to the list changed when it changes. With nul, the path ends at
    the first NUL character, as in a "writtenBranches" entry, which holds
    "<repository path>\\0<branch>"."""
    try:
        v = container[key]
    except (KeyError, IndexError, TypeError):
        return
    if not isinstance(v, str):
        return
    path, sep, rest = v.partition("\0") if nul else (v, "", "")
    np = move(path)
    if np is not None:
        container[key] = np + sep + rest
        if field not in changed:
            changed.append(field)

def is_remote(o):
    """True for a session that runs on an SSH host or in WSL: its paths are
    not paths on this machine."""
    return bool(o.get("sshConfig") or o.get("wslConfig"))

def migrate_session_file(o, move):
    """Move the path fields of a desktop-app session file. Return the names
    of the fields that changed."""
    changed = []
    if not isinstance(o, dict) or is_remote(o):
        return changed
    for k in SESSION_FIELDS:
        _slot(o, k, move, changed, k)
    for a in _as_list(o.get("gitAnchors")):
        for k in ANCHOR_FIELDS:
            _slot(a, k, move, changed, "gitAnchors")
    for u in _as_list(o.get("sessionPermissionUpdates")):
        dirs = _as_list(u.get("directories")) if isinstance(u, dict) else []
        for i in range(len(dirs)):
            _slot(dirs, i, move, changed, "sessionPermissionUpdates")
    branches = _as_list(o.get("writtenBranches"))
    for i in range(len(branches)):
        _slot(branches, i, move, changed, "writtenBranches", nul=True)
    _slot(o.get("worktreeLazy"), "path", move, changed, "worktreeLazy")
    for k in ("path", "baseRepo"):
        _slot(o.get("keptWorktreeLeftover"), k, move, changed, "keptWorktreeLeftover")
    return changed

def migrate_registry(r, move):
    """Move the paths of the entries in the desktop app's git-worktrees.json.
    Return (worktree name, changed fields) for each entry that changed. A
    worktree on an SSH host keeps its paths."""
    out = []
    worktrees = r.get("worktrees") if isinstance(r, dict) else None
    if isinstance(worktrees, dict):
        for name, w in worktrees.items():
            if not isinstance(w, dict) or w.get("remote"):
                continue
            changed = []
            for k in REGISTRY_FIELDS:
                _slot(w, k, move, changed, k)
            for a in _as_list(w.get("anchors")):
                for k in ANCHOR_FIELDS:
                    _slot(a, k, move, changed, "anchors")
            if changed:
                out.append((name, changed))
    return out


def _is_empty(v):
    return v is None or v is False or v == "" or v == [] or v == {} or (type(v) in (int, float) and v == 0)

def merge_project_entries(old_val, new_val):
    """Merge the old ~/.claude.json projects entry into the new one. A setting
    only the old entry has is added, an empty new value takes the old value,
    and two lists are joined. Where both hold other values that differ, the new
    value stays. Return the merged entry and the keys whose old value is lost."""
    if not (isinstance(old_val, dict) and isinstance(new_val, dict)):
        return new_val, ([] if old_val == new_val else ["(the whole entry)"])
    merged = dict(new_val)
    kept_new = []
    for k, ov in old_val.items():
        nv = merged.get(k)
        if k not in merged or (_is_empty(nv) and not _is_empty(ov)):
            merged[k] = ov
        elif nv == ov or _is_empty(ov):
            continue
        elif isinstance(nv, list) and isinstance(ov, list):
            merged[k] = nv + [x for x in ov if x not in nv]
        else:
            kept_new.append(k)
    return merged, kept_new

def migrate_config(c, move):
    """Move the paths in the ~/.claude.json object c: the paths in each
    projects entry's activeWorktreeSession, then each projects key at or under
    the old path (an entry merges into a key that exists already), then the
    githubRepoPaths lists. Return (keys, entries, repo_paths): keys lists
    (old key, new key, settings kept from the new entry, or None when there
    was no new entry), entries counts the entries whose worktree-session paths
    changed, and repo_paths counts the githubRepoPaths paths that changed."""
    keys, entries, repo_paths = [], 0, 0
    projs = c.get("projects")
    if isinstance(projs, dict):
        for v in projs.values():
            changed = []
            aws = v.get("activeWorktreeSession") if isinstance(v, dict) else None
            if isinstance(aws, dict):
                for k in WORKTREE_SESSION_FIELDS:
                    _slot(aws, k, move, changed, k)
            entries += bool(changed)
        # each key keeps its place; an entry that merges into a key that
        # stays goes to the place of that key
        new_keys = {k: move(k) for k in projs}
        staying = {k for k, nk in new_keys.items() if nk is None}
        incoming = {}  # key that stays -> ([old keys], their joined entry)
        for k, nk in new_keys.items():
            if nk is not None and nk in staying:
                if nk in incoming:  # two spellings of one path: join them first
                    oks, ov = incoming[nk]
                    incoming[nk] = (oks + [k], merge_project_entries(projs[k], ov)[0])
                else:
                    incoming[nk] = ([k], projs[k])
        result = {}
        for k, v in projs.items():
            nk = new_keys[k]
            if nk is None:
                if k in incoming:
                    oks, ov = incoming[k]
                    v, kept_new = merge_project_entries(ov, v)
                    keys += [(ok, k, kept_new) for ok in oks]
                result[k] = v
            elif nk not in staying:
                if nk in result:
                    # two spellings of one path, such as "/a/./b" and "/a/b"
                    result[nk], kept_new = merge_project_entries(v, result[nk])
                    keys.append((k, nk, kept_new))
                else:
                    result[nk] = v
                    keys.append((k, nk, None))
        c["projects"] = result
    repos = c.get("githubRepoPaths")
    if isinstance(repos, dict):
        for repo, paths in repos.items():
            moved = [move(p) for p in paths] if isinstance(paths, list) else []
            if not any(m is not None for m in moved):
                continue
            out = []
            for p, m in zip(paths, moved):
                if m is not None:
                    repo_paths += 1
                    p = m
                if p not in out:
                    out.append(p)
            repos[repo] = out
    return keys, entries, repo_paths


# ---------------------------------------------------------------------------
# Main migration
# ---------------------------------------------------------------------------

def claude_desktop_running():
    try:
        out = subprocess.run(["ps", "-axo", "command"], capture_output=True, text=True, timeout=10).stdout
    except Exception:
        return False
    for line in out.splitlines():
        if "/Claude.app/" in line and "Electron Framework" in line:
            return True
    return False


TAIL_BYTES = 64 * 1024

def _json_dict(line):
    try:
        rec = json.loads(line)
    except (ValueError, RecursionError):
        return None
    return rec if isinstance(rec, dict) else None

def transcript_project(path):
    """Return the project path a transcript belongs to, read the way Claude
    Code reads it: the relocatedCwd of the last "relocated" record in the
    file's last 64 KiB, which Claude Code keeps stamping at the end, else the
    first cwd in the file. Most transcripts start with a queue-operation record
    that has no cwd, so the first record is not enough."""
    with open(path, "rb") as fh:
        fh.seek(0, os.SEEK_END)
        fh.seek(max(0, fh.tell() - TAIL_BYTES))
        tail = fh.read().decode("utf-8", "replace")
    for line in reversed(tail.split("\n")):
        if '"relocatedCwd"' in line:
            rec = _json_dict(line)
            if rec and rec.get("type") == "relocated" and isinstance(rec.get("relocatedCwd"), str):
                return rec["relocatedCwd"]
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if '"cwd"' in line:
                rec = _json_dict(line)
                if rec and isinstance(rec.get("cwd"), str):
                    return rec["cwd"]
    return None


def read_session_files(sessions_dir, old):
    """The desktop-app session files (local_*.json) under sessions_dir.
    Return (files, skipped): files lists (path, object) pairs in a fixed
    order; skipped lists (path, reason) for each file that cannot be read,
    or that does not parse and mentions the old path. A file that holds
    other JSON than an object is not a session file."""
    files, skipped = [], []
    if os.path.isdir(sessions_dir):
        for r, dirs, names in os.walk(sessions_dir):
            dirs.sort()
            for f in sorted(names):
                if f.startswith("local_") and f.endswith(".json"):
                    p = os.path.join(r, f)
                    try:
                        with open(p, "rb") as fh:
                            raw = fh.read()
                    except OSError as e:
                        skipped.append((p, e.strerror or "cannot read"))
                        continue
                    try:
                        o = json.loads(raw.decode("utf-8"))
                    except (ValueError, RecursionError):
                        if old.encode("utf-8", "surrogateescape") in raw:
                            skipped.append((p, "not valid JSON"))
                        continue
                    if isinstance(o, dict):
                        files.append((p, o))
    return files, skipped

def project_paths(cfg, sessions, registry):
    """The project paths that the JSON stores name: the projects keys, the
    session folders of desktop-app sessions and the desktop app's worktrees."""
    found = set()
    projs = cfg.get("projects") if isinstance(cfg, dict) else None
    if isinstance(projs, dict):
        found.update(projs)
    for _, o in sessions:
        if not is_remote(o):
            found.update(v for v in (o.get(k) for k in ("cwd", "originCwd", "worktreePath")) if isinstance(v, str))
    worktrees = registry.get("worktrees") if isinstance(registry, dict) else None
    if isinstance(worktrees, dict):
        found.update(w.get("path") for w in worktrees.values()
                     if isinstance(w, dict) and not w.get("remote") and isinstance(w.get("path"), str))
    return {p for p in found if isinstance(p, str)}

def scan_transcript_dirs(projects_dir):
    """Read every folder in projects_dir except the backups. Map each folder
    name to {"projects": {transcript: project path or None}, "unreadable":
    number of transcripts that could not be read}, for the transcripts at the
    top of the folder (see transcript_project)."""
    out = {}
    try:
        names = sorted(os.listdir(projects_dir))
    except OSError:
        return out
    for name in names:
        d = os.path.join(projects_dir, name)
        if name.startswith("_move-") or not os.path.isdir(d):
            continue
        info = {"projects": {}, "unreadable": 0}
        try:
            files = sorted(os.listdir(d))
        except OSError:
            files = []
            info["unreadable"] += 1
        for fn in files:
            p = os.path.join(d, fn)
            if fn.endswith(".jsonl") and os.path.isfile(p):
                try:
                    info["projects"][fn] = transcript_project(p)
                except OSError:
                    info["unreadable"] += 1
        out[name] = info
    return out


def find_transcript_folders(projects_dir, old, new, move, known, encoders, scan):
    """Decide which transcript folders move, and where to.

    A folder moves when a transcript in it belongs to a path at or under the
    old path, or when its name is the encoded name of such a path and no
    transcript in it belongs to a path elsewhere. The paths are the old path,
    the paths at or under it that the JSON stores name (from `known`, all the
    project paths that the stores name) and those of the transcripts. A
    folder's new name comes from the path that it is named for, or else from
    the paths of its transcripts. A folder that also holds transcripts of a
    project outside the old path that is still in use does not move: that is
    a problem for a person. A project is in use if its folder exists or the
    JSON stores name it.

    Two folders can need the same new name, such as an old folder under an
    older name rule and a newer one. Only one of them moves in this run, and
    the plan tells the user to run the script again for the other. If one of
    them is at the new name already, the other merges into it. A folder whose
    new name is the current name of another folder that moves runs after that
    folder.

    Return a dict: "moves" lists (name, new name, info, freed) in the order
    they must run, where info is the folder's entry in `sources` and freed is
    True when the new name is free only once an earlier move has run;
    "deferred" maps each folder that waits for another run to ("same", the
    folder that takes its new name) or ("held", the folder that holds its new
    name and does not move in this run); "merge_into" maps a folder that
    merges into another folder of the move to that folder; "problems" lists
    (name or None, lines); "notes" lists lines; "paths" is the set of project
    paths at or under the old path that the transcripts name."""
    # When the new path is a folder above the old one, the paths under it are
    # other paths, such as siblings of the old path.
    up = old.startswith(new + "/")
    down = new.startswith(old + "/")

    def new_side(q):
        # a session at the new path or under it, which is not part of the move
        if move(q) is not None:
            return False
        if up:
            return q == new or case_variant(q, new) == q
        return q == new or q.startswith(new + "/") or case_variant(q, new) is not None

    def belongs(q):
        # part of the move, at the new path, or a path of the move spelled in
        # another letter case or Unicode form, which a disk that ignores
        # those stores in the same folder
        return move(q) is not None or case_variant(q, old) is not None or new_side(q)

    def join(name):
        return os.path.join(projects_dir, name)

    projects = {name: {q for q in info["projects"].values() if q is not None} for name, info in scan.items()}
    inside = {name: {q for q in qs if move(q) is not None} for name, qs in projects.items()}
    paths = set().union(*inside.values()) if inside else set()
    found = {old} | {p for p in known if move(p) is not None}
    if not (up or down):
        # A store path that moved in an earlier run still names its old
        # folder, which can wait for its own move, such as a memory-only
        # folder that the plan left for a second run.
        origins = {old + p[len(new):] for p in known if p == new or p.startswith(new + "/")}
        found |= {o for o in origins if move(o) is not None}
    # the projects in use outside the move, whose folders must not move
    others = {p for p in known if not belongs(p)}

    # A folder is found by name through its file identity, so that on a disk
    # that ignores case a name that differs in case finds the same folder.
    ids = {}
    for name in scan:
        try:
            st = os.lstat(join(name))
        except OSError:
            continue
        ids[(st.st_dev, st.st_ino)] = name

    def folders_named(names_of):
        """Map each folder to [best encoder rank, the paths it is named for]."""
        out = {}
        for p in sorted(names_of):
            for rank, encode in enumerate(encoders):
                try:
                    st = os.lstat(join(encode(p)))
                except (OSError, ValueError):
                    continue
                name = ids.get((st.st_dev, st.st_ino))
                if name is not None:
                    entry = out.setdefault(name, [rank, set()])
                    entry[0] = min(entry[0], rank)
                    entry[1].add(p)
        return out

    named = folders_named(found | paths)
    named_others = folders_named(others)

    # the start of the name of a folder for a path under the old path, by
    # each rule, before a long name is cut
    prefixes = {re.sub(r"[^A-Za-z0-9]", "-", old)[:MAX_NAME_LEN].lower()}
    prefixes |= {encode(old)[:MAX_NAME_LEN].lower() for encode in encoders if encode is not enc_nonalnum}

    problems, notes = [], []
    sources = {}  # folder name -> facts about the folder, for the checks below
    for name, info in scan.items():
        outside = sorted(q for q in projects[name] if not belongs(q))
        # the projects in use outside the move whose history this folder holds
        live = [q for q in outside if q in known or os.path.isdir(q)]
        # the projects in use outside the move whose folder name this folder has
        also = sorted(named_others.get(name, [0, set()])[1])
        rank, by_name = named.get(name, [len(encoders), set()])
        # sessions at the new path whose own folder this is
        homed = sorted(q for q in projects[name] if new_side(q) and enc_nonalnum(q).lower() == name.lower())
        if inside[name] or (by_name and not outside and not also and not homed):
            sources[name] = {"paths": by_name or inside[name], "rank": rank,
                             "how": "name" if by_name else "transcripts",
                             "stale": [q for q in outside if q not in live], "live": live,
                             "also": also, "homed": homed,
                             # the transcripts of other paths, which a folder that keeps
                             # its name keeps as they are
                             "keep": {fn for fn, q in info["projects"].items()
                                      if q is not None and move(q) is None
                                      and (new_side(q) or case_variant(q, old) is None)}}
        elif info["unreadable"] and any(name.lower().startswith(p) for p in prefixes):
            notes += [f"NOTE: {info['unreadable']} transcript(s) in {name} cannot be read, so the script",
                      "      cannot tell if that dir belongs to a path under the old path. It",
                      "      stays as it is. Check its read permissions, then run again."]

    targets, bad = {}, set()
    for name, s in sources.items():
        if os.path.islink(join(name)):
            problems.append((name, ["ABORT: this dir is a symlink. Inspect it manually."]))
            bad.add(name)
            continue
        names = sorted({enc_nonalnum(m) for m in map(move, s["paths"]) if m is not None})
        if not names:
            bad.add(name)
            continue
        if len({t.lower() for t in names}) > 1:
            problems.append((name, ["ABORT: this dir holds transcripts of paths that need different folder",
                                    "       names after the move:"]
                             + [f"         {p}" for p in sorted(s["paths"])]
                             + ["       Inspect it manually."]))
            bad.add(name)
            continue
        targets[name] = names[0]
        if same_dir(join(name), join(names[0])):
            continue  # it keeps its name, so the history of other paths in it stays
        # A folder that moves takes everything in it along. That must not
        # be the history of a project in use outside the move, files of such
        # a project whose folder name it also has (memory/, say), or the
        # sessions at the new path whose own folder it is.
        unowned = unowned_entries(join(name), scan[name]["projects"], belongs) if s["also"] else []
        if s["live"]:
            lines = ["ABORT: this dir also holds the history of a project outside the old path",
                     "       that is still in use (its folder exists, or Claude Code lists it):"]
            lines += [f"         {q}" for q in s["live"]]
            lines += ["       Both paths give the same folder name, so moving the dir would",
                      "       move that project's history as well. Inspect it manually."]
        elif unowned:
            lines = ["ABORT: this dir has the folder name of a project outside the old path that",
                     "       is still in use (its folder exists, or Claude Code lists it):"]
            lines += [f"         {q}" for q in s["also"]]
            lines += [f"       It holds files that belong to no session in it ({', '.join(unowned)}),",
                      "       which can belong to that project. Inspect it manually."]
        elif s["homed"]:
            lines = ["ABORT: this dir is also the dir of sessions at the new path:"]
            lines += [f"         {q}" for q in s["homed"]]
            lines += [f"       Moving it to {names[0]} would take those sessions from",
                      "       where Claude Code looks for them. Inspect it manually."]
        else:
            continue
        problems.append((name, lines))
        bad.add(name)
        del targets[name]

    # One folder goes to each new name in this run. A name that differs only
    # in case counts as the same, as it is on a disk that ignores case. If a
    # folder of the group is at the new name already, another one merges into
    # it, and it is not rewritten in this run, as for any folder at the new name.
    groups = {}
    for name in sorted(targets, key=lambda n: (sources[n]["rank"], n)):
        groups.setdefault(targets[name].lower(), []).append(name)
    run, deferred, merge_into = [], {}, {}
    for members in groups.values():
        stay = [n for n in members if same_dir(join(n), join(targets[n]))]
        movers = [n for n in members if n not in stay]
        if movers:
            run.append(movers[0])
            deferred.update((n, ("same", movers[0])) for n in movers[1:])
            if stay:
                merge_into[movers[0]] = stay[0]
        else:
            run.append(stay[0])

    # a new name that is the current name of another folder that moves
    holder = {}
    for n in run:
        t = join(targets[n])
        if n not in merge_into and os.path.lexists(t) and not same_dir(join(n), t):
            for m in sources:
                if m != n and same_dir(join(m), t):
                    holder[n] = m
                    break
    waiting = True
    while waiting:
        waiting = False
        for n in list(run):
            if n in holder and holder[n] not in run:
                run.remove(n)
                deferred[n] = ("held", holder[n])
                waiting = True

    # the folder that frees a name moves before the folder that takes it
    order, done = [], set()
    for n in run:
        chain, cur = [], n
        while cur is not None and cur not in done and cur not in chain:
            chain.append(cur)
            cur = holder.get(cur)
        if cur is not None and cur in chain:
            cycle = chain[chain.index(cur):]
            problems.append((None, ["ABORT: the new names of these dirs are each other's current names:",
                                    f"         {', '.join(cycle)}",
                                    "       Rename one of them by hand first."]))
            done.update(chain)
            continue
        for x in reversed(chain):
            order.append(x)
            done.add(x)

    return {"moves": [(n, targets[n], sources[n], n in holder) for n in order], "deferred": deferred,
            "merge_into": merge_into, "problems": problems, "notes": notes, "paths": paths,
            "inside": {n: {fn for fn, q in scan[n]["projects"].items() if q is not None and move(q) is not None}
                       for n in sources}, "found": found}


_SESSION_ID = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}(\.|$)")

def unowned_entries(d, transcripts, belongs):
    """The entries at the top of transcript folder d that belong to no
    session, such as memory/. A transcript belongs to its session, and so does
    a file or folder named after a session ID, such as <id>.desktop-released.json
    or a <id>/ folder whose transcript is gone; such a folder belongs elsewhere
    only if its subagent transcripts say so (`belongs` tells). The Finder's
    .DS_Store, an old sessions-index.json and a temporary file of this script
    belong to no project."""
    try:
        names = os.listdir(d)
    except OSError:
        return ["(cannot list it)"]
    ids = {fn[:-len(".jsonl")] for fn in transcripts}
    out = []
    for n in names:
        if (n.endswith(".jsonl") or n in (".DS_Store", "sessions-index.json")
                or n.startswith(".migrate-tmp-")):
            continue
        if n in ids or _SESSION_ID.match(n):
            sub = os.path.join(d, n, "subagents")
            try:
                agents = [f for f in os.listdir(sub) if f.endswith(".jsonl")] if n not in ids else []
            except OSError:
                agents = []
            if any(q is not None and not belongs(q)
                   for q in (_project_or_none(os.path.join(sub, f)) for f in agents)):
                out.append(n)
            continue
        out.append(n)
    return sorted(out)

def _project_or_none(path):
    try:
        return transcript_project(path)
    except OSError:
        return None


def plan_folder(src, dst, freed, old_j, new_j, keep=()):
    """Plan how transcript folder src goes to dst: a rename, a rewrite in
    place, or a merge into the folder that is at dst already. freed is True
    when dst is the current place of a folder that moves away earlier in this
    run. A rewrite in place skips the transcripts named in keep, which belong
    to other paths, such as sessions at the new path, and their subfolders.
    Every check runs here,
    before any change. Return a dict with the plan lines, the problem lines
    (empty when the folder may go ahead), and what the apply run needs."""
    plan = {"src": src, "dst": dst, "lines": [], "problems": [], "rename": False,
            "merge": False, "kinds": {}, "jsonl": [], "rewrite": set(), "write_dirs": set(),
            "change_files": set()}
    lines, problems = plan["lines"], plan["problems"]

    def rewrite(text):
        return rewrite_lines(text, old_j, new_j)[0]

    # one pass over the transcripts: the boundary guard, and a trial rewrite
    # that must leave every valid JSON line valid. The backup copies every
    # file, so each one must be readable.
    total_risky = 0
    broken = []
    unreadable = []

    def readable_entries(d):
        try:
            found = list_entries(d)
        except OSError as e:
            unreadable.append(f"{e.filename} ({e.strerror})")
            return [], set()
        locked = {rel for rel in found if not os.path.islink(os.path.join(d, rel))
                  and not os.access(os.path.join(d, rel), os.R_OK)}
        unreadable.extend(f"{os.path.join(os.path.basename(d), rel)} (no read permission)"
                          for rel in sorted(locked))
        return found, locked

    entries, locked = readable_entries(src)
    jsonl = [rel for rel in entries if rel.endswith(".jsonl") and not os.path.islink(os.path.join(src, rel))]
    stays = os.path.abspath(src) == os.path.abspath(dst) or (not freed and same_dir(src, dst))
    if stays and keep:
        kept_ids = {fn[:-len(".jsonl")] for fn in keep}
        skipped = [rel for rel in jsonl if rel in keep or rel.split(os.sep)[0] in kept_ids]
        jsonl = [rel for rel in jsonl if rel not in skipped]
    else:
        skipped = []
    protect = new_j if old_j in new_j else None
    for rel in jsonl:
        if rel in locked:
            continue
        try:
            text = read_text(os.path.join(src, rel))
        except OSError as e:
            unreadable.append(f"{os.path.join(os.path.basename(src), rel)} ({e.strerror})")
            continue
        total_risky += risky_occurrences(text, old_j, protect)
        new_text, n_broken = rewrite_lines(text, old_j, new_j)
        if new_text != text:
            plan["rewrite"].add(rel)
        if n_broken:
            broken.append(rel)
    if total_risky:
        problems += [f"ABORT: {total_risky} occurrence(s) of the old path are a prefix of a",
                     "       longer name (e.g. a sibling dir). Refusing to string-replace.",
                     "       Inspect manually; this guard prevents corrupting a different path."]
        return plan

    rename = os.path.abspath(src) != os.path.abspath(dst)
    # on a case-insensitive disk, a new name that differs only in case is
    # the same folder: rename it, and never merge it into itself
    exists = os.path.lexists(dst) and not freed
    same_folder = rename and exists and same_dir(src, dst)
    merge = rename and exists and not same_folder
    if merge and (os.path.islink(dst) or not os.path.isdir(dst)):
        problems += [f"ABORT: {dst} exists but is not a folder.",
                     "       Inspect it manually."]
        return plan

    kinds = {}  # rel -> merge_kind(), for a merge
    if merge:
        readable_entries(dst)
        jsonl_set = set(jsonl)
        for rel in entries:
            if rel in locked:
                continue
            try:
                kinds[rel] = merge_kind(rel, os.path.join(src, rel), os.path.join(dst, rel),
                                        dst, rewrite if rel in jsonl_set else None)
            except OSError as e:
                unreadable.append(f"{os.path.join(os.path.basename(dst), rel)} ({e.strerror})")
    if broken or unreadable:
        if broken:
            problems.append("ABORT: replacing the old path would break JSON lines in:")
            problems += [f"         {rel}" for rel in broken]
        if unreadable:
            problems.append("ABORT: cannot read:")
            problems += [f"         {item}" for item in unreadable]
        problems.append("       Inspect these files manually.")
        return plan

    new_name = os.path.basename(dst)
    if merge:
        conflicts = [rel for rel, k in kinds.items() if k == "conflict"]
        if conflicts:
            problems += [f"ABORT: the new dir {new_name} already exists, and {len(conflicts)} file(s)",
                         "       cannot merge: they differ between the two dirs, or the new dir",
                         "       reaches them through a symlink:"]
            problems += [f"         {rel}" for rel in conflicts]
            problems += ["       Merge each pair by hand into the new dir's copy, or keep the better",
                         "       copy there. Then move the old dir's copy out of ~/.claude/projects.",
                         "       Do not rename a transcript (*.jsonl): its name is its session ID.",
                         "       Replace a symlinked folder in the new dir with a real folder.",
                         "       Then run the script again."]
            return plan
        count = {k: sum(1 for v in kinds.values() if v == k) for k in ("move", "replace", "drop")}
        lines.append(f"new dir {new_name} already exists: merge the old dir into it")
        lines.append(f"move {count['move']} file(s) into the new dir")
        if count["replace"]:
            lines.append(f"replace {count['replace']} file(s) in the new dir that hold a raw or shorter copy")
        if count["drop"]:
            lines.append(f"drop {count['drop']} file(s) of the old dir that the new dir already holds")
        for rel in (r for r, k in kinds.items() if k == "join"):
            n = len(memory_index_extra(read_text(os.path.join(dst, rel)), read_text(os.path.join(src, rel))))
            lines.append(f"join {rel}: add {n} line(s) from the old copy to the end of the new copy")
        lines.append("then remove the old dir")
        n_rewrite = sum(1 for rel in plan["rewrite"] if kinds[rel] in ("move", "replace"))
    else:
        lines.append(f"rename dir -> {new_name}" if rename else "dir name already correct")
        n_rewrite = len(plan["rewrite"])
    lines.append(f"rewrite internal 'cwd'/file refs in {n_rewrite} of {len(jsonl)} transcript file(s)")
    if skipped:
        lines.append(f"leave {len(skipped)} transcript file(s) of other paths as they are")
    plan.update(rename=rename, merge=merge, kinds=kinds, jsonl=jsonl)

    # the folders that the apply run writes in, and the files and folders
    # that it replaces or removes, which the plan checks
    dirs, files = plan["write_dirs"], plan["change_files"]
    if merge:
        files.add(src)
        files.update(os.path.join(src, rel) for rel in entries)
        for r, ds, _ in os.walk(src):
            files.update(os.path.join(r, x) for x in ds)
            dirs.add(r)
        files.update(os.path.join(dst, rel) for rel, kind in kinds.items() if kind in ("replace", "join"))
    else:
        if rename:
            files.add(src)
        files.update(os.path.join(src, rel) for rel in plan["rewrite"])
    if merge:
        dirs.update((os.path.dirname(src), src))
        for rel in entries:
            d = os.path.dirname(os.path.join(src, rel))
            while len(d) > len(src):
                dirs.add(d)
                d = os.path.dirname(d)
        for rel, kind in kinds.items():
            if kind in ("move", "replace", "join"):
                d = os.path.dirname(os.path.join(dst, rel))
                while not os.path.lexists(d):
                    d = os.path.dirname(d)
                dirs.add(d)
    else:
        if rename:
            dirs.add(os.path.dirname(src))
        dirs.update(os.path.dirname(os.path.join(src, rel)) for rel in plan["rewrite"])
    return plan

def backup_folder(plan, root):
    shutil.copytree(plan["src"], os.path.join(root, os.path.basename(plan["src"])), symlinks=True)
    if plan["merge"]:
        shutil.copytree(plan["dst"], os.path.join(root, os.path.basename(plan["dst"])), symlinks=True)

def apply_folder(plan, old_j, new_j):
    src, dst = plan["src"], plan["dst"]
    if not plan["merge"]:
        if plan["rename"]:
            os.rename(src, dst)
        target = dst if plan["rename"] else src
        for rel in sorted(plan["rewrite"]):
            p = os.path.join(target, rel)
            rewrite_file(p, p, old_j, new_j)
        return
    for rel, kind in plan["kinds"].items():
        s, d = os.path.join(src, rel), os.path.join(dst, rel)
        if kind in ("move", "replace"):
            os.makedirs(os.path.dirname(d), exist_ok=True)
            if rel in plan["rewrite"]:
                rewrite_file(s, d, old_j, new_j)
                os.remove(s)
            else:
                os.replace(s, d)
        elif kind == "join":
            d_text = read_text(d)
            write_atomic(d, append_lines(d_text, memory_index_extra(d_text, read_text(s))))
            os.remove(s)
        else:  # drop
            os.remove(s)
    left = remove_empty_dirs(src)
    if left:
        print(f"  WARNING: {len(left)} file(s) appeared in the old dir during the run and stay there:")
        for rel in left:
            print(f"      {os.path.join(src, rel)}")
    elif os.path.lexists(src):
        print(f"  WARNING: the old dir stays, with empty folders that could not be removed: {src}")

def verify_folder(plan, backup_root, old_j, new_j):
    """Count the transcripts of a moved folder that do not hold their planned
    text, or (after a merge) a longer copy of it, checked against the backup."""
    bdir = os.path.join(backup_root, os.path.basename(plan["src"]))
    target = plan["dst"] if plan["rename"] else plan["src"]
    bad = 0
    for rel in plan["jsonl"]:
        try:
            planned = rewrite_lines(read_text(os.path.join(bdir, rel)), old_j, new_j)[0]
            if not is_line_prefix(planned, read_text(os.path.join(target, rel))):
                bad += 1
        except OSError:
            bad += 1
    return bad


def plan_and_apply(old, new, apply, force):
    home = os.path.expanduser("~")
    projects_dir = os.path.join(home, ".claude", "projects")
    config_path = os.path.join(home, ".claude.json")
    appdir = app_support_dir()
    registry_path = os.path.join(appdir, REGISTRY_FILE)

    enc_name, encode, scores = detect_encoder(projects_dir, config_path)
    fits = ", ".join(f"{name} {n}" for name, n in scores.items())
    print(f"Detected projects/ encoder: {enc_name} (folder names reproduced: {fits})")
    if enc_name != ENCODERS[0][0]:
        print(f"NOTE: the folders on this machine fit the older {enc_name} rule best, so the old")
        print("      dirs are looked up by that rule too. The new dirs still get the names that")
        print(f"      Claude Code 2.1 reads ({ENCODERS[0][0]} rule).")
    print(f"Old path: {old}")
    print(f"New path: {new}")
    print()

    if not os.path.isdir(new):
        print(f"WARNING: new path does not exist on disk yet: {new}")
        print("         Move the project directory first, then run this.\n")
    if os.path.isdir(old) and not new.startswith(old + "/"):
        print(f"WARNING: old path still exists on disk: {old}")
        print("         This script only edits Claude metadata; it does not move files.\n")

    if apply and not force and claude_desktop_running():
        print("REFUSING: the Claude desktop app appears to be running.")
        print("Quit it completely (Cmd-Q), then re-run with --apply.")
        print("Editing its session store while it runs gets clobbered and won't show until restart.")
        print("Use --force to override (not recommended).")
        return EXIT_APP_RUNNING

    def move(p):
        return moved_path(p, old, new)

    # When the new path is a folder above the old one, a path under the old
    # path after the move can be a real path of the moved project. When it is
    # a folder below the old one, a new path under the old path, outside the
    # new one, can be a new project. Either way a second run would move what
    # it must not, so the run must finish everything at once, and a second
    # run of the same move is refused.
    up = old.startswith(new + "/")
    down = new.startswith(old + "/")
    one_run = up or down

    def at_new(p):
        # the new path, or a path under it that is not part of the move; when
        # the new path is a folder above the old one, only the new path itself
        if not isinstance(p, str):
            return False
        return p == new or (not up and p.startswith(new + "/"))

    variants = set()  # other spellings of the old path (letter case, Unicode form)

    def move_or_note(p):
        np = move(p)
        if np is None and not at_new(p):
            v = case_variant(p, old)
            if v:
                variants.add(v)
        return np

    backups_dir = os.path.join(projects_dir, "_move-backups")
    records_dir = os.path.join(projects_dir, RECORDS_DIR)
    if one_run:
        if up:
            print("WARNING: the new path is a folder above the old path. After --apply, a path")
            print("         under the old path can be a real path of the moved project.")
        else:
            print("WARNING: the new path is a folder below the old path. After --apply, a path")
            print("         under the old path, outside the new path, can be a new project. A path")
            print("         at or under the new path counts as moved already.")
        print("         So this move must finish in one run, and it must not run again.")
        print("         The script refuses a second run of it.\n")
        records, problem = read_move_records(records_dir)
        if problem:
            print("ABORT: the script cannot read its records of finished moves:")
            print(f"           {problem}")
            print("       Fix that, then run the script again. Nothing was changed.")
            return EXIT_ABORT
        for record_file, record in records:
            if record.get("from") == old and record.get("to") == new:
                print("ABORT: this move was applied already. Its record is:")
                print(f"           {record_file}")
                print("       A second run would move paths that are not part of the move. If you")
                print("       moved the project back since then, or restored the backup of that")
                print("       run by hand, delete the record, then run the script again.")
                return EXIT_ABORT
    rerun = []  # what would need another run

    # Every check below runs before the first change. With --apply, all the
    # backups are written first, then the actions run in order.
    backups = []  # callables taking the backup root
    actions = []  # (description, callable)
    checks = []   # callables taking the backup root, run after the actions; each counts bad transcripts

    # The JSON stores are read first: their paths name the projects inside
    # the old path, whose transcript folders move as well.
    cfg, cfg_error = load_json(config_path)
    registry, registry_error = load_json(registry_path)
    sessions, skipped_sessions = read_session_files(os.path.join(appdir, "claude-code-sessions"), old)
    known = project_paths(cfg, sessions, registry)

    # Transcripts hold paths as JSON string text, so the transcript rewrite
    # works on the JSON-escaped form of each path.
    old_j, new_j = json_text(old), json_text(new)

    # --- Store 1: transcripts -------------------------------------------------
    scan = scan_transcript_dirs(projects_dir)
    for info in scan.values():
        for q in info["projects"].values():
            move_or_note(q)
    # the old dirs are looked up by every rule, the detected one first
    encoders = [encode] + [fn for _, fn in ENCODERS if fn is not encode]
    folders = find_transcript_folders(projects_dir, old, new, move, known, encoders, scan)
    moves, deferred, problems = folders["moves"], folders["deferred"], folders["problems"]

    in_scope = sorted(folders["found"] | folders["paths"])
    print(f"Scope: the old path and every path under it. {len(in_scope)} project path(s) found:")
    for p in in_scope:
        print(f"    {p}")
    print()
    # a project path under the old path that is still there while its new
    # place is not: it did not move with the folder, as hidden folders such as
    # .claude often do not when files are moved with "mv dir/*" or the Finder
    stayed = sorted(p for p in in_scope if p != old and move(p) is not None
                    and os.path.isdir(p) and not os.path.isdir(move(p)))
    if stayed:
        print(f"NOTE: {len(stayed)} project path(s) under the old path are still at their old place,")
        print("      and their new place does not exist, so they did not move with the folder.")
        print("      Hidden folders such as .claude are easy to leave behind:")
        for p in stayed:
            print(f"          {p}")
        if one_run:
            print("      Move them to the new place first, then run the script again.")
        else:
            print("      Their records move all the same, so move them to the new place too.")
        print()
        rerun.append("project paths that are still at their old place")
    if down:
        moved_already = sorted(p for p in known if p == new or p.startswith(new + "/"))
        if moved_already:
            print(f"NOTE: {len(moved_already)} project path(s) are at or under the new path, so the script")
            print("      counts them as moved already:")
            for p in moved_already:
                print(f"          {p}")
            print("      If one of them was a project inside the old folder before the move, it")
            print("      is one level deeper now. Inspect it by hand first.")
            print()

    plans = []
    for name, new_name, info, freed in moves:
        plan = plan_folder(os.path.join(projects_dir, name), os.path.join(projects_dir, new_name),
                           freed, old_j, new_j, keep=info["keep"])
        plan["name"], plan["info"] = name, info
        plans.append(plan)
    blocked = [p for p in plans if p["problems"]] or problems

    if plans or problems:
        print(f"[transcripts] {len(plans)} project dir(s) to move:")
    else:
        print("[transcripts] no transcript dir found for the old path or a path under it (nothing to do)")
    for plan in plans:
        how = "by name" if plan["info"]["how"] == "name" else "by its transcripts"
        print(f"  {plan['name']}  (found {how})")
        for line in plan["problems"] or plan["lines"]:
            print(f"    {line}")
        if not plan["problems"] and not (plan["rename"] or plan["rewrite"]):
            print("    (nothing to do)")
        stale = plan["info"]["stale"]
        if stale and not plan["problems"] and plan["rename"]:
            print(f"    NOTE: it also holds transcripts of {len(stale)} path(s) outside the old path that no")
            print(f"          longer exist, such as {stale[0]}.")
            print("          They move with the dir and keep their paths.")
        target = folders["merge_into"].get(plan["name"])
        if target and not plan["problems"]:
            replaced = {rel for rel, k in plan["kinds"].items() if k == "replace"}
            left = folders["inside"][target] - replaced
            if left:
                print(f"    NOTE: the new dir also holds {len(left)} transcript(s) of the old path that the merge")
                if one_run:
                    print("          does not replace. Replace the old path in them by hand, or move them")
                    print("          out of ~/.claude/projects, then run the script again.")
                else:
                    print("          does not replace. Run the script again after --apply to rewrite them.")
                rerun.append(f"{target}: transcripts of the old path that the merge does not replace")
    for name, lines in problems:
        if name:
            print(f"  {name}")
        for line in lines:
            print(f"    {line}")
    for line in folders["notes"]:
        print(f"  {line}")
    if folders["notes"]:
        rerun.append("transcript dirs that cannot be read")
    for name in sorted(deferred) if not blocked else []:
        why, other = deferred[name]
        if why == "same":
            print(f"  NOTE: {name} also belongs to the old path or a path under it, and")
            print(f"        it goes to the same new dir as {other}.")
            if one_run:
                print(f"        Move its files into {other} by hand first (join the two copies of")
                print("        memory/MEMORY.md if both have one), then run the script again.")
            else:
                print("        Run the script again after --apply to merge that dir as well.")
        else:
            print(f"  NOTE: the new name of {name} is the current name of {other},")
            print("        which does not move in this run.")
            if one_run:
                print("        Inspect both dirs by hand, then run the script again.")
            else:
                print("        Run the script again after --apply to move that dir as well.")
        rerun.append(f"{name}: waits for a second run")
    if blocked:
        print()
        print("ABORT: nothing was changed. Fix the problems above, then run the script again.")
        return EXIT_ABORT

    for plan in plans:
        if plan["rename"] or plan["rewrite"]:
            backups.append(functools.partial(backup_folder, plan))
            actions.append((f"transcripts {plan['name']}", functools.partial(apply_folder, plan, old_j, new_j)))
            checks.append(functools.partial(verify_folder, plan, old_j=old_j, new_j=new_j))
    print()

    # --- Store 2: ~/.claude.json ---------------------------------------------
    write_dirs = set()    # the folders that the apply run writes in
    change_files = set()  # the files and folders that it replaces or removes
    for plan in plans:
        if plan["rename"] or plan["rewrite"]:
            write_dirs |= plan["write_dirs"]
            change_files |= plan["change_files"]
    if cfg_error:
        print(f"[config] WARNING: cannot parse ~/.claude.json ({cfg_error}).")
        print("    The script leaves it as it is. Fix the file, then run again.")
        rerun.append("~/.claude.json does not parse")
    elif isinstance(cfg, dict):
        keys, entries, repo_paths = migrate_config(copy.deepcopy(cfg), move_or_note)
        if keys or entries or repo_paths:
            print("[config] ~/.claude.json:" + (f" will migrate {len(keys)} projects key(s)" if keys else ""))
            for k, nk, kept_new in keys:
                print(f"    {k}")
                print(f" -> {nk}")
                if kept_new is not None:
                    print("    the new key already exists: merge the old entry into it. A setting")
                    print("    only the old entry has is added, an empty new value takes the old")
                    print("    value, and two lists are joined.")
                    if kept_new:
                        print(f"    both entries hold a different value for: {', '.join(kept_new)}")
                        print("    the new values stay (the backup keeps the old ones)")
            if entries:
                print(f"    rewrite the activeWorktreeSession paths of {entries} projects entr{'y' if entries == 1 else 'ies'}")
            if repo_paths:
                print(f"    rewrite {repo_paths} path(s) in githubRepoPaths")

            def backup_config(root):
                shutil.copy2(config_path, os.path.join(root, ".claude.json"))

            def do_config():
                with open(config_path, encoding="utf-8") as fh:
                    c = json.load(fh)
                migrate_config(c, move)
                write_atomic(config_path, json.dumps(c, indent=2))

            backups.append(backup_config)
            actions.append(("config", do_config))
            write_dirs.add(os.path.dirname(os.path.realpath(config_path)))
            change_files.add(os.path.realpath(config_path))
        else:
            print("[config] ~/.claude.json: no projects key or path under the old path (nothing to do)")
    else:
        print("[config] ~/.claude.json: no projects key or path under the old path (nothing to do)")
    print()

    # --- Store 3: desktop app local_*.json -----------------------------------
    sidebar_hits = []  # (path, title, changed fields)
    for p, o in sessions:
        fields = migrate_session_file(copy.deepcopy(o), move_or_note)
        if fields:
            sidebar_hits.append((p, o.get("title", ""), fields))
    if skipped_sessions:
        print(f"[sidebar] WARNING: {len(skipped_sessions)} session file(s) cannot be read, or do not parse and")
        print("    mention the old path. The script leaves them as they are:")
        for p, why in skipped_sessions:
            print(f"        {os.path.relpath(p, appdir)} ({why})")
        rerun.append("session files that cannot be read")
    if sidebar_hits:
        print(f"[sidebar] {len(sidebar_hits)} desktop-app session file(s) hold paths under the old path:")
        for p, title, fields in sidebar_hits:
            print(f"    {os.path.basename(p)}  ({title})  {', '.join(fields)}")
            write_dirs.add(os.path.dirname(os.path.realpath(p)))
            change_files.add(os.path.realpath(p))

        def backup_sidebar(root):
            # keep each file's subfolders, so the backup shows where it goes back
            for p, _, _ in sidebar_hits:
                dst = os.path.join(root, os.path.relpath(p, appdir))
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copy2(p, dst)

        def do_sidebar():
            for p, _, _ in sidebar_hits:
                with open(p, encoding="utf-8") as fh:
                    o = json.load(fh)
                migrate_session_file(o, move)
                # the app writes these files as compact JSON
                write_atomic(p, json.dumps(o, separators=(",", ":")))

        backups.append(backup_sidebar)
        actions.append(("sidebar", do_sidebar))
    else:
        print("[sidebar] no desktop-app session files hold paths under the old path (nothing to do)")
    print()

    # --- Store 4: desktop app git-worktrees.json -----------------------------
    if registry_error:
        print(f"[worktrees] WARNING: cannot parse {REGISTRY_FILE} ({registry_error}).")
        print("    The script leaves it as it is. Fix the file, then run again.")
        rerun.append(f"{REGISTRY_FILE} does not parse")
    else:
        registry_hits = migrate_registry(copy.deepcopy(registry), move_or_note) if registry is not None else []
        if registry_hits:
            print(f"[worktrees] {REGISTRY_FILE}: {len(registry_hits)} desktop-app worktree(s) hold paths under the old path:")
            for name, fields in registry_hits:
                print(f"    {name}  {', '.join(fields)}")

            def backup_registry(root):
                shutil.copy2(registry_path, os.path.join(root, REGISTRY_FILE))

            def do_registry():
                with open(registry_path, encoding="utf-8") as fh:
                    r = json.load(fh)
                migrate_registry(r, move)
                # the app writes this file with tabs
                write_atomic(registry_path, json.dumps(r, indent="\t"))

            backups.append(backup_registry)
            actions.append(("worktrees", do_registry))
            write_dirs.add(os.path.dirname(os.path.realpath(registry_path)))
            change_files.add(os.path.realpath(registry_path))
        else:
            print("[worktrees] no desktop-app worktree holds paths under the old path (nothing to do)")
    print()

    if variants:
        print(f"NOTE: {len(variants)} other spelling(s) of the old path appear in the stores:")
        for v in sorted(variants):
            if unicodedata.normalize("NFC", v) == unicodedata.normalize("NFC", old):
                kind = "another Unicode form"
            elif v.lower() == old.lower():
                kind = "another letter case"
            else:
                kind = "another letter case and Unicode form"
            print(f"          {v}  ({kind})")
        print("      The script changes only the exact spelling, so the paths with these")
        print("      spellings stay as they are. On a disk that ignores letter case and")
        print("      Unicode form, as on macOS, they name the same folder.")
        if one_run:
            print("      Change them by hand, because this move cannot run again.")
        else:
            print("      To move them too, run the script again with --from set to that spelling.")
        print()

    if not actions:
        print("Nothing to migrate. Either already migrated, or the old path was not found.")
        return EXIT_OK

    if one_run and rerun:
        print("ABORT: one path is a folder above the other, so this move must finish in one")
        print("       run, but these parts would need another run:")
        for why in rerun:
            print(f"         {why}")
        print("       Fix them by hand as the messages above say, then run the script again.")
        print("       Nothing was changed.")
        return EXIT_ABORT

    create_only = set()  # folders that only get new entries, which append-only allows
    for d in (backups_dir, records_dir) if one_run else (backups_dir,):
        if os.path.lexists(d) and not os.path.isdir(d):
            print(f"ABORT: {d} is not a folder. Move it away, then run the script again.")
            print("       Nothing was changed.")
            return EXIT_ABORT
        only_new = d == backups_dir
        while not os.path.lexists(d):
            d = os.path.dirname(d)
        if only_new and d not in write_dirs:
            create_only.add(d)
        write_dirs.add(d)
    locked_dirs = sorted(d for d in write_dirs if not os.access(d, os.W_OK | os.X_OK))
    if locked_dirs:
        print("ABORT: the apply run must write in these folders, but it may not:")
        for d in locked_dirs:
            print(f"         {d}")
        print("       Fix their permissions, then run the script again. Nothing was changed.")
        return EXIT_ABORT
    locked_files = sorted(f for f in change_files | write_dirs
                          if is_locked(f, _IMMUTABLE_FLAGS if f in create_only else _LOCK_FLAGS))
    if locked_files:
        print("ABORT: the apply run must change these files or folders, but a file flag")
        print("       (immutable or append-only, set with chflags) stops it:")
        for f in locked_files:
            print(f"         {f}")
        print("       Clear the flags (chflags nouchg, nouappnd), then run the script again.")
        print("       Nothing was changed.")
        return EXIT_ABORT

    if not apply:
        print("DRY RUN. Re-run with --apply to perform the changes above.")
        return EXIT_OK

    backup_root = None
    try:
        backup_root = make_backup_root(projects_dir, old, new)
        for fn in backups:
            fn(backup_root)
    except Exception as e:
        print(f"ERROR: could not write the backup: {e}")
        print("Nothing was changed. Fix the cause (for example, free some disk space) and run again.")
        if backup_root:
            print(f"The incomplete backup can be deleted: {backup_root}")
        return EXIT_ERROR
    print(f"Backups -> {backup_root}")

    done = []
    for name, fn in actions:
        try:
            fn()
        except Exception as e:
            print(f"ERROR while applying {name}: {e}")
            print(f"Applied before the error: {', '.join(done) or 'nothing'}. The {name} store may be")
            print("partly changed. The backup holds each file as it was before this run:")
            print(f"    {backup_root}")
            print("Restore from it by hand before you run the script again.")
            return EXIT_ERROR
        done.append(name)
        print(f"  applied: {name}")
    print()

    # verification: each transcript from a moved dir now holds its planned
    # text (or, after a merge, a longer copy of it), checked against the backup
    if checks:
        bad = sum(check(backup_root) for check in checks)
        total = sum(len(p["jsonl"]) for p in plans if p["rename"] or p["rewrite"])
        print(f"Verification: {bad} of {total} transcript file(s) differ from the plan (want 0).")
        print()
        if bad:
            print("ERROR: the transcripts are not as planned. The backup holds each file as it was")
            print(f"before this run: {backup_root}")
            print("Restore from it by hand before you run the script again.")
            return EXIT_ERROR
    if one_run:
        record = {"from": old, "to": new, "backup": backup_root,
                  "finished": datetime.now().isoformat(timespec="seconds")}
        try:
            os.makedirs(records_dir, exist_ok=True)
            write_atomic(os.path.join(records_dir, os.path.basename(backup_root) + ".json"),
                         json.dumps(record, indent=2))
        except OSError as e:
            print(f"WARNING: could not record the finished move ({e}). Do not run this move again.")
    print("Done. Now relaunch the Claude desktop app; it reloads the session list")
    print("on startup, so the project reappears in the sidebar at its new location.")
    return EXIT_OK


def main():
    ap = argparse.ArgumentParser(description="Migrate Claude Code project metadata after a move.")
    ap.add_argument("--from", dest="old", required=True, help="OLD absolute project path")
    ap.add_argument("--to", dest="new", required=True, help="NEW absolute project path")
    ap.add_argument("--apply", action="store_true", help="perform changes (default: dry run)")
    ap.add_argument("--force", action="store_true", help="apply even if the desktop app is running")
    args = ap.parse_args()
    if not args.old.strip() or not args.new.strip():
        ap.error("--from and --to must not be empty")
    # a path in a store can hold text that the terminal cannot show
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="backslashreplace")
        except (AttributeError, ValueError):
            pass

    old = re.sub(r"^/+", "/", os.path.abspath(os.path.expanduser(args.old))).rstrip("/")
    new = re.sub(r"^/+", "/", os.path.abspath(os.path.expanduser(args.new))).rstrip("/")
    if not old or not new:
        ap.error("--from and --to must name project folders, not the root folder")
    if old == new:
        print("Old and new paths are identical; nothing to do.")
        return EXIT_OK
    return plan_and_apply(old, new, args.apply, args.force)


if __name__ == "__main__":
    sys.exit(main())
