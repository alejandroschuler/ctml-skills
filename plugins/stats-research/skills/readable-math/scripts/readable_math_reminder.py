#!/usr/bin/env python3
"""PostToolUse hook for Edit, Write and MultiEdit on LaTeX documents (.tex).

When the edited file is a .tex file, print a reminder to invoke the
readable-math skill. The harness reads it from
hookSpecificOutput.additionalContext and places it next to the tool result.
Any other file, or input that does not parse, gives no output.
"""

import json
import sys

REMINDER = (
    "REMINDER: You just edited a LaTeX document. Before declaring this task "
    "done, invoke the `stats-research:readable-math` skill via the Skill tool "
    "to review the new mathematics: its notation, scope and glosses, and the "
    "correctness of its proofs and derivations."
)


def main():
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return
    tool_input = payload.get("tool_input") or {}
    file_path = str(tool_input.get("file_path") or "")
    if not file_path.lower().endswith(".tex"):
        return
    json.dump(
        {
            "hookSpecificOutput": {
                "hookEventName": "PostToolUse",
                "additionalContext": REMINDER,
            }
        },
        sys.stdout,
    )


if __name__ == "__main__":
    main()
