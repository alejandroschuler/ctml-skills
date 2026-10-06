#!/usr/bin/env python3
"""
Migrate a Claude Code project's metadata after its directory has been moved or
renamed on disk, so the desktop-app sidebar and `claude --resume` keep working.

Moving a project breaks Claude Code because the project's *old absolute path* is
baked into three separate stores. When that path no longer exists, the sidebar
drops the project and the CLI can't find its history. This script rewrites the
old path to the new one in all three stores.

Stores handled (macOS paths shown; see app_support_dir() for other OSes):

  1. CLI transcripts:  ~/.claude/projects/<encoded-path>/
       - the directory name is the project path with every character other
         than an ASCII letter or digit replaced by "-", cut to 200 characters
         plus a hash when longer (the rule of Claude Code 2.1)
       - each *.jsonl record (incl. subagents/) has an internal "cwd" plus
         file references that point at the old path
       - if the new directory already exists (a session already ran at the new
         path), the old directory merges into it
  2. Global config:    ~/.claude.json
       - the "projects" object is keyed by absolute path; if the new key
         already exists, the old entry merges into it
  3. Desktop sidebar:  ~/Library/Application Support/Claude/claude-code-sessions/**/local_*.json
       - each file has "cwd" and "originCwd"; the sidebar groups by "cwd"

A project inside the moved directory, such as a worktree under .claude/worktrees/,
has its own path in each store. The plan lists those paths; each needs a run of
its own.

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
  - The script matches each project's OWN path (exact directory name and exact
    cwd field values). It does NOT blanket-replace the path string everywhere,
    because the path can appear incidentally in unrelated projects' transcripts.
  - Every check runs before the first change, in a dry run and with --apply
    alike, and the backup is complete before the first change.
"""

import argparse
import filecmp
import json
import os
import platform
import re
import shutil
import stat
import subprocess
import sys
import tempfile
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


# ---------------------------------------------------------------------------
# Boundary-safe path matching inside transcripts
# ---------------------------------------------------------------------------
# When we string-replace the old path inside a .jsonl, we must not catch a
# sibling like "/a/b/proj-backup" when migrating "/a/b/proj". A genuine
# occurrence of the project path is always followed by a path separator or a
# string delimiter, never by another name character.

def _name_char(c):
    return c.isalnum() or c in "-_"

