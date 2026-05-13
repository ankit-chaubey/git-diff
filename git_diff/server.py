"""server.py -- HTTP server and REST API for git-diff. Pure stdlib."""
import json
import os
import shlex
import threading
import webbrowser
import time
import socket
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from pathlib import Path

from .git_data import (
    collect_all_data,
    collect_lazy_data,
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
    get_untracked_content,
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

        if path in ("/", "/index.html"):
            html = TEMPLATE_PATH.read_text(encoding="utf-8")
            self.send_html(html)
            return

        if path == "/api/data":
            self.send_json(self.initial_data)
            return

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

        if path == "/api/commits":
            branch = p("branch", "HEAD")
            limit = pi("limit", 100)
            offset = pi("offset", 0)
            author = p("author") or None
            search = p("search") or None
            filepath = p("path") or None
            commits = get_commit_history(root, limit=limit, offset=offset, branch=branch,
                                         author=author, search=search, path_filter=filepath)
            total_raw = run_git(["rev-list", "--count", branch], cwd=root).strip()
            total = int(total_raw) if total_raw.isdigit() else len(commits) + offset
            self.send_json({"commits": commits, "total": total})
            return

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
                ["log", "--format=%H%x1f%h%x1f%s%x1f%an%x1f%ar", f"{base}..{compare}"],
                cwd=root,
            )
            range_commits = []
            for line in commits_raw.splitlines():
                pts = line.split("\x1f", 4)
                if len(pts) == 5:
                    range_commits.append({
                        "hash": pts[0], "short_hash": pts[1],
                        "subject": pts[2], "author": pts[3], "relative": pts[4],
                    })
            self.send_json({"diff": diff, "commits": range_commits, "base": base, "compare": compare})
            return

        if path == "/api/staged":
            ctx = pi("context", 3)
            self.send_json(get_staged_diff(root, context=ctx))
            return

        if path == "/api/unstaged":
            ctx = pi("context", 3)
            self.send_json(get_unstaged_diff(root, context=ctx))
            return

        if path == "/api/stash":
            ref = p("ref", "stash@{0}")
            ctx = pi("context", 3)
            self.send_json({"diff": get_stash_diff(root, ref, context=ctx)})
            return

        if path == "/api/file":
            fp = p("path")
            ref = p("ref", "HEAD")
            if not fp:
                self.send_json({"error": "Missing ?path="}, 400)
                return
            self.send_json(get_file_content(root, fp, ref))
            return

        if path == "/api/file-log":
            fp = p("path")
            limit = pi("limit", 50)
            if not fp:
                self.send_json({"error": "Missing ?path="}, 400)
                return
            self.send_json({"commits": get_file_log(root, fp, limit=limit)})
            return

        if path == "/api/blame":
            fp = p("path")
            ref = p("ref", "HEAD")
            if not fp:
                self.send_json({"error": "Missing ?path="}, 400)
                return
            self.send_json({"blame": get_file_blame(root, fp, ref)})
            return

        if path == "/api/activity":
            days = pi("days", 90)
            self.send_json({"data": get_commit_stats_by_day(root, days=days)})
            return

        if path == "/api/langs":
            self.send_json({"data": get_language_stats(root)})
            return

        if path == "/api/lazy-data":
            data = collect_lazy_data(root)
            # Merge into stored initial data so /api/data stays consistent
            if GitDiffHandler.initial_data:
                GitDiffHandler.initial_data.update(data)
                GitDiffHandler.initial_data["repo"].update({
                    "contributors": data["contributors"],
                    "size": data["size"],
                    "git_size": data["git_size"],
                    "size_bytes": data["size_bytes"],
                })
            self.send_json(data)
            return

        if path == "/api/untracked":
            fp = p("path")
            if not fp:
                self.send_json({"error": "Missing ?path="}, 400)
                return
            self.send_json({"diff": get_untracked_content(root, fp)})
            return

        if path == "/api/refresh":
            data = collect_all_data(root)
            GitDiffHandler.initial_data = data
            self.send_json({"status": "ok", "timestamp": int(time.time())})
            return

        if path == "/api/git":
            cmd = p("cmd")
            SAFE = {"log", "show", "diff", "blame", "ls-tree", "ls-files",
                    "rev-list", "rev-parse", "shortlog", "for-each-ref",
                    "stash", "tag", "branch", "remote", "status", "describe"}
            try:
                args = shlex.split(cmd)
            except ValueError as exc:
                self.send_json({"error": f"Invalid command syntax: {exc}"}, 400)
                return
            if not args or args[0] not in SAFE:
                self.send_json({"error": "Command not allowed"}, 403)
                return
            out = run_git(args, cwd=root)
            self.send_json({"output": out})
            return

        self.send_json({"error": "Not found"}, 404)

# Server lifecycle

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

    server = ThreadingHTTPServer((host, port), GitDiffHandler)
    url = f"http://{host}:{port}"

    import socket as _socket
    try:
        lan_ip = _socket.gethostbyname(_socket.gethostname())
    except Exception:
        lan_ip = host
    print(f"\n  Server  ->  {url}")
    if host == "0.0.0.0":
        print(f"  LAN     ->  http://{lan_ip}:{port}")
    print(f"  Repo    ->  {repo_root}")
    print(f"\n  Press Ctrl+C to stop\n")

    if not no_browser:
        def _open():
            time.sleep(0.6)
            webbrowser.open(url)
        threading.Thread(target=_open, daemon=True).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  git-diff stopped. Have a good one!\n")
    finally:
        server.server_close()
