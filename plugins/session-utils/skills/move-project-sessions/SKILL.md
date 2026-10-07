---
name: move-project-sessions
description: >-
  Fixes a Claude Code project whose sidebar tab / session history disappeared
  after the project folder was moved or renamed on disk. It also fixes the
  worktree sessions and other projects inside that folder. Handles both the
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

Claude Code and its desktop app record a project's absolute path in four
stores. After the project folder moves or is renamed, the old path no longer
exists. The desktop app then drops the project from its sidebar, and the CLI
cannot find its transcripts. The sessions are all still on disk, but their
records point at the old path. The fix is to rewrite the old path to the new
one in all four stores. The bundled script `scripts/migrate_claude_project.py`
does this. It runs with `python3` and uses only the Python standard library.

A project folder often holds other Claude Code projects, mostly worktrees
under `.claude/worktrees/`. Each of them has its own path in the stores. The
script moves them in the same run, so one run covers the whole folder.

## Quit the desktop app before applying

The Claude desktop app must be fully quit (Cmd-Q) before any change is
applied, by the script or by hand. The app holds the session list in memory
and rewrites its store as it works, so it overwrites edits made while it
runs. Even an edit that survives does not show until the app restarts. The
script refuses to apply while it detects the app running, unless `--force` is
passed: it prints `REFUSING` and exits with code 4. Do not pass `--force` to
get past that refusal while the app runs. Also end each `claude` session in a
terminal or an IDE before the apply run, because those sessions write
`~/.claude.json` and the transcripts too.

If Claude runs inside the desktop app, quitting the app ends Claude's own
session. The user then applies the changes in a plain terminal
(Terminal.app), as step 3 of the procedure says.

## Procedure

1. **Move the folder first.** The script edits Claude Code's metadata only. It
   does not move project files. Move or rename the folder in Finder or with
   `mv`. To move the contents of a folder instead, as into a folder below it,
   also move the hidden folders such as `.claude` and `.git`, because
   `mv dir/*` and a Finder select-all leave them behind. The dry run names
   each project path that stayed behind. Git records the absolute path of
   each worktree. If the repository has worktrees under
   `.claude/worktrees/`, run `git worktree repair .claude/worktrees/*` in the
   moved repository.
2. **Run the dry run.** It shows exactly what will change and touches
   nothing. The script checks for the desktop app only when it applies, so
   Claude runs the dry run itself, even while the app is open. Run it for the
   folder that moved, not for each worktree. Run it again only when a `NOTE`
   in the plan says so, right after the first apply run. A later run of the
   same move would also move a new project that uses the old path since:

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
The backup holds a copy of each transcript folder that moves, and of each
folder that one of them merges into. It also holds a copy of each of these
files that the apply run changes: `.claude.json`, `git-worktrees.json` and
the sidebar files. The sidebar copies keep their subfolders under
`claude-code-sessions/`. The apply run writes the full backup before its
first change, and it makes no backup folder when it changes nothing. To
revert, restore those copies. If a write fails during the apply run, the
script stops, names the backup folder, and exits with code 1. It does the
same if its check after the apply run finds a transcript that is not as
planned. Restore from that folder before you run the script again.

## How the script stays safe

- **Scope: the moved folder.** The script moves the old path and every path
  under it. A path under the old path becomes the same path under the new
  path. The projects inside the moved folder move in the same run: their
  transcript folders, `projects` keys, sidebar files and worktree entries.
  In the JSON stores, the script changes only the path fields that "The four
  stores" lists. It changes such a field when it holds the old path or a
  path under it, in every file and entry. An example is another project's
  session that has the moved folder as an added directory. Free text, such
  as a session title, stays as it is. In the transcripts, the script
  replaces the path string only in the transcript folders that move. It
  never replaces the path string across all of `~/.claude`, because the same
  string can appear in other projects' transcripts and in `.claude.json`
  backups. Those mentions stay as they are.
- **Boundary guard.** If the old path appears in the transcripts as the prefix
  of a longer name, for example `/a/b/proj-backup` when `/a/b/proj` moves, a
  string replace would corrupt that other path. The script then prints
  `ABORT` and exits with code 3, in a dry run as well as with `--apply`, and
  changes none of the stores. Inspect those matches by hand. The guard looks
  only for a letter, a digit, `-` or `_` right after the path, or after a
  `.` there, as in `/a/b/proj.bak`. Other punctuation, such as a full stop
  or a question mark at the end of a sentence, does not count. If the new
  path contains the old one, as in a move from `thesis` to `thesis-final`,
  the mentions of the new path do not count, and they stay as they are. In
  the JSON stores, a path is part of the move only if it is the old path or
  continues with `/` after it, so `/a/b/proj-backup` never changes.