def risky_occurrences(text, old, protect=None):
    """Return count of occurrences of `old` immediately followed by a name
    character (a letter, a digit, '-' or '_'), or by dots and then a name
    character, i.e. where `old` is a prefix of a longer final path component
    such as proj-backup or proj.bak. Those would be wrong to replace. Any other
    character is a boundary, such as a '.' or '?' that ends a sentence. Spans
    that hold `protect` (the new path, when it contains the old one) are
    skipped."""
    if protect:
        return sum(risky_occurrences(part, old) for part in text.split(protect))
    risky = 0
    i = text.find(old)
    while i != -1:
        j = i + len(old)
        while j < len(text) and text[j] == ".":
            j += 1
        if j < len(text) and _name_char(text[j]):
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
    If new contains old, as in a move from thesis to thesis-final, a span that
    already holds new stays as it is, so it is not rewritten a second time.
    Lines split on "\\n" only: str.splitlines() also splits at characters such
    as U+2028, which JSON strings may hold."""
    lines = text.split("\n")
    broken = 0
    for i, line in enumerate(lines):
        if old in line:
            if old in new:
                changed = new.join(part.replace(old, new) for part in line.split(new))
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

def make_backup_root(projects_dir, old, new):
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    tag = f"{os.path.basename(old) or 'root'}-to-{os.path.basename(new) or 'root'}-{stamp}"
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
# Config merge
# ---------------------------------------------------------------------------

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


def holds_project(d, old):
    """True if a transcript at the top of dir d belongs to the old path."""
    try:
        names = sorted(os.listdir(d))
    except OSError:
        return False
    for fn in names:
        if fn.endswith(".jsonl"):
            try:
                if transcript_project(os.path.join(d, fn)) == old:
                    return True
            except OSError:
                pass
    return False


def find_transcript_dir(projects_dir, old, encoders):
    """Locate the project's transcript directory. Try the name each encoder
    gives the old path, then fall back to scanning each dir's transcripts for
    the old path. Also return the further dirs that hold transcripts of the
    old path: a second name that fits, or a second match of the scan."""
    named = []
    for encode in encoders:
        cand = os.path.join(projects_dir, encode(old))
        if os.path.isdir(cand) and not any(os.path.samefile(cand, d) for d in named):
            named.append(cand)
    if named:
        return named[0], "encoded-name", [d for d in named[1:] if holds_project(d, old)]
    # content scan fallback (handles version/encoding drift)
    try:
        names = sorted(os.listdir(projects_dir))
    except OSError:
        names = []
    matches = [os.path.join(projects_dir, name) for name in names
               if not name.startswith("_move-backups")
               and os.path.isdir(os.path.join(projects_dir, name))
               and holds_project(os.path.join(projects_dir, name), old)]
    if not matches:
        return None, None, []
    return matches[0], "cwd-content-match", matches[1:]


def plan_and_apply(old, new, apply, force):
    home = os.path.expanduser("~")
    projects_dir = os.path.join(home, ".claude", "projects")
    config_path = os.path.join(home, ".claude.json")
    appdir = app_support_dir()

    enc_name, encode, scores = detect_encoder(projects_dir, config_path)
    fits = ", ".join(f"{name} {n}" for name, n in scores.items())
    print(f"Detected projects/ encoder: {enc_name} (folder names reproduced: {fits})")
    if enc_name != ENCODERS[0][0]:
        print(f"NOTE: the folders on this machine fit the older {enc_name} rule best, so the old")
        print("      dir is looked up by that rule too. The new dir still gets the name that")
        print(f"      Claude Code 2.1 reads ({ENCODERS[0][0]} rule).")
    print(f"Old path: {old}")
    print(f"New path: {new}")
    print()

    if not os.path.isdir(new):
        print(f"WARNING: new path does not exist on disk yet: {new}")
        print("         Move the project directory first, then run this.\n")
    if os.path.isdir(old):
        print(f"WARNING: old path still exists on disk: {old}")
        print("         This script only edits Claude metadata; it does not move files.\n")

    if apply and not force and claude_desktop_running():
        print("REFUSING: the Claude desktop app appears to be running.")
        print("Quit it completely (Cmd-Q), then re-run with --apply.")
        print("Editing its session store while it runs gets clobbered and won't show until restart.")
        print("Use --force to override (not recommended).")
        return EXIT_APP_RUNNING

    # Every check below runs before the first change. With --apply, all the
    # backups are written first, then the actions run in order.
    backups = []  # callables taking the backup root
    actions = []  # (description, callable)
    nested = set()  # project paths inside the old path, which need runs of their own

    # Transcripts hold paths as JSON string text, so the transcript rewrite
    # works on the JSON-escaped form of each path.
    old_j, new_j = json_text(old), json_text(new)

    def rewrite(text):
        return rewrite_lines(text, old_j, new_j)[0]

    # --- Store 1: transcripts -------------------------------------------------
    tdir, how, other_dirs = find_transcript_dir(projects_dir, old, [encode, enc_nonalnum])
    new_dirname = enc_nonalnum(new)
    new_dir = os.path.join(projects_dir, new_dirname)
    jsonl_rels = []
    target_dir = None

    if tdir:
        print(f"[transcripts] found project dir via {how}:")
        print(f"    {tdir}")
        for d in other_dirs:
            print(f"    NOTE: {d} also holds transcripts of the old path.")
            print("          Run the script again after --apply to merge that dir as well.")
        if os.path.islink(tdir):
            print("    ABORT: this dir is a symlink. Inspect it manually. Nothing was changed.")
            return EXIT_ABORT

        # one pass over the transcripts: the boundary guard, and a trial
        # rewrite that must leave every valid JSON line valid. The backup
        # copies every file, so each one must be readable.
        total_risky = 0
        to_rewrite = set()
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

        entries, locked = readable_entries(tdir)
        jsonl_rels = [rel for rel in entries
                      if rel.endswith(".jsonl") and not os.path.islink(os.path.join(tdir, rel))]
        protect = new_j if old_j in new_j else None
        for rel in jsonl_rels:
            if rel in locked:
                continue
            try:
                text = read_text(os.path.join(tdir, rel))
            except OSError as e:
                unreadable.append(f"{os.path.join(os.path.basename(tdir), rel)} ({e.strerror})")
                continue
            total_risky += risky_occurrences(text, old_j, protect)
            new_text, n_broken = rewrite_lines(text, old_j, new_j)
            if new_text != text:
                to_rewrite.add(rel)
            if n_broken:
                broken.append(rel)
        if total_risky:
            print(f"    ABORT: {total_risky} occurrence(s) of the old path are a prefix of a")
            print(f"           longer name (e.g. a sibling dir). Refusing to string-replace.")
            print(f"           Inspect manually; this guard prevents corrupting a different path.")
            return EXIT_ABORT

        rename_needed = os.path.abspath(tdir) != os.path.abspath(new_dir)
        # on a case-insensitive disk, a new name that differs only in case is
        # the same folder: rename it, and never merge it into itself
        same_folder = (rename_needed and os.path.isdir(new_dir) and not os.path.islink(new_dir)
                       and os.path.samefile(tdir, new_dir))
        merge = rename_needed and os.path.lexists(new_dir) and not same_folder
        target_dir = new_dir if rename_needed else tdir
        if merge and (os.path.islink(new_dir) or not os.path.isdir(new_dir)):
            print(f"    ABORT: {new_dir} exists but is not a folder.")
            print("           Inspect it manually. Nothing was changed.")
            return EXIT_ABORT

        kinds = {}  # rel -> merge_kind(), for a merge
        if merge:
            readable_entries(new_dir)
            jsonl_set = set(jsonl_rels)
            for rel in entries:
                if rel in locked:
                    continue
                try:
                    kinds[rel] = merge_kind(rel, os.path.join(tdir, rel), os.path.join(new_dir, rel),
                                            new_dir, rewrite if rel in jsonl_set else None)
                except OSError as e:
                    unreadable.append(f"{os.path.join(new_dirname, rel)} ({e.strerror})")
        if broken or unreadable:
            if broken:
                print("    ABORT: replacing the old path would break JSON lines in:")
                for rel in broken:
                    print(f"             {rel}")
            if unreadable:
                print("    ABORT: cannot read:")
                for item in unreadable:
                    print(f"             {item}")
            print("           Inspect these files manually. Nothing was changed.")
            return EXIT_ABORT

        if merge:
            conflicts = [rel for rel, k in kinds.items() if k == "conflict"]
            if conflicts:
                print(f"    ABORT: the new dir {new_dirname} already exists, and {len(conflicts)} file(s)")
                print("           cannot merge: they differ between the two dirs, or the new dir")
                print("           reaches them through a symlink:")
                for rel in conflicts:
                    print(f"             {rel}")
                print("           Merge each pair by hand into the new dir's copy, or keep the better")
                print("           copy there. Then move the old dir's copy out of ~/.claude/projects.")
                print("           Do not rename a transcript (*.jsonl): its name is its session ID.")
                print("           Replace a symlinked folder in the new dir with a real folder.")
                print("           Then run the script again. Nothing was changed.")
                return EXIT_ABORT
            count = {k: sum(1 for v in kinds.values() if v == k) for k in ("move", "replace", "drop")}
            print(f"    new dir {new_dirname} already exists: merge the old dir into it")
            print(f"    move {count['move']} file(s) into the new dir")
            if count["replace"]:
                print(f"    replace {count['replace']} file(s) in the new dir that hold a raw or shorter copy")
            if count["drop"]:
                print(f"    drop {count['drop']} file(s) of the old dir that the new dir already holds")
            for rel in (r for r, k in kinds.items() if k == "join"):
                n = len(memory_index_extra(read_text(os.path.join(new_dir, rel)), read_text(os.path.join(tdir, rel))))
                print(f"    join {rel}: add {n} line(s) from the old copy to the end of the new copy")
            print("    then remove the old dir")
            n_rewrite = sum(1 for rel in to_rewrite if kinds[rel] in ("move", "replace"))
        else:
            print(f"    rename dir -> {new_dirname}" if rename_needed else "    dir name already correct")
            n_rewrite = len(to_rewrite)
        print(f"    rewrite internal 'cwd'/file refs in {n_rewrite} of {len(jsonl_rels)} transcript file(s)")

        def backup_transcripts(root):
            shutil.copytree(tdir, os.path.join(root, os.path.basename(tdir)), symlinks=True)
            if merge:
                shutil.copytree(new_dir, os.path.join(root, os.path.basename(new_dir)), symlinks=True)

        def do_transcripts():
            if not merge:
                if rename_needed:
                    os.rename(tdir, new_dir)
                for rel in sorted(to_rewrite):
                    p = os.path.join(target_dir, rel)
                    rewrite_file(p, p, old_j, new_j)
                return
            for rel, kind in kinds.items():
                src, dst = os.path.join(tdir, rel), os.path.join(new_dir, rel)
                if kind in ("move", "replace"):
                    os.makedirs(os.path.dirname(dst), exist_ok=True)
                    if rel in to_rewrite:
                        rewrite_file(src, dst, old_j, new_j)
                        os.remove(src)
                    else:
                        os.replace(src, dst)
                elif kind == "join":
                    dst_text = read_text(dst)
                    write_atomic(dst, append_lines(dst_text, memory_index_extra(dst_text, read_text(src))))
                    os.remove(src)
                else:  # drop
                    os.remove(src)
            left = remove_empty_dirs(tdir)
            if left:
                print(f"  WARNING: {len(left)} file(s) appeared in the old dir during the run and stay there:")
                for rel in left:
                    print(f"      {os.path.join(tdir, rel)}")

        if rename_needed or to_rewrite:
            backups.append(backup_transcripts)
            actions.append(("transcripts", do_transcripts))
        else:
            print("    (nothing to do)")
    else:
        print("[transcripts] no project transcript directory found (nothing to do)")
    print()

    # --- Store 2: ~/.claude.json ---------------------------------------------
    cfg, cfg_error = None, None
    if os.path.isfile(config_path):
        try:
            with open(config_path, encoding="utf-8") as fh:
                cfg = json.load(fh)
        except Exception as e:
            cfg_error = e
    projs = cfg.get("projects") if isinstance(cfg, dict) else None
    if isinstance(projs, dict):
        nested.update(k for k in projs if k.startswith(old + "/"))
    if cfg_error:
        print(f"[config] WARNING: cannot parse ~/.claude.json ({cfg_error}).")
        print("    The script leaves it as it is. Fix the file, then run again.")
    elif isinstance(projs, dict) and old in projs:
        print("[config] ~/.claude.json: will migrate projects key")
        print(f"    {old}")
        print(f" -> {new}")
        if new in projs:
            kept_new = merge_project_entries(projs[old], projs[new])[1]
            print("    the new key already exists: merge the old entry into it. A setting")
            print("    only the old entry has is added, an empty new value takes the old")
            print("    value, and two lists are joined.")
            if kept_new:
                print(f"    both entries hold a different value for: {', '.join(kept_new)}")
                print("    the new values stay (the backup keeps the old ones)")

        def backup_config(root):
            shutil.copy2(config_path, os.path.join(root, ".claude.json"))

        def do_config():
            with open(config_path, encoding="utf-8") as fh:
                c = json.load(fh)
            projs = c.get("projects", {})
            val = projs.pop(old)
            if new in projs:
                projs[new] = merge_project_entries(val, projs[new])[0]
            else:
                projs[new] = val
            c["projects"] = projs
            write_atomic(config_path, json.dumps(c, indent=2))

        backups.append(backup_config)
        actions.append(("config", do_config))
    else:
        print("[config] ~/.claude.json: no old projects key (nothing to do)")
    print()

    # --- Store 3: desktop app local_*.json -----------------------------------
    sidebar_hits = []
    if os.path.isdir(appdir):
        for r, _, files in os.walk(appdir):
            for f in files:
                if f.startswith("local_") and f.endswith(".json"):
                    p = os.path.join(r, f)
                    try:
                        with open(p, encoding="utf-8") as fh:
                            o = json.load(fh)
                    except Exception:
                        continue
                    if not isinstance(o, dict):
                        continue
                    if o.get("cwd") == old or o.get("originCwd") == old:
                        sidebar_hits.append(p)
                    nested.update(v for v in (o.get("cwd"), o.get("originCwd"))
                                  if isinstance(v, str) and v.startswith(old + "/"))
    if sidebar_hits:
        print(f"[sidebar] {len(sidebar_hits)} desktop-app session file(s) point at the old path:")
        for p in sidebar_hits:
            try:
                with open(p, encoding="utf-8") as fh:
                    title = json.load(fh).get("title", "")
            except Exception:
                title = ""
            print(f"    {os.path.basename(p)}  ({title})")

        def backup_sidebar(root):
            # keep each file's subfolders, so the backup shows where it goes back
            for p in sidebar_hits:
                dst = os.path.join(root, os.path.relpath(p, appdir))
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copy2(p, dst)

        def do_sidebar():
            for p in sidebar_hits:
                with open(p, encoding="utf-8") as fh:
                    o = json.load(fh)
                if o.get("cwd") == old:
                    o["cwd"] = new
                if o.get("originCwd") == old:
                    o["originCwd"] = new
                # the app writes these files as compact JSON
                write_atomic(p, json.dumps(o, separators=(",", ":")))

        backups.append(backup_sidebar)
        actions.append(("sidebar", do_sidebar))
    else:
        print("[sidebar] no desktop-app session files point at the old path (nothing to do)")
    print()

    # the new path and the paths under it are already in place, even when the
    # project moved into a folder inside its old path
    nested = {p for p in nested if p != new and not p.startswith(new + "/")}
    if nested:
        print(f"NOTE: {len(nested)} other project path(s) lie inside the old path, such as worktrees.")
        print("      Each has its own transcripts, projects key and sidebar files, which this")
        print("      run leaves as they are:")
        for p in sorted(nested):
            print(f"          {p}")
        print("      Run the script once for each of them, with --to set to the same path")
        print("      under the new path.")
        print()

    if not actions:
        print("Nothing to migrate. Either already migrated, or the old path was not found.")
        return EXIT_OK

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

    # verification: each transcript from the old dir now holds its planned
    # text (or, after a merge, a longer copy of it), checked against the backup
    if "transcripts" in done:
        bdir = os.path.join(backup_root, os.path.basename(tdir))
        bad = 0
        for rel in jsonl_rels:
            try:
                if not is_line_prefix(rewrite(read_text(os.path.join(bdir, rel))),
                                      read_text(os.path.join(target_dir, rel))):
                    bad += 1
            except OSError:
                bad += 1
        print(f"Verification: {bad} of {len(jsonl_rels)} transcript file(s) differ from the plan (want 0).")
        print()
        if bad:
            print("ERROR: the transcripts are not as planned. The backup holds each file as it was")
            print(f"before this run: {backup_root}")
            print("Restore from it by hand before you run the script again.")
            return EXIT_ERROR
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

    old = os.path.abspath(os.path.expanduser(args.old)).rstrip("/")
    new = os.path.abspath(os.path.expanduser(args.new)).rstrip("/")
    if not old or not new:
        ap.error("--from and --to must name project folders, not the root folder")
    if old == new:
        print("Old and new paths are identical; nothing to do.")
        return EXIT_OK
    return plan_and_apply(old, new, args.apply, args.force)


if __name__ == "__main__":
    sys.exit(main())
