"""
server.py — Lightweight HTTP server and REST API for git-diff.
No external dependencies — pure Python stdlib only.
"""
import json
import os
import threading
import webbrowser
import time
import socket
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from pathlib import Path

from .git_data import (
    collect_all_data,
    get_commit_diff,
    get_commit_detail,
    get_commit_history,
    get_staged_diff,
    get_unstaged_diff,
    get_range_diff,
    get_stash_diff,
    get_file_content,
    get_file_log,
    get_file_blame,
    get_commit_stats_by_day,
    get_language_stats,
    parse_diff,
    run_git,
)

TEMPLATE_PATH = Path(__file__).parent / "templates" / "index.html"


class GitDiffHandler(BaseHTTPRequestHandler):
    """HTTP handler serving the git-diff web UI and JSON API."""

    repo_root: str = None
    initial_data: dict = None

    def log_message(self, fmt, *args):
        pass  # silent

    def send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(body)

    def send_html(self, html: str):
        body = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        params = parse_qs(parsed.query)

        def p(key, default=""):
            vals = params.get(key)
            return vals[0] if vals else default

        def pi(key, default=0):
            try:
                return int(p(key, str(default)))
            except ValueError:
                return default

        try:
            self._route(path, p, pi)
        except Exception as e:
            self.send_json({"error": str(e)}, 500)

    def _route(self, path, p, pi):
        root = self.repo_root

        # ── Serve the SPA ──────────────────────────────────────────────
        if path in ("/", "/index.html"):
            html = TEMPLATE_PATH.read_text(encoding="utf-8")
            self.send_html(html)
            return

        # ── Initial bundle ─────────────────────────────────────────────
        if path == "/api/data":
            self.send_json(self.initial_data)
            return

        # ── Commit detail + diff ───────────────────────────────────────
        if path == "/api/commit":
            h = p("hash")
            if not h:
                self.send_json({"error": "Missing ?hash="}, 400)
                return
            ctx = pi("context", 3)
            diff = get_commit_diff(h, root, context=ctx)
            detail = get_commit_detail(h, root)
            self.send_json({"diff": diff, "detail": detail})
            return

        # ── Paginated commit history ───────────────────────────────────
        if path == "/api/commits":
            branch = p("branch", "HEAD")
            limit = pi("limit", 100)
            offset = pi("offset", 0)
            author = p("author") or None
            search = p("search") or None
            commits = get_commit_history(root, limit=limit + offset, branch=branch,
                                         author=author, search=search)
            self.send_json({"commits": commits[offset:offset + limit], "total": len(commits)})
            return

        # ── Range diff: branch-to-branch or SHA-to-SHA ────────────────
        if path == "/api/range-diff":
            base = p("base")
            compare = p("compare")
            ctx = pi("context", 3)
            if not base or not compare:
                self.send_json({"error": "Missing ?base= or ?compare="}, 400)
                return
            diff = get_range_diff(root, base, compare, context=ctx)
            # Also get commits in range
            commits_raw = run_git(
                ["log", "--format=%H|%h|%s|%an|%ar", f"{base}..{compare}"],
                cwd=root,
            )
            range_commits = []
            for line in commits_raw.splitlines():
                pts = line.split("|", 4)
                if len(pts) == 5:
                    range_commits.append({
                        "hash": pts[0], "short_hash": pts[1],
                        "subject": pts[2], "author": pts[3], "relative": pts[4],
                    })
            self.send_json({"diff": diff, "commits": range_commits, "base": base, "compare": compare})
            return

        # ── Staged diff ───────────────────────────────────────────────
        if path == "/api/staged":
            ctx = pi("context", 3)
            self.send_json(get_staged_diff(root, context=ctx))
            return

        # ── Unstaged diff ─────────────────────────────────────────────
        if path == "/api/unstaged":
            ctx = pi("context", 3)
            self.send_json(get_unstaged_diff(root, context=ctx))
            return

        # ── Stash diff ────────────────────────────────────────────────
        if path == "/api/stash":
            ref = p("ref", "stash@{0}")
            ctx = pi("context", 3)
            self.send_json({"diff": get_stash_diff(root, ref, context=ctx)})
            return

        # ── File content at ref ───────────────────────────────────────
        if path == "/api/file":
            fp = p("path")
            ref = p("ref", "HEAD")
            if not fp:
                self.send_json({"error": "Missing ?path="}, 400)
                return
            self.send_json(get_file_content(root, fp, ref))
            return

        # ── File commit history ───────────────────────────────────────
        if path == "/api/file-log":
            fp = p("path")
            limit = pi("limit", 50)
            if not fp:
                self.send_json({"error": "Missing ?path="}, 400)
                return
            self.send_json({"commits": get_file_log(root, fp, limit=limit)})
            return

        # ── File blame ────────────────────────────────────────────────
        if path == "/api/blame":
            fp = p("path")
            ref = p("ref", "HEAD")
            if not fp:
                self.send_json({"error": "Missing ?path="}, 400)
                return
            self.send_json({"blame": get_file_blame(root, fp, ref)})
            return

        # ── Commit activity chart ─────────────────────────────────────
        if path == "/api/activity":
            days = pi("days", 90)
            self.send_json({"data": get_commit_stats_by_day(root, days=days)})
            return

        # ── Language stats ────────────────────────────────────────────
        if path == "/api/langs":
            self.send_json({"data": get_language_stats(root)})
            return

        # ── Full refresh ──────────────────────────────────────────────
        if path == "/api/refresh":
            data = collect_all_data(root)
            GitDiffHandler.initial_data = data
            self.send_json({"status": "ok", "timestamp": int(time.time())})
            return

        # ── Raw git command (safe read-only subset) ───────────────────
        if path == "/api/git":
            cmd = p("cmd")
            SAFE = {"log", "show", "diff", "blame", "ls-tree", "ls-files",
                    "rev-list", "rev-parse", "shortlog", "for-each-ref",
                    "stash", "tag", "branch", "remote", "status", "describe"}
            args = cmd.split()
            if not args or args[0] not in SAFE:
                self.send_json({"error": "Command not allowed"}, 403)
                return
            out = run_git(args, cwd=root)
            self.send_json({"output": out})
            return

        self.send_json({"error": "Not found"}, 404)


# ---------------------------------------------------------------------------
# Server lifecycle
# ---------------------------------------------------------------------------

def find_free_port(start=7433, end=7500):
    for port in range(start, end):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    return start


def start_server(repo_root: str, data: dict, port: int = None, no_browser: bool = False, host: str = "127.0.0.1"):
    port = port or find_free_port()

    GitDiffHandler.repo_root = repo_root
    GitDiffHandler.initial_data = data

    server = HTTPServer((host, port), GitDiffHandler)
    url = f"http://{host}:{port}"

    print(f"\n  🌐  Server  →  {url}")
    print(f"  📁  Repo    →  {repo_root}")
    print(f"\n  Press Ctrl+C to stop\n")

    if not no_browser:
        def _open():
            time.sleep(0.6)
            webbrowser.open(url)
        threading.Thread(target=_open, daemon=True).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  👋  git-diff stopped. Have a good one!\n")
    finally:
        server.server_close()
