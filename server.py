#!/usr/bin/env python3
"""Lattice Vault local web UI v2 — read-only list + search. Python stdlib only.

Usage: VAULT_DB=path/vault.db python3 server.py [--db PATH] [--port 8765]
Binds 127.0.0.1 only. Opens the DB read-only (sqlite URI mode=ro) per request.
Visual prototype (v2); does not touch lattice-vault-ui (v1).
"""
import argparse, json, os, sqlite3, sys
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs, quote

HERE = os.path.dirname(os.path.abspath(__file__))
_parent = os.path.dirname(HERE)
_default_src = next(
    (p for p in (
        os.path.join(_parent, "lattice-vault"),
        os.path.join(_parent, "lattice-vault-release"),
    ) if os.path.isfile(os.path.join(p, "vault.py"))),
    os.path.join(_parent, "lattice-vault"),
)
VAULT_SRC = os.environ.get("VAULT_SRC", _default_src)
sys.path.insert(0, VAULT_SRC)
import vault  # noqa: E402  (reused: search(); do NOT call vault.connect() — opens RW)

STATIC = os.path.join(HERE, "static")
STATUSES = ("proposed", "active", "rejected", "reverted")
TRUSTS = ("verified", "agent", "unverified")
MAX_LIMIT = 200


def open_ro(path):
    if not os.path.exists(path):
        raise FileNotFoundError(path)
    db = sqlite3.connect(
        f"file:{quote(os.path.abspath(path))}?mode=ro",
        uri=True,
        check_same_thread=False,
    )
    db.row_factory = sqlite3.Row
    return db


def short_text(payload_json, n=120):
    try:
        p = json.loads(payload_json)
    except ValueError:
        return ""
    if p.get("redacted") is True:
        return "[redacted]"
    parts = []

    def walk(o):
        if isinstance(o, dict):
            if "$enc" in o:
                parts.append("[encrypted]")
                return
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
        elif o is not None:
            parts.append(str(o))

    walk(p)
    s = " · ".join(parts)
    return s if len(s) <= n else s[: n - 1] + "…"


def list_events(db, status=None, trust=None, limit=50, offset=0):
    sql = (
        "SELECT e.seq, e.id, e.type, e.ts, e.subject, e.actor, e.trust, "
        "s.status, s.trust_eff, e.payload "
        "FROM events e LEFT JOIN proj_status s ON s.event_id = e.id WHERE 1=1"
    )
    args = []
    if status:
        sql += " AND s.status = ?"
        args.append(status)
    if trust:
        sql += " AND COALESCE(s.trust_eff, e.trust) = ?"
        args.append(trust)
    total = db.execute(f"SELECT count(*) FROM ({sql})", args).fetchone()[0]
    sql += " ORDER BY e.hlc DESC, e.id DESC LIMIT ? OFFSET ?"
    args += [limit, offset]
    items = []
    for r in db.execute(sql, args):
        items.append({
            "id": r["id"],
            "seq": r["seq"],
            "type": r["type"],
            "ts": r["ts"],
            "source": r["actor"] or "",
            "subject": r["subject"],
            "status": r["status"],
            "trust": r["trust_eff"] or r["trust"],
            "text_short": short_text(r["payload"]),
        })
    return {"total": total, "limit": limit, "offset": offset, "items": items}


def search_events(db, q, limit=20):
    res = vault.search(db, q, limit=limit)
    return {
        "q": q,
        "results": [
            {
                "id": r["id"],
                "type": r["type"],
                "subject": r["subject"],
                "trust": r["trust"],
                "status": r["status"],
                "snippet": r["snip"],
                "score": r["score"],
            }
            for r in res
        ],
    }


def _int(qs, k, d, lo, hi):
    try:
        return max(lo, min(hi, int(qs.get(k, [d])[0])))
    except ValueError:
        return d


class Handler(BaseHTTPRequestHandler):
    db_path = None

    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        data = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; connect-src 'self'")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        u = urlparse(self.path)
        qs = parse_qs(u.query)
        try:
            if u.path in ("/", "/index.html"):
                return self._static("index.html", "text/html; charset=utf-8")
            if u.path == "/styles.css":
                return self._static("styles.css", "text/css; charset=utf-8")
            if u.path == "/app.js":
                return self._static("app.js", "text/javascript; charset=utf-8")
            if u.path == "/api/events":
                status = qs.get("status", [None])[0] or None
                trust = qs.get("trust", [None])[0] or None
                if status and status not in STATUSES:
                    return self._send(400, {"error": f"status must be one of {STATUSES}"})
                if trust and trust not in TRUSTS:
                    return self._send(400, {"error": f"trust must be one of {TRUSTS}"})
                with open_ro(self.db_path) as db:
                    return self._send(
                        200,
                        list_events(
                            db,
                            status,
                            trust,
                            _int(qs, "limit", 50, 1, MAX_LIMIT),
                            _int(qs, "offset", 0, 0, 10**9),
                        ),
                    )
            if u.path == "/api/search":
                q = qs.get("q", [""])[0][:200]
                with open_ro(self.db_path) as db:
                    return self._send(200, search_events(db, q, _int(qs, "limit", 20, 1, 100)))
            if u.path.startswith("/api/"):
                return self._send(404, {"error": "not found"})
            return self._send(404, b"not found", "text/plain")
        except sqlite3.Error as e:
            return self._send(500, {"error": f"database error: {e}"})

    def do_POST(self):
        # Read-only prototype; approve is human-only (CLI, step 2)
        self._send(405, {"error": "read-only prototype"})

    def _static(self, name, ctype):
        with open(os.path.join(STATIC, name), "rb") as f:
            self._send(200, f.read(), ctype)

    def log_message(self, fmt, *a):
        sys.stderr.write("%s\n" % (fmt % a))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=os.environ.get("VAULT_DB", "./vault.db"))
    ap.add_argument("--port", type=int, default=8765)
    a = ap.parse_args(argv)
    open_ro(a.db).close()
    Handler.db_path = a.db
    srv = ThreadingHTTPServer(("127.0.0.1", a.port), Handler)
    print(
        f"Lattice Vault UI v2 (read-only) on http://127.0.0.1:{a.port}/  db={a.db}",
        flush=True,
    )
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
