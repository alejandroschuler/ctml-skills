#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = ["requests>=2.28", "websocket-client>=1.6"]
# ///
"""Read the review comments and tracked changes on an Overleaf project.

Overleaf keeps comments and tracked changes outside the project files, so the
git bridge never carries them. This script reads them through the same
channels the Overleaf editor uses, with a login session saved on this machine.

    uv run overleaf_comments.py login            # once; opens a browser window
    uv run overleaf_comments.py read [PROJECT]   # open comments, as Markdown
    uv run overleaf_comments.py read PROJECT --include-resolved --changes --json
    uv run overleaf_comments.py status           # is the saved session valid?
    uv run overleaf_comments.py logout           # end the session and delete it

PROJECT is an editor URL (https://www.overleaf.com/project/<id>), a git bridge
URL (https://git.overleaf.com/<id>), a bare project id, or a directory whose
git remote is the git bridge. Without PROJECT, the script tries the current
directory and then ./paper.

Exit codes: 0 success, 1 unexpected failure, 2 bad arguments, 3 no valid login
session (run `login`), 4 this account cannot open the project.

The session lasts while it is used at least once every five days. It lives in
~/.config/overleaf-comments/ (or $OVERLEAF_COMMENTS_HOME), readable only by
you, and holds cookies for the Overleaf host and nothing else.

The script only reads. It never edits a file, posts a reply, or resolves a
thread. It uses Overleaf's private web API, which can change without notice.
"""

from __future__ import annotations

import argparse
import fnmatch
import getpass
import json
import os
import re
import shutil
import subprocess
import sys
import time
from bisect import bisect_left, bisect_right
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

try:
    import requests
    import websocket  # the websocket-client package
except ImportError:
    sys.exit(
        "overleaf_comments.py needs the packages requests and websocket-client.\n"
        "Run it with `uv run overleaf_comments.py ...`, which installs them."
    )

__version__ = "0.1.0"

DEFAULT_BASE_URL = "https://www.overleaf.com"
USER_AGENT = (
    f"overleaf-comments/{__version__} "
    "(+https://github.com/alejandroschuler/ctml-skills)"
)
PROJECT_ID = re.compile(r"[0-9a-f]{24}")
TIMEOUT = 30  # seconds, for each network call

EXIT_ERROR, EXIT_USAGE, EXIT_AUTH, EXIT_ACCESS = 1, 2, 3, 4


class ToolError(Exception):
    exit_code = EXIT_ERROR


class UsageError(ToolError):
    exit_code = EXIT_USAGE


class AuthError(ToolError):
    exit_code = EXIT_AUTH


class AccessError(ToolError):
    exit_code = EXIT_ACCESS


def script_command() -> str:
    return f"uv run {sys.argv[0]}"


def auth_error(detail: str) -> AuthError:
    return AuthError(
        f"{detail}\nLog in with:\n    {script_command()} login\n"
        "A browser window opens at the Overleaf login page. The session is "
        "saved when the login finishes."
    )


# ---------------------------------------------------------------------------
# The saved session
# ---------------------------------------------------------------------------


def home_dir() -> Path:
    if os.environ.get("OVERLEAF_COMMENTS_HOME"):
        return Path(os.environ["OVERLEAF_COMMENTS_HOME"]).expanduser()
    config = os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config"
    return Path(config) / "overleaf-comments"


def session_path(base_url: str) -> Path:
    return home_dir() / f"session-{urlparse(base_url).netloc}.json"


def profile_path() -> Path:
    return home_dir() / "browser-profile"


def private_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    os.chmod(path, 0o700)
    return path


def host_of(base_url: str) -> str:
    return urlparse(base_url).hostname or ""


def domain_matches(host: str, domain: str) -> bool:
    domain = domain.lstrip(".").lower()
    return host == domain or host.endswith("." + domain)


def new_http() -> requests.Session:
    http = requests.Session()
    http.headers["User-Agent"] = USER_AGENT
    return http


def add_cookie(http: requests.Session, cookie: dict) -> None:
    http.cookies.set(
        cookie["name"],
        cookie["value"],
        domain=cookie["domain"],
        path=cookie.get("path") or "/",
        secure=bool(cookie.get("secure")),
        expires=cookie.get("expires"),
        rest={"HttpOnly": None} if cookie.get("httpOnly") else {},
    )


def load_session(base_url: str) -> requests.Session:
    path = session_path(base_url)
    if not path.exists():
        raise auth_error(f"No saved Overleaf session for {base_url}.")
    try:
        saved = json.loads(path.read_text())
    except (OSError, ValueError) as err:
        raise auth_error(f"The saved session in {path} cannot be read ({err}).")
    http = new_http()
    for cookie in saved.get("cookies", []):
        add_cookie(http, cookie)
    return http


