#!/usr/bin/env python3
"""
Comptoir — real backend for account creation and login.
Standard library only: no packages to install.

- SQLite database on disk (comptoir.db) — real, durable storage.
- Passwords hashed with PBKDF2-HMAC-SHA256 (100k iterations) + per-user random salt.
- Session tokens are cryptographically random (secrets.token_hex), stored server-side.
- Serves the static frontend (index.html, app.js, styles.css) from the same process,
  so the app and its API share one origin — no CORS needed.
"""
from __future__ import annotations

import hashlib
import http.server
import json
import os
import re
import secrets
import sqlite3
import sys
import urllib.parse

ROOT = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(ROOT, "comptoir.db")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PBKDF2_ITERATIONS = 100_000
SESSION_TTL_DAYS = 30


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            password_salt TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS sessions (
            token TEXT PRIMARY KEY,
            user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS app_state (
            user_id TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
            data TEXT NOT NULL,
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
    """)
    conn.commit()
    conn.close()


def hash_password(password: str, salt_hex: str | None = None):
    salt = bytes.fromhex(salt_hex) if salt_hex else secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return digest.hex(), salt.hex()


def verify_password(password: str, stored_hash_hex: str, salt_hex: str) -> bool:
    candidate_hash, _ = hash_password(password, salt_hex)
    return secrets.compare_digest(candidate_hash, stored_hash_hex)


class ApiError(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status
        self.message = message


def require_fields(body, fields):
    for f in fields:
        if not body.get(f) or not str(body.get(f)).strip():
            raise ApiError(400, f"Le champ « {f} » est requis.")


def create_session(user_id: str) -> str:
    token = secrets.token_hex(32)
    conn = get_db()
    conn.execute("INSERT INTO sessions (token, user_id) VALUES (?, ?)", (token, user_id))
    conn.commit()
    conn.close()
    return token


def user_from_token(token: str):
    if not token:
        return None
    conn = get_db()
    row = conn.execute(
        """SELECT u.id, u.email FROM sessions s
           JOIN users u ON u.id = s.user_id
           WHERE s.token = ? AND s.created_at >= datetime('now', ?)""",
        (token, f"-{SESSION_TTL_DAYS} days"),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def handle_signup(body):
    require_fields(body, ["email", "password"])
    email = body["email"].strip().lower()
    password = body["password"]
    if not EMAIL_RE.match(email):
        raise ApiError(400, "Adresse email invalide.")
    if len(password) < 8:
        raise ApiError(400, "Le mot de passe doit contenir au moins 8 caractères.")

    conn = get_db()
    existing = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
    if existing:
        conn.close()
        raise ApiError(409, "Un compte existe déjà avec cet email.")

    user_id = secrets.token_hex(12)
    pw_hash, pw_salt = hash_password(password)
    conn.execute(
        "INSERT INTO users (id, email, password_hash, password_salt) VALUES (?, ?, ?, ?)",
        (user_id, email, pw_hash, pw_salt),
    )
    conn.commit()
    conn.close()
    token = create_session(user_id)
    return {"token": token, "email": email}


def handle_login(body):
    require_fields(body, ["email", "password"])
    email = body["email"].strip().lower()
    password = body["password"]

    conn = get_db()
    row = conn.execute(
        "SELECT id, email, password_hash, password_salt FROM users WHERE email = ?", (email,)
    ).fetchone()
    conn.close()
    if not row or not verify_password(password, row["password_hash"], row["password_salt"]):
        raise ApiError(401, "Email ou mot de passe incorrect.")

    token = create_session(row["id"])
    return {"token": token, "email": row["email"]}


def handle_logout(token):
    if token:
        conn = get_db()
        conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
        conn.commit()
        conn.close()
    return {"ok": True}


def handle_me(token):
    user = user_from_token(token)
    if not user:
        raise ApiError(401, "Session invalide ou expirée.")
    return user


# Comptoir's business data (products, orders, stock, SAV, connectors...) is stored as one
# JSON document per user, rather than fully normalized tables. This is a deliberate
# trade-off for an early-stage product: it gives every user their own real, isolated,
# durable data — the part that matters for testing with real people — without the much
# larger project of designing and migrating a full relational schema up front. That
# normalization is the natural next step once the product needs cross-user querying
# (e.g. the admin/monitoring view from the technical plan) rather than per-user storage.
MAX_STATE_BYTES = 2_000_000  # 2 MB — generous for this app's data, cheap to guard.


def handle_get_state(token):
    user = user_from_token(token)
    if not user:
        raise ApiError(401, "Session invalide ou expirée.")
    conn = get_db()
    row = conn.execute("SELECT data FROM app_state WHERE user_id = ?", (user["id"],)).fetchone()
    conn.close()
    return {"data": row["data"] if row else None}


def handle_put_state(token, body):
    user = user_from_token(token)
    if not user:
        raise ApiError(401, "Session invalide ou expirée.")
    if "data" not in body or not isinstance(body["data"], str):
        raise ApiError(400, "Le champ « data » (JSON sérialisé en texte) est requis.")
    if len(body["data"]) > MAX_STATE_BYTES:
        raise ApiError(413, "Données trop volumineuses.")
    try:
        json.loads(body["data"])  # must itself be valid JSON
    except json.JSONDecodeError:
        raise ApiError(400, "Le champ « data » doit être du JSON valide.")
    conn = get_db()
    conn.execute(
        """INSERT INTO app_state (user_id, data, updated_at) VALUES (?, ?, datetime('now'))
           ON CONFLICT(user_id) DO UPDATE SET data = excluded.data, updated_at = excluded.updated_at""",
        (user["id"], body["data"]),
    )
    conn.commit()
    conn.close()
    return {"ok": True}


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=ROOT, **kwargs)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
        self.send_header("Pragma", "no-cache")
        super().end_headers()

    def _bearer_token(self):
        auth = self.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            return auth[7:].strip()
        return None

    def _send_json(self, status, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json_body(self):
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return {}
        raw = self.rfile.read(length)
        try:
            return json.loads(raw or b"{}")
        except json.JSONDecodeError:
            raise ApiError(400, "Corps de requête JSON invalide.")

    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path
        if not path.startswith("/api/"):
            self.send_error(404)
            return
        try:
            body = self._read_json_body()
            if path == "/api/signup":
                return self._send_json(200, handle_signup(body))
            if path == "/api/login":
                return self._send_json(200, handle_login(body))
            if path == "/api/logout":
                return self._send_json(200, handle_logout(self._bearer_token()))
            raise ApiError(404, "Route inconnue.")
        except ApiError as e:
            self._send_json(e.status, {"error": e.message})
        except Exception as e:  # pragma: no cover
            self._send_json(500, {"error": f"Erreur serveur : {e}"})

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        if path == "/api/me":
            try:
                return self._send_json(200, handle_me(self._bearer_token()))
            except ApiError as e:
                return self._send_json(e.status, {"error": e.message})
        if path == "/api/state":
            try:
                return self._send_json(200, handle_get_state(self._bearer_token()))
            except ApiError as e:
                return self._send_json(e.status, {"error": e.message})
        return super().do_GET()

    def do_PUT(self):
        path = urllib.parse.urlparse(self.path).path
        if path != "/api/state":
            self.send_error(404)
            return
        try:
            body = self._read_json_body()
            return self._send_json(200, handle_put_state(self._bearer_token(), body))
        except ApiError as e:
            self._send_json(e.status, {"error": e.message})
        except Exception as e:  # pragma: no cover
            self._send_json(500, {"error": f"Erreur serveur : {e}"})

    def log_message(self, fmt, *args):
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))


def main():
    # Hosting platforms (Railway, Render, Fly.io...) assign a port via $PORT.
    # A CLI argument still wins locally, e.g. `python3 server.py 8082`.
    if len(sys.argv) > 1:
        port = int(sys.argv[1])
    else:
        port = int(os.environ.get("PORT", 8082))
    init_db()
    server = http.server.ThreadingHTTPServer(("", port), Handler)
    print(f"Comptoir server running on port {port}  (db: {DB_PATH})")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()


if __name__ == "__main__":
    main()
