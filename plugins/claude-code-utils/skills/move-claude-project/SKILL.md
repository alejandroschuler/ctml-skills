---
name: move-claude-project
description: >-
  Fix a Claude Code project whose sidebar tab / session history disappeared
  after the project folder was moved or renamed on disk. Use this whenever a
  user moves, renames, or relocates a project directory and wants Claude Code
  to keep tracking it, or reports that a project "vanished from the sidebar",
  "lost its history", "shows the old path", or "won't resume" after a move.
  Also use proactively before moving a project, to do the move cleanly. Triggers
  on phrases like "I moved my project", "renamed the folder", "sidebar lost the
  project", "restore my Claude sessions after moving", "claude can't find my
  project anymore". Handles both the macOS desktop app sidebar and the
  `claude --resume` CLI history.
---

# Moving a Claude Code project without losing the sidebar / history

## Why this happens

Claude Code records a project's **absolute path** in three independent places.
When you move or rename the folder, the old path stops existing, so the desktop
app can't locate the project (it drops it from the sidebar) and the CLI can't
find its transcripts. The files are all still there; they just point at a dead
path. Fixing it means rewriting the old path to the new one in all three stores.

The three stores (macOS paths; the script handles Linux/Windows variants too):

1. **CLI transcripts** `~/.claude/projects/<encoded-path>/`
   - The directory **name** is the project path with separators replaced by `-`
     (the exact rule varies by version, so the script detects it rather than
     guessing). This name must match the *new* path or the CLI looks in the
     wrong place.
   - Each `*.jsonl` record (including `subagents/`) stores an internal `cwd` and
     references files by absolute path. These still point at the old location.
2. **Global config** `~/.claude.json`
   - The `projects` object is keyed by absolute path. The old key is a stale stub.
3. **Desktop sidebar** `~/Library/Application Support/Claude/claude-code-sessions/**/local_*.json`
   - One small file per session, each with `cwd` and `originCwd`. This is the
     store that feeds the desktop sidebar; it groups sessions by `cwd`. People
     most often miss it, because it lives under the app's data directory rather
     than `~/.claude`.

There is no SQLite database for Claude Code's own sessions, so these three (plus
the transcript file contents) are the complete set.

## The one thing that bites everyone

**Quit the Claude desktop app before applying changes.** It holds the session
list in memory and rewrites its store as you work, so edits made while it's
running get clobbered. Even a clean edit won't show until you restart it
anyway. Run the migration from a plain terminal (Terminal.app), with the app
fully quit (Cmd-Q), then relaunch the app afterward. The bundled script refuses
to apply while it detects the app running, unless you pass `--force`.

## Procedure

1. **Move the folder first.** This script edits Claude's metadata only; it does
   not move project files. Move/rename the directory in Finder or with `mv`.
2. **Quit the Claude desktop app** (Cmd-Q), if you use it.
3. **Dry run** to see exactly what will change (touches nothing):

   ```bash
   python3 ~/.claude/skills/move-claude-project/scripts/migrate_claude_project.py \
     --from /old/absolute/path \
     --to   /new/absolute/path
   ```

4. **Apply** once the plan looks right (writes a timestamped backup first):

   ```bash
   python3 ~/.claude/skills/move-claude-project/scripts/migrate_claude_project.py \
     --from /old/absolute/path \
     --to   /new/absolute/path --apply
   ```

5. **Relaunch the desktop app.** The project reappears in the sidebar at the new
   location with its history intact. For the CLI, `cd` into the new path and
   `claude --resume`.

Backups land in `~/.claude/projects/_move-backups/<old>-to-<new>-<timestamp>/`
(a copy of the transcript directory, `.claude.json`, and each touched sidebar
file). To revert, restore those copies.

## How the script stays safe

It is deliberately conservative, because these are the user's chat history and
global config:

- **Per-project scoping, not global search-and-replace.** The same path string
  can appear incidentally in *other* projects' transcripts and in `.claude.json`
  backups. The script only touches the moved project's own transcript directory,
  its own `projects` key, and sidebar files whose `cwd`/`originCwd` *equals* the
  old path. It never blanket-replaces the string across all of `~/.claude`.
- **Boundary guard.** When rewriting the path inside transcripts, it refuses if
  the old path appears as a prefix of a longer name (e.g. migrating
  `/a/b/proj` when `/a/b/proj-backup` is also referenced), which would otherwise
  corrupt a different path.
- **JSON validation.** Every rewritten `.jsonl` line is re-parsed before the
  file is saved.
- **Encoder detection.** It infers the path→directory-name rule from the
  existing `(.claude.json key → projects/ dir)` pairs on the machine, so it
  adapts to version differences instead of assuming one rule.

## Manual fallback

If you can't run the script, do the same edits by hand (app quit, back up first):

1. Rename `~/.claude/projects/<old-encoded>` to `<new-encoded>` (path with `/`
   and `.` replaced by `-`), and in every `*.jsonl` inside it replace the old
   absolute path with the new one (keep the JSON valid).
2. In `~/.claude.json`, rename the `projects` key from the old path to the new.
3. In `~/Library/Application Support/Claude/claude-code-sessions/`, find the
   `local_*.json` files whose `cwd` is the old path and set `cwd` and
   `originCwd` to the new path. (`grep -rl '<old path>'` over that directory
   finds them.)
4. Relaunch the app.

## Other operating systems

- **Linux:** desktop store under `~/.config/Claude/claude-code-sessions/`.
- **Windows:** `%APPDATA%\Claude\claude-code-sessions\`.

`~/.claude/projects/` and `~/.claude.json` are in the home directory on all
platforms. The script picks the right app-support location automatically.
