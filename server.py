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
import threading
import time
import traceback
import unicodedata
import urllib.parse
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.abspath(__file__))
# On most hosts the container's own filesystem is wiped on every redeploy, which would
# silently delete every user's account and data. COMPTOIR_DB_PATH lets the deploy point
# the database at a persistent volume (e.g. Railway) instead; it falls back to a plain
# local file for development, where that risk doesn't apply.
DB_PATH = os.environ.get("COMPTOIR_DB_PATH") or os.path.join(ROOT, "comptoir.db")
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
        CREATE TABLE IF NOT EXISTS api_keys (
            key TEXT PRIMARY KEY,
            user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            connector_id TEXT NOT NULL,
            label TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
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


# Login has no other brute-force protection (no account lockout, no CAPTCHA), so a bare
# password check would let anyone try passwords for a known email as fast as the network
# allows. This is a simple in-memory sliding-window limiter keyed by email — good enough at
# this stage's traffic; a shared store (e.g. Redis) is the natural upgrade once the app runs
# across multiple processes/instances where in-memory state wouldn't be shared.
LOGIN_ATTEMPTS = {}
LOGIN_LOCK = threading.Lock()
MAX_LOGIN_ATTEMPTS = 8
LOGIN_WINDOW_SECONDS = 300  # 5 minutes


def check_login_rate_limit(email):
    now = time.time()
    with LOGIN_LOCK:
        attempts = [t for t in LOGIN_ATTEMPTS.get(email, []) if now - t < LOGIN_WINDOW_SECONDS]
        LOGIN_ATTEMPTS[email] = attempts
        return len(attempts) < MAX_LOGIN_ATTEMPTS


def record_login_failure(email):
    with LOGIN_LOCK:
        LOGIN_ATTEMPTS.setdefault(email, []).append(time.time())


def clear_login_failures(email):
    with LOGIN_LOCK:
        LOGIN_ATTEMPTS.pop(email, None)


def handle_login(body):
    require_fields(body, ["email", "password"])
    email = body["email"].strip().lower()
    password = body["password"]

    if not check_login_rate_limit(email):
        raise ApiError(429, "Trop de tentatives — réessayez dans quelques minutes.")

    conn = get_db()
    row = conn.execute(
        "SELECT id, email, password_hash, password_salt FROM users WHERE email = ?", (email,)
    ).fetchone()
    conn.close()
    if not row or not verify_password(password, row["password_hash"], row["password_salt"]):
        record_login_failure(email)
        raise ApiError(401, "Email ou mot de passe incorrect.")

    clear_login_failures(email)
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


# Real inbound integration for platforms Comptoir doesn't have a built-in connector for
# (a custom homemade shop, a no-code site whose owner's own backend can call out). The
# user generates an API key from the app; her site's backend calls POST /api/ingest/orders
# with that key whenever an order happens. One global lock serializes the read-modify-write
# on app_state across both this path and PUT /api/state — simple and correct at this stage's
# traffic; sharding per user is the natural upgrade once concurrent writers matter.
STATE_LOCK = threading.Lock()
ORDER_STATUSES = {"livree", "preparation", "retour"}


def handle_create_connector(token, body):
    user = user_from_token(token)
    if not user:
        raise ApiError(401, "Session invalide ou expirée.")
    label = str(body.get("label", "")).strip()
    if not label:
        raise ApiError(400, "Le nom de la plateforme est requis.")
    connector_id = secrets.token_hex(8)
    api_key = "cpt_live_" + secrets.token_hex(24)
    conn = get_db()
    conn.execute(
        "INSERT INTO api_keys (key, user_id, connector_id, label) VALUES (?, ?, ?, ?)",
        (api_key, user["id"], connector_id, label),
    )
    conn.commit()
    conn.close()
    return {"connectorId": connector_id, "apiKey": api_key}


def handle_delete_connector(token, connector_id):
    user = user_from_token(token)
    if not user:
        raise ApiError(401, "Session invalide ou expirée.")
    conn = get_db()
    conn.execute(
        "DELETE FROM api_keys WHERE user_id = ? AND connector_id = ?",
        (user["id"], connector_id),
    )
    conn.commit()
    conn.close()
    return {"ok": True}


# Every external site names its fields differently — one shop's API says "total", another
# says "montant" or "amount". Rather than force every integrator onto one exact schema,
# ingestion recognizes the common aliases (case-insensitive) and picks whichever is present.
FIELD_ALIASES = {
    "amount": ["amount", "total", "totalAmount", "total_amount", "montant", "price", "totalPrice", "total_price", "grandTotal", "grand_total", "total_ttc", "totalTtc"],
    "externalId": ["externalId", "external_id", "id", "orderId", "order_id", "reference", "ref", "orderRef", "order_ref", "orderNumber", "order_number", "number"],
    "date": ["date", "created_at", "createdAt", "order_date", "orderDate", "date_creation", "dateCreation"],
    "status": ["status", "state", "statut", "orderStatus", "order_status"],
    "customerName": ["customerName", "customer_name", "client", "clientName", "client_name", "nom_client", "buyer", "buyerName", "name"],
    "productName": ["productName", "product_name", "product", "article", "item", "itemName", "item_name", "designation"],
    "quantity": ["quantity", "qty", "quantite", "quantité", "nombre", "count", "units"],
}
STATUS_ALIASES = {
    "livree": {"livree", "delivered", "shipped", "completed", "complete", "fulfilled", "paid", "payee", "done"},
    "preparation": {"preparation", "pending", "processing", "en_attente", "created", "new", "confirmed", "awaiting", "open", "en_preparation"},
    "retour": {"retour", "refunded", "returned", "cancelled", "canceled", "annulee", "rembourse", "refund"},
}


def _pick_field(source, aliases):
    """Case-insensitive lookup of the first alias present with a non-empty value."""
    if not isinstance(source, dict):
        return None
    lower_map = {str(k).strip().lower(): v for k, v in source.items()}
    for alias in aliases:
        val = lower_map.get(alias.lower())
        if val not in (None, ""):
            return val
    return None


def _strip_accents(text):
    return "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c))


def _normalize_status(raw):
    """Returns (status, note) — note is set when the input didn't match a known alias
    and we fell back to 'preparation', so the caller can see what happened."""
    if raw in (None, ""):
        return "preparation", None
    # French status words are often accented ("livrée", "préparation") — match
    # regardless, since the aliases below are written unaccented.
    key = _strip_accents(str(raw).strip().lower()).replace("-", "_").replace(" ", "_")
    if key in ORDER_STATUSES:
        return key, None
    for status, aliases in STATUS_ALIASES.items():
        if key in aliases:
            return status, None
    return "preparation", f"Statut « {raw} » non reconnu — mis en « preparation » par défaut."


def _truthy(value):
    return value not in (None, "", False, 0, "0", "false", "no", "non")


def _infer_status_from_signals(body):
    """Many real order payloads don't carry a clean 'status' field at all — they carry
    booleans or timestamps instead (Shopify-style fulfillment_status/cancelled_at, a
    payment webhook's refunded flag...). When no status field is present, infer one from
    whichever of these common signals shows up, cancellation/refund taking priority since
    a shipped-then-cancelled order is a 'retour', not a 'livree'."""
    cancel_keys = ["cancelled", "canceled", "is_cancelled", "is_canceled", "cancelled_at", "canceled_at",
                   "refunded", "is_refunded", "refunded_at", "refund_amount", "refundAmount"]
    if any(_truthy(_pick_field(body, [k])) for k in cancel_keys):
        return "retour"

    financial_status = _pick_field(body, ["financial_status", "financialStatus"])
    if financial_status and str(financial_status).strip().lower() in {"refunded", "partially_refunded", "voided"}:
        return "retour"

    ship_keys = ["delivered", "is_delivered", "delivered_at", "deliveredAt", "shipped", "is_shipped",
                 "shipped_at", "shippedAt", "fulfilled", "is_fulfilled", "fulfilled_at", "fulfilledAt"]
    if any(_truthy(_pick_field(body, [k])) for k in ship_keys):
        return "livree"

    fulfillment_status = _pick_field(body, ["fulfillment_status", "fulfillmentStatus"])
    if fulfillment_status and str(fulfillment_status).strip().lower() in {"fulfilled", "shipped", "delivered"}:
        return "livree"

    return None


def _parse_amount(raw):
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return float(raw)
    s = re.sub(r"[^\d,.\-]", "", str(raw)).strip()
    if not s:
        return None
    if "," in s and "." not in s:
        s = s.replace(",", ".")
    elif "," in s and "." in s:
        s = s.replace(",", "")  # comma read as a thousands separator
    try:
        return float(s)
    except ValueError:
        return None


def handle_ingest_order(api_key, body):
    if not api_key:
        raise ApiError(401, "Clé API manquante.")
    conn = get_db()
    row = conn.execute(
        "SELECT user_id, connector_id FROM api_keys WHERE key = ?", (api_key,)
    ).fetchone()
    if not row:
        conn.close()
        raise ApiError(401, "Clé API invalide ou révoquée.")
    user_id, connector_id = row["user_id"], row["connector_id"]

    if not isinstance(body, dict):
        conn.close()
        raise ApiError(400, "Le corps de la requête doit être un objet JSON.")

    amount = _parse_amount(_pick_field(body, FIELD_ALIASES["amount"]))
    if amount is None:
        conn.close()
        raise ApiError(400, "Montant introuvable — envoyez un champ « amount » (ou total/montant/price...) avec un nombre.")
    if amount < 0:
        conn.close()
        raise ApiError(400, "Le montant ne peut pas être négatif.")

    status_raw = _pick_field(body, FIELD_ALIASES["status"])
    if status_raw not in (None, ""):
        status, status_note = _normalize_status(status_raw)
    else:
        inferred = _infer_status_from_signals(body)
        status, status_note = (inferred, None) if inferred else ("preparation", None)

    external_id_raw = _pick_field(body, FIELD_ALIASES["externalId"])
    external_id = str(external_id_raw).strip() if external_id_raw not in (None, "") else None

    date = _pick_field(body, FIELD_ALIASES["date"])
    if date:
        try:
            datetime.fromisoformat(str(date).replace("Z", "+00:00"))  # validate only; store as given
        except ValueError:
            conn.close()
            raise ApiError(400, "La date fournie doit être au format ISO 8601 (ex. 2026-09-08T10:00:00Z).")
    else:
        date = datetime.now(timezone.utc).isoformat()

    customer_name = _pick_field(body, FIELD_ALIASES["customerName"])
    if not customer_name and isinstance(body.get("customer"), dict):
        customer_name = _pick_field(body["customer"], ["name", "fullName", "full_name", "nom"])
    customer_name = str(customer_name).strip() if customer_name not in (None, "") else "Client"

    product_name = _pick_field(body, FIELD_ALIASES["productName"])
    if not product_name:
        items = body.get("items") or body.get("products") or body.get("lineItems") or body.get("line_items")
        if isinstance(items, list) and items:
            first = items[0]
            if isinstance(first, dict):
                product_name = _pick_field(first, FIELD_ALIASES["productName"] + ["title", "label"])
            elif isinstance(first, str):
                product_name = first
    product_name = str(product_name).strip() if product_name not in (None, "") else None

    quantity_raw = _pick_field(body, FIELD_ALIASES["quantity"])
    if quantity_raw is None and isinstance(body.get("items"), list) and body["items"]:
        first_item = body["items"][0]
        if isinstance(first_item, dict):
            quantity_raw = _pick_field(first_item, FIELD_ALIASES["quantity"])
    quantity = _parse_amount(quantity_raw)
    quantity = int(quantity) if quantity and quantity > 0 else 1

    with STATE_LOCK:
        state_row = conn.execute("SELECT data FROM app_state WHERE user_id = ?", (user_id,)).fetchone()
        if not state_row:
            conn.close()
            raise ApiError(409, "Compte non initialisé — connectez-vous une première fois à l'application avant d'envoyer des commandes.")
        data = json.loads(state_row["data"])
        orders = data.setdefault("orders", [])

        products = data.setdefault("products", [])

        def find_or_create_product(name):
            match = next((p for p in products if p.get("name", "").strip().lower() == name.lower()), None)
            if match:
                return match["id"]
            # Unknown product on a real sale — create it rather than silently losing the
            # link. Stock is never guessed: it starts at 0, flagged for the merchant to
            # fill in for real, same as cost price and supplier.
            new_product = {
                "id": secrets.token_hex(8),
                "name": name,
                "stock": 0,
                "threshold": 10,
                "costPrice": 0,
                "salePrice": None,
                "supplier": "",
                "custom": {},
                "channels": [],
            }
            products.append(new_product)
            return new_product["id"]

        if external_id:
            existing = next((o for o in orders if o.get("externalId") == external_id), None)
            if existing:
                # An order ingested before product auto-creation existed (or before this
                # product had a name Comptoir recognized) can be missing its product link.
                # Re-sending the same order (same externalId) is exactly how a merchant
                # backfills that — fix the link now instead of just reporting "duplicate".
                backfilled = False
                if not existing.get("productId") and product_name:
                    pid = find_or_create_product(product_name)
                    existing["productId"] = pid
                    # This sale was never reflected in stock the first time (no product
                    # was linked yet) — apply it now, same rule as a fresh order.
                    product = next((p for p in products if p["id"] == pid), None)
                    if product is not None:
                        existing_qty = existing.get("quantity") or 1
                        current = product.get("stock", 0) or 0
                        existing_status = existing.get("status")
                        product["stock"] = current + existing_qty if existing_status == "retour" else max(0, current - existing_qty)
                    backfilled = True
                if backfilled:
                    new_data = json.dumps(data)
                    conn.execute(
                        "UPDATE app_state SET data = ?, updated_at = datetime('now') WHERE user_id = ?",
                        (new_data, user_id),
                    )
                    conn.commit()
                conn.close()
                result = {"ok": True, "duplicate": True, "orderId": existing["id"], "orderNumber": existing["orderNumber"]}
                if backfilled:
                    result["backfilled"] = True
                return result

        product_id = None
        if product_name:
            product_id = find_or_create_product(product_name)
            # Stock stays in sync with sales automatically: a real sale takes units out,
            # a return puts them back. Never goes negative — a mismatch (oversold before
            # a restock was recorded) shows up as 0, not a nonsensical negative count.
            product = next((p for p in products if p["id"] == product_id), None)
            if product is not None:
                current = product.get("stock", 0) or 0
                product["stock"] = current + quantity if status == "retour" else max(0, current - quantity)

        next_number = max([o.get("orderNumber", 0) for o in orders], default=1000) + 1
        order = {
            "id": secrets.token_hex(8),
            "orderNumber": next_number,
            "channelType": "custom",
            "connectorId": connector_id,
            "productId": product_id,
            "customer": customer_name,
            "amount": round(amount, 2),
            "status": status,
            "quantity": quantity,
            "date": date,
            "custom": {},
            "externalId": external_id,
        }
        orders.insert(0, order)

        new_data = json.dumps(data)
        if len(new_data) > MAX_STATE_BYTES:
            conn.close()
            raise ApiError(413, "Données trop volumineuses — impossible d'ajouter cette commande.")
        conn.execute(
            "UPDATE app_state SET data = ?, updated_at = datetime('now') WHERE user_id = ?",
            (new_data, user_id),
        )
        conn.commit()
    conn.close()
    result = {"ok": True, "orderId": order["id"], "orderNumber": order["orderNumber"]}
    if status_note:
        result["note"] = status_note
    return result


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=ROOT, **kwargs)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
        self.send_header("Pragma", "no-cache")
        # Baseline hardening headers — cheap, safe defaults with no functional trade-off for
        # this app. A real Content-Security-Policy is deliberately NOT added here: the UI
        # relies on inline style="..." attributes throughout, so a CSP tight enough to matter
        # needs to be worked out and tested against every page, not bolted on in one pass.
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "strict-origin-when-cross-origin")
        self.send_header("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
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

    def _send_server_error(self, e):
        # The exception text itself (stack traces, file paths, library internals) is never
        # sent to the client — only logged server-side. An attacker probing the API for a
        # 500 shouldn't learn anything about how it's built from the response body.
        traceback.print_exc(file=sys.stderr)
        self._send_json(500, {"error": "Erreur serveur — réessayez dans un instant."})

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
            if path == "/api/connectors/custom":
                return self._send_json(200, handle_create_connector(self._bearer_token(), body))
            if path == "/api/ingest/orders":
                return self._send_json(200, handle_ingest_order(self._bearer_token(), body))
            raise ApiError(404, "Route inconnue.")
        except ApiError as e:
            self._send_json(e.status, {"error": e.message})
        except Exception as e:  # pragma: no cover
            self._send_server_error(e)

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
            self._send_server_error(e)

    def do_DELETE(self):
        path = urllib.parse.urlparse(self.path).path
        match = re.match(r"^/api/connectors/([^/]+)$", path)
        if not match:
            self.send_error(404)
            return
        try:
            return self._send_json(200, handle_delete_connector(self._bearer_token(), match.group(1)))
        except ApiError as e:
            self._send_json(e.status, {"error": e.message})
        except Exception as e:  # pragma: no cover
            self._send_server_error(e)

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