- **Shared folder.** Two paths can give the same folder name, for example
  `my_thesis` and `my-thesis`. A folder that moves can then also hold the
  history of a project outside the old path. If that project is still in
  use, the script prints `ABORT` and exits with code 3, and none of the
  stores changes. A project is in use if its folder exists or the stores
  still list it. The script also stops in two more cases: the folder has the
  folder name of such a project and holds files that belong to no session in
  it, such as `memory/`, or the folder holds the sessions of the new path.
  Inspect that folder by hand. If the other path no longer exists and the
  stores do not list it, its transcripts move with the folder. Often they
  are left over from an earlier move. The dry run counts them in a `NOTE`
  and names one of them. A folder that keeps its name does not move, so the
  transcripts of other paths in it stay as they are.
- **Merge into an existing new folder.** If a session already ran at a new
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
  in the new folder. If one of them belongs to the old path, such as a
  copy, the dry run says so in a `NOTE`, and the next apply run rewrites it
  (in a move inside the same tree, see below).
  If the old and new paths give the same folder name, the folder stays where
  it is. The script then rewrites the transcripts that belong to the old
  path, and the transcripts of other paths, such as sessions at the new
  path, stay as they are.
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
- **Config merge.** If `.claude.json` has a key for a new path too, the old
  entry merges into it. A setting that only the old entry has is added, an
  empty new value takes the old value, and two lists are joined. If both
  entries have a different value for a setting, the new value stays. The dry
  run names those settings, and the backup keeps the old values.
- **JSON validation.** Before any change, in a dry run as well as with
  `--apply`, the script tries the rewrite on each transcript line. If a valid
  JSON line would become invalid, the script prints `ABORT` and exits with
  code 3, and changes none of the stores.
- **Write access.** Before any change, the script checks that it may write in
  each folder that the apply run changes, and that no file flag set with
  `chflags` (immutable or append-only) locks a file that it changes. If it
  may not, it prints `ABORT` and exits with code 3.
- **A move inside the same tree.** The new path can be a folder above the old
  path, as in a move from `/a/proj/proj` to `/a/proj`, or a folder below it,
  as in a move from `/a/work` to `/a/work/2025`. After such a move, a path
  under the old path can be a real path of the moved project, or a project
  made later. A second run of the same move would move those paths too. So
  the script makes such a move in one run only. It prints `ABORT` if a part
  of the move would need another run, or if a project path under the old
  path is still at its old place, and the `NOTE`s say what to fix by hand
  first. In a move to a folder below, a path at or under the new path counts
  as moved already, and a `NOTE` lists such paths. After the apply run, it records the finished move in
  `~/.claude/projects/_move-records/`, and it refuses a second run of the
  same move. Do not delete that folder. If the project moved back since
  then, or you restored the backup by hand, delete the record that the
  refusal names, then run again.
- **Letter case and Unicode form.** The script matches the exact spelling of
  the old path. On a disk that ignores letter case and Unicode form, as on
  macOS, the stores can hold the same path in another spelling, for example
  `.../HAR` and `.../har`, or an `é` as one character or as two. The dry run
  lists such spellings in a `NOTE`, and the paths with them stay as they
  are. To move them too, run the script again with `--from` set to that
  spelling, copied from the `NOTE`. In a move inside the same tree, change
  them by hand, because that move cannot run again.

Any other `ABORT` works the same way: the script exits with code 3, nothing
changes, and the message says what to inspect.

## The four stores

The paths here are for macOS. "Other operating systems" below gives the
others.

1. **CLI transcripts:** `~/.claude/projects/<encoded-path>/`, one folder for
   each project path, worktrees included.
   - The folder name is the project path encoded as a name. Claude Code 2.1
     replaces every character other than an ASCII letter or digit with `-`.
     It cuts a name longer than 200 characters to its first 200 and adds `-`
     and a hash of the path. The script gives each new folder this name,
     because the CLI looks for the new path there. Older versions replaced
     fewer characters, so an old folder can have an older name. To find it,
     the script first tests the rule that best fits the existing pairs of
     `.claude.json` keys and folder names on the machine, then the other
     rules. It also reads which project each transcript belongs to, so it
     finds an old folder under any name. If two folders need the same new
     name, one of them moves, and the dry run names the other in a `NOTE`.
     Run the apply again after the first one, to merge that folder (in a
     move inside the same tree, see "How the script stays safe").
   - Each `*.jsonl` record, including those in `subagents/`, stores an
     internal `cwd` and refers to files by absolute path. These still point at
     the old location.
