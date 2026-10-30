#!/usr/bin/env python3
"""Move chosen desktop sessions (not a whole folder) to another project folder.

Usage:
  move_sessions.py --from /old/path --to /new/path SESSION_ID [SESSION_ID ...] [--apply]

SESSION_ID is a desktop id such as local_a3f3b187-... (list_sessions shows them).
Include linked subchats by listing their ids too.
Dry run by default. Quit the Claude desktop app (Cmd-Q) before --apply.
Only the session cwd changes. File paths inside the transcripts stay as they are.
"""
import argparse, glob, json, os, re, shutil, subprocess, sys, time

ap = argparse.ArgumentParser()
ap.add_argument("--from", dest="old", required=True)
ap.add_argument("--to", dest="new", required=True)
ap.add_argument("--apply", action="store_true")
ap.add_argument("sessions", nargs="+")
a = ap.parse_args()

H = os.path.expanduser("~")
PROJ = f"{H}/.claude/projects"
SIDEBAR = f"{H}/Library/Application Support/Claude/claude-code-sessions"
FIELDS = ["cwd", "originCwd", "gitAnchorsFolderRealpath"]
enc = lambda p: re.sub(r"[^A-Za-z0-9]", "-", p)[:200]
old_dir, new_dir = f"{PROJ}/{enc(a.old)}", f"{PROJ}/{enc(a.new)}"

if a.apply and subprocess.run(["pgrep", "-x", "Claude"], capture_output=True).stdout.strip():
    sys.exit("REFUSING: the Claude app is running. Quit it with Cmd-Q first.")
if not os.path.isdir(new_dir):
    sys.exit(f"ABORT: {new_dir} does not exist. Run a session in the new folder first.")

plan = []
for did in a.sessions:
    side = glob.glob(f"{SIDEBAR}/**/{did}.json", recursive=True)
    if len(side) != 1:
        sys.exit(f"ABORT: need exactly one sidebar file for {did}, found {side}")
    d = json.load(open(side[0]))
    if d.get("cwd") != a.old:
        sys.exit(f"ABORT: {did} has cwd {d.get('cwd')}, not {a.old}")
    cid = d["cliSessionId"]
    jl, sub = f"{old_dir}/{cid}.jsonl", f"{old_dir}/{cid}"
    if not os.path.exists(jl):
        sys.exit(f"ABORT: missing transcript {jl}")
    for p in (f"{new_dir}/{cid}.jsonl", f"{new_dir}/{cid}"):
        if os.path.exists(p):
            sys.exit(f"ABORT: already exists: {p}")
    n = open(jl).read().count(f'"cwd":"{a.old}"')
    print(f"{did}: {n} cwd entries in transcript")
    plan.append((did, cid, jl, sub, side[0], d))

if not a.apply:
    print("Dry run only. Add --apply to change files.")
    sys.exit(0)

backup = f"{PROJ}/_move-backups/sessions-{time.strftime('%Y%m%d-%H%M%S')}"
os.makedirs(backup)
for did, cid, jl, sub, side, d in plan:
    shutil.copy2(jl, backup)
    shutil.copy2(side, f"{backup}/{did}.json")
    for k in FIELDS:
        if d.get(k) == a.old:
            d[k] = a.new
    json.dump(d, open(side, "w"), ensure_ascii=False, indent=2)
    txt = open(jl).read().replace(f'"cwd":"{a.old}"', f'"cwd":"{a.new}"')
    open(f"{new_dir}/{cid}.jsonl", "w").write(txt)
    os.remove(jl)
    if os.path.isdir(sub):
        shutil.move(sub, f"{new_dir}/{cid}")
    print("moved", did)
print("Done. Backup:", backup, "\nRelaunch the Claude app.")
