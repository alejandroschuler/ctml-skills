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
       - the directory name is the project path with separators replaced
       - each *.jsonl record (incl. subagents/) has an internal "cwd" plus
         file references that point at the old path
  2. Global config:    ~/.claude.json
       - the "projects" object is keyed by absolute path
  3. Desktop sidebar:  ~/Library/Application Support/Claude/claude-code-sessions/**/local_*.json
       - each file has "cwd" and "originCwd"; the sidebar groups by "cwd"

Usage:
    # dry run (default): shows exactly what would change, touches nothing
    python3 migrate_claude_project.py --from /old/abs/path --to /new/abs/path

    # apply the changes (makes a timestamped backup first)
    python3 migrate_claude_project.py --from /old/abs/path --to /new/abs/path --apply

Safety notes:
  - Quit the Claude desktop app before running with --apply. It caches the
    session list in memory and rewrites its store on activity, so edits made
    while it runs can be clobbered and won't appear until a restart anyway.
  - The script matches each project's OWN path (exact directory name and exact
    cwd field values). It does NOT blanket-replace the path string everywhere,
    because the path can appear incidentally in unrelated projects' transcripts.
"""

import argparse
import json
import os
import platform
import re
import shutil
import subprocess
import sys
from datetime import datetime


# ---------------------------------------------------------------------------
# Path encoding (path -> ~/.claude/projects directory name)
# ---------------------------------------------------------------------------
# Claude Code derives the projects/ subdirectory name from the absolute path by
# replacing certain characters with "-". The exact set has varied across
# versions (some replace only "/"; observed installs also replace "."). Rather
# than hardcode a rule, we detect which candidate reproduces the most existing
# (path -> directory) pairs on THIS machine, then use it for both old and new.

def enc_slash(p):
    return p.replace("/", "-")

def enc_slash_dot(p):
    return p.replace("/", "-").replace(".", "-")

def enc_nonalnum(p):
    return re.sub(r"[^A-Za-z0-9]", "-", p)

ENCODERS = [("slash", enc_slash), ("slash+dot", enc_slash_dot), ("nonalnum", enc_nonalnum)]


def detect_encoder(projects_dir, config_path):
    """Pick the encoder that best maps real .claude.json project keys to real
    projects/ directory names on this machine."""
    keys = []
    if os.path.isfile(config_path):
        try:
            with open(config_path) as fh:
                keys = list(json.load(fh).get("projects", {}).keys())
        except Exception:
            keys = []
    dirs = set(os.listdir(projects_dir)) if os.path.isdir(projects_dir) else set()
    best_name, best_fn, best_score = "slash+dot", enc_slash_dot, -1
    for name, fn in ENCODERS:
        score = sum(1 for k in keys if fn(k) in dirs)
        if score > best_score:
            best_name, best_fn, best_score = name, fn, score
    return best_name, best_fn


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
_SAFE_NEXT = set("/\"'\\ \t\r\n,;:)]}<>|`")

def risky_occurrences(text, old):
    """Return count of occurrences of `old` immediately followed by a name
    character (alnum, '-', '_', '.'), i.e. where `old` is a prefix of a longer
    final path component. Those would be wrong to replace."""
    risky = 0
    i = text.find(old)
    while i != -1:
        nxt = text[i + len(old)] if i + len(old) < len(text) else ""
        if nxt != "" and nxt not in _SAFE_NEXT:
            risky += 1
        i = text.find(old, i + 1)
    return risky


# ---------------------------------------------------------------------------
# Backups
# ---------------------------------------------------------------------------

def make_backup_root(projects_dir, old, new):
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    tag = f"{os.path.basename(old) or 'root'}-to-{os.path.basename(new) or 'root'}-{stamp}"
    root = os.path.join(projects_dir, "_move-backups", tag)
    os.makedirs(root, exist_ok=True)
    return root


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


def find_transcript_dir(projects_dir, old, encode):
    """Locate the project's transcript directory. Try the encoded name first,
    then fall back to scanning each dir's jsonl for cwd == old."""
    cand = os.path.join(projects_dir, encode(old))
    if os.path.isdir(cand):
        return cand, "encoded-name"
    # content scan fallback (handles version/encoding drift)
    if os.path.isdir(projects_dir):
        for name in os.listdir(projects_dir):
            d = os.path.join(projects_dir, name)
            if not os.path.isdir(d) or name.startswith("_move-backups"):
                continue
            for fn in os.listdir(d):
                if not fn.endswith(".jsonl"):
                    continue
                try:
                    with open(os.path.join(d, fn), encoding="utf-8") as fh:
                        for line in fh:
                            line = line.strip()
                            if not line:
                                continue
                            try:
                                rec = json.loads(line)
                            except Exception:
                                continue
                            if isinstance(rec, dict) and rec.get("cwd") == old:
                                return d, "cwd-content-match"
                            break  # only need the first record per file
                except Exception:
                    pass
    return None, None