2. **Global config:** `~/.claude.json`. Its `projects` object is keyed by
   absolute path, so the old keys are stale stubs. The paths in each entry's
   `activeWorktreeSession`, and in the top-level `githubRepoPaths` lists,
   also point at the old location.
3. **Desktop sidebar:**
   `~/Library/Application Support/Claude/claude-code-sessions/**/local_*.json`.
   There is one small file per session. This store feeds the desktop
   sidebar, which groups sessions by `cwd`. The script changes these path
   fields: `cwd`, `originCwd`, `worktreePath`, `gitAnchors` (`gitRoot`,
   `commonDir`, `gitDir`), `gitAnchorsFolderRealpath`, `planPath`,
   `worktreeLazy` (`path`), `keptWorktreeLeftover` (`path`, `baseRepo`), the
   directories in `sessionPermissionUpdates`, and the path part of each
   `writtenBranches` entry. It is the store most often missed, because it
   lives under the app's data folder and not under `~/.claude`. Sessions on
   an SSH host or in WSL keep their paths, because those paths are on
   another machine. A session file that cannot be read, or that does not
   parse and mentions the old path, stays as it is, and the dry run names it
   in a `WARNING`.
4. **Desktop worktrees:**
   `~/Library/Application Support/Claude/git-worktrees.json`. The desktop app
   lists here the worktrees that it made. The script changes `path`,
   `baseRepo`, `originTopLevel`, `placementRoot` and `anchors` of each
   entry. A worktree on an SSH host keeps its paths. The script leaves the
   caches in this file (`untrackedDirGc`, `originUrls`, `originPins`) as
   they are, because the app fills them again for the new paths.

The git anchors in stores 3 and 4 are the desktop app's record of the
repositories that the user trusts. The app runs git itself only in a
repository with a matching anchor. The script moves the anchors with the
project, so the trust moves too, as it does with the `projects` key and its
`hasTrustDialogAccepted`.

Claude Code keeps no SQLite database of its own sessions, so these four
stores, with the contents of the transcript files, hold the paths that the
sidebar and `claude --resume` read.

## What the script does not change

- Absolute paths in the project's own files, such as
  `.claude/settings.json`, `.claude/settings.local.json`, `.mcp.json` and
  hook scripts, and in `~/.claude/settings.json`.
- Desktop routines (scheduled tasks) that run in the moved folder.
- Paths that reach the moved folder through a symlink.

Check these by hand after the move.

## Manual fallback

If the script cannot run, make the same edits by hand. Quit the desktop app
first, and back up each file before editing it. As with the apply run, the
user makes these edits in a plain terminal (Terminal.app), not in a Claude
Code session, so give the user the commands or the steps. Make each edit for
the old path and for each project path under it, such as each worktree under
`.claude/worktrees/`. For a path under the old path, put the new path in
place of the old path and keep the rest.

1. Rename `~/.claude/projects/<old-encoded>` to `<new-encoded>`, the new path
   encoded as "The four stores" describes. Check the rule against the names
   of the folders already there. In every `*.jsonl` inside the folder, replace
   the old absolute path with the new one, and keep the JSON valid.
2. In `~/.claude.json`, rename the `projects` key from the old path to the new
   one. If the new key exists already, merge the old entry into it as
   "Config merge" describes. Change the paths in each entry's
   `activeWorktreeSession` and in the top-level `githubRepoPaths` lists too.
3. In `~/Library/Application Support/Claude/claude-code-sessions/`, find the
   `local_*.json` files that hold the old path. `grep -rl '<old path>'` over
   that folder finds them. Where `cwd` and `originCwd` hold the old path, set
   them to the new path. Change the other path fields that "The four stores"
   lists in the same way, and leave titles and other text as they are.
4. In `~/Library/Application Support/Claude/git-worktrees.json`, change the
   paths of each worktree entry under the old path.
5. Relaunch the app.

## Other operating systems

- **Linux:** desktop stores under `~/.config/Claude/`
  (`claude-code-sessions/` and `git-worktrees.json`).
- **Windows:** desktop stores under `%APPDATA%\Claude\`.

`~/.claude/projects/` and `~/.claude.json` are in the home folder on all
platforms. The script picks the right app-support location by itself. Its
check for a running desktop app looks only for the macOS app, so on Linux and
Windows make sure that the app is quit before applying. The script was
tested only on macOS. Its rule for paths under the old path looks for `/`,
but Claude Code on Windows writes paths with `\`. On Windows, the script can
then move only the exact old path. Check the plan there, and give each
worktree a run of its own if the plan does not list it.
