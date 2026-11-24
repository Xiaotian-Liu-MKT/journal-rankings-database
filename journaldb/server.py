"""Loopback-only, read-only web UI and JSON API, with no runtime dependencies."""
import csv
import io
import json
import sqlite3
import socket
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from . import ROOT, DEFAULT_DB
from .query import connect, decode, detail, meta, search, selection


def serve(database=DEFAULT_DB, port=8765, open_browser=False):
    # Fail before opening the server if the database is absent.
    probe = connect(database)
    try:
        probe.execute("SELECT count(*) FROM catalogue").fetchone()
        built_at = probe.execute("SELECT value FROM metadata WHERE key='built_at'").fetchone()[0]
    finally:
        probe.close()
    def reopen_existing():
        if not open_browser:
            return False
        from urllib.request import urlopen
        try:
            with urlopen(f"http://127.0.0.1:{port}/api/meta", timeout=2) as response:
                existing = json.load(response)
            if existing.get("built_at") == built_at and "sources" in existing:
                import webbrowser
                webbrowser.open(f"http://127.0.0.1:{port}")
                print(f"已打开现有期刊查询：http://127.0.0.1:{port}", flush=True)
                return True
        except (OSError, ValueError):
            pass
        return False
    if reopen_existing():
        return
    class Handler(BaseHTTPRequestHandler):
        def respond(self, status, body, mime="application/json; charset=utf-8", attachment=None):
            if isinstance(body, (dict, list)):
                body = json.dumps(body, ensure_ascii=False, allow_nan=False).encode("utf-8")
            elif isinstance(body, str):
                body = body.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Cache-Control", "no-store")
            if attachment:
                self.send_header("Content-Disposition", 'attachment; filename="' + attachment + '"')
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            parsed = urlparse(self.path)
            params = {key: values[-1] for key, values in parse_qs(parsed.query).items()}
            if parsed.path in ("/", "/index.html"):
                self.respond(200, (ROOT / "web" / "index.html").read_bytes(), "text/html; charset=utf-8")
                return
            if parsed.path in ("/static-client.js", "/i18n.js", "/app.js", "/journal-title.js", "/metric-info.js", "/help-popover.js"):
                self.respond(200, (ROOT / "web" / parsed.path[1:]).read_bytes(), "application/javascript; charset=utf-8")
                return
            if parsed.path in ("/help.css", "/detail.css"):
                self.respond(200, (ROOT / "web" / parsed.path[1:]).read_bytes(), "text/css; charset=utf-8")
                return
            if parsed.path in ("/brand/panda-throne.png", "/brand/panda-emperor.png"):
                self.respond(200, (ROOT / "web" / parsed.path.lstrip("/")).read_bytes(), "image/png")
                return
            if parsed.path == "/favicon.ico":
                self.respond(204, b"", "image/x-icon")
                return
            con = connect(database)
            try:
                if parsed.path == "/api/journals":
                    self.respond(200, search(con, **params))
                elif parsed.path.startswith("/api/journals/"):
                    result = detail(con, parsed.path.removeprefix("/api/journals/"))
                    self.respond(200 if result else 404, result or {"error": "未找到此期刊"})
                elif parsed.path == "/api/meta":
                    self.respond(200, meta(con))
                elif parsed.path == "/api/export.csv":
                    from .classifications import taxonomy_definition
                    nodes = {node["id"]: node for node in taxonomy_definition()["nodes"]}
                    where, values, order_sql = selection(params)
                    rows = con.execute("SELECT c.* FROM catalogue c" + where + order_sql, values)
                    stream = io.StringIO(newline="")
                    writer = None
                    for row in rows:
                        obj = decode(row)
                        obj.pop("search_text", None)
                        paths = obj.pop("taxonomy_paths", [])
                        obj["classification"] = "; ".join(" > ".join(nodes[node_id]["label_en"] for node_id in (path["broad_id"], path["subcategory_id"]) if node_id) for path in paths)
                        flat = {k: "; ".join(map(str, v)) if isinstance(v, list) else v for k, v in obj.items()}
                        # Avoid spreadsheet formula execution when source text begins with an operator.
                        flat = {k: "'" + v if isinstance(v, str) and v.startswith(("=", "+", "-", "@")) else v for k, v in flat.items()}
                        if writer is None:
                            writer = csv.DictWriter(stream, fieldnames=list(flat))
                            writer.writeheader()
                        writer.writerow(flat)
                    if writer is None:
                        stream.write("journal_id,title\r\n")
                    self.respond(200, "\ufeff" + stream.getvalue(), "text/csv; charset=utf-8", "journals.csv")
                else:
                    self.respond(404, {"error": "接口不存在"})
            except (ValueError, TypeError) as exc:
                self.respond(400, {"error": str(exc)})
            except sqlite3.Error:
                self.respond(500, {"error": "数据库查询失败"})
            finally:
                con.close()

        def log_message(self, fmt, *args):
            pass

    class LocalHTTPServer(ThreadingHTTPServer):
        allow_reuse_address = False

        def server_bind(self):
            if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
                self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            super().server_bind()
    try:
        server = LocalHTTPServer(("127.0.0.1", port), Handler)
    except OSError:
        if reopen_existing():
            return
        raise
    url = f"http://127.0.0.1:{server.server_port}"
    print(f"期刊数据库：{url}  （Ctrl+C 停止）", flush=True)
    if open_browser:
        import webbrowser
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