def plan_and_apply(old, new, apply, force):
    home = os.path.expanduser("~")
    projects_dir = os.path.join(home, ".claude", "projects")
    config_path = os.path.join(home, ".claude.json")
    appdir = app_support_dir()

    enc_name, encode = detect_encoder(projects_dir, config_path)
    print(f"Detected projects/ encoder: {enc_name}")
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
        return 2

    actions = []  # (description, callable)
    backup_root = make_backup_root(projects_dir, old, new) if apply else None

    # --- Store 1: transcripts -------------------------------------------------
    tdir, how = find_transcript_dir(projects_dir, old, encode)
    new_dirname = encode(new)
    new_dir = os.path.join(projects_dir, new_dirname)

    if tdir:
        print(f"[transcripts] found project dir via {how}:")
        print(f"    {tdir}")
        jsonls = []
        for r, _, files in os.walk(tdir):
            for f in files:
                if f.endswith(".jsonl"):
                    jsonls.append(os.path.join(r, f))
        # boundary safety check across all transcripts
        total_risky = 0
        for jf in jsonls:
            try:
                total_risky += risky_occurrences(open(jf, encoding="utf-8").read(), old)
            except Exception:
                pass
        if total_risky:
            print(f"    ABORT: {total_risky} occurrence(s) of the old path are a prefix of a")
            print(f"           longer name (e.g. a sibling dir). Refusing to string-replace.")
            print(f"           Inspect manually; this guard prevents corrupting a different path.")
            return 3

        rename_needed = os.path.abspath(tdir) != os.path.abspath(new_dir)
        print(f"    rename dir -> {new_dirname}" if rename_needed else "    dir name already correct")
        print(f"    rewrite internal 'cwd'/file refs in {len(jsonls)} transcript file(s)")

        def do_transcripts():
            # backup whole dir
            shutil.copytree(tdir, os.path.join(backup_root, os.path.basename(tdir)))
            target = tdir
            if rename_needed:
                if os.path.isdir(new_dir):
                    # merge: move files that don't collide, then drop old dir
                    for r, _, files in os.walk(tdir):
                        rel = os.path.relpath(r, tdir)
                        dst = os.path.join(new_dir, rel) if rel != "." else new_dir
                        os.makedirs(dst, exist_ok=True)
                        for f in files:
                            d = os.path.join(dst, f)
                            if not os.path.exists(d):
                                shutil.move(os.path.join(r, f), d)
                    shutil.rmtree(tdir, ignore_errors=True)
                else:
                    os.rename(tdir, new_dir)
                target = new_dir
            # rewrite contents
            for r, _, files in os.walk(target):
                for f in files:
                    if not f.endswith(".jsonl"):
                        continue
                    p = os.path.join(r, f)
                    raw = open(p, encoding="utf-8").read()
                    if old not in raw:
                        continue
                    new_raw = raw.replace(old, new)
                    for line in new_raw.splitlines():
                        line = line.strip()
                        if line:
                            json.loads(line)  # validate
                    open(p, "w", encoding="utf-8").write(new_raw)

        actions.append(("transcripts", do_transcripts))
    else:
        print("[transcripts] no project transcript directory found (nothing to do)")
    print()

    # --- Store 2: ~/.claude.json ---------------------------------------------
    cfg_change = False
    if os.path.isfile(config_path):
        try:
            cfg = json.load(open(config_path))
        except Exception:
            cfg = None
        if isinstance(cfg, dict) and old in cfg.get("projects", {}):
            cfg_change = True
            print("[config] ~/.claude.json: will migrate projects key")
            print(f"    {old}")
            print(f" -> {new}")

            def do_config():
                shutil.copy2(config_path, os.path.join(backup_root, ".claude.json"))
                c = json.load(open(config_path))
                projs = c.get("projects", {})
                val = projs.pop(old)
                projs.setdefault(new, val)  # keep existing new entry if present
                c["projects"] = projs
                with open(config_path, "w") as fh:
                    json.dump(c, fh, indent=2)

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
                        o = json.load(open(p))
                    except Exception:
                        continue
                    if isinstance(o, dict) and (o.get("cwd") == old or o.get("originCwd") == old):
                        sidebar_hits.append(p)
    if sidebar_hits:
        print(f"[sidebar] {len(sidebar_hits)} desktop-app session file(s) point at the old path:")
        for p in sidebar_hits:
            try:
                title = json.load(open(p)).get("title", "")
            except Exception:
                title = ""
            print(f"    {os.path.basename(p)}  ({title})")

        def do_sidebar():
            bdir = os.path.join(backup_root, "claude-code-sessions")
            os.makedirs(bdir, exist_ok=True)
            for p in sidebar_hits:
                shutil.copy2(p, os.path.join(bdir, os.path.basename(p)))
                o = json.load(open(p))
                if o.get("cwd") == old:
                    o["cwd"] = new
                if o.get("originCwd") == old:
                    o["originCwd"] = new
                with open(p, "w") as fh:
                    json.dump(o, fh, indent=2)

        actions.append(("sidebar", do_sidebar))
    else:
        print("[sidebar] no desktop-app session files point at the old path (nothing to do)")
    print()

    if not actions:
        print("Nothing to migrate. Either already migrated, or the old path was not found.")
        return 0

    if not apply:
        print("DRY RUN. Re-run with --apply to perform the changes above.")
        return 0

    print(f"Backups -> {backup_root}")
    for name, fn in actions:
        fn()
        print(f"  applied: {name}")
    print()

    # verification
    remaining = 0
    if tdir:
        check_dir = new_dir if os.path.isdir(new_dir) else tdir
        for r, _, files in os.walk(check_dir):
            for f in files:
                if f.endswith(".jsonl"):
                    try:
                        if old in open(os.path.join(r, f), encoding="utf-8").read():
                            remaining += 1
                    except Exception:
                        pass
    print(f"Verification: {remaining} transcript file(s) still contain the old path (want 0).")
    print()
    print("Done. Now relaunch the Claude desktop app; it reloads the session list")
    print("on startup, so the project reappears in the sidebar at its new location.")
    return 0


def main():
    ap = argparse.ArgumentParser(description="Migrate Claude Code project metadata after a move.")
    ap.add_argument("--from", dest="old", required=True, help="OLD absolute project path")
    ap.add_argument("--to", dest="new", required=True, help="NEW absolute project path")
    ap.add_argument("--apply", action="store_true", help="perform changes (default: dry run)")
    ap.add_argument("--force", action="store_true", help="apply even if the desktop app is running")
    args = ap.parse_args()

    old = os.path.abspath(os.path.expanduser(args.old)).rstrip("/")
    new = os.path.abspath(os.path.expanduser(args.new)).rstrip("/")
    if old == new:
        print("Old and new paths are identical; nothing to do.")
        return 0
    return plan_and_apply(old, new, args.apply, args.force)


if __name__ == "__main__":
    sys.exit(main())
