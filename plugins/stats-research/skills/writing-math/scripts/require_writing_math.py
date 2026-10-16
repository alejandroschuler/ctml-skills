#!/usr/bin/env python3
"""PreToolUse hook for Edit, Write and MultiEdit on LaTeX documents (.tex).

Before the first .tex edit in a conversation, and before the first one in each
subagent, the hook refuses the edit and tells Claude to load the
stats-research:writing-math and stats-research:writing-proofs skills.
Claude then loads the skills and makes the edit again, and later edits pass.
A marker file in the temp folder, one for each session and subagent, records
that the hook has asked.

In the main conversation the first edit also passes when the transcript shows
that both skills are already loaded. A subagent's hook input may carry the main
conversation's transcript, so a subagent is always asked once. Any other file,
or input that does not parse, passes.
"""

import json
import re
import sys
import tempfile
from pathlib import Path

SKILLS = ("writing-math", "writing-proofs")
LOADED = {
    name: re.compile(r'"skill"\s*:\s*"(?:stats-research:)?' + name + '"')
    for name in SKILLS
}
REASON = (
    "Before the first edit to a .tex file, load the `stats-research:writing-math` "
    "and `stats-research:writing-proofs` skills with the Skill tool, then make "
    "this edit again, following their rules. If those rules are already in your "
    "context, make the edit again."
)


def safe(value: object, default: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]", "_", str(value or default))


def marker(payload: dict) -> Path:
    base = Path(tempfile.gettempdir()) / "stats-research-writing-math"
    return base / safe(payload.get("session_id"), "no-session") / safe(payload.get("agent_id"), "main")


def loaded_in_transcript(payload: dict) -> bool:
    if payload.get("agent_id"):
        return False
    path = payload.get("transcript_path")
    if not path:
        return False
    missing = set(SKILLS)
    try:
        with open(Path(path).expanduser(), encoding="utf-8", errors="replace") as f:
            for line in f:
                missing -= {name for name in missing if LOADED[name].search(line)}
                if not missing:
                    return True
    except OSError:
        return False
    return False


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return
    if not isinstance(payload, dict):
        return
    tool_input = payload.get("tool_input") or {}
    if not str(tool_input.get("file_path") or "").lower().endswith(".tex"):
        return
    mark = marker(payload)
    if mark.exists():
        return
    ask = not loaded_in_transcript(payload)
    try:
        mark.parent.mkdir(parents=True, exist_ok=True)
        mark.touch()
    except OSError:
        return  # without a marker the hook would refuse every edit, so let this one pass
    if ask:
        json.dump(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": REASON,
                }
            },
            sys.stdout,
        )


if __name__ == "__main__":
    main()
