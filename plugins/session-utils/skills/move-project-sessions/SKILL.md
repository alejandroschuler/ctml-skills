---
name: move-project-sessions
description: >-
  Fixes a Claude Code project whose sidebar tab / session history disappeared
  after the project folder was moved or renamed on disk. Handles both the
  macOS desktop app sidebar and the `claude --resume` CLI history. Use this
  whenever a user moves, renames, or relocates a project directory and wants
  Claude Code to keep tracking it, or reports that a project "vanished from
  the sidebar", "lost its history", "shows the old path", or "won't resume"
  after a move. Also use proactively before moving a project, to do the move
  cleanly. Triggers on phrases like "I moved my project", "renamed the
  folder", "sidebar lost the project", "restore my Claude sessions after
  moving", "claude can't find my project anymore".
---

# Moving a Claude Code project without losing the sidebar / history

Claude Code records a project's absolute path in three separate stores. After
the project folder moves or is renamed, the old path no longer exists. The
desktop app then drops the project from its sidebar, and the CLI cannot find
its transcripts. The sessions are all still on disk, but their records point
at the old path. The fix is to rewrite the old path to the new one in all
three stores. The bundled script `scripts/migrate_claude_project.py` does
this. It runs with `python3` and uses only the Python standard library.

## Quit the desktop app before applying

The Claude desktop app must be fully quit (Cmd-Q) before any change is
applied, by the script or by hand. The app holds the session list in memory
and rewrites its store as it works, so it overwrites edits made while it
runs. Even an edit that survives does not show until the app restarts. The
script refuses to apply while it detects the app running, unless `--force` is
passed. Do not pass `--force` to get past that refusal while the app runs.

If Claude runs inside the desktop app, quitting the app ends Claude's own
session. The user then applies the changes in a plain terminal
(Terminal.app), as step 3 of the procedure says.

## Procedure

1. **Move the folder first.** The script edits Claude Code's metadata only. It
   does not move project files. Move or rename the folder in Finder or with
   `mv`.
2. **Run the dry run.** It shows exactly what will change and touches
   nothing. The script checks for the desktop app only when it applies, so
   Claude runs the dry run itself, even while the app is open:

   ```bash
   python3 "${CLAUDE_SKILL_DIR}/scripts/migrate_claude_project.py" \
     --from "/old/absolute/path" \
     --to   "/new/absolute/path"
   ```

   Show the user the plan that it prints.
3. **Apply** once the plan looks right, with the desktop app fully quit if the
   user uses it. The apply run writes a timestamped backup first:

   ```bash
   python3 "${CLAUDE_SKILL_DIR}/scripts/migrate_claude_project.py" \
     --from "/old/absolute/path" \
     --to   "/new/absolute/path" --apply
   ```

   Give the user this command to run in a plain terminal (Terminal.app).
   Write the script's absolute path out in full, because the user's shell
   does not know where this skill is installed. Tell the user to quit the
   desktop app with Cmd-Q, run the command, and then relaunch the app. Give
   all of this before the user quits the app.
4. **Relaunch the desktop app.** The project reappears in the sidebar at the
   new location with its history intact. For the CLI, `cd` into the new path
   and run `claude --resume`.

Backups land in `~/.claude/projects/_move-backups/<old>-to-<new>-<timestamp>/`:
a copy of the transcript folder, of `.claude.json`, and of each sidebar file
that the apply run changes. To revert, restore those copies.

## How the script stays safe

- **Per-project scoping.** The script touches only the moved project's own
  transcript folder, its own `projects` key, and the sidebar files whose `cwd`
  or `originCwd` equals the old path. It never replaces the path string across
  all of `~/.claude`, because the same string can appear in other projects'
  transcripts and in `.claude.json` backups. Those mentions stay as they are.
- **Boundary guard.** If the old path appears in the transcripts as the prefix
  of a longer name, for example `/a/b/proj-backup` when `/a/b/proj` moves, a
  string replace would corrupt that other path. The script then prints
  `ABORT` and exits with code 3, in a dry run as well as with `--apply`, and
  changes none of the stores. Inspect those matches by hand.
- **JSON validation.** The script parses each rewritten transcript line as
  JSON before it saves the file.

## The three stores

The paths here are for macOS. "Other operating systems" below gives the
others.

1. **CLI transcripts:** `~/.claude/projects/<encoded-path>/`.
   - The folder name is the project path encoded as a name. Claude Code 2.1
     replaces every character other than an ASCII letter or digit with `-`.
     It cuts a name longer than 200 characters to its first 200 and adds a
     hash of the path. The rule varies by version, so the script infers it
     from the existing pairs of `.claude.json` keys and folder names on the
     machine, rather than guessing. The name must match the new path, or the
     CLI looks in the wrong place.
   - Each `*.jsonl` record, including those in `subagents/`, stores an
     internal `cwd` and refers to files by absolute path. These still point at
     the old location.
2. **Global config:** `~/.claude.json`. Its `projects` object is keyed by
   absolute path, so the old key is a stale stub.
3. **Desktop sidebar:**
   `~/Library/Application Support/Claude/claude-code-sessions/**/local_*.json`.
   There is one small file per session, each with `cwd` and `originCwd`. This
   store feeds the desktop sidebar, which groups sessions by `cwd`. It is the
   store most often missed, because it lives under the app's data folder and
   not under `~/.claude`.

Claude Code keeps no SQLite database of its own sessions, so these three
stores, with the contents of the transcript files, are the complete set.

## Manual fallback

If the script cannot run, make the same edits by hand. Quit the desktop app
first, and back up each file before editing it. As with the apply run, the
user makes these edits in a plain terminal (Terminal.app), not in a Claude
Code session, so give the user the commands or the steps.

1. Rename `~/.claude/projects/<old-encoded>` to `<new-encoded>`, the new path
   encoded as "The three stores" describes. Check the rule against the names
   of the folders already there. In every `*.jsonl` inside the folder, replace
   the old absolute path with the new one, and keep the JSON valid.
2. In `~/.claude.json`, rename the `projects` key from the old path to the new
   one.
3. In `~/Library/Application Support/Claude/claude-code-sessions/`, find the
   `local_*.json` files whose `cwd` is the old path, and set `cwd` and
   `originCwd` to the new path. `grep -rl '<old path>'` over that folder finds
   them.
4. Relaunch the app.

## Other operating systems

- **Linux:** desktop store under `~/.config/Claude/claude-code-sessions/`.
- **Windows:** `%APPDATA%\Claude\claude-code-sessions\`.

`~/.claude/projects/` and `~/.claude.json` are in the home folder on all
platforms. The script picks the right app-support location by itself. Its
check for a running desktop app looks only for the macOS app, so on Linux and
Windows make sure that the app is quit before applying.