def save_session(http: requests.Session, base_url: str) -> None:
    """Write the Overleaf cookies, with their refreshed expiry, to a private file."""
    host = host_of(base_url)
    cookies = [
        {
            "name": c.name,
            "value": c.value,
            "domain": c.domain,
            "path": c.path,
            "secure": bool(c.secure),
            "expires": c.expires,
            "httpOnly": c.has_nonstandard_attr("HttpOnly"),
        }
        for c in http.cookies
        # GCLB only routes one real-time connection to one server.
        if domain_matches(host, c.domain) and c.name != "GCLB"
    ]
    path = session_path(base_url)
    private_dir(path.parent)
    tmp = path.with_name(path.name + ".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as fh:
        json.dump({"base_url": base_url, "cookies": cookies}, fh, indent=1)
    os.replace(tmp, path)


def session_expiry(http: requests.Session, base_url: str) -> datetime | None:
    host = host_of(base_url)
    expiries = [
        c.expires
        for c in http.cookies
        if domain_matches(host, c.domain)
        and c.expires
        and re.search(r"sess|sid", c.name, re.I)
    ]
    if not expiries:
        return None
    return datetime.fromtimestamp(min(expiries), tz=timezone.utc)


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------


def get_json(http: requests.Session, url: str, what: str):
    try:
        resp = http.get(
            url,
            headers={"Accept": "application/json"},
            allow_redirects=False,
            timeout=TIMEOUT,
        )
    except requests.RequestException as err:
        raise ToolError(f"Could not reach Overleaf for {what}: {err}")
    location = resp.headers.get("Location", "")
    if resp.status_code == 401 or (resp.is_redirect and "/login" in location):
        raise auth_error("The Overleaf session is missing or has expired.")
    if resp.status_code in (403, 404):
        raise AccessError(
            f"Overleaf answered {resp.status_code} for {what}. This account "
            "cannot open the project, or the project does not exist."
        )
    if resp.status_code != 200:
        raise ToolError(f"Overleaf answered {resp.status_code} for {what}.")
    try:
        return resp.json()
    except ValueError:
        raise ToolError(
            f"Overleaf sent {resp.headers.get('Content-Type')} instead of JSON "
            f"for {what}. Its private API may have changed."
        )


def whoami(http: requests.Session, base_url: str) -> dict:
    return get_json(http, f"{base_url}/user/personal_info", "the account details")


def user_label(user: dict | None, fallback: str = "unknown user") -> str:
    if not user:
        return fallback
    name = " ".join(
        part for part in (user.get("first_name"), user.get("last_name")) if part
    ).strip()
    return name or user.get("email") or fallback


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------

BROWSERS = {
    "darwin": [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
        "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
        "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
    ],
    "win32": [
        r"%ProgramFiles%\Google\Chrome\Application\chrome.exe",
        r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe",
        r"%LocalAppData%\Google\Chrome\Application\chrome.exe",
        r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe",
    ],
    "linux": [
        "google-chrome",
        "google-chrome-stable",
        "chromium",
        "chromium-browser",
        "microsoft-edge",
        "brave-browser",
    ],
}


def find_browser(explicit: str | None) -> str:
    candidates = [explicit] if explicit else BROWSERS.get(sys.platform, BROWSERS["linux"])
    for candidate in candidates:
        path = os.path.expandvars(candidate)
        if os.path.isabs(path) and os.path.exists(path):
            return path
        if not os.path.isabs(path) and shutil.which(path):
            return shutil.which(path)
    if explicit:
        raise UsageError(f"No browser at {explicit}.")
    raise ToolError(
        "No Chrome, Chromium, Edge or Brave browser found. Pass --browser PATH, "
        "or use `login --cookie`."
    )


class DevTools:
    """Just enough of the Chrome DevTools protocol to read the browser's cookies."""

    def __init__(self, ws_url: str):
        # Chrome refuses DevTools connections that carry an Origin header.
        self.ws = websocket.create_connection(ws_url, suppress_origin=True, timeout=10)
        self.last_id = 0

    def call(self, method: str, **params) -> dict:
        self.last_id += 1
        self.ws.send(json.dumps({"id": self.last_id, "method": method, "params": params}))
        while True:
            reply = json.loads(self.ws.recv())
            if reply.get("id") == self.last_id:
                if "error" in reply:
                    raise ToolError(f"The browser refused {method}: {reply['error']}")
                return reply.get("result", {})

    def close(self) -> None:
        try:
            self.ws.close()
        except Exception:
            pass


def login_with_browser(base_url: str, browser: str | None, timeout: int) -> dict:
    """Open a browser window with its own profile, wait for the user to log in,
    then keep that session's Overleaf cookies."""
    executable = find_browser(browser)
    profile = private_dir(profile_path())
    port_file = profile / "DevToolsActivePort"
    port_file.unlink(missing_ok=True)
    proc = subprocess.Popen(
        [
            executable,
            f"--user-data-dir={profile}",
            "--remote-debugging-port=0",
            "--no-first-run",
            "--no-default-browser-check",
            f"{base_url}/login",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    devtools = None
    try:
        started = time.time()
        while not port_file.exists():
            if proc.poll() is not None:
                raise ToolError(
                    "The browser quit before it was ready. If a login window "
                    "from an earlier run is still open, close it and try again."
                )
            if time.time() - started > 30:
                raise ToolError("The browser did not open its DevTools port.")
            time.sleep(0.2)
        time.sleep(0.2)  # the port file can appear before it is written
        port, ws_path = port_file.read_text().split()[:2]
        devtools = DevTools(f"ws://127.0.0.1:{port}{ws_path}")
        print(
            "A browser window is open at the Overleaf login page. Log in there.\n"
            "The window closes by itself when the login is done.",
            file=sys.stderr,
            flush=True,
        )
        host = host_of(base_url)
        last_seen, last_check = None, 0.0
        while time.time() - started < timeout:
            if proc.poll() is not None:
                raise AuthError("The login window was closed before the login finished.")
            try:
                cookies = devtools.call("Storage.getCookies")["cookies"]
            except (websocket.WebSocketException, OSError):
                time.sleep(1)
                continue
            ours = [c for c in cookies if domain_matches(host, c["domain"])]
            session_cookies = [c for c in ours if re.search(r"sess|sid", c["name"], re.I)]
            fingerprint = sorted((c["name"], c["value"]) for c in session_cookies or ours)
            # Overleaf issues a new session cookie at login, so a changed
            # cookie is the signal to check. The timed check is a fallback.
            if ours and (fingerprint != last_seen or time.time() - last_check > 15):
                last_seen, last_check = fingerprint, time.time()
                http = new_http()
                for c in ours:
                    add_cookie(
                        http,
                        {
                            **c,
                            "expires": None if c.get("session") else int(c["expires"]),
                        },
                    )
                try:
                    user = whoami(http, base_url)
                except AuthError:
                    pass  # not logged in yet
                else:
                    save_session(http, base_url)
                    return user
            time.sleep(2)
        raise AuthError(f"No login within {timeout} seconds.")
    finally:
        if devtools is not None:
            try:
                devtools.call("Browser.close")
            except Exception:
                pass
            devtools.close()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.terminate()


def login_with_cookie(base_url: str) -> dict:
    """Take a session cookie that the user copies from their own browser."""
    prompt = (
        "Paste the value of the Overleaf session cookie (overleaf_session2 on "
        "overleaf.com), or a whole Cookie header, then press Enter: "
    )
    raw = getpass.getpass(prompt) if sys.stdin.isatty() else sys.stdin.read()
    raw = raw.strip()
    if raw.lower().startswith("cookie:"):
        raw = raw[len("cookie:"):].strip()
    if not raw:
        raise UsageError("No cookie was given.")
    pairs = [part.strip() for part in raw.split(";") if part.strip()]
    if len(pairs) == 1 and "=" not in pairs[0]:
        pairs = [f"overleaf_session2={pairs[0]}"]
    http = new_http()
    for pair in pairs:
        name, _, value = pair.partition("=")
        add_cookie(http, {"name": name.strip(), "value": value.strip(), "domain": host_of(base_url), "secure": True})
    try:
        user = whoami(http, base_url)
    except AuthError:
        raise AuthError("Overleaf did not accept that cookie. Copy it again from a logged-in browser tab.")
    save_session(http, base_url)
    return user


# ---------------------------------------------------------------------------
# The real-time connection
# ---------------------------------------------------------------------------

PACKET = re.compile(r"^(\d):(\d*)(\+?):([^:]*):?(.*)$", re.S)
ACK = re.compile(r"^(\d+)\+?(.*)$", re.S)


def split_frames(raw: str) -> list[str]:
    """socket.io 0.9 can pack several packets into one frame, each one written
    as U+FFFD, its length, U+FFFD, then the packet."""
    if not raw.startswith("\ufffd"):
        return [raw]
    frames, i = [], 0
    while i < len(raw) and raw[i] == "\ufffd":
        j = raw.index("\ufffd", i + 1)
        n = int(raw[i + 1 : j])
        frames.append(raw[j + 1 : j + 1 + n])
        i = j + 1 + n
    return frames


class RealTime:
    """A minimal socket.io 0.9 client for Overleaf's real-time service: it joins
    one project and reads its documents, the way the editor does on load. It
    never sends an edit."""

    def __init__(self, http: requests.Session, base_url: str, project_id: str):
        stamp = str(int(time.time() * 1000))
        try:
            resp = http.get(
                f"{base_url}/socket.io/1/",
                params={"projectId": project_id, "t": stamp},
                timeout=TIMEOUT,
            )
        except requests.RequestException as err:
            raise ToolError(f"Could not reach Overleaf's real-time service: {err}")
        sid = resp.text.split(":", 1)[0]
        if resp.status_code != 200 or not re.fullmatch(r"[\w-]+", sid):
            raise ToolError(
                f"Overleaf's real-time handshake failed (HTTP {resp.status_code})."
            )
        parsed = urlparse(base_url)
        scheme = "wss" if parsed.scheme == "https" else "ws"
        url = (
            f"{scheme}://{parsed.netloc}/socket.io/1/websocket/{sid}"
            f"?projectId={project_id}&t={stamp}"
        )
        # The handshake sets a load-balancer cookie (GCLB) that must go with
        # the websocket, so that both reach the same server.
        cookie = "; ".join(
            f"{c.name}={c.value}"
            for c in http.cookies
            if domain_matches(parsed.hostname or "", c.domain)
        )
        try:
            self.ws = websocket.create_connection(
                url,
                header=[f"User-Agent: {USER_AGENT}"],
                cookie=cookie,
                origin=f"{parsed.scheme}://{parsed.netloc}",
                timeout=TIMEOUT,
            )
        except (websocket.WebSocketException, OSError) as err:
            raise ToolError(f"Could not open the real-time connection: {err}")
        self.last_ack = 0
        self.permissions, self.project = self._await_project()

    def _packets(self):
        """Yield ("event", name, args) and ("ack", id, args) from the next frame."""
        try:
            raw = self.ws.recv()
        except websocket.WebSocketTimeoutException:
            raise ToolError("Overleaf's real-time service stopped answering.")
        except (websocket.WebSocketException, OSError) as err:
            raise ToolError(f"The real-time connection failed: {err}")
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        for frame in split_frames(raw):
            match = PACKET.match(frame)
            if not match:
                continue
            kind, _, _, _, data = match.groups()
            if kind == "2":  # heartbeat
                self.ws.send("2::")
            elif kind == "0":
                raise ToolError("Overleaf closed the real-time connection.")
            elif kind == "7":
                raise ToolError(f"Overleaf's real-time service reported an error: {data}")
            elif kind == "5":
                try:
                    event = json.loads(data)
                except ValueError:
                    continue
                yield "event", event.get("name"), event.get("args") or []
            elif kind == "6":
                ack = ACK.match(data)
                if ack:
                    try:
                        yield "ack", int(ack.group(1)), json.loads(ack.group(2) or "[]")
                    except ValueError:
                        raise ToolError("Overleaf sent a reply that is not JSON. Its protocol may have changed.")

    def _check_rejection(self, name, args) -> None:
        if name == "connectionRejected":
            message = (args[0] or {}).get("message") if args else None
            if message == "invalid session":
                raise auth_error("Overleaf rejected the saved session.")
            if message == "not authorized":
                raise AccessError("This account cannot open the project.")
            raise ToolError(f"Overleaf refused the connection: {message}")
        if name in ("forceDisconnect", "reconnectGracefully"):
            raise ToolError("Overleaf asked the connection to close. Try again in a minute.")

    def _await_project(self):
        started = time.time()
        while time.time() - started < TIMEOUT:
            for kind, name, args in self._packets():
                if kind != "event":
                    continue
                self._check_rejection(name, args)
                if name == "joinProjectResponse":
                    body = args[0] if args else {}
                    return body.get("permissionsLevel"), body.get("project") or {}
        raise ToolError("Overleaf did not open the project in time.")

    def join_docs(self, doc_ids: list[str], window: int = 8) -> dict:
        """Join each document and return {doc_id: (lines, ranges, ot_type)}, or
        {doc_id: error message} for a document Overleaf would not open."""
        results, pending, queue = {}, {}, list(doc_ids)
        while queue or pending:
            while queue and len(pending) < window:
                doc_id = queue.pop(0)
                self.last_ack += 1
                pending[self.last_ack] = doc_id
                options = {"encodeRanges": True, "supportsHistoryOT": True}
                event = json.dumps({"name": "joinDoc", "args": [doc_id, options]})
                self.ws.send(f"5:{self.last_ack}+::{event}")
            for kind, key, args in self._packets():
                if kind == "event":
                    self._check_rejection(key, args)
                elif kind == "ack" and key in pending:
                    doc_id = pending.pop(key)
                    args = list(args) + [None] * 7
                    error, lines, _version, _ops, ranges, ot_type = args[:6]
                    if error:
                        results[doc_id] = str(error.get("message", error) if isinstance(error, dict) else error)
                    else:
                        results[doc_id] = (lines, ranges or {}, ot_type or "sharejs-text-ot")
        return results

    def close(self) -> None:
        try:
            self.ws.send("0::")
            self.ws.close()
        except Exception:
            pass


def walk_docs(folder: dict, prefix: str = ""):
    for doc in folder.get("docs") or []:
        yield prefix + doc["name"], doc["_id"]
    for child in folder.get("folders") or []:
        yield from walk_docs(child, prefix + child["name"] + "/")


# ---------------------------------------------------------------------------
# Positions
# ---------------------------------------------------------------------------


def unpack_utf8(text: str) -> str:
    """Undo the editor channel's packing, which sends UTF-8 bytes as latin-1 characters."""
    try:
        return text.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return text


class Utf16:
    """Overleaf counts positions in UTF-16 code units, as JavaScript does.
    Python counts code points, and the two differ after any character outside
    the Basic Multilingual Plane, such as a math letter like U+1D53C."""

    def __init__(self, text: str):
        self.text = text
        self.astral = [i for i, ch in enumerate(text) if ord(ch) > 0xFFFF]

    def index(self, units: int) -> int:
        if not self.astral:
            return min(units, len(self.text))
        lo, hi = 0, len(self.text)
        while lo < hi:
            mid = (lo + hi) // 2
            if mid + bisect_left(self.astral, mid) < units:
                lo = mid + 1
            else:
                hi = mid
        return lo


class Visible:
    """Map positions in a history-OT document, which still holds the text of
    tracked deletions, to positions in the text that the editor shows."""

    def __init__(self, raw: str, deletes: list[tuple[int, int]]):
        self.deletes = sorted(deletes)
        pieces, cursor = [], 0
        for start, end in self.deletes:
            pieces.append(raw[cursor:start])
            cursor = max(cursor, end)
        pieces.append(raw[cursor:])
        self.text = "".join(pieces)

    def index(self, pos: int) -> int:
        removed = 0
        for start, end in self.deletes:
            if pos <= start:
                break
            removed += min(pos, end) - start
        return pos - removed


def read_doc(lines, ranges: dict, ot_type: str):
    """Return the visible text, its comments and its tracked changes, with every
    position given as a Python index into the visible text."""
    comments, changes = [], []
    if ot_type == "history-ot":
        raw = lines.get("content", "") if isinstance(lines, dict) else ""
        units = Utf16(raw)

        def span(rng):
            start = units.index(rng["pos"])
            return start, units.index(rng["pos"] + rng["length"])

        tracked = (lines or {}).get("trackedChanges") or []
        visible = Visible(
            raw, [span(tc["range"]) for tc in tracked if tc["tracking"]["type"] == "delete"]
        )
        for comment in (lines or {}).get("comments") or []:
            spans = [span(rng) for rng in comment.get("ranges") or []]
            if not spans:
                continue  # commented text was deleted; the thread is reported as detached
            start = visible.index(spans[0][0])
            end = visible.index(spans[0][1])
            quoted = " … ".join(visible.text[visible.index(a) : visible.index(b)] for a, b in spans)
            comments.append(
                {"thread_id": comment["id"], "start": start, "end": end, "text": quoted,
                 "resolved": bool(comment.get("resolved"))}
            )
        for tc in tracked:
            start, end = span(tc["range"])
            tracking = tc["tracking"]
            changes.append(
                {"type": tracking["type"], "start": visible.index(start), "text": raw[start:end],
                 "user_id": tracking.get("userId"), "timestamp": tracking.get("ts")}
            )
        return visible.text, comments, changes

    text = "\n".join(unpack_utf8(line) for line in lines or [])
    units = Utf16(text)
    for comment in ranges.get("comments") or []:
        op = comment.get("op") or {}
        quoted = unpack_utf8(op.get("c") or "")
        start = units.index(op.get("p", 0))
        comments.append(
            {"thread_id": op.get("t") or comment.get("id"), "start": start,
             "end": start + len(quoted), "text": quoted, "resolved": False}
        )
    for change in ranges.get("changes") or []:
        op = change.get("op") or {}
        meta = change.get("metadata") or {}
        kind = "insert" if "i" in op else "delete"
        changes.append(
            {"type": kind, "start": units.index(op.get("p", 0)),
             "text": unpack_utf8(op.get("i") if kind == "insert" else op.get("d") or ""),
             "user_id": meta.get("user_id"), "timestamp": meta.get("ts")}
        )
    return text, comments, changes


class Lines:
    def __init__(self, text: str):
        self.text = text
        self.starts = [0] + [m.end() for m in re.finditer("\n", text)]

    def line(self, pos: int) -> int:
        return bisect_right(self.starts, pos)

    def column(self, pos: int) -> int:
        return pos - self.starts[self.line(pos) - 1] + 1

    def snippet(self, start: int, end: int, width: int = 100) -> str:
        """The highlighted text in ⟦ ⟧, with up to `width` characters of its
        line on each side."""
        line_start = self.text.rfind("\n", 0, start) + 1
        line_end = self.text.find("\n", end)
        line_end = len(self.text) if line_end == -1 else line_end
        left = max(line_start, start - width)
        right = min(line_end, end + width)
        return (
            ("…" if left > line_start else "")
            + self.text[left:start]
            + "⟦" + self.text[start:end] + "⟧"
            + self.text[end:right]
            + ("…" if right < line_end else "")
        )


# ---------------------------------------------------------------------------
# The report
# ---------------------------------------------------------------------------


def to_datetime(value) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value / 1000, tz=timezone.utc)
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def iso(value) -> str | None:
    moment = to_datetime(value)
    return moment.isoformat().replace("+00:00", "Z") if moment else None


def local(value) -> str:
    moment = to_datetime(value)
    return moment.astimezone().strftime("%Y-%m-%d %H:%M %Z") if moment else "unknown time"


def local_copy_state(clone: str, path: str, text: str) -> str:
    """Whether the clone's copy of a file has the text that Overleaf has now."""
    try:
        local = (Path(clone) / path).read_text(encoding="utf-8", errors="replace")
    except FileNotFoundError:
        return "missing"
    except OSError:
        return "unreadable"
    same = local.replace("\r\n", "\n").rstrip("\n") == text.rstrip("\n")
    return "same" if same else "differs"


def build_report(base_url, project_id, project, permissions, reader, docs, joined, threads, args, clone=None):
    users = {}
    for member in [project.get("owner") or {}] + list(project.get("members") or []):
        if member.get("_id"):
            users[member["_id"]] = user_label(member, member["_id"])
    for thread in threads.values():
        for message in thread.get("messages") or []:
            if message.get("user"):
                users[message["user_id"]] = user_label(message["user"])
    users[reader.get("id")] = user_label(reader)

    def thread_view(thread_id, comment_resolved=False):
        thread = threads.get(thread_id) or {}
        resolved = bool(thread.get("resolved")) or comment_resolved
        view = {
            "thread_id": thread_id,
            "status": "resolved" if resolved else "open",
            "messages": [
                {
                    "author": user_label(m.get("user"), users.get(m.get("user_id"), "unknown user")),
                    "email": (m.get("user") or {}).get("email"),
                    "user_id": m.get("user_id"),
                    "timestamp": iso(m.get("timestamp")),
                    "edited_at": iso(m.get("edited_at")),
                    "content": m.get("content", ""),
                }
                for m in thread.get("messages") or []
            ],
        }
        if resolved:
            # History-OT documents can hold the resolved state on the comment
            # itself, with no record of who resolved it or when.
            by = thread.get("resolved_by_user") or users.get(thread.get("resolved_by_user_id"))
            view["resolved_by"] = user_label(by) if isinstance(by, dict) else by
            view["resolved_at"] = iso(thread.get("resolved_at"))
        return view

    files, failed, anchored = [], [], set()
    counts = {"open": 0, "resolved": 0, "changes": 0, "detached_open": 0, "detached_resolved": 0}
    for path, doc_id in docs:
        result = joined.get(doc_id)
        if not isinstance(result, tuple):
            failed.append({"path": path, "doc_id": doc_id, "error": result or "no answer"})
            continue
        text, comments, changes = read_doc(*result)
        lines = Lines(text)
        entry = {"path": path, "doc_id": doc_id, "ot_type": result[2], "comments": [], "changes": []}
        for comment in sorted(comments, key=lambda c: c["start"]):
            anchored.add(comment["thread_id"])
            view = thread_view(comment["thread_id"], comment["resolved"])
            counts[view["status"]] += 1
            if view["status"] == "resolved" and not args.include_resolved:
                continue
            start, end = comment["start"], comment["end"]
            entry["comments"].append(
                {
                    **view,
                    "line": lines.line(start),
                    "column": lines.column(start),
                    "end_line": lines.line(max(start, end - 1)),
                    "text": comment["text"],
                    "context": lines.snippet(start, end),
                }
            )
        for change in sorted(changes, key=lambda c: c["start"]):
            counts["changes"] += 1
            if args.changes:
                entry["changes"].append(
                    {
                        "type": change["type"],
                        "line": lines.line(change["start"]),
                        "column": lines.column(change["start"]),
                        "text": change["text"],
                        "author": users.get(change["user_id"], change["user_id"] or "unknown user"),
                        "user_id": change["user_id"],
                        "timestamp": iso(change["timestamp"]),
                    }
                )
        if entry["comments"] or entry["changes"]:
            if clone:
                entry["local_copy"] = local_copy_state(clone, path, text)
            files.append(entry)

    # A thread with no anchor had its text deleted, or lives in a file that was
    # skipped. Only report them when every file was read.
    detached = []
    if not args.file and not failed:
        for thread_id in sorted(set(threads) - anchored):
            view = thread_view(thread_id)
            counts["detached_" + view["status"]] += 1
            if view["status"] == "open" or args.include_resolved:
                detached.append(view)

    restricted = permissions == "readOnly" and not project.get("members") and not (project.get("owner") or {}).get("email")
    return {
        "project": {"id": project_id, "name": project.get("name"), "url": f"{base_url}/project/{project_id}"},
        "clone": os.path.relpath(clone) if clone else None,
        "read_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "reader": {"name": user_label(reader), "email": reader.get("email"), "permissions": permissions},
        "restricted_access": restricted,
        "counts": counts,
        "shown": {"resolved": bool(args.include_resolved), "changes": bool(args.changes), "files": args.file or None},
        "files": files,
        "detached_threads": detached,
        "unreadable_files": failed,
    }


def indent(text: str, prefix: str) -> str:
    return text.replace("\n", "\n" + prefix)


def clip(text: str, limit: int = 300) -> str:
    return text if len(text) <= limit else text[:limit] + f"… [{len(text) - limit} more characters]"


def render_messages(out: list[str], view: dict) -> None:
    if not view["messages"]:
        out.append("(This thread has no messages.)")
    for n, message in enumerate(view["messages"], 1):
        edited = " (edited)" if message["edited_at"] else ""
        out.append(
            f"{n}. {message['author']}, {local(message['timestamp'])}{edited}: "
            + indent(message["content"], "   ")
        )
    if view["status"] == "resolved":
        who = f" by {view['resolved_by']}" if view.get("resolved_by") else ""
        when = f", {local(view['resolved_at'])}" if view.get("resolved_at") else ""
        out.append(f"\nResolved{who}{when}.")


def render_markdown(report: dict) -> str:
    counts, shown = report["counts"], report["shown"]
    out = [f"# Overleaf comments: {report['project']['name']}", ""]
    out.append(
        f"Project {report['project']['url']}, read {local(report['read_at'])} "
        f"as {report['reader']['name']} ({report['reader']['permissions']})."
    )
    if report.get("clone"):
        out.append(f"The local clone is {report['clone']}/, and the paths below are relative to it.")
    if shown["files"]:
        out.append(f"Only files matching {', '.join(shown['files'])}.")
    summary = [f"{counts['open']} open comment threads."]
    if counts["resolved"]:
        summary.append(
            f"{counts['resolved']} resolved threads"
            + (" are marked below." if shown["resolved"] else " are not shown (pass --include-resolved).")
        )
    if counts["changes"]:
        summary.append(
            f"{counts['changes']} tracked changes"
            + (" are listed below." if shown["changes"] else " are not shown (pass --changes).")
        )
    out += ["", " ".join(summary)]
    if report["restricted_access"]:
        out += ["", "This account opens the project through a read-only link, and Overleaf hides comments from such links."]

    for entry in report["files"]:
        out += ["", f"## {entry['path']}"]
        local_path = os.path.join(report.get("clone") or ".", entry["path"])
        if entry.get("local_copy") == "differs":
            out += ["", f"The local copy, {local_path}, differs from Overleaf. Pull before editing, "
                    "and find each place by its commented text."]
        elif entry.get("local_copy") == "missing":
            out += ["", f"There is no local copy at {local_path}. Pull before editing."]
        for comment in entry["comments"]:
            where = f"{entry['path']}:{comment['line']}"
            if comment["end_line"] != comment["line"]:
                where += f"-{comment['end_line']}"
            out += ["", f"### {where} ({comment['status']})", "", "```text", comment["context"], "```", ""]
            render_messages(out, comment)
        if entry["changes"]:
            out += ["", f"### Tracked changes in {entry['path']}", ""]
            for change in entry["changes"]:
                kind = "Insertion" if change["type"] == "insert" else "Deletion"
                out.append(
                    f"- {entry['path']}:{change['line']} {kind} by {change['author']}, "
                    f"{local(change['timestamp'])}: {json.dumps(clip(change['text']), ensure_ascii=False)}"
                )
    if report["detached_threads"]:
        out += ["", "## Threads whose commented text was deleted"]
        for view in report["detached_threads"]:
            out += ["", f"### Thread {view['thread_id']} ({view['status']})", ""]
            render_messages(out, view)
    if report["unreadable_files"]:
        out += ["", "## Files that could not be read", ""]
        for item in report["unreadable_files"]:
            out.append(f"- {item['path']}: {item['error']}")
    if not report["files"] and not report["detached_threads"]:
        out += ["", "No comments to show."]
    return "\n".join(out) + "\n"


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


def project_from_git(directory: str) -> tuple[str, str] | None:
    """The Overleaf project id and the top directory of the git clone at `directory`."""
    git = ["git", "-C", directory]
    try:
        top = subprocess.run(git + ["rev-parse", "--show-toplevel"], capture_output=True, text=True, timeout=10)
        remotes = subprocess.run(git + ["remote", "-v"], capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    for line in remotes.stdout.splitlines():
        # Print nothing from the remote URL: it can hold a git bridge token.
        match = re.search(r"[/:]([0-9a-f]{24})(?:\.git)?/?\s", line + " ")
        if match and top.returncode == 0:
            return match.group(1), top.stdout.strip()
    return None


def find_clone(project_id: str) -> str | None:
    for directory in (".", "paper"):
        found = project_from_git(directory) if os.path.isdir(directory) else None
        if found and found[0] == project_id:
            return found[1]
    return None


def resolve_project(arg: str | None) -> tuple[str, str | None]:
    """The project id, and the local clone of it here, if there is one."""
    if arg:
        match = re.search(r"/project/([0-9a-f]{24})", arg) or re.search(
            r"git\.[^/]+/([0-9a-f]{24})", arg
        )
        if match:
            return match.group(1), find_clone(match.group(1))
        if PROJECT_ID.fullmatch(arg):
            return arg, find_clone(arg)
        if os.path.isdir(arg):
            found = project_from_git(arg)
            if found:
                return found
            raise UsageError(f"{arg} is a directory, and none of its git remotes is an Overleaf project.")
        raise UsageError(f"{arg} is not an Overleaf project URL, project id, or directory.")
    for directory in (".", "paper"):
        found = project_from_git(directory) if os.path.isdir(directory) else None
        if found:
            return found
    raise UsageError(
        "Give the project as an Overleaf URL or id, or run from a clone of it "
        "(or from a directory that holds the clone as paper/)."
    )


def cmd_read(args) -> int:
    project_id, clone = resolve_project(args.project)
    http = load_session(args.base_url)
    try:
        reader = whoami(http, args.base_url)
        threads = get_json(http, f"{args.base_url}/project/{project_id}/threads", "the comment threads")
        realtime = RealTime(http, args.base_url, project_id)
        try:
            root = (realtime.project.get("rootFolder") or [{}])[0]
            docs = sorted(walk_docs(root))
            if args.file:
                docs = [d for d in docs if any(fnmatch.fnmatch(d[0], pat) for pat in args.file)]
            joined = realtime.join_docs([doc_id for _, doc_id in docs])
        finally:
            realtime.close()
    finally:
        try:
            save_session(http, args.base_url)  # keeps the refreshed expiry
        except OSError:
            pass
    report = build_report(
        args.base_url, project_id, realtime.project, realtime.permissions,
        reader, docs, joined, threads, args, clone,
    )
    if args.json:
        json.dump(report, sys.stdout, indent=2, ensure_ascii=False)
        sys.stdout.write("\n")
    else:
        sys.stdout.write(render_markdown(report))
    return 0


def cmd_login(args) -> int:
    if args.cookie:
        user = login_with_cookie(args.base_url)
    else:
        user = login_with_browser(args.base_url, args.browser, args.timeout)
    print(f"Logged in to {args.base_url} as {user_label(user)} <{user.get('email')}>. "
          f"The session is saved in {session_path(args.base_url)}.")
    return 0


def cmd_status(args) -> int:
    http = load_session(args.base_url)
    user = whoami(http, args.base_url)
    save_session(http, args.base_url)
    expiry = session_expiry(http, args.base_url)
    until = f" It expires {local(expiry.timestamp() * 1000)} unless it is used again." if expiry else ""
    print(f"Logged in to {args.base_url} as {user_label(user)} <{user.get('email')}>.{until}")
    return 0


def cmd_logout(args) -> int:
    path = session_path(args.base_url)
    if path.exists():
        http = load_session(args.base_url)
        try:
            token = http.get(f"{args.base_url}/dev/csrf", timeout=TIMEOUT).text.strip()
            resp = http.post(
                f"{args.base_url}/logout",
                data={"_csrf": token},
                headers={"X-CSRF-Token": token, "Accept": "application/json"},
                allow_redirects=False,
                timeout=TIMEOUT,
            )
            ended = resp.status_code in (200, 302)
        except requests.RequestException:
            ended = False
        if not ended:
            print(
                "Could not end the session on Overleaf. It expires after five idle "
                "days, or you can end it in Overleaf's Account Settings, Sessions.",
                file=sys.stderr,
            )
        path.unlink()
        print(f"Deleted {path}.")
    else:
        print("No saved session.")
    if args.forget_browser and profile_path().exists():
        shutil.rmtree(profile_path())
        print(f"Deleted the login browser profile in {profile_path()}.")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="overleaf_comments.py",
        description="Read the review comments and tracked changes on an Overleaf project.",
    )
    parser.add_argument(
        "--base-url",
        default=os.environ.get("OVERLEAF_URL", DEFAULT_BASE_URL).rstrip("/"),
        help="Overleaf server (default: $OVERLEAF_URL or %(default)s)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    read = sub.add_parser("read", help="print the comments on a project")
    read.add_argument("project", nargs="?", help="editor URL, git URL, project id, or clone directory")
    read.add_argument("--include-resolved", action="store_true", help="also show resolved threads")
    read.add_argument("--changes", action="store_true", help="also list tracked changes")
    read.add_argument("--file", action="append", metavar="GLOB", help="only files whose path matches GLOB (repeatable)")
    read.add_argument("--json", action="store_true", help="print JSON instead of Markdown")
    read.set_defaults(handler=cmd_read)

    login = sub.add_parser("login", help="log in through a browser window, once")
    login.add_argument("--cookie", action="store_true", help="paste a session cookie instead of opening a browser")
    login.add_argument("--browser", help="path to a Chrome, Chromium, Edge or Brave executable")
    login.add_argument("--timeout", type=int, default=600, help="seconds to wait for the login (default %(default)s)")
    login.set_defaults(handler=cmd_login)

    status = sub.add_parser("status", help="check that the saved session still works")
    status.set_defaults(handler=cmd_status)

    logout = sub.add_parser("logout", help="end the saved session and delete it")
    logout.add_argument("--forget-browser", action="store_true", help="also delete the login browser profile")
    logout.set_defaults(handler=cmd_logout)

    args = parser.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    try:
        return args.handler(args)
    except ToolError as err:
        print(f"overleaf_comments.py: {err}", file=sys.stderr)
        return err.exit_code
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
