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
passed: it prints `REFUSING` and exits with code 4. Do not pass `--force` to
get past that refusal while the app runs.

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

Backups land in `~/.claude/projects/_move-backups/<old>-to-<new>-<timestamp>/`.
The backup holds a copy of the transcript folder, or of both folders when
they merge. It also holds a copy of `.claude.json` and of each sidebar file
that the apply run changes. The sidebar copies keep their subfolders under
`claude-code-sessions/`. The apply run writes the full backup before its
first change, and it makes no backup folder when it changes nothing. To
revert, restore those copies. If a write fails during the apply run, the
script stops, names the backup folder, and exits with code 1. It does the
same if its check after the apply run finds a transcript that is not as
planned. Restore from that folder before you run the script again.

## How the script stays safe

- **Per-project scoping.** The script touches only the moved project's own
  transcript folder, its own `projects` key, and the sidebar files whose `cwd`
  or `originCwd` equals the old path. It never replaces the path string across
  all of `~/.claude`, because the same string can appear in other projects'
  transcripts and in `.claude.json` backups. Those mentions stay as they are.
- **Projects inside the moved folder.** A project inside the moved folder,
  such as a worktree under `.claude/worktrees/`, has its own path in each
  store. The dry run lists these paths in a `NOTE`. Give each of them its own
  dry run and apply run, with `--to` set to the same path under the new
  folder. Git also records where each worktree is. After the move, run
  `git worktree repair .claude/worktrees/*` in the moved repository.
- **Boundary guard.** If the old path appears in the transcripts as the prefix
  of a longer name, for example `/a/b/proj-backup` when `/a/b/proj` moves, a
  string replace would corrupt that other path. The script then prints
  `ABORT` and exits with code 3, in a dry run as well as with `--apply`, and
  changes none of the stores. Inspect those matches by hand. The guard looks
  only for a letter, a digit, `-` or `_` right after the path, or after a
  `.` there, as in `/a/b/proj.bak`. Other punctuation, such as a full stop
  or a question mark at the end of a sentence, does not count. If the new
  path contains the old one, as in a move from `thesis` to `thesis-final`,
  the mentions of the new path do not count, and they stay as they are.
- **Merge into an existing new folder.** If a session already ran at the new
  path, its transcript folder exists already. The old folder then merges into
  it, and the dry run gives the number of files for each step:
  - A file that only the old folder has moves over.
  - If the new folder already holds the same file, the old copy is deleted.
    A Finder `.DS_Store` file counts as the same.
  - If the new folder holds a copy of the same transcript that still has the
    old path, or that has fewer lines, the rewritten old copy replaces it. If
    it holds a longer copy, the longer copy stays.
  - The lines of the old `memory/MEMORY.md` that the new copy does not have
    go to the end of the new copy.

  The script does not replace the old path in the files that were already
  in the new folder.
- **Merge conflicts.** If any other file is in both folders with different
  contents, the script prints `ABORT` and exits with code 3. It does the
  same if the new folder reaches a file through a symlink, because a merge
  through a symlink can delete the only copy. This happens in a dry run as
  well as with `--apply`, and none of the stores changes. Merge each such
  pair by hand into the new folder's copy, or keep the better copy there.
  Then move the old folder's copy out of `~/.claude/projects`. Do not rename
  a transcript (`*.jsonl`), because its name is its session ID. Replace a
  symlinked folder in the new folder with a real folder. Then run the dry
  run again.
- **Config merge.** If `.claude.json` has a key for the new path too, the old
  entry merges into it. A setting that only the old entry has is added, an
  empty new value takes the old value, and two lists are joined. If both
  entries have a different value for a setting, the new value stays. The dry
  run names those settings, and the backup keeps the old values.
- **JSON validation.** Before any change, in a dry run as well as with
  `--apply`, the script tries the rewrite on each transcript line. If a valid
  JSON line would become invalid, the script prints `ABORT` and exits with
  code 3, and changes none of the stores.

## The three stores

The paths here are for macOS. "Other operating systems" below gives the
others.

1. **CLI transcripts:** `~/.claude/projects/<encoded-path>/`.
   - The folder name is the project path encoded as a name. Claude Code 2.1
     replaces every character other than an ASCII letter or digit with `-`.
     It cuts a name longer than 200 characters to its first 200 and adds `-`
     and a hash of the path. The script gives the new folder this name,
     because the CLI looks for the new path there. Older versions replaced
     fewer characters, so the old folder can have an older name. To find it,
     the script also tests each rule on the existing pairs of `.claude.json`
     keys and folder names on the machine. If no folder has a name that
     fits, the script looks for the folder whose transcripts belong to the
     old path. If more than one folder does, the dry run says so in a
     `NOTE`. Run the apply again after the first one, to merge the next
     folder.
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
