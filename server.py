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

import base64
import gzip
import hashlib
import hmac
import html
import http.server
import json
import os
import re
import secrets
import sqlite3
import sys
import tempfile
import threading
import time
import traceback
from collections import deque
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.abspath(__file__))
# On most hosts the container's own filesystem is wiped on every redeploy, which would
# silently delete every user's account and data. COMPTOIR_DB_PATH lets the deploy point
# the database at a persistent volume (e.g. Railway) instead; it falls back to a plain
# local file for development, where that risk doesn't apply.
DB_PATH = os.environ.get("COMPTOIR_DB_PATH") or os.path.join(ROOT, "comptoir.db")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PBKDF2_ITERATIONS = 100_000
SESSION_TTL_DAYS = 30

# Free first month: Stripe runs a trial of TRIAL_DAYS on the first subscription of an account
# (card collected up front, charged only when the trial ends). 0 switches the offer off.
TRIAL_DAYS = int(os.environ.get("TRIAL_DAYS") or 30)

# Pre-launch gate: new sign-ups are refused until LAUNCH_AT (existing accounts keep logging
# in). Set LAUNCH_AT (ISO 8601) on the host to move the date; SIGNUP_ALLOWLIST (comma-
# separated emails) lets specific people create an account early, e.g. for a demo or test.
LAUNCH_AT_RAW = os.environ.get("LAUNCH_AT") or "2026-09-28T09:00:00+02:00"
SIGNUP_ALLOWLIST = {e.strip().lower() for e in (os.environ.get("SIGNUP_ALLOWLIST") or "").split(",") if e.strip()}


def _launch_at():
    try:
        d = datetime.fromisoformat(LAUNCH_AT_RAW.replace("Z", "+00:00"))
    except ValueError:
        return datetime(2000, 1, 1, tzinfo=timezone.utc)  # a broken value must never lock everyone out
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def launch_is_open():
    return datetime.now(timezone.utc) >= _launch_at()


def handle_launch():
    return {"launchAt": _launch_at().astimezone(timezone.utc).isoformat(), "serverNow": datetime.now(timezone.utc).isoformat(), "open": launch_is_open(), "trialDays": TRIAL_DAYS}
PASSWORD_RESET_TTL_MINUTES = 60
# Where reset links point. Kept as an explicit env var rather than trusting the request's
# Host header (which can be spoofed or, behind a proxy, wrong) — same reasoning as
# COMPTOIR_DB_PATH above.
PUBLIC_BASE_URL = (os.environ.get("PUBLIC_BASE_URL") or "https://getcomptoir.fr").rstrip("/")
# Real outbound email goes through Brevo's HTTP API rather than SMTP: Railway's outbound
# network drops both port 587 and 465 (confirmed live — STARTTLS and implicit-TLS attempts
# both hung until timeout, after ruling out IPv6 routing and credentials as the cause), a
# common anti-spam restriction on cloud hosts. An HTTPS POST to api.brevo.com uses port 443,
# which is never blocked. Set BREVO_API_KEY (and optionally EMAIL_FROM/EMAIL_FROM_NAME) on
# the host; until then, send_email() logs the message (reset link included) to stderr
# instead of sending, so local dev and an unconfigured deploy keep working.
BREVO_API_KEY = os.environ.get("BREVO_API_KEY")
EMAIL_FROM_ADDRESS = os.environ.get("EMAIL_FROM") or "contact@getcomptoir.fr"
EMAIL_FROM_NAME = os.environ.get("EMAIL_FROM_NAME") or "Comptoir"


def send_email(to_addr: str, subject: str, text_body: str, html_body: str | None = None):
    if not BREVO_API_KEY:
        print(f"[email non envoyé — BREVO_API_KEY non configurée] à={to_addr} sujet={subject!r}\n{text_body}", file=sys.stderr)
        return
    payload = {
        "sender": {"name": EMAIL_FROM_NAME, "email": EMAIL_FROM_ADDRESS},
        "to": [{"email": to_addr}],
        "subject": subject,
        "textContent": text_body,
    }
    if html_body:
        payload["htmlContent"] = html_body
    req = urllib.request.Request(
        "https://api.brevo.com/v3/smtp/email",
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={"api-key": BREVO_API_KEY, "Content-Type": "application/json", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10):
            pass
    except urllib.error.HTTPError as e:
        # Brevo's error body names the actual problem (unverified sender, bad key, daily
        # quota...) — worth logging in full rather than collapsing to a generic traceback.
        detail = ""
        try:
            detail = e.read().decode("utf-8", "replace")
        except Exception:
            pass
        print(f"[Brevo a refusé l'envoi — {e.code}] à={to_addr}\n{detail}", file=sys.stderr)
    except Exception:
        # Never let a flaky email provider turn into a 500 for the caller (e.g. signup,
        # which doesn't yet send an email but will) — log it, the request that triggered
        # it still succeeds from the user's point of view where that's the right trade-off.
        traceback.print_exc(file=sys.stderr)


def branded_email_html(heading: str, body_html: str, footnote: str, cta_label: str | None = None, cta_link: str | None = None) -> str:
    """Shared look for every transactional email (this reset email today; welcome/receipt/
    alert emails later) — table-based layout with inline styles only, since email clients
    (Outlook especially) ignore <style> blocks and most CSS layout. Colors match the brand
    tokens in styles.css (kept as literals here, not shared — a mail client can't read a
    stylesheet or CSS variables) and the logo is a dedicated flat PNG (icons/email-logo.png
    — the plain two-tone "C" mark, not the app's PWA icon, which carries fine detail that
    turns to mud at the ~26px this renders at) rather than inline SVG, which renders
    inconsistently across mail clients."""
    logo_url = f"{PUBLIC_BASE_URL}/icons/email-logo.png"
    cta_html = "" if not cta_label else f"""
        <tr><td style="padding:6px 32px 8px;">
          <table role="presentation" cellpadding="0" cellspacing="0"><tr>
            <td style="border-radius:8px; background:#146356;">
              <a href="{cta_link}" style="display:inline-block; padding:12px 22px; font-size:14px; font-weight:700; color:#FFFFFF; text-decoration:none;">{cta_label}</a>
            </td>
          </tr></table>
        </td></tr>"""
    return f"""<!doctype html>
<html lang="fr">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>{html.escape(heading)}</title></head>
<body style="margin:0; padding:0; background:#F3F4F1; font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#F3F4F1; padding:32px 16px;">
    <tr><td align="center">
      <table role="presentation" width="480" cellpadding="0" cellspacing="0" style="max-width:480px; width:100%; background:#FFFFFF; border-radius:14px; border:1px solid #E1E3DC;">
        <tr><td style="padding:28px 32px 0;">
          <table role="presentation" cellpadding="0" cellspacing="0"><tr>
            <td style="padding-right:9px;"><img src="{logo_url}" width="26" height="26" alt="" style="display:block;"></td>
            <td style="font-size:17px; font-weight:800; color:#1B211D; letter-spacing:-0.02em; font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;">Comptoir</td>
          </tr></table>
        </td></tr>
        <tr><td style="padding:24px 32px 8px;">
          <h1 style="margin:0 0 14px; font-size:20px; line-height:1.3; color:#1B211D; font-weight:800;">{html.escape(heading)}</h1>
          <div style="font-size:14.5px; line-height:1.65; color:#566058;">{body_html}</div>
        </td></tr>{cta_html}
        <tr><td style="padding:18px 32px 28px;">
          <p style="margin:0; font-size:12.5px; line-height:1.6; color:#8A9186;">{footnote}</p>
        </td></tr>
        <tr><td style="padding:16px 32px; border-top:1px solid #E1E3DC;">
          <p style="margin:0; font-size:12px; color:#8A9186;">Comptoir — Vendez partout. Comptez ici.<br><a href="{PUBLIC_BASE_URL}/" style="color:#8A9186;">getcomptoir.fr</a></p>
        </td></tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""


# The version accepted at signup is decided HERE, not sent by the client — trusting a
# client-supplied version would let anyone claim they accepted a version they never actually
# saw. Bump this string (matches the "Dernière mise à jour" date on the legal pages) whenever
# the terms/privacy policy change materially.
CONSENT_VERSION = "2026-09-21"

# Server-authoritative mirror of app.js's PLAN_META — limits are enforced HERE, not in the
# client, since a client can always be edited to lie about its own plan. `channels` is the
# max number of distinct sales channels that may be marked connected at once (see
# connected_channels below); `orders` is the max real orders ingested per calendar month via
# the one real inbound path (handle_ingest_order). None means unlimited. Keep in sync with
# PLAN_META in app.js by hand — there's no shared source between the two runtimes here.
PLAN_LIMITS = {
    "decouverte": {"channels": 1, "orders": 50},
    "multicanal": {"channels": 3, "orders": 500},
    "croissance": {"channels": None, "orders": 3000},
}
# Accounts that use Comptoir free forever, by explicit one-off agreement — never billed,
# never blocked by plan limits, regardless of what's in the users table. Keep this list
# short and deliberate; it bypasses Stripe entirely for whoever's in it.
FREE_FOREVER_EMAILS = {"killian.belabbes@gmail.com"}

STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET")
# One Stripe Price ID per tier (a recurring monthly price configured in the Stripe
# dashboard) — maps PLAN_LIMITS keys to what Stripe actually needs to create a subscription.
STRIPE_PRICE_IDS = {
    "decouverte": os.environ.get("STRIPE_PRICE_DECOUVERTE"),
    "multicanal": os.environ.get("STRIPE_PRICE_MULTICANAL"),
    "croissance": os.environ.get("STRIPE_PRICE_CROISSANCE"),
}


def _stripe_flatten(data, prefix=""):
    """Stripe's API takes form-encoded bodies with bracket-nested keys for nested data
    (line_items[0][price]=... ), not JSON — this mirrors what Stripe's own client
    libraries do, since there's no SDK here (stdlib only)."""
    pairs = []
    if isinstance(data, dict):
        for k, v in data.items():
            pairs.extend(_stripe_flatten(v, f"{prefix}[{k}]" if prefix else str(k)))
    elif isinstance(data, list):
        for i, v in enumerate(data):
            pairs.extend(_stripe_flatten(v, f"{prefix}[{i}]"))
    elif data is not None:
        pairs.append((prefix, data))
    return pairs


def stripe_request(method: str, path: str, data: dict | None = None) -> dict:
    if not STRIPE_SECRET_KEY:
        raise ApiError(503, "Le paiement n'est pas encore configuré — réessayez plus tard.")
    url = f"https://api.stripe.com/v1{path}"
    body = urllib.parse.urlencode(_stripe_flatten(data or {})).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body if method != "GET" else None,
        method=method,
        headers={"Authorization": f"Bearer {STRIPE_SECRET_KEY}", "Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")
        try:
            message = json.loads(detail).get("error", {}).get("message") or detail
        except json.JSONDecodeError:
            message = detail
        print(f"[Stripe a refusé la requête — {e.code}] {method} {path}\n{detail}", file=sys.stderr)
        raise ApiError(502, f"Stripe : {message}")


def resolve_plan(user_row) -> dict:
    """The server-authoritative plan for an account — never trust anything the client
    claims about its own plan (the app_state JSON blob is client-editable). Three sources,
    in priority order: 1) the free-forever allowlist, always active Découverte, no Stripe
    involved; 2) whatever's in the users table (kept in sync by grandfathering at migration
    time and by the Stripe webhook from here on); 3) no plan at all for an account that has
    neither — must subscribe via Checkout before the app will accept real usage."""
    # Accessed via .get() on a plain dict rather than sqlite3.Row's bracket access
    # throughout this function — a caller's SELECT that forgets a column (this has
    # happened more than once) then loses that one field instead of throwing a 500 on
    # every plan check in the app, including ones nowhere near whatever query was wrong.
    row = dict(user_row)
    if row.get("email") in FREE_FOREVER_EMAILS:
        return {"tier": "decouverte", "status": "active", "renewsAt": None, "freeForever": True}
    tier = row.get("plan_tier")
    status = row.get("plan_status")
    if not tier or status != "active":
        return {"tier": None, "status": status or "inactive", "renewsAt": None, "freeForever": False}
    return {"tier": tier, "status": status, "renewsAt": row.get("plan_renews_at"), "freeForever": False}


# Real Shopify integration: an OAuth app any merchant can install on her own shop (no
# App Store listing needed — installed directly via a link Comptoir generates), plus order
# webhooks that feed the same _ingest_order_core() the custom connector already uses.
# Needs a free Shopify Partners account + an app created there; see handle_shopify_install.
SHOPIFY_API_KEY = os.environ.get("SHOPIFY_API_KEY")
SHOPIFY_API_SECRET = os.environ.get("SHOPIFY_API_SECRET")
SHOPIFY_SCOPES = os.environ.get("SHOPIFY_SCOPES") or "read_orders,read_products"
SHOPIFY_API_VERSION = os.environ.get("SHOPIFY_API_VERSION") or "2025-01"
SHOPIFY_SHOP_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9-]*\.myshopify\.com$")
SHOPIFY_OAUTH_STATE_TTL_MINUTES = 10
SHOPIFY_WEBHOOK_TOPICS = ["orders/create", "orders/updated", "orders/cancelled", "app/uninstalled"]


def shopify_admin_request(shop_domain: str, access_token: str, method: str, path: str, data: dict | None = None) -> dict:
    url = f"https://{shop_domain}/admin/api/{SHOPIFY_API_VERSION}{path}"
    body = json.dumps(data).encode("utf-8") if data is not None else None
    req = urllib.request.Request(
        url, data=body, method=method,
        headers={"X-Shopify-Access-Token": access_token, "Content-Type": "application/json", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")
        print(f"[Shopify Admin API a refusé — {e.code}] {method} {path} ({shop_domain})\n{detail}", file=sys.stderr)
        raise ApiError(502, "Shopify a refusé cette requête.")


def verify_shopify_hmac(params: dict, hmac_value: str) -> bool:
    """Verifies Shopify's own signature on OAuth callback query params — proves the
    request genuinely came from Shopify and wasn't forged. Shopify's documented scheme:
    sort every param except hmac/signature, join as a query string, HMAC-SHA256 it with
    the app's client secret."""
    if not SHOPIFY_API_SECRET or not hmac_value:
        return False
    pairs = sorted((k, v) for k, v in params.items() if k not in ("hmac", "signature"))
    message = "&".join(f"{k}={v}" for k, v in pairs)
    expected = hmac.new(SHOPIFY_API_SECRET.encode("utf-8"), message.encode("utf-8"), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, hmac_value)


def verify_shopify_webhook_hmac(raw_body: bytes, hmac_header: str | None) -> bool:
    """Webhook deliveries are signed differently from the OAuth callback: base64 of an
    HMAC-SHA256 over the exact raw request body."""
    if not SHOPIFY_API_SECRET or not hmac_header:
        return False
    digest = hmac.new(SHOPIFY_API_SECRET.encode("utf-8"), raw_body, hashlib.sha256).digest()
    expected = base64.b64encode(digest).decode("utf-8")
    return hmac.compare_digest(expected, hmac_header)


def get_db():
    # timeout + busy_timeout: several threads write (ingestion, tracking beacons, state
    # saves) — wait for a lock instead of failing with "database is locked". WAL lets
    # readers proceed during a write and is much friendlier to concurrent requests.
    conn = sqlite3.connect(DB_PATH, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 15000")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
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
        CREATE TABLE IF NOT EXISTS password_resets (
            token TEXT PRIMARY KEY,
            user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            used_at TEXT
        );
        CREATE TABLE IF NOT EXISTS connected_channels (
            user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            channel_type TEXT NOT NULL,
            connected_at TEXT NOT NULL DEFAULT (datetime('now')),
            PRIMARY KEY (user_id, channel_type)
        );
        CREATE TABLE IF NOT EXISTS shopify_shops (
            user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            shop_domain TEXT NOT NULL UNIQUE,
            access_token TEXT NOT NULL,
            connected_at TEXT NOT NULL DEFAULT (datetime('now')),
            PRIMARY KEY (user_id, shop_domain)
        );
        CREATE TABLE IF NOT EXISTS shopify_oauth_states (
            state TEXT PRIMARY KEY,
            user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            shop_domain TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS notification_queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            kind TEXT NOT NULL,
            payload TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS notification_state (
            user_id TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
            last_sent_at TEXT
        );
        CREATE TABLE IF NOT EXISTS tracking_sites (
            site_key TEXT PRIMARY KEY,
            user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            connector_id TEXT NOT NULL,
            channel_type TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            last_seen_at TEXT,
            UNIQUE (user_id, connector_id)
        );
        CREATE TABLE IF NOT EXISTS tracking_stats (
            site_key TEXT NOT NULL REFERENCES tracking_sites(site_key) ON DELETE CASCADE,
            day TEXT NOT NULL,
            country TEXT NOT NULL DEFAULT '',
            source TEXT NOT NULL DEFAULT 'Direct',
            visitors INTEGER NOT NULL DEFAULT 0,
            views INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (site_key, day, country, source)
        );
        CREATE TABLE IF NOT EXISTS tracking_seen (
            hash TEXT PRIMARY KEY,
            day TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS email_verifications (
            token TEXT PRIMARY KEY,
            user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            used_at TEXT
        );
    """)
    # Migration: existing deployments already have a `users` table from before consent
    # tracking existed — CREATE TABLE IF NOT EXISTS above leaves it untouched, so the new
    # columns are added explicitly, once, guarded by a check rather than a bare ALTER TABLE
    # (which would error every startup on a column that already exists).
    existing_cols = {row["name"] for row in conn.execute("PRAGMA table_info(users)")}
    if "consent_version" not in existing_cols:
        conn.execute("ALTER TABLE users ADD COLUMN consent_version TEXT")
    if "consent_accepted_at" not in existing_cols:
        conn.execute("ALTER TABLE users ADD COLUMN consent_accepted_at TEXT")
    # email_verified_at is retroactively backfilled to "already verified" for every account
    # that existed before this column did — they've been using the app for a while, it
    # would be actively harmful to suddenly block their billing/connectors over an email
    # confirmation step that didn't exist when they signed up. Only accounts created from
    # here on start out NULL (unverified) and go through the real flow.
    if "email_verified_at" not in existing_cols:
        conn.execute("ALTER TABLE users ADD COLUMN email_verified_at TEXT")
        conn.execute("UPDATE users SET email_verified_at = created_at")
    # api_keys originally only ever meant the custom connector — channel_type generalizes
    # it to any real integration that authenticates with a plain shared secret rather than
    # Shopify-style OAuth (WooCommerce today). Existing rows default to 'custom', which is
    # exactly what they already were.
    notif_cols = {row["name"] for row in conn.execute("PRAGMA table_info(notification_state)")}
    user_cols = {row["name"] for row in conn.execute("PRAGMA table_info(users)")}
    if "trial_used_at" not in user_cols:
        conn.execute("ALTER TABLE users ADD COLUMN trial_used_at TEXT")
    if "last_monthly" not in notif_cols:
        conn.execute("ALTER TABLE notification_state ADD COLUMN last_monthly TEXT")
    api_keys_cols = {row["name"] for row in conn.execute("PRAGMA table_info(api_keys)")}
    if "channel_type" not in api_keys_cols:
        conn.execute("ALTER TABLE api_keys ADD COLUMN channel_type TEXT NOT NULL DEFAULT 'custom'")
    # Billing columns. plan_tier is deliberately NULLable with no DEFAULT: a brand-new
    # signup gets NULL (no active plan — must subscribe via Stripe Checkout to use the
    # app), which only works because this ALTER runs once, here, when these columns don't
    # exist yet. That first run also grandfathers every account that already existed at
    # that moment (see the backfill below) — accounts created after this migration has
    # already run get NULL from SQLite's column default like anyone else.
    is_first_billing_migration = "plan_tier" not in existing_cols
    if is_first_billing_migration:
        conn.execute("ALTER TABLE users ADD COLUMN plan_tier TEXT")
        conn.execute("ALTER TABLE users ADD COLUMN plan_status TEXT")
        conn.execute("ALTER TABLE users ADD COLUMN plan_renews_at TEXT")
        conn.execute("ALTER TABLE users ADD COLUMN stripe_customer_id TEXT")
        conn.execute("ALTER TABLE users ADD COLUMN stripe_subscription_id TEXT")
    conn.commit()
    if is_first_billing_migration:
        # Grandfather every account that existed before real billing did: freeze it on
        # whatever plan it was already showing (read from its saved app_state — that's
        # the only record of what it was on, since plan was purely client-side before
        # today), active, with no Stripe link — it will never be charged or gated by a
        # webhook, unlike every account created from here on. Falls back to the cheapest
        # tier if a user has no saved state yet (mid-signup, or never logged in).
        for row in conn.execute("SELECT id FROM users WHERE plan_tier IS NULL").fetchall():
            tier = "decouverte"
            state_row = conn.execute("SELECT data FROM app_state WHERE user_id = ?", (row["id"],)).fetchone()
            if state_row:
                try:
                    saved_tier = json.loads(state_row["data"]).get("plan", {}).get("tier")
                    if saved_tier in PLAN_LIMITS:
                        tier = saved_tier
                except (json.JSONDecodeError, AttributeError):
                    pass
            conn.execute(
                "UPDATE users SET plan_tier = ?, plan_status = 'active' WHERE id = ?",
                (tier, row["id"]),
            )
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
        """SELECT u.id, u.email, u.consent_version, u.consent_accepted_at,
                  u.plan_tier, u.plan_status, u.plan_renews_at, u.stripe_customer_id, u.email_verified_at
           FROM sessions s
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
    if not launch_is_open() and email not in SIGNUP_ALLOWLIST:
        raise ApiError(403, "Les inscriptions ne sont pas encore ouvertes : rendez-vous à l'ouverture de Comptoir.")
    if len(password) < 8:
        raise ApiError(400, "Le mot de passe doit contenir au moins 8 caractères.")
    if not body.get("acceptTerms"):
        raise ApiError(400, "Vous devez accepter les conditions générales et la politique de confidentialité pour créer un compte.")

    conn = get_db()
    existing = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
    if existing:
        conn.close()
        raise ApiError(409, "Un compte existe déjà avec cet email.")

    user_id = secrets.token_hex(12)
    pw_hash, pw_salt = hash_password(password)
    # Consent is recorded server-side, tied to the account, timestamped and versioned — this
    # is what makes it a real audit trail (Art. 7 RGPD: the controller must be able to
    # demonstrate consent was given), not just a checkbox the client could silently skip.
    conn.execute(
        "INSERT INTO users (id, email, password_hash, password_salt, consent_version, consent_accepted_at) VALUES (?, ?, ?, ?, ?, datetime('now'))",
        (user_id, email, pw_hash, pw_salt, CONSENT_VERSION),
    )
    verify_token = secrets.token_hex(32)
    conn.execute("INSERT INTO email_verifications (token, user_id) VALUES (?, ?)", (verify_token, user_id))
    conn.commit()
    conn.close()
    token = create_session(user_id)
    send_welcome_email(email, f"{PUBLIC_BASE_URL}/?verifyToken={verify_token}")
    return {"token": token, "email": email}


def send_welcome_email(email: str, verify_link: str):
    text_body = (
        f"Bienvenue sur Comptoir !\n\n"
        f"Confirmez d'abord votre adresse email — indispensable pour recevoir vos factures "
        f"et réinitialiser votre mot de passe si besoin, et nécessaire avant de choisir un "
        f"forfait ou de connecter un canal de vente :\n{verify_link}\n\n"
        f"Ensuite, trois choses à faire pour démarrer :\n\n"
        f"1. Choisissez un forfait — Facturation, dans le menu de gauche.\n"
        f"2. Connectez votre premier canal de vente — Connecteurs.\n"
        f"3. Ajoutez vos produits — Mon catalogue.\n\n"
        f"Une question ? Répondez simplement à cet email.\n\n"
        f"— Comptoir"
    )
    html_body = branded_email_html(
        heading="Bienvenue sur Comptoir",
        body_html=(
            f"<p style=\"margin:0 0 14px;\">Votre compte (<strong style=\"color:#1B211D;\">{html.escape(email)}</strong>) est créé. Confirmez d'abord votre adresse email — nécessaire avant de choisir un forfait ou de connecter un canal de vente.</p>"
        ),
        cta_label="Confirmer mon adresse email",
        cta_link=verify_link,
        footnote=(
            "Une fois confirmé : Facturation pour choisir un forfait, Connecteurs pour brancher votre première "
            "plateforme, Mon catalogue pour ajouter vos produits. Une question ? Répondez simplement à cet email."
        ),
    )
    send_email(email, "Bienvenue sur Comptoir — confirmez votre email", text_body, html_body)


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


# Same in-memory sliding-window shape as the login limiter above, keyed by email — keeps
# someone from mass-emailing a stranger's inbox with reset links, or from hammering the
# token-guessing surface (moot given secrets.token_hex(32), but cheap to bound anyway).
RESET_ATTEMPTS = {}
RESET_LOCK = threading.Lock()
MAX_RESET_ATTEMPTS = 5
RESET_WINDOW_SECONDS = 3600  # 1 hour


def check_reset_rate_limit(email):
    now = time.time()
    with RESET_LOCK:
        attempts = [t for t in RESET_ATTEMPTS.get(email, []) if now - t < RESET_WINDOW_SECONDS]
        RESET_ATTEMPTS[email] = attempts
        if len(attempts) >= MAX_RESET_ATTEMPTS:
            return False
        attempts.append(now)
        return True


def handle_password_reset_request(body):
    require_fields(body, ["email"])
    email = body["email"].strip().lower()

    # Always return the same generic response whether or not the account exists, and
    # whether or not it was rate-limited — anything else (a distinct error message, a
    # different status code) would let an attacker enumerate which emails have accounts
    # just by watching how the response changes.
    generic = {"ok": True, "message": "Si un compte existe avec cette adresse, un email vient d'être envoyé avec un lien de réinitialisation."}

    if not EMAIL_RE.match(email) or not check_reset_rate_limit(email):
        return generic

    conn = get_db()
    user = conn.execute("SELECT id, email FROM users WHERE email = ?", (email,)).fetchone()
    if not user:
        conn.close()
        return generic

    token = secrets.token_hex(32)
    conn.execute("INSERT INTO password_resets (token, user_id) VALUES (?, ?)", (token, user["id"]))
    conn.commit()
    conn.close()

    reset_link = f"{PUBLIC_BASE_URL}/?resetToken={token}"
    text_body = (
        f"Bonjour,\n\n"
        f"Une demande de réinitialisation de mot de passe a été faite pour ce compte Comptoir "
        f"({user['email']}).\n\n"
        f"Pour choisir un nouveau mot de passe, ouvrez ce lien (valable {PASSWORD_RESET_TTL_MINUTES} minutes) :\n"
        f"{reset_link}\n\n"
        f"Si vous n'êtes pas à l'origine de cette demande, ignorez cet email — votre mot de passe actuel reste inchangé.\n\n"
        f"— Comptoir"
    )
    html_body = branded_email_html(
        heading="Réinitialisez votre mot de passe",
        body_html=(
            f"<p style=\"margin:0 0 14px;\">Une demande de réinitialisation a été faite pour le compte "
            f"<strong style=\"color:#1B211D;\">{html.escape(user['email'])}</strong>.</p>"
            f"<p style=\"margin:0;\">Cliquez sur le bouton ci-dessous pour choisir un nouveau mot de passe.</p>"
        ),
        cta_label="Choisir un nouveau mot de passe",
        cta_link=reset_link,
        footnote=(
            f"Ce lien est valable {PASSWORD_RESET_TTL_MINUTES} minutes. Si vous n'êtes pas à l'origine "
            f"de cette demande, ignorez cet email — votre mot de passe actuel reste inchangé."
        ),
    )
    send_email(user["email"], "Réinitialisez votre mot de passe Comptoir", text_body, html_body)
    return generic


def handle_password_reset_confirm(body):
    require_fields(body, ["token", "password"])
    token = body["token"].strip()
    password = body["password"]
    if len(password) < 8:
        raise ApiError(400, "Le mot de passe doit contenir au moins 8 caractères.")

    conn = get_db()
    row = conn.execute(
        """SELECT user_id FROM password_resets
           WHERE token = ? AND used_at IS NULL AND created_at >= datetime('now', ?)""",
        (token, f"-{PASSWORD_RESET_TTL_MINUTES} minutes"),
    ).fetchone()
    if not row:
        conn.close()
        raise ApiError(400, "Ce lien de réinitialisation est invalide ou a expiré — refaites une demande.")

    user_id = row["user_id"]
    pw_hash, pw_salt = hash_password(password)
    conn.execute("UPDATE users SET password_hash = ?, password_salt = ? WHERE id = ?", (pw_hash, pw_salt, user_id))
    conn.execute("UPDATE password_resets SET used_at = datetime('now') WHERE token = ?", (token,))
    # A password reset is exactly the moment to invalidate every existing session — if
    # someone else's session was the reason the password needed changing, this is what
    # actually locks them out, not just the new password on its own.
    conn.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
    conn.commit()
    user = conn.execute("SELECT email FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()

    new_token = create_session(user_id)
    return {"token": new_token, "email": user["email"]}


EMAIL_VERIFY_TTL_DAYS = 7
# Same shape as the password-reset limiter, keyed by user id instead of email since this
# path is authenticated (you can only resend your own account's verification).
RESEND_VERIFY_ATTEMPTS = {}
RESEND_VERIFY_LOCK = threading.Lock()
MAX_RESEND_VERIFY_ATTEMPTS = 5
RESEND_VERIFY_WINDOW_SECONDS = 3600


def check_resend_verify_rate_limit(user_id):
    now = time.time()
    with RESEND_VERIFY_LOCK:
        attempts = [t for t in RESEND_VERIFY_ATTEMPTS.get(user_id, []) if now - t < RESEND_VERIFY_WINDOW_SECONDS]
        RESEND_VERIFY_ATTEMPTS[user_id] = attempts
        if len(attempts) >= MAX_RESEND_VERIFY_ATTEMPTS:
            return False
        attempts.append(now)
        return True


def send_verification_email(email: str, verify_link: str):
    text_body = (
        f"Confirmez votre adresse email pour continuer sur Comptoir :\n{verify_link}\n\n"
        f"Ce lien est valable {EMAIL_VERIFY_TTL_DAYS} jours.\n\n— Comptoir"
    )
    html_body = branded_email_html(
        heading="Confirmez votre adresse email",
        body_html="<p style=\"margin:0;\">Cliquez sur le bouton ci-dessous pour confirmer votre adresse et débloquer le choix d'un forfait et la connexion de vos canaux de vente.</p>",
        cta_label="Confirmer mon adresse email",
        cta_link=verify_link,
        footnote=f"Ce lien est valable {EMAIL_VERIFY_TTL_DAYS} jours.",
    )
    send_email(email, "Confirmez votre adresse email — Comptoir", text_body, html_body)


def handle_email_verify_confirm(body):
    verify_token = str(body.get("token", "")).strip()
    if not verify_token:
        raise ApiError(400, "Lien de confirmation invalide.")
    conn = get_db()
    row = conn.execute(
        """SELECT user_id FROM email_verifications
           WHERE token = ? AND used_at IS NULL AND created_at >= datetime('now', ?)""",
        (verify_token, f"-{EMAIL_VERIFY_TTL_DAYS} days"),
    ).fetchone()
    if not row:
        conn.close()
        raise ApiError(400, "Ce lien de confirmation est invalide ou a expiré — demandez-en un nouveau depuis l'application.")
    conn.execute(
        "UPDATE users SET email_verified_at = datetime('now') WHERE id = ? AND email_verified_at IS NULL",
        (row["user_id"],),
    )
    conn.execute("UPDATE email_verifications SET used_at = datetime('now') WHERE token = ?", (verify_token,))
    conn.commit()
    conn.close()
    return {"ok": True}


def handle_email_verify_resend(token):
    user = user_from_token(token)
    if not user:
        raise ApiError(401, "Session invalide ou expirée.")
    if user["email_verified_at"] is not None:
        return {"ok": True, "alreadyVerified": True}
    if not check_resend_verify_rate_limit(user["id"]):
        raise ApiError(429, "Trop de demandes — réessayez dans quelques minutes.")
    verify_token = secrets.token_hex(32)
    conn = get_db()
    conn.execute("INSERT INTO email_verifications (token, user_id) VALUES (?, ?)", (verify_token, user["id"]))
    conn.commit()
    conn.close()
    send_verification_email(user["email"], f"{PUBLIC_BASE_URL}/?verifyToken={verify_token}")
    return {"ok": True}


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
    user["plan"] = resolve_plan(user)
    user["emailVerified"] = user["email_verified_at"] is not None
    user["trial"] = {"days": TRIAL_DAYS, "eligible": _trial_eligible(user["id"]) and user["email"] not in FREE_FOREVER_EMAILS}
    return user


# Comptoir's business data (products, orders, stock, SAV, connectors...) is stored as one
# JSON document per user, rather than fully normalized tables. This is a deliberate
# trade-off for an early-stage product: it gives every user their own real, isolated,
# durable data — the part that matters for testing with real people — without the much
# larger project of designing and migrating a full relational schema up front. That
# normalization is the natural next step once the product needs cross-user querying
# (e.g. the admin/monitoring view from the technical plan) rather than per-user storage.
MAX_BODY_BYTES = 5_000_000  # hard cap on any request body, checked before it is read
MAX_STATE_BYTES = 2_000_000  # 2 MB — generous for this app's data, cheap to guard.


def handle_get_state(token):
    user = user_from_token(token)
    if not user:
        raise ApiError(401, "Session invalide ou expirée.")
    conn = get_db()
    row = conn.execute("SELECT data FROM app_state WHERE user_id = ?", (user["id"],)).fetchone()
    conn.close()
    return {"data": row["data"] if row else None}


def _parse_ts(ts):
    if not ts:
        return 0.0
    try:
        return datetime.fromisoformat(str(ts).replace("Z", "+00:00")).timestamp()
    except (ValueError, TypeError):
        return 0.0


def _merge_touched_collection(server_list, client_list):
    """Per-record last-write-wins merge, keyed by id and compared by each record's own
    'updatedAt' stamp. Exists because orders and products aren't exclusively client-owned:
    a real connector (webhook, or a homemade site's own periodic bulk resync — see
    /api/ingest/orders/bulk) can update one server-side at any moment, with no way to
    tell an already-open browser tab. Without this, that tab's next PUT /api/state (its
    full, possibly now-stale snapshot, sent for an entirely unrelated reason — switching
    theme, changing the date range...) would silently overwrite the fresher server-side
    change. A record present on the server but missing from the client's payload is kept
    rather than dropped — this app never lets the client delete an order or product, so a
    gap only ever means a stale/partial client payload, never an intentional deletion."""
    server_by_id = {r.get("id"): r for r in server_list if r.get("id")}
    seen = set()
    merged = []
    for client_rec in client_list:
        rid = client_rec.get("id")
        server_rec = server_by_id.get(rid) if rid else None
        if server_rec is None:
            merged.append(client_rec)
        else:
            seen.add(rid)
            merged.append(server_rec if _parse_ts(server_rec.get("updatedAt")) >= _parse_ts(client_rec.get("updatedAt")) else client_rec)
    for rid, server_rec in server_by_id.items():
        if rid not in seen:
            merged.append(server_rec)
    return merged


def handle_put_state(token, body):
    user = user_from_token(token)
    if not user:
        raise ApiError(401, "Session invalide ou expirée.")
    if "data" not in body or not isinstance(body["data"], str):
        raise ApiError(400, "Le champ « data » (JSON sérialisé en texte) est requis.")
    if len(body["data"]) > MAX_STATE_BYTES:
        raise ApiError(413, "Données trop volumineuses.")
    try:
        client_data = json.loads(body["data"])  # must itself be valid JSON
    except json.JSONDecodeError:
        raise ApiError(400, "Le champ « data » doit être du JSON valide.")
    conn = get_db()
    with STATE_LOCK:
        row = conn.execute("SELECT data FROM app_state WHERE user_id = ?", (user["id"],)).fetchone()
        if row and isinstance(client_data, dict):
            try:
                server_data = json.loads(row["data"])
            except json.JSONDecodeError:
                server_data = None
            if isinstance(server_data, dict):
                if isinstance(client_data.get("orders"), list) and isinstance(server_data.get("orders"), list):
                    client_data["orders"] = _merge_touched_collection(server_data["orders"], client_data["orders"])
                if isinstance(client_data.get("products"), list) and isinstance(server_data.get("products"), list):
                    client_data["products"] = _merge_touched_collection(server_data["products"], client_data["products"])
        new_data = json.dumps(client_data)
        conn.execute(
            """INSERT INTO app_state (user_id, data, updated_at) VALUES (?, ?, datetime('now'))
               ON CONFLICT(user_id) DO UPDATE SET data = excluded.data, updated_at = excluded.updated_at""",
            (user["id"], new_data),
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
ORDER_STATUSES = {"livree", "en_route", "preparation", "retour"}


def require_active_plan(user):
    """Raises 402 for any account with no active plan — free-forever and grandfathered
    accounts always pass (resolve_plan gives them tier+status='active'); anyone who
    signed up after real billing shipped and hasn't subscribed yet does not."""
    plan = resolve_plan(user)
    if not plan["tier"]:
        raise ApiError(402, "Choisissez un forfait pour continuer — rendez-vous dans Facturation.")
    return plan


def require_verified_email(user):
    """Raises 403 for an account whose email was never confirmed — gates the actions where
    an unreachable address is a real problem (getting billed, or a channel silently
    dropping orders no one will ever be told about): choosing a plan, connecting a channel.
    Every account that existed before this check shipped was backfilled to 'verified' at
    migration time (see init_db) — this only ever blocks a genuinely new, unconfirmed
    signup."""
    if user["email_verified_at"] is None:
        raise ApiError(403, "Confirmez votre adresse email avant de continuer — vérifiez votre boîte de réception (et vos spams).")


def count_connected_channels(conn, user_id: str) -> int:
    return conn.execute("SELECT COUNT(*) FROM connected_channels WHERE user_id = ?", (user_id,)).fetchone()[0]


def handle_connect_channel(token, body):
    """Registers a sales channel as connected against the plan's channel limit. The sync
    itself stays exactly as simulated as before (no real Shopify/Etsy/... API call exists
    yet — disclosed honestly on the landing page); what's real here is the COUNT and the
    limit it's checked against, which is the actual point of this endpoint."""
    user = user_from_token(token)
    if not user:
        raise ApiError(401, "Session invalide ou expirée.")
    require_verified_email(user)
    plan = require_active_plan(user)
    channel_type = str(body.get("type", "")).strip().lower()
    if not channel_type:
        raise ApiError(400, "Le type de canal est requis.")
    conn = get_db()
    already = conn.execute(
        "SELECT 1 FROM connected_channels WHERE user_id = ? AND channel_type = ?", (user["id"], channel_type)
    ).fetchone()
    if not already:
        limit = PLAN_LIMITS[plan["tier"]]["channels"]
        current = count_connected_channels(conn, user["id"])
        if limit is not None and current >= limit:
            conn.close()
            raise ApiError(402, f"Votre forfait autorise {limit} canal{'aux' if limit > 1 else ''} connecté{'s' if limit > 1 else ''} maximum — passez à un forfait supérieur pour en connecter davantage.")
        conn.execute("INSERT INTO connected_channels (user_id, channel_type) VALUES (?, ?)", (user["id"], channel_type))
        conn.commit()
    conn.close()
    return {"ok": True}


def handle_disconnect_channel(token, channel_type):
    user = user_from_token(token)
    if not user:
        raise ApiError(401, "Session invalide ou expirée.")
    conn = get_db()
    conn.execute("DELETE FROM connected_channels WHERE user_id = ? AND channel_type = ?", (user["id"], channel_type))
    if channel_type == "shopify":
        # Forget the stored access token too — Shopify has no explicit "revoke" call, but
        # there's no reason to keep a live credential around once the merchant disconnects
        # from our side. Doesn't touch her install in the Shopify admin (she can remove
        # the app there separately; that fires app/uninstalled, which cleans this up too).
        conn.execute("DELETE FROM shopify_shops WHERE user_id = ?", (user["id"],))
    conn.commit()
    conn.close()
    return {"ok": True}


def handle_create_connector(token, body, channel_type: str = "custom"):
    user = user_from_token(token)
    if not user:
        raise ApiError(401, "Session invalide ou expirée.")
    require_verified_email(user)
    plan = require_active_plan(user)
    label = str(body.get("label", "")).strip()
    if not label:
        raise ApiError(400, "Le nom de la plateforme est requis.")
    connector_id = secrets.token_hex(8)
    api_key = "cpt_live_" + secrets.token_hex(24)
    conn = get_db()
    # Every connector of the same channel_type shares one channel slot (this is a category
    # of channel, like Shopify or WooCommerce, not one slot per store) — only check and
    # consume the limit the first time, so a second connector of the same type doesn't
    # need its own.
    already = conn.execute(
        "SELECT 1 FROM connected_channels WHERE user_id = ? AND channel_type = ?", (user["id"], channel_type)
    ).fetchone()
    if not already:
        limit = PLAN_LIMITS[plan["tier"]]["channels"]
        current = count_connected_channels(conn, user["id"])
        if limit is not None and current >= limit:
            conn.close()
            raise ApiError(402, f"Votre forfait autorise {limit} canal{'aux' if limit > 1 else ''} connecté{'s' if limit > 1 else ''} maximum — passez à un forfait supérieur pour en connecter davantage.")
        conn.execute("INSERT INTO connected_channels (user_id, channel_type) VALUES (?, ?)", (user["id"], channel_type))
    conn.execute(
        "INSERT INTO api_keys (key, user_id, connector_id, label, channel_type) VALUES (?, ?, ?, ?, ?)",
        (api_key, user["id"], connector_id, label, channel_type),
    )
    conn.commit()
    conn.close()
    return {"connectorId": connector_id, "apiKey": api_key}


def handle_delete_connector(token, connector_id):
    user = user_from_token(token)
    if not user:
        raise ApiError(401, "Session invalide ou expirée.")
    conn = get_db()
    row = conn.execute(
        "SELECT channel_type FROM api_keys WHERE user_id = ? AND connector_id = ?", (user["id"], connector_id)
    ).fetchone()
    conn.execute(
        "DELETE FROM api_keys WHERE user_id = ? AND connector_id = ?",
        (user["id"], connector_id),
    )
    # Free that channel_type's slot only once no connector of the SAME type is left — a
    # user with two WooCommerce connectors deleting one should still count as using the
    # slot, but deleting her only WooCommerce connector shouldn't touch a separate custom
    # connector's slot.
    if row:
        remaining = conn.execute(
            "SELECT COUNT(*) FROM api_keys WHERE user_id = ? AND channel_type = ?", (user["id"], row["channel_type"])
        ).fetchone()[0]
        if remaining == 0:
            conn.execute(
                "DELETE FROM connected_channels WHERE user_id = ? AND channel_type = ?", (user["id"], row["channel_type"])
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
    "date": ["date", "created_at", "createdAt", "date_created", "dateCreated", "order_date", "orderDate", "date_creation", "dateCreation"],
    "status": ["status", "state", "statut", "orderStatus", "order_status"],
    "customerName": ["customerName", "customer_name", "client", "clientName", "client_name", "nom_client", "buyer", "buyerName", "name"],
    "productName": ["productName", "product_name", "product", "article", "item", "itemName", "item_name", "designation"],
    "quantity": ["quantity", "qty", "quantite", "quantité", "nombre", "count", "units"],
}
STATUS_ALIASES = {
    "livree": {"livree", "livre", "delivered", "completed", "complete", "paid", "payee", "done", "picked_up", "collected", "retire", "retiree", "remis", "remise"},
    "en_route": {"en_route", "enroute", "expedie", "expediee", "envoye", "envoyee", "shipped", "fulfilled", "dispatched", "in_transit", "en_transit",
                 "out_for_delivery", "en_livraison", "en_cours_de_livraison", "en_cours_d_acheminement", "in_delivery", "sent", "pris_en_charge"},
    "preparation": {"preparation", "pending", "processing", "en_attente", "created", "new", "confirmed", "awaiting", "open", "en_preparation"},
    "retour": {"retour", "refunded", "returned", "cancelled", "canceled", "annulee", "annule", "rembourse", "refund",
               "retourne", "retournee", "refuse", "refusee", "failed", "echec", "lost", "perdue"},
}
# Every alias name across every recognized field, lowercased — never re-offer one of these
# as a "discovered" extra field, it's already surfaced as amount/status/customer/etc.
_CONSUMED_FIELD_KEYS = {alias.lower() for aliases in FIELD_ALIASES.values() for alias in aliases} | {
    "customer", "billing", "shipping", "country", "countrycode", "country_code", "pays", "items", "products", "lineitems", "line_items",
}
MAX_EXTRA_FIELDS_PER_ORDER = 20


def _extract_extra_fields(body: dict) -> dict:
    """Real platforms (Shopify, WooCommerce, a custom site's own API) send far more fields
    than the ones mapped above — this captures the rest as trackable custom fields, so
    'Ajouter un champ de suivi' in the app can offer what a merchant's real connected data
    actually contains instead of a guessed, invented list. Only flat scalars: a nested
    object or array (line_items, billing...) has no single value to show in a table column,
    and capturing it wholesale risks real storage bloat for no display benefit."""
    extra = {}
    for k, v in body.items():
        if len(extra) >= MAX_EXTRA_FIELDS_PER_ORDER:
            break
        # Keys become column names in the merchant's dashboard: keep them plain text (no
        # markup characters, bounded length) so a hostile or sloppy payload can't inject
        # HTML into the UI, and values are bounded so they can't bloat the account's state.
        key = re.sub(r"[<>\"'`&\x00-\x1f]", "", str(k)).strip()[:60]
        if not key or key.lower() in _CONSUMED_FIELD_KEYS:
            continue
        if isinstance(v, bool) or isinstance(v, (int, float)):
            extra[key] = str(v)
        elif isinstance(v, str) and v.strip():
            extra[key] = v.strip()[:300]
    return extra


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

    delivered_keys = ["delivered", "is_delivered", "delivered_at", "deliveredAt"]
    if any(_truthy(_pick_field(body, [k])) for k in delivered_keys):
        return "livree"
    # Shopify reports the carrier's delivery on each fulfillment (shipment_status), which is
    # the only place it distinguishes "shipped" from "delivered".
    fulfillments = body.get("fulfillments")
    if isinstance(fulfillments, list) and any(
        isinstance(f, dict) and str(f.get("shipment_status", "")).strip().lower() == "delivered" for f in fulfillments
    ):
        return "livree"

    ship_keys = ["shipped", "is_shipped", "shipped_at", "shippedAt", "fulfilled", "is_fulfilled", "fulfilled_at", "fulfilledAt"]
    if any(_truthy(_pick_field(body, [k])) for k in ship_keys):
        return "en_route"

    fulfillment_status = _pick_field(body, ["fulfillment_status", "fulfillmentStatus"])
    if fulfillment_status:
        fs = str(fulfillment_status).strip().lower()
        if fs == "delivered":
            return "livree"
        if fs in {"fulfilled", "shipped", "partial"}:
            return "en_route"

    return None


_COUNTRY_NAMES = {
    "france": "FR", "belgique": "BE", "belgium": "BE", "suisse": "CH", "switzerland": "CH",
    "allemagne": "DE", "germany": "DE", "espagne": "ES", "spain": "ES", "italie": "IT", "italy": "IT",
    "portugal": "PT", "royaume-uni": "GB", "royaume uni": "GB", "united kingdom": "GB", "uk": "GB",
    "etats-unis": "US", "états-unis": "US", "united states": "US", "usa": "US", "canada": "CA",
    "pays-bas": "NL", "netherlands": "NL", "luxembourg": "LU", "irlande": "IE", "ireland": "IE",
    "autriche": "AT", "austria": "AT", "maroc": "MA", "morocco": "MA", "tunisie": "TN", "algerie": "DZ",
    "algérie": "DZ", "suede": "SE", "suède": "SE", "sweden": "SE", "danemark": "DK", "denmark": "DK",
    "norvege": "NO", "norvège": "NO", "norway": "NO", "pologne": "PL", "poland": "PL", "japon": "JP", "japan": "JP",
    "australie": "AU", "australia": "AU",
}


def _to_country_code(raw):
    """ISO 3166-1 alpha-2 (uppercase) from a code or a common country name, else None."""
    if raw in (None, ""):
        return None
    v = str(raw).strip()
    if len(v) == 2 and v.isalpha():
        return v.upper()
    return _COUNTRY_NAMES.get(v.lower())


def _extract_country(body):
    keys = ["countryCode", "country_code", "country", "pays", "shippingCountry", "shipping_country"]
    code = _to_country_code(_pick_field(body, keys))
    if code:
        return code
    for nested in ("shipping_address", "shippingAddress", "shipping", "billing_address", "billingAddress", "billing", "address", "customer"):
        obj = body.get(nested)
        if isinstance(obj, dict):
            code = _to_country_code(_pick_field(obj, keys))
            if code:
                return code
            default_addr = obj.get("default_address")
            if isinstance(default_addr, dict):
                code = _to_country_code(_pick_field(default_addr, keys))
                if code:
                    return code
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
        "SELECT user_id, connector_id, channel_type FROM api_keys WHERE key = ?", (api_key,)
    ).fetchone()
    if not row:
        conn.close()
        raise ApiError(401, "Clé API invalide ou révoquée.")
    return _ingest_order_core(conn, row["user_id"], row["channel_type"], row["connector_id"], body)


MAX_BULK_INGEST_ORDERS = 500


def handle_ingest_orders_bulk(api_key, body):
    """A homemade site has no platform-native webhook system to tell Comptoir when an
    order's status changes later — POST /api/ingest/orders only ever covers the moment it's
    called. Rather than requiring the site's own code to be instrumented at every place an
    order can change (unrealistic for a lot of small custom sites), this lets it push its
    FULL current order list in one call, on whatever schedule the site owner sets up
    (a cron job, a button, on each of their own admin page loads...) — each item goes
    through the exact same matching-by-externalId logic as the single-order endpoint, so
    a resend of an unchanged order is a no-op and a changed one updates in place."""
    if not api_key:
        raise ApiError(401, "Clé API manquante.")
    if not isinstance(body, dict) or not isinstance(body.get("orders"), list) or not body["orders"]:
        raise ApiError(400, "Le corps de la requête doit contenir un tableau « orders » non vide.")
    if len(body["orders"]) > MAX_BULK_INGEST_ORDERS:
        raise ApiError(400, f"Maximum {MAX_BULK_INGEST_ORDERS} commandes par appel groupé.")

    results = []
    for i, order_body in enumerate(body["orders"]):
        conn = get_db()
        row = conn.execute(
            "SELECT user_id, connector_id, channel_type FROM api_keys WHERE key = ?", (api_key,)
        ).fetchone()
        if not row:
            conn.close()
            raise ApiError(401, "Clé API invalide ou révoquée.")
        try:
            result = _ingest_order_core(conn, row["user_id"], row["channel_type"], row["connector_id"], order_body)
            results.append({"index": i, "ok": True, **result})
        except ApiError as e:
            results.append({"index": i, "ok": False, "error": e.message})

    created = sum(1 for r in results if r["ok"] and not r.get("duplicate"))
    updated = sum(1 for r in results if r["ok"] and r.get("duplicate") and r.get("updated"))
    unchanged = sum(1 for r in results if r["ok"] and r.get("duplicate") and not r.get("updated"))
    failed = sum(1 for r in results if not r["ok"])
    return {"ok": True, "total": len(results), "created": created, "updated": updated, "unchanged": unchanged, "failed": failed, "results": results}


def _ingest_order_core(conn, user_id: str, channel_type: str, connector_id: str, body: dict):
    """Shared by every real inbound order path — today the custom API connector
    (handle_ingest_order) and Shopify's order webhooks (handle_shopify_webhook). Takes
    the resolved account + which channel this came from; everything else (field-alias
    matching, status inference, product auto-creation, stock sync, duplicate/backfill
    detection, plan limit) is identical regardless of source."""
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
    status_known = True
    if status_raw not in (None, ""):
        status, status_note = _normalize_status(status_raw)
    else:
        inferred = _infer_status_from_signals(body)
        status_known = bool(inferred)
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
    # "customer" (Shopify and most others) or "billing" (WooCommerce's order webhook
    # payload names it that — it's really just who the order belongs to).
    customer_obj = body.get("customer") if isinstance(body.get("customer"), dict) else body.get("billing") if isinstance(body.get("billing"), dict) else None
    if not customer_name and customer_obj:
        customer_name = _pick_field(customer_obj, ["name", "fullName", "full_name", "nom"])
        if not customer_name:
            # Several platforms (Shopify, WooCommerce...) split the name into
            # first_name/last_name rather than a single combined field.
            first = _pick_field(customer_obj, ["first_name", "firstName"])
            last = _pick_field(customer_obj, ["last_name", "lastName"])
            combined = " ".join(str(p) for p in (first, last) if p)
            customer_name = combined or None
    customer_name = str(customer_name).strip() if customer_name not in (None, "") else "Client"

    product_name = _pick_field(body, FIELD_ALIASES["productName"])
    if not product_name:
        items = body.get("items") or body.get("products") or body.get("lineItems") or body.get("line_items")
        if isinstance(items, list) and items:
            first = items[0]
            if isinstance(first, dict):
                # "name" is WooCommerce line_items' product-name field; "title"/"label"
                # cover other common shapes.
                product_name = _pick_field(first, FIELD_ALIASES["productName"] + ["name", "title", "label"])
            elif isinstance(first, str):
                product_name = first
    product_name = str(product_name).strip() if product_name not in (None, "") else None

    country = _extract_country(body)

    quantity_raw = _pick_field(body, FIELD_ALIASES["quantity"])
    if quantity_raw is None and isinstance(body.get("items"), list) and body["items"]:
        first_item = body["items"][0]
        if isinstance(first_item, dict):
            quantity_raw = _pick_field(first_item, FIELD_ALIASES["quantity"])
    quantity_provided = quantity_raw is not None
    quantity = _parse_amount(quantity_raw)
    quantity = int(quantity) if quantity and quantity > 0 else 1

    now_iso = datetime.now(timezone.utc).isoformat()

    with STATE_LOCK:
        state_row = conn.execute("SELECT data FROM app_state WHERE user_id = ?", (user_id,)).fetchone()
        if not state_row:
            conn.close()
            raise ApiError(409, "Compte non initialisé — connectez-vous une première fois à l'application avant d'envoyer des commandes.")
        data = json.loads(state_row["data"])
        orders = data.setdefault("orders", [])

        products = data.setdefault("products", [])
        notify_events = []

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
                "updatedAt": now_iso,
            }
            products.append(new_product)
            return new_product["id"]

        if external_id:
            existing = next((o for o in orders if o.get("externalId") == external_id), None)
            if existing:
                # A platform with real webhooks (Shopify: created → paid → fulfilled →
                # refunded...) sends the SAME order multiple times as it moves through its
                # lifecycle, each time with the same externalId — this is where that gets
                # reflected, not just a "duplicate, ignored" no-op. A merchant re-sending an
                # order by hand to backfill a missing product link goes through the same path.
                changed = False
                # A partial update (say, just a new status) must not reset what it doesn't
                # mention: no quantity sent keeps the order's quantity, no status information
                # at all keeps its status — otherwise a delivered order would silently fall
                # back to "en préparation" and its quantity to 1 on the next bare update.
                if not quantity_provided:
                    quantity = existing.get("quantity") or 1
                if not status_known:
                    status = existing.get("status") or status

                def _adjust_stock(product_id_, qty, order_status, reverse=False):
                    if not product_id_:
                        return
                    product = next((p for p in products if p["id"] == product_id_), None)
                    if product is None:
                        return
                    delta = qty if order_status == "retour" else -qty
                    if reverse:
                        delta = -delta
                    before_stock = product.get("stock", 0) or 0
                    product["stock"] = max(0, before_stock + delta)
                    product["updatedAt"] = now_iso
                    _stock_event(notify_events, product, before_stock, product["stock"])

                had_product_id = bool(existing.get("productId"))
                if not had_product_id and product_name:
                    existing["productId"] = find_or_create_product(product_name)
                    changed = True

                if existing.get("status") == "livree" and status == "en_route":
                    # Delivered can't go back to "en route": platforms keep re-sending
                    # "fulfilled" on every later update, which must not undo a delivery.
                    status = "livree"
                old_status = existing.get("status")
                old_quantity = existing.get("quantity") or 1
                if existing.get("productId"):
                    if had_product_id and (old_status != status or old_quantity != quantity):
                        # Already had a product linked, so stock was already adjusted once
                        # for this order — reverse that old effect, apply the current one.
                        # Correct however many times status/quantity change across
                        # deliveries, not just the first.
                        _adjust_stock(existing["productId"], old_quantity, old_status, reverse=True)
                        _adjust_stock(existing["productId"], quantity, status)
                    elif not had_product_id:
                        # Just got its first product link — this sale was never reflected
                        # in stock at all yet, apply it now.
                        _adjust_stock(existing["productId"], quantity, status)

                if existing.get("status") != status:
                    history = existing.setdefault("history", [])
                    if not history and existing.get("status"):
                        history.append({"status": existing["status"], "at": existing.get("date") or now_iso})
                    history.append({"status": status, "at": now_iso})
                    del history[:-50]
                    existing["status"] = status
                    changed = True
                if existing.get("quantity") != quantity:
                    existing["quantity"] = quantity
                    changed = True
                if country and existing.get("country") != country:
                    existing["country"] = country
                    changed = True
                if round(existing.get("amount", 0) or 0, 2) != round(amount, 2):
                    existing["amount"] = round(amount, 2)
                    changed = True

                if changed:
                    existing["updatedAt"] = now_iso
                    _queue_events(conn, user_id, data, notify_events)
                    new_data = json.dumps(data)
                    conn.execute(
                        "UPDATE app_state SET data = ?, updated_at = datetime('now') WHERE user_id = ?",
                        (new_data, user_id),
                    )
                    conn.commit()
                conn.close()
                return {"ok": True, "duplicate": True, "updated": changed, "orderId": existing["id"], "orderNumber": existing["orderNumber"]}

        # Plan limit on real inbound orders: count only orders that came through a real
        # ingestion path this calendar month — identified by having a connectorId at all,
        # which only a real path ever sets (never the demo/seed data pre-loaded before real
        # billing existed, or an account's own manual entries). Deliberately not scoped to
        # this one channel_type: the limit is one number per account across every real
        # channel, custom API and Shopify (and whatever's next) together.
        user_row = conn.execute(
            "SELECT id, email, plan_tier, plan_status, plan_renews_at FROM users WHERE id = ?", (user_id,)
        ).fetchone()
        if user_row:
            plan = require_active_plan(user_row)
            limit = PLAN_LIMITS[plan["tier"]]["orders"]
            if limit is not None:
                month_prefix = datetime.now(timezone.utc).strftime("%Y-%m")
                this_month_count = sum(
                    1 for o in orders
                    if o.get("connectorId") and str(o.get("date", "")).startswith(month_prefix)
                )
                if this_month_count >= limit:
                    conn.close()
                    raise ApiError(402, f"Votre forfait autorise {limit} commandes par mois maximum — passez à un forfait supérieur.")

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
                product["updatedAt"] = now_iso
                _stock_event(notify_events, product, current, product["stock"])

        next_number = max([o.get("orderNumber", 0) for o in orders], default=1000) + 1
        order = {
            "id": secrets.token_hex(8),
            "orderNumber": next_number,
            "channelType": channel_type,
            "connectorId": connector_id,
            "productId": product_id,
            "customer": customer_name,
            "amount": round(amount, 2),
            "status": status,
            "quantity": quantity,
            "date": date,
            "custom": _extract_extra_fields(body) if isinstance(body, dict) else {},
            "externalId": external_id,
            "country": country,
            "history": [{"status": status, "at": now_iso}],
            "updatedAt": now_iso,
        }
        orders.insert(0, order)
        if status != "retour" and _is_recent(date):
            product_row = next((p for p in products if p["id"] == product_id), None) if product_id else None
            notify_events.insert(0, {
                "kind": "sale", "customer": customer_name, "amount": round(amount, 2), "quantity": quantity,
                "product": product_row.get("name") if product_row else None, "channel": connector_label_for(data, channel_type),
                "country": country, "ref": external_id or str(next_number),
            })
        if _is_recent(date):
            _queue_events(conn, user_id, data, notify_events)

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


def _get_or_create_stripe_customer(conn, user) -> str:
    if user["stripe_customer_id"]:
        return user["stripe_customer_id"]
    customer = stripe_request("POST", "/customers", {"email": user["email"], "metadata": {"comptoir_user_id": user["id"]}})
    conn.execute("UPDATE users SET stripe_customer_id = ? WHERE id = ?", (customer["id"], user["id"]))
    conn.commit()
    return customer["id"]


def _trial_eligible(user_id):
    """One free month per account, and only for someone who has never subscribed."""
    if TRIAL_DAYS <= 0:
        return False
    conn = get_db()
    row = conn.execute("SELECT trial_used_at, stripe_subscription_id, plan_tier FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    return bool(row) and not row["trial_used_at"] and not row["stripe_subscription_id"] and not row["plan_tier"]


def handle_billing_checkout(token, body):
    user = user_from_token(token)
    if not user:
        raise ApiError(401, "Session invalide ou expirée.")
    require_verified_email(user)
    if user["email"] in FREE_FOREVER_EMAILS:
        raise ApiError(400, "Ce compte est en accès gratuit permanent — aucun paiement n'est nécessaire.")
    tier = body.get("tier")
    price_id = STRIPE_PRICE_IDS.get(tier)
    if not price_id:
        raise ApiError(400, "Forfait inconnu ou non configuré.")
    conn = get_db()
    customer_id = _get_or_create_stripe_customer(conn, user)
    conn.close()
    trial = _trial_eligible(user["id"])
    subscription_data = {"metadata": {"comptoir_user_id": user["id"], "comptoir_tier": tier}}
    if trial:
        subscription_data["trial_period_days"] = TRIAL_DAYS
        # No card at the end of the trial = the subscription simply stops, never a surprise charge.
        subscription_data["trial_settings"] = {"end_behavior": {"missing_payment_method": "cancel"}}
    session = stripe_request("POST", "/checkout/sessions", {
        "mode": "subscription",
        "customer": customer_id,
        "line_items": [{"price": price_id, "quantity": 1}],
        # Query string before the hash, never after: app.js's router reads location.hash
        # as the route path verbatim (#facturation), so anything appended past it there
        # would corrupt the route match — location.search is where a returning query
        # param belongs, same convention as the password-reset link.
        "success_url": f"{PUBLIC_BASE_URL}/?checkout=success#facturation",
        "cancel_url": f"{PUBLIC_BASE_URL}/?checkout=cancel#facturation",
        "payment_method_collection": "always",
        "metadata": {"comptoir_user_id": user["id"], "comptoir_tier": tier, "comptoir_trial": "1" if trial else "0"},
        "subscription_data": subscription_data,
    })
    return {"url": session["url"]}


def handle_billing_portal(token):
    user = user_from_token(token)
    if not user:
        raise ApiError(401, "Session invalide ou expirée.")
    if not user["stripe_customer_id"]:
        raise ApiError(400, "Aucun abonnement à gérer pour l'instant.")
    session = stripe_request("POST", "/billing_portal/sessions", {
        "customer": user["stripe_customer_id"],
        "return_url": f"{PUBLIC_BASE_URL}/#facturation",
    })
    return {"url": session["url"]}


def verify_stripe_signature(payload: bytes, sig_header: str | None) -> bool:
    if not STRIPE_WEBHOOK_SECRET or not sig_header:
        return False
    try:
        parts = dict(p.split("=", 1) for p in sig_header.split(",") if "=" in p)
        t, v1 = parts["t"], parts["v1"]
    except (KeyError, ValueError):
        return False
    # 5-minute tolerance against replay of an old, previously-valid signed request.
    try:
        if abs(time.time() - int(t)) > 300:
            return False
    except ValueError:
        return False
    expected = hmac.new(STRIPE_WEBHOOK_SECRET.encode("utf-8"), f"{t}.".encode("utf-8") + payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, v1)


def _tier_from_stripe_price_id(price_id: str) -> str | None:
    for tier, pid in STRIPE_PRICE_IDS.items():
        if pid and pid == price_id:
            return tier
    return None


def handle_stripe_webhook(payload: bytes, sig_header: str | None):
    if not verify_stripe_signature(payload, sig_header):
        raise ApiError(400, "Signature Stripe invalide.")
    event = json.loads(payload.decode("utf-8"))
    event_type = event.get("type")
    obj = event.get("data", {}).get("object", {})
    conn = get_db()

    if event_type == "checkout.session.completed":
        user_id = obj.get("metadata", {}).get("comptoir_user_id")
        tier = obj.get("metadata", {}).get("comptoir_tier")
        subscription_id = obj.get("subscription")
        customer_id = obj.get("customer")
        if user_id and tier:
            trial = obj.get("metadata", {}).get("comptoir_trial") == "1"
            conn.execute(
                "UPDATE users SET plan_tier = ?, plan_status = ?, stripe_subscription_id = ?, stripe_customer_id = COALESCE(stripe_customer_id, ?), trial_used_at = CASE WHEN ? THEN COALESCE(trial_used_at, datetime('now')) ELSE trial_used_at END WHERE id = ?",
                (tier, "trialing" if trial else "active", subscription_id, customer_id, 1 if trial else 0, user_id),
            )
            conn.commit()

    elif event_type in ("customer.subscription.updated", "customer.subscription.created"):
        subscription_id = obj.get("id")
        items = obj.get("items", {}).get("data", [])
        price_id = items[0]["price"]["id"] if items and items[0].get("price") else None
        tier = _tier_from_stripe_price_id(price_id) if price_id else None
        status = obj.get("status")  # active | past_due | canceled | unpaid | trialing...
        period_end = obj.get("current_period_end")
        renews_at = datetime.fromtimestamp(period_end, tz=timezone.utc).isoformat() if period_end else None
        plan_status = "active" if status == "active" else status
        if tier:
            conn.execute(
                "UPDATE users SET plan_tier = ?, plan_status = ?, plan_renews_at = ? WHERE stripe_subscription_id = ?",
                (tier, plan_status, renews_at, subscription_id),
            )
        else:
            conn.execute(
                "UPDATE users SET plan_status = ?, plan_renews_at = ? WHERE stripe_subscription_id = ?",
                (plan_status, renews_at, subscription_id),
            )
        conn.commit()

    elif event_type == "customer.subscription.deleted":
        subscription_id = obj.get("id")
        conn.execute("UPDATE users SET plan_status = 'canceled' WHERE stripe_subscription_id = ?", (subscription_id,))
        conn.commit()

    conn.close()
    return {"ok": True}


def handle_shopify_install(token, body):
    """Step 1 of OAuth: the merchant has typed her shop's .myshopify.com domain into
    Comptoir — this checks she's allowed to connect one more channel, then hands back the
    Shopify authorize URL to redirect the whole tab to (same shape as Stripe Checkout)."""
    if not SHOPIFY_API_KEY or not SHOPIFY_API_SECRET:
        raise ApiError(503, "La connexion Shopify n'est pas encore configurée — réessayez plus tard.")
    user = user_from_token(token)
    if not user:
        raise ApiError(401, "Session invalide ou expirée.")
    require_verified_email(user)
    plan = require_active_plan(user)
    shop = str(body.get("shop", "")).strip().lower()
    if not SHOPIFY_SHOP_RE.match(shop):
        raise ApiError(400, "Adresse de boutique invalide — attendu : votre-boutique.myshopify.com")

    conn = get_db()
    already = conn.execute(
        "SELECT 1 FROM connected_channels WHERE user_id = ? AND channel_type = 'shopify'", (user["id"],)
    ).fetchone()
    if not already:
        limit = PLAN_LIMITS[plan["tier"]]["channels"]
        current = count_connected_channels(conn, user["id"])
        if limit is not None and current >= limit:
            conn.close()
            raise ApiError(402, f"Votre forfait autorise {limit} canal{'aux' if limit > 1 else ''} connecté{'s' if limit > 1 else ''} maximum — passez à un forfait supérieur pour en connecter davantage.")

    state = secrets.token_hex(24)
    conn.execute(
        "INSERT INTO shopify_oauth_states (state, user_id, shop_domain) VALUES (?, ?, ?)",
        (state, user["id"], shop),
    )
    conn.commit()
    conn.close()

    params = {
        "client_id": SHOPIFY_API_KEY,
        "scope": SHOPIFY_SCOPES,
        "redirect_uri": f"{PUBLIC_BASE_URL}/api/connectors/shopify/callback",
        "state": state,
    }
    return {"url": f"https://{shop}/admin/oauth/authorize?{urllib.parse.urlencode(params)}"}


def handle_shopify_callback(params: dict):
    """Step 2: Shopify redirects the merchant's browser back here after she approves the
    install. Not called by our own frontend — verified independently (Shopify's own HMAC
    on the query string, plus our own single-use state token) since anyone could otherwise
    hit this URL directly. Returns a redirect target (success or error) for the caller to
    send the browser to; never raises ApiError, because there's no JSON client waiting on
    the other end of a browser navigation."""
    shop = str(params.get("shop", "")).strip().lower()
    code = params.get("code")
    state = params.get("state")
    hmac_value = params.get("hmac")

    if not SHOPIFY_SHOP_RE.match(shop) or not code or not state:
        return f"{PUBLIC_BASE_URL}/?shopify=error#connecteurs"
    if not verify_shopify_hmac(params, hmac_value):
        print("[Shopify callback] signature HMAC invalide — requête rejetée.", file=sys.stderr)
        return f"{PUBLIC_BASE_URL}/?shopify=error#connecteurs"

    conn = get_db()
    row = conn.execute(
        "SELECT user_id, shop_domain, created_at FROM shopify_oauth_states WHERE state = ?", (state,)
    ).fetchone()
    if row:
        conn.execute("DELETE FROM shopify_oauth_states WHERE state = ?", (state,))  # single-use
        conn.commit()
    if not row or row["shop_domain"] != shop:
        conn.close()
        return f"{PUBLIC_BASE_URL}/?shopify=error#connecteurs"
    try:
        created_at = datetime.fromisoformat(row["created_at"] + "+00:00")
        if datetime.now(timezone.utc) - created_at > timedelta(minutes=SHOPIFY_OAUTH_STATE_TTL_MINUTES):
            conn.close()
            return f"{PUBLIC_BASE_URL}/?shopify=error#connecteurs"
    except ValueError:
        pass
    user_id = row["user_id"]

    user_row = conn.execute("SELECT id, email, plan_tier, plan_status, plan_renews_at FROM users WHERE id = ?", (user_id,)).fetchone()
    if not user_row:
        conn.close()
        return f"{PUBLIC_BASE_URL}/?shopify=error#connecteurs"
    try:
        plan = require_active_plan(user_row)
        already = conn.execute(
            "SELECT 1 FROM connected_channels WHERE user_id = ? AND channel_type = 'shopify'", (user_id,)
        ).fetchone()
        if not already:
            limit = PLAN_LIMITS[plan["tier"]]["channels"]
            current = count_connected_channels(conn, user_id)
            if limit is not None and current >= limit:
                conn.close()
                return f"{PUBLIC_BASE_URL}/?shopify=limit#connecteurs"
    except ApiError:
        conn.close()
        return f"{PUBLIC_BASE_URL}/?shopify=error#connecteurs"

    # Exchange the one-time code for a real access token — this is the one HTTP call in
    # this whole flow that actually proves we're allowed to read this shop's orders.
    try:
        token_resp = urllib.request.urlopen(
            urllib.request.Request(
                f"https://{shop}/admin/oauth/access_token",
                data=json.dumps({"client_id": SHOPIFY_API_KEY, "client_secret": SHOPIFY_API_SECRET, "code": code}).encode("utf-8"),
                method="POST",
                headers={"Content-Type": "application/json", "Accept": "application/json"},
            ),
            timeout=15,
        )
        access_token = json.loads(token_resp.read()).get("access_token")
    except Exception:
        traceback.print_exc(file=sys.stderr)
        access_token = None
    if not access_token:
        conn.close()
        return f"{PUBLIC_BASE_URL}/?shopify=error#connecteurs"

    conn.execute(
        """INSERT INTO shopify_shops (user_id, shop_domain, access_token) VALUES (?, ?, ?)
           ON CONFLICT(user_id, shop_domain) DO UPDATE SET access_token = excluded.access_token""",
        (user_id, shop, access_token),
    )
    conn.execute(
        "INSERT OR IGNORE INTO connected_channels (user_id, channel_type) VALUES (?, 'shopify')", (user_id,)
    )
    conn.commit()
    conn.close()

    # Subscribe to the events that keep Comptoir's copy of this shop's orders current.
    # Registering is best-effort per topic — one failing (e.g. a scope Shopify didn't
    # grant) shouldn't undo an otherwise-successful connection.
    for topic in SHOPIFY_WEBHOOK_TOPICS:
        try:
            shopify_admin_request(shop, access_token, "POST", "/webhooks.json", {
                "webhook": {"topic": topic, "address": f"{PUBLIC_BASE_URL}/api/connectors/shopify/webhook", "format": "json"}
            })
        except ApiError:
            pass

    return f"{PUBLIC_BASE_URL}/?shopify=success#connecteurs"


def handle_shopify_webhook(headers, raw_body: bytes):
    if not verify_shopify_webhook_hmac(raw_body, headers.get("X-Shopify-Hmac-Sha256")):
        raise ApiError(401, "Signature Shopify invalide.")
    shop = headers.get("X-Shopify-Shop-Domain", "")
    topic = headers.get("X-Shopify-Topic", "")
    conn = get_db()
    row = conn.execute("SELECT user_id FROM shopify_shops WHERE shop_domain = ?", (shop,)).fetchone()
    if not row:
        conn.close()
        # Not an error from Shopify's point of view (e.g. a webhook arriving just after a
        # disconnect) — 200 tells it to stop retrying rather than hammering a dead link.
        return {"ok": True, "ignored": True}
    user_id = row["user_id"]

    if topic == "app/uninstalled":
        conn.execute("DELETE FROM shopify_shops WHERE user_id = ? AND shop_domain = ?", (user_id, shop))
        conn.execute("DELETE FROM connected_channels WHERE user_id = ? AND channel_type = 'shopify'", (user_id,))
        conn.commit()
        conn.close()
        return {"ok": True}

    try:
        order = json.loads(raw_body.decode("utf-8"))
    except json.JSONDecodeError:
        conn.close()
        raise ApiError(400, "Corps de webhook JSON invalide.")
    return _ingest_order_core(conn, user_id, "shopify", shop, order)


def handle_woocommerce_webhook(connector_id: str, headers, raw_body: bytes):
    """WooCommerce (self-hosted — every merchant runs her own WordPress site, there's no
    central platform to register an OAuth app with) signs each webhook delivery with a
    per-webhook secret, sent as base64(HMAC-SHA256(raw_body, secret)) in
    X-WC-Webhook-Signature — no custom Authorization header support exists in WooCommerce's
    native webhook UI, so the connector is identified by this URL's own path instead, and
    that per-connector secret (reusing the same random value handle_create_connector
    already generates for the custom connector) is what the merchant pastes into
    WooCommerce's webhook 'Secret' field."""
    conn = get_db()
    row = conn.execute(
        "SELECT user_id, key FROM api_keys WHERE connector_id = ? AND channel_type = 'woocommerce'", (connector_id,)
    ).fetchone()
    if not row:
        conn.close()
        return {"ok": True, "ignored": True}  # disconnected connector — tell WooCommerce to stop retrying

    signature = headers.get("X-WC-Webhook-Signature", "")
    expected = base64.b64encode(hmac.new(row["key"].encode("utf-8"), raw_body, hashlib.sha256).digest()).decode("utf-8")
    if not hmac.compare_digest(expected, signature):
        conn.close()
        raise ApiError(401, "Signature WooCommerce invalide.")

    # WooCommerce sends an empty/near-empty body as a one-time 'ping' right when the
    # webhook is first created, to confirm the URL is reachable — not a real order, and
    # not something to error on (a non-2xx here can get the webhook auto-disabled).
    try:
        order = json.loads(raw_body.decode("utf-8")) if raw_body else {}
    except json.JSONDecodeError:
        conn.close()
        return {"ok": True, "ping": True}
    if not isinstance(order, dict) or not order:
        conn.close()
        return {"ok": True, "ping": True}

    try:
        return _ingest_order_core(conn, row["user_id"], "woocommerce", connector_id, order)
    except ApiError as e:
        # Same reasoning as the ping case: a real delivery failure (account over its plan
        # limit, no active plan, a malformed order) should be logged and swallowed here,
        # not returned as an HTTP error — WooCommerce disables a webhook after enough
        # failed deliveries, which would silently kill the whole connection over one bad
        # or rate-limited order rather than just that order.
        print(f"[WooCommerce webhook ignoré — {e.status}] connector={connector_id}: {e.message}", file=sys.stderr)
        return {"ok": True, "ignored": True}


# ---------------------------------------------------------------------------------------
# Visitor tracking (cookieless). A merchant pastes one <script> on a site they control
# (custom site, WooCommerce, Shopify); every page view is reported here. No cookie and no
# stored identifier: a visitor is counted once per day through a hash of (IP, user agent,
# site, day, server-side salt) kept only until the next day, then deleted — the same
# approach as Plausible/Umami — so no consent banner is needed and nothing personal is kept.
# Only daily aggregates (visitors/views by country and source) are stored.
# ---------------------------------------------------------------------------------------
TRACKING_CHANNELS = {"custom", "woocommerce", "shopify"}
TRACK_SALT = os.environ.get("TRACK_SALT") or secrets.token_hex(16)
_TRACK_RATE = {}
_TRACK_RATE_LOCK = threading.Lock()
_BOT_RE = re.compile(r"bot|crawl|spider|slurp|headless|preview|monitor|curl|wget|python-requests|facebookexternalhit", re.I)
_TZ_COUNTRY = {
    "Europe/Paris": "FR", "Europe/Brussels": "BE", "Europe/Zurich": "CH", "Europe/Berlin": "DE", "Europe/Madrid": "ES",
    "Europe/Rome": "IT", "Europe/Lisbon": "PT", "Europe/London": "GB", "Europe/Amsterdam": "NL", "Europe/Luxembourg": "LU",
    "Europe/Dublin": "IE", "Europe/Vienna": "AT", "Europe/Stockholm": "SE", "Europe/Copenhagen": "DK", "Europe/Oslo": "NO",
    "Europe/Warsaw": "PL", "America/Toronto": "CA", "America/Montreal": "CA", "America/Vancouver": "CA",
    "America/New_York": "US", "America/Chicago": "US", "America/Denver": "US", "America/Los_Angeles": "US",
    "Africa/Casablanca": "MA", "Africa/Tunis": "TN", "Africa/Algiers": "DZ", "Asia/Tokyo": "JP", "Australia/Sydney": "AU",
    "Indian/Reunion": "RE", "America/Martinique": "MQ", "America/Guadeloupe": "GP", "Pacific/Noumea": "NC",
}
_SEARCH = {"google": "Google", "bing": "Bing", "duckduckgo": "DuckDuckGo", "qwant": "Qwant", "ecosia": "Ecosia", "yahoo": "Yahoo"}
_SOCIAL = {"facebook": "Facebook", "instagram": "Instagram", "tiktok": "TikTok", "pinterest": "Pinterest", "t.co": "X (Twitter)",
           "twitter": "X (Twitter)", "linkedin": "LinkedIn", "youtube": "YouTube", "snapchat": "Snapchat", "whatsapp": "WhatsApp"}


def _classify_source(referrer, page_url):
    """Traffic source label: utm_source wins, else the referrer, else Direct."""
    page_host = urllib.parse.urlparse(page_url or "").hostname or ""
    qs = urllib.parse.parse_qs(urllib.parse.urlparse(page_url or "").query)
    utm = (qs.get("utm_source") or [""])[0].strip().lower()
    host = (urllib.parse.urlparse(referrer or "").hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    label = utm or host
    if not label or (host and host == (page_host[4:] if page_host.startswith("www.") else page_host) and not utm):
        return "Direct"
    for table in (_SEARCH, _SOCIAL):
        for key, name in table.items():
            if key in label:
                return name
    return label[:60]


def _visitor_country(headers, tz, lang):
    for h in ("CF-IPCountry", "X-Vercel-IP-Country", "CloudFront-Viewer-Country", "X-Country-Code"):
        v = (headers.get(h) or "").strip().upper()
        if len(v) == 2 and v.isalpha() and v not in ("XX", "T1"):
            return v
    if tz in _TZ_COUNTRY:
        return _TZ_COUNTRY[tz]
    m = re.match(r"^[a-z]{2,3}[-_]([A-Za-z]{2})$", str(lang or ""))
    return m.group(1).upper() if m else ""


def handle_track(body, headers, client_ip):
    """Public (no auth) — the site key is the only credential and grants write-only access
    to that one site's counters. Always answers quietly: a tracker must never break a page."""
    if not isinstance(body, dict):
        return
    site_key = str(body.get("site", ""))[:64]
    ua = headers.get("User-Agent", "")
    if not site_key or not ua or _BOT_RE.search(ua):
        return
    now = time.time()
    with _TRACK_RATE_LOCK:
        q = _TRACK_RATE.setdefault(client_ip, deque())
        while q and now - q[0] > 60:
            q.popleft()
        if len(q) >= 60:
            return
        q.append(now)
        if len(_TRACK_RATE) > 5000:
            _TRACK_RATE.clear()
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    source = _classify_source(str(body.get("ref", ""))[:500], str(body.get("url", ""))[:500])
    country = _visitor_country(headers, str(body.get("tz", ""))[:60], str(body.get("lang", ""))[:20])
    vhash = hashlib.sha256(f"{TRACK_SALT}|{day}|{site_key}|{client_ip}|{ua}".encode()).hexdigest()
    conn = get_db()
    try:
        if not conn.execute("SELECT 1 FROM tracking_sites WHERE site_key = ?", (site_key,)).fetchone():
            return
        first_today = conn.execute("INSERT OR IGNORE INTO tracking_seen (hash, day) VALUES (?, ?)", (vhash, day)).rowcount > 0
        conn.execute(
            """INSERT INTO tracking_stats (site_key, day, country, source, visitors, views) VALUES (?, ?, ?, ?, ?, 1)
               ON CONFLICT(site_key, day, country, source) DO UPDATE SET visitors = visitors + excluded.visitors, views = views + 1""",
            (site_key, day, country, source, 1 if first_today else 0),
        )
        conn.execute("UPDATE tracking_sites SET last_seen_at = datetime('now') WHERE site_key = ?", (site_key,))
        if secrets.randbelow(100) == 0:
            conn.execute("DELETE FROM tracking_seen WHERE day < ?", (day,))
        conn.commit()
    finally:
        conn.close()


def handle_tracking_site(token, body):
    user = user_from_token(token)
    if not user:
        raise ApiError(401, "Session invalide ou expirée.")
    connector_id = str(body.get("connectorId", "")).strip()
    channel_type = str(body.get("channelType", "")).strip().lower()
    if not connector_id:
        raise ApiError(400, "Le connecteur est requis.")
    if channel_type not in TRACKING_CHANNELS:
        raise ApiError(400, "Le suivi des visiteurs n'est pas disponible pour ce type de canal : la plateforme n'autorise pas l'ajout d'un script.")
    conn = get_db()
    row = conn.execute("SELECT site_key FROM tracking_sites WHERE user_id = ? AND connector_id = ?", (user["id"], connector_id)).fetchone()
    if row:
        key = row["site_key"]
    else:
        key = "cmp_" + secrets.token_urlsafe(12)
        conn.execute("INSERT INTO tracking_sites (site_key, user_id, connector_id, channel_type) VALUES (?, ?, ?, ?)", (key, user["id"], connector_id, channel_type))
        conn.commit()
    conn.close()
    return {"siteKey": key}


def handle_tracking_stats(token, params):
    user = user_from_token(token)
    if not user:
        raise ApiError(401, "Session invalide ou expirée.")
    date_re = re.compile(r"^\d{4}-\d{2}-\d{2}$")
    to_day = params.get("to") if date_re.match(params.get("to", "")) else datetime.now(timezone.utc).strftime("%Y-%m-%d")
    from_day = params.get("from") if date_re.match(params.get("from", "")) else (datetime.now(timezone.utc) - timedelta(days=29)).strftime("%Y-%m-%d")
    conn = get_db()
    sites = [dict(r) for r in conn.execute(
        "SELECT site_key, connector_id, channel_type, last_seen_at FROM tracking_sites WHERE user_id = ?", (user["id"],))]
    keys = [x["site_key"] for x in sites]
    out = {"sites": [], "daily": [], "sources": [], "countries": [], "visitors": 0, "views": 0}
    if keys:
        ph = ",".join("?" * len(keys))
        rng = (*keys, from_day, to_day)
        per_site = {r["site_key"]: (r["v"], r["w"]) for r in conn.execute(
            f"SELECT site_key, SUM(visitors) v, SUM(views) w FROM tracking_stats WHERE site_key IN ({ph}) AND day BETWEEN ? AND ? GROUP BY site_key", rng)}
        for x in sites:
            v, w = per_site.get(x["site_key"], (0, 0))
            out["sites"].append({"connectorId": x["connector_id"], "channelType": x["channel_type"], "lastSeenAt": x["last_seen_at"], "visitors": v or 0, "views": w or 0})
        out["daily"] = [{"day": r["day"], "visitors": r["v"]} for r in conn.execute(
            f"SELECT day, SUM(visitors) v FROM tracking_stats WHERE site_key IN ({ph}) AND day BETWEEN ? AND ? GROUP BY day ORDER BY day", rng)]
        out["sources"] = [{"source": r["source"], "visitors": r["v"]} for r in conn.execute(
            f"SELECT source, SUM(visitors) v FROM tracking_stats WHERE site_key IN ({ph}) AND day BETWEEN ? AND ? GROUP BY source HAVING v > 0 ORDER BY v DESC LIMIT 8", rng)]
        out["countries"] = [{"country": r["country"], "visitors": r["v"]} for r in conn.execute(
            f"SELECT country, SUM(visitors) v FROM tracking_stats WHERE site_key IN ({ph}) AND day BETWEEN ? AND ? GROUP BY country HAVING v > 0 ORDER BY v DESC LIMIT 8", rng)]
        out["visitors"] = sum(v for v, _ in per_site.values() if v)
        out["views"] = sum(w for _, w in per_site.values() if w)
    conn.close()
    return out


# ---------------------------------------------------------------------------------------
# Account rights (RGPD): export everything held about an account, and delete it.
# ---------------------------------------------------------------------------------------
def handle_account_export(token):
    user = user_from_token(token)
    if not user:
        raise ApiError(401, "Session invalide ou expirée.")
    conn = get_db()
    row = conn.execute(
        "SELECT email, created_at, consent_version, consent_accepted_at, plan_tier, plan_status, plan_renews_at, email_verified_at FROM users WHERE id = ?",
        (user["id"],),
    ).fetchone()
    state_row = conn.execute("SELECT data FROM app_state WHERE user_id = ?", (user["id"],)).fetchone()
    connectors = [dict(r) for r in conn.execute(
        "SELECT connector_id, label, channel_type, created_at FROM api_keys WHERE user_id = ?", (user["id"],))]
    channels = [dict(r) for r in conn.execute(
        "SELECT channel_type, connected_at FROM connected_channels WHERE user_id = ?", (user["id"],))]
    sites = [dict(r) for r in conn.execute(
        "SELECT connector_id, channel_type, created_at, last_seen_at FROM tracking_sites WHERE user_id = ?", (user["id"],))]
    conn.close()
    try:
        state = json.loads(state_row["data"]) if state_row else None
    except json.JSONDecodeError:
        state = None
    if isinstance(state, dict):
        # Secrets stay out of the export: an API key is a credential, not the user's data.
        for c in state.get("connectors", []) or []:
            if isinstance(c, dict):
                c.pop("apiKey", None)
    return {
        "exportedAt": datetime.now(timezone.utc).isoformat(),
        "account": dict(row) if row else {},
        "connectors": connectors,
        "channels": channels,
        "trackingSites": sites,
        "data": state,
    }


def handle_account_delete(token, body):
    user = user_from_token(token)
    if not user:
        raise ApiError(401, "Session invalide ou expirée.")
    password = body.get("password") if isinstance(body, dict) else None
    if not isinstance(password, str) or not password:
        raise ApiError(400, "Saisissez votre mot de passe pour confirmer la suppression.")
    conn = get_db()
    row = conn.execute(
        "SELECT password_hash, password_salt, stripe_subscription_id FROM users WHERE id = ?", (user["id"],)
    ).fetchone()
    if not row or not verify_password(password, row["password_hash"], row["password_salt"]):
        conn.close()
        raise ApiError(403, "Mot de passe incorrect.")
    # A live subscription must be cancelled BEFORE the account disappears — otherwise the
    # customer would keep being billed for something they can no longer reach.
    if row["stripe_subscription_id"] and STRIPE_SECRET_KEY:
        try:
            stripe_request("DELETE", f"/subscriptions/{row['stripe_subscription_id']}")
        except ApiError as e:
            if e.status != 404:
                conn.close()
                raise ApiError(502, "Impossible de résilier votre abonnement pour l'instant : le compte n'a pas été supprimé. Réessayez dans un instant ou contactez-nous.")
    # Every table that holds account data references users(id) ON DELETE CASCADE.
    conn.execute("DELETE FROM users WHERE id = ?", (user["id"],))
    conn.commit()
    conn.close()
    return {"ok": True}


def handle_health():
    """Cheap liveness/readiness probe for an uptime monitor: the database answers, and the
    backup job's last outcome is visible (without any credential)."""
    try:
        conn = get_db()
        conn.execute("SELECT 1").fetchone()
        conn.close()
    except Exception:
        return 503, {"ok": False, "db": False}
    configured = bool(R2_ACCOUNT_ID and R2_ACCESS_KEY_ID and R2_SECRET_ACCESS_KEY and R2_BUCKET_NAME)
    last = BACKUP_STATE.get("lastSuccessAt")
    stale = bool(last) and (time.time() - BACKUP_STATE["lastSuccessEpoch"]) > BACKUP_INTERVAL_SECONDS * 2.5
    if not configured:
        status = "not_configured"
    elif BACKUP_STATE.get("lastError") and not last:
        status = "failing"
    elif stale or BACKUP_STATE.get("lastError"):
        status = "stale"
    elif last:
        status = "ok"
    else:
        status = "pending"
    return 200, {"ok": True, "db": True, "backup": {"status": status, "lastSuccessAt": last, "lastError": BACKUP_STATE.get("lastError")}}


# ---------------------------------------------------------------------------------------
# Email notifications (new sales, low stock). Events are queued while an order is ingested
# and sent by a background worker as ONE grouped email: a bulk resync of 500 orders must
# never mean 500 emails. Preferences live in the account's state document
# (data["notifications"]) so the Paramètres screen and the server share one source of truth.
# ---------------------------------------------------------------------------------------
NOTIFY_DEFAULTS = {"sales": False, "stock": False, "monthly": False, "frequency": "instant"}  # opt-in
NOTIFY_COALESCE_SECONDS = 120     # wait a little so a burst of orders becomes one email
NOTIFY_MIN_GAP_SECONDS = 300      # instant mode: at most one email every 5 minutes
NOTIFY_DIGEST_HOUR = 8            # daily mode: sent once a day from 08:00 (Paris)
NOTIFY_MAX_ITEMS = 10             # rows listed per section, the rest is summarised
NOTIFY_RECENT_DAYS = 3            # a backfilled old order is history, not news


def notify_prefs(data):
    raw = data.get("notifications") if isinstance(data, dict) else None
    prefs = dict(NOTIFY_DEFAULTS)
    # Opt-in: only preferences the merchant actually set (the app marks them "configured")
    # count. Anything else — including values a client wrote before notifications were
    # opt-in — is ignored, so nobody is emailed without having asked for it.
    if isinstance(raw, dict) and raw.get("configured") is True:
        for key in ("sales", "stock", "monthly"):
            if isinstance(raw.get(key), bool):
                prefs[key] = raw[key]
        if raw.get("frequency") in ("instant", "daily"):
            prefs["frequency"] = raw["frequency"]
    return prefs


def _is_recent(date_str):
    try:
        d = datetime.fromisoformat(str(date_str).replace("Z", "+00:00"))
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) - d <= timedelta(days=NOTIFY_RECENT_DAYS)
    except (ValueError, TypeError):
        return True


def _stock_event(events, product, before, after):
    """Only the moment stock CROSSES a line is news — not every sale while already low."""
    if after >= before:
        return
    threshold = product.get("threshold", 10) or 0
    if after <= 0 < before:
        level = "out"
    elif before > threshold >= after and after > 0:
        level = "low"
    else:
        return
    events.append({"kind": "stock", "name": product.get("name", "Produit"), "stock": after, "threshold": threshold, "level": level})


CHANNEL_LABELS = {"shopify": "Shopify", "woocommerce": "WooCommerce", "custom": "Site personnalisé", "etsy": "Etsy", "instagram": "Instagram Shop", "tiktok": "TikTok Shop"}


def connector_label_for(data, channel_type):
    for c in (data.get("connectors") or []):
        if isinstance(c, dict) and c.get("type") == channel_type and c.get("label"):
            return str(c["label"])
    return CHANNEL_LABELS.get(channel_type, channel_type)


def _queue_events(conn, user_id, data, events):
    if not events:
        return
    prefs = notify_prefs(data)
    for ev in events:
        wanted = prefs["sales"] if ev["kind"] == "sale" else prefs["stock"]
        if wanted:
            conn.execute("INSERT INTO notification_queue (user_id, kind, payload) VALUES (?, ?, ?)", (user_id, ev["kind"], json.dumps(ev)))


def _eur(amount):
    return f"{float(amount):,.2f}".replace(",", " ").replace(".", ",") + " €"


def _flag(cc):
    return "".join(chr(0x1F1E6 + ord(c) - 65) for c in cc.upper()) if isinstance(cc, str) and len(cc) == 2 and cc.isalpha() else ""


def build_notification_email(events):
    """Returns (subject, text, html) for a list of queued events — the single template used
    for every notification (also for the preview and test email in Paramètres)."""
    sales = [e for e in events if e.get("kind") == "sale"]
    stocks = [e for e in events if e.get("kind") == "stock"]
    parts, text_lines = [], []
    if sales:
        total = sum(float(e.get("amount", 0)) for e in sales)
        rows = ""
        for e in sales[:NOTIFY_MAX_ITEMS]:
            who = html.escape(str(e.get("customer", "Client")))
            flag = _flag(e.get("country"))
            prod = html.escape(str(e.get("product") or "—")) + (f" × {int(e.get('quantity', 1))}" if e.get("product") else "")
            rows += (
                f'<tr><td style="padding:10px 0; border-bottom:1px solid #E1E3DC;">'
                f'<div style="font-size:14px; font-weight:700; color:#1B211D;">{flag + " " if flag else ""}{who}</div>'
                f'<div style="font-size:12.5px; color:#8A9186;">{prod} · {html.escape(str(e.get("channel", "")))}</div></td>'
                f'<td align="right" style="padding:10px 0; border-bottom:1px solid #E1E3DC; font-size:15px; font-weight:800; color:#146356; white-space:nowrap;">{_eur(e.get("amount", 0))}</td></tr>'
            )
            text_lines.append(f"- {e.get('customer', 'Client')} : {_eur(e.get('amount', 0))} ({e.get('product') or 'sans produit'})")
        more = len(sales) - NOTIFY_MAX_ITEMS
        if more > 0:
            rows += f'<tr><td colspan="2" style="padding:10px 0; font-size:12.5px; color:#8A9186;">… et {more} autre{"s" if more > 1 else ""} vente{"s" if more > 1 else ""}</td></tr>'
            text_lines.append(f"… et {more} autres ventes")
        title = "Nouvelle vente" if len(sales) == 1 else f"{len(sales)} nouvelles ventes"
        parts.append(
            f'<div style="font-size:11.5px; letter-spacing:.08em; text-transform:uppercase; color:#8A9186; font-weight:700; margin:4px 0 2px;">{title}'
            + (f" · {_eur(total)}" if len(sales) > 1 else "") + "</div>"
            f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:18px;">{rows}</table>'
        )
    if stocks:
        rows = ""
        for e in stocks[:NOTIFY_MAX_ITEMS]:
            out = e.get("level") == "out"
            pill = ('<span style="background:#FBE4E4; color:#B3261E; padding:3px 9px; border-radius:10px; font-size:12px; font-weight:700;">Rupture</span>' if out
                    else f'<span style="background:#FDF0D5; color:#8A5A00; padding:3px 9px; border-radius:10px; font-size:12px; font-weight:700;">{int(e.get("stock", 0))} restant{"s" if int(e.get("stock", 0)) > 1 else ""}</span>')
            rows += (
                f'<tr><td style="padding:10px 0; border-bottom:1px solid #E1E3DC; font-size:14px; font-weight:700; color:#1B211D;">{html.escape(str(e.get("name", "")))}'
                f'<div style="font-size:12.5px; font-weight:400; color:#8A9186;">Seuil d\'alerte : {int(e.get("threshold", 0))}</div></td>'
                f'<td align="right" style="padding:10px 0; border-bottom:1px solid #E1E3DC;">{pill}</td></tr>'
            )
            text_lines.append(f"- {e.get('name')} : {'rupture' if out else str(int(e.get('stock', 0))) + ' restant(s)'} (seuil {int(e.get('threshold', 0))})")
        parts.append(
            '<div style="font-size:11.5px; letter-spacing:.08em; text-transform:uppercase; color:#8A9186; font-weight:700; margin:4px 0 2px;">Stock à surveiller</div>'
            f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:8px;">{rows}</table>'
        )
    if sales and stocks:
        heading = f"{len(sales)} vente{'s' if len(sales) > 1 else ''} et {len(stocks)} alerte{'s' if len(stocks) > 1 else ''} de stock"
        subject = f"Comptoir — {heading}"
        target = "#"
    elif sales:
        heading = f"Nouvelle vente de {_eur(sales[0].get('amount', 0))}" if len(sales) == 1 else f"{len(sales)} nouvelles ventes"
        subject = f"Comptoir — {heading}" + (f" · {sales[0].get('customer', '')}" if len(sales) == 1 else "")
        target = "#ventes"
    else:
        out_count = sum(1 for e in stocks if e.get("level") == "out")
        heading = f"{stocks[0].get('name')} : {'rupture de stock' if stocks[0].get('level') == 'out' else 'stock bas'}" if len(stocks) == 1 else f"{len(stocks)} produits à réapprovisionner"
        subject = f"Comptoir — {heading}"
        target = "#stock"
    footnote = (
        "Vous recevez cet email car les notifications sont activées sur votre compte. "
        f'<a href="{PUBLIC_BASE_URL}/#parametres" style="color:#146356;">Les modifier ou les désactiver</a> dans Paramètres.'
    )
    body = "".join(parts)
    html_body = branded_email_html(heading, body, footnote, "Ouvrir Comptoir", f"{PUBLIC_BASE_URL}/{target}")
    text = heading + "\n\n" + "\n".join(text_lines) + f"\n\nOuvrir Comptoir : {PUBLIC_BASE_URL}/{target}\nModifier ou désactiver les notifications : {PUBLIC_BASE_URL}/#parametres"
    return subject, text, html_body


def _sample_events(kind="digest"):
    sale = {"kind": "sale", "customer": "Marie Dupont", "amount": 42.9, "product": "Bougie parfumée Cèdre", "quantity": 2, "channel": "Shopify", "country": "FR"}
    sale2 = {"kind": "sale", "customer": "Lucas Martin", "amount": 89.0, "product": "Plaid en laine", "quantity": 1, "channel": "Site personnalisé", "country": "BE"}
    low = {"kind": "stock", "name": "Bougie parfumée Cèdre", "stock": 4, "threshold": 10, "level": "low"}
    out = {"kind": "stock", "name": "Savon artisanal", "stock": 0, "threshold": 10, "level": "out"}
    return {"sale": [sale], "stock": [low, out], "digest": [sale, sale2, low, out]}.get(kind, [sale, low])



MONTHS_FR = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"]
VAT_RATE = 0.20


def _parse_dt(value):
    try:
        d = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return None


def _month_bounds(year, month):
    start = datetime(year, month, 1, tzinfo=timezone.utc)
    end = datetime(year + (month == 12), month % 12 + 1, 1, tzinfo=timezone.utc)
    return start, end


def _expense_total(expenses, start, end):
    total = 0.0
    for e in expenses or []:
        if not isinstance(e, dict):
            continue
        d = _parse_dt(e.get("date"))
        try:
            amount = float(e.get("amount", 0) or 0)
        except (TypeError, ValueError):
            continue
        if d is None:
            continue
        rec = e.get("recurrence") or "none"
        guard = 0
        while d < end and guard < 600:
            if d >= start:
                total += amount
            if rec == "none":
                break
            if rec == "weekly":
                d += timedelta(days=7)
            elif rec == "monthly":
                d = d.replace(year=d.year + (d.month == 12), month=d.month % 12 + 1, day=min(d.day, 28))
            elif rec == "yearly":
                d = d.replace(year=d.year + 1, day=min(d.day, 28))
            else:
                break
            guard += 1
    return total


def compute_month_summary(data, year, month):
    """Same rules as the app's Vue d'ensemble / Comptabilité (returns excluded from revenue,
    VAT estimated at 20 %, purchase cost x quantity, expenses incl. recurring ones)."""
    start, end = _month_bounds(year, month)
    pstart, pend = _month_bounds(year - (month == 1), 12 if month == 1 else month - 1)
    products = {p.get("id"): p for p in (data.get("products") or []) if isinstance(p, dict)}
    cur, prev_ca, returns = [], 0.0, 0
    for o in data.get("orders") or []:
        d = _parse_dt(o.get("date")) if isinstance(o, dict) else None
        if d is None:
            continue
        if start <= d < end:
            if o.get("status") == "retour":
                returns += 1
            else:
                cur.append(o)
        elif pstart <= d < pend and o.get("status") != "retour":
            prev_ca += float(o.get("amount", 0) or 0)
    ca = sum(float(o.get("amount", 0) or 0) for o in cur)
    cost = 0.0
    by_product, by_country, unset_cost = {}, {}, set()
    for o in cur:
        p = products.get(o.get("productId"))
        qty = int(o.get("quantity") or 1)
        if p:
            cost += float(p.get("costPrice") or 0) * qty
            by_product[p.get("name", "Produit")] = by_product.get(p.get("name", "Produit"), 0) + qty
            if not p.get("costPrice"):
                unset_cost.add(p.get("name", "Produit"))
        if o.get("country"):
            by_country[str(o["country"]).upper()] = by_country.get(str(o["country"]).upper(), 0) + 1
    ht = ca / (1 + VAT_RATE)
    expenses = _expense_total(data.get("expenses"), start, end)
    total_orders = len(cur) + returns
    return {
        "label": f"{MONTHS_FR[month - 1]} {year}", "orders": len(cur), "returns": returns,
        "returnRate": (returns / total_orders * 100) if total_orders else 0.0,
        "ca": ca, "avgBasket": ca / len(cur) if cur else 0.0,
        "caDelta": ((ca - prev_ca) / prev_ca * 100) if prev_ca else None,
        "tva": ca - ht, "cost": cost, "expenses": expenses, "net": ht - cost - expenses,
        "topProducts": sorted(by_product.items(), key=lambda kv: -kv[1])[:3],
        "topCountries": sorted(by_country.items(), key=lambda kv: -kv[1])[:3],
        "missingCost": sorted(unset_cost), "noExpenses": not (data.get("expenses") or []),
    }


def build_monthly_email(sm):
    def stat(label, value, sub=""):
        return (f'<td width="50%" style="padding:6px;"><div style="background:#F3F4F1; border-radius:10px; padding:12px 14px;">'
                f'<div style="font-size:11.5px; color:#8A9186;">{label}</div>'
                f'<div style="font-size:19px; font-weight:800; color:#1B211D; margin-top:2px;">{value}</div>'
                + (f'<div style="font-size:11.5px; color:#8A9186; margin-top:2px;">{sub}</div>' if sub else "") + "</div></td>")
    delta = "" if sm["caDelta"] is None else f'{"+" if sm["caDelta"] >= 0 else ""}{sm["caDelta"]:.0f} % vs mois précédent'
    grid = ('<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin:6px -6px 14px;"><tr>'
            + stat("Chiffre d'affaires", _eur(sm["ca"]), delta) + stat("Commandes", str(sm["orders"]), f'{sm["returns"]} retour{"s" if sm["returns"] > 1 else ""} ({sm["returnRate"]:.0f} %)') + "</tr><tr>"
            + stat("Panier moyen", _eur(sm["avgBasket"])) + stat("Bénéfice net estimé", _eur(sm["net"]), "après TVA, coûts et charges") + "</tr></table>")
    lines = [
        ("TVA à reverser (estimée à 20 %)", "− " + _eur(sm["tva"])),
        ("Coût d'achat des produits vendus", "− " + _eur(sm["cost"])),
        ("Charges du mois", "− " + _eur(sm["expenses"])),
    ]
    detail = "".join(f'<tr><td style="padding:7px 0; border-bottom:1px solid #E1E3DC; font-size:13.5px; color:#566058;">{a}</td><td align="right" style="padding:7px 0; border-bottom:1px solid #E1E3DC; font-size:13.5px; font-weight:700; color:#1B211D; white-space:nowrap;">{b}</td></tr>' for a, b in lines)
    detail = f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:16px;">{detail}</table>'
    extras = ""
    if sm["topProducts"]:
        extras += ('<div style="font-size:11.5px; letter-spacing:.08em; text-transform:uppercase; color:#8A9186; font-weight:700; margin:4px 0 6px;">Produits les plus vendus</div>'
                   + "".join(f'<div style="font-size:13.5px; color:#1B211D; padding:3px 0;">{html.escape(str(n))} <span style="color:#8A9186;">· {q} vendu{"s" if q > 1 else ""}</span></div>' for n, q in sm["topProducts"]))
    if sm["topCountries"]:
        extras += ('<div style="font-size:11.5px; letter-spacing:.08em; text-transform:uppercase; color:#8A9186; font-weight:700; margin:14px 0 6px;">Pays</div>'
                   + "".join(f'<div style="font-size:13.5px; color:#1B211D; padding:3px 0;">{_flag(c)} {html.escape(c)} <span style="color:#8A9186;">· {n} vente{"s" if n > 1 else ""}</span></div>' for c, n in sm["topCountries"]))
    gaps = []
    if sm["missingCost"]:
        names = ", ".join(html.escape(n) for n in sm["missingCost"][:3]) + (" …" if len(sm["missingCost"]) > 3 else "")
        gaps.append(f"{len(sm['missingCost'])} produit{'s' if len(sm['missingCost']) > 1 else ''} vendu{'s' if len(sm['missingCost']) > 1 else ''} sans prix d'achat ({names})")
    if sm["noExpenses"]:
        gaps.append("aucune charge enregistrée")
    warn = ('<div style="margin-top:18px; background:#FDF0D5; border-radius:10px; padding:12px 14px; font-size:12.5px; line-height:1.6; color:#6B4A00;">'
            "<b>Ces chiffres dépendent des données saisies dans Comptoir</b> : commandes reçues de vos plateformes, prix d'achat de vos produits et charges renseignées. "
            + ("Ici, il manque : " + " ; ".join(gaps) + ", donc le bénéfice est probablement surestimé. " if gaps else "")
            + f'Complétez-les dans <a href="{PUBLIC_BASE_URL}/#catalogue" style="color:#6B4A00;">Mon catalogue</a> et <a href="{PUBLIC_BASE_URL}/#comptabilite" style="color:#6B4A00;">Comptabilité</a>. '
            "Estimation simplifiée, elle ne remplace pas votre comptable.</div>")
    footnote = (f'Vous recevez ce bilan car le résumé mensuel est activé sur votre compte. <a href="{PUBLIC_BASE_URL}/#parametres" style="color:#146356;">Le désactiver</a> dans Paramètres.')
    heading = f"Votre bilan de {sm['label']}"
    body = grid + detail + extras + warn
    html_body = branded_email_html(heading, body, footnote, "Voir le détail dans Comptoir", f"{PUBLIC_BASE_URL}/#comptabilite")
    text = (f"{heading}\n\nChiffre d'affaires : {_eur(sm['ca'])}\nCommandes : {sm['orders']} (retours : {sm['returns']})\nPanier moyen : {_eur(sm['avgBasket'])}\n"
            f"TVA estimée : {_eur(sm['tva'])}\nCoût d'achat : {_eur(sm['cost'])}\nCharges : {_eur(sm['expenses'])}\nBénéfice net estimé : {_eur(sm['net'])}\n\n"
            "Ces chiffres dépendent des données saisies dans Comptoir (commandes, prix d'achat, charges).\n" + (("Il manque : " + " ; ".join(gaps) + ".\n") if gaps else "")
            + f"\nDétail : {PUBLIC_BASE_URL}/#comptabilite\nDésactiver : {PUBLIC_BASE_URL}/#parametres")
    return f"Comptoir — Votre bilan de {sm['label']}", text, html_body


def _sample_month_summary():
    return {"label": "septembre 2026", "orders": 62, "returns": 6, "returnRate": 8.8, "ca": 2245.33, "avgBasket": 36.22, "caDelta": 12.4,
            "tva": 374.22, "cost": 512.0, "expenses": 71.0, "net": 914.11,
            "topProducts": [("Bougie parfumée Cèdre", 41), ("Savon artisanal", 28), ("Vase en grès", 9)], "topCountries": [("FR", 48), ("BE", 9), ("CH", 5)],
            "missingCost": ["Plaid en laine"], "noExpenses": False}


def process_monthly_summaries():
    """From the 1st to the 5th of each month (08:00 Paris and after), send last month's summary
    to every account that opted in — once. Outside that window this returns immediately."""
    paris = _paris_now()
    if paris.day > 5 or paris.hour < NOTIFY_DIGEST_HOUR:
        return
    py, pm = paris.year - (paris.month == 1), 12 if paris.month == 1 else paris.month - 1
    key = f"{py}-{pm:02d}"
    conn = get_db()
    try:
        rows = conn.execute("SELECT u.id, u.email, s.data FROM users u JOIN app_state s ON s.user_id = u.id WHERE u.email_verified_at IS NOT NULL AND u.plan_status IN ('active','trialing','past_due')").fetchall()
        for r in rows:
            try:
                data = json.loads(r["data"])
            except json.JSONDecodeError:
                continue
            if not notify_prefs(data)["monthly"]:
                continue
            st = conn.execute("SELECT last_monthly FROM notification_state WHERE user_id = ?", (r["id"],)).fetchone()
            if st and st["last_monthly"] == key:
                continue
            summary = compute_month_summary(data, py, pm)
            if summary["orders"] + summary["returns"] > 0:
                subject, text, html_body = build_monthly_email(summary)
                send_email(r["email"], subject, text, html_body)
            conn.execute("INSERT INTO notification_state (user_id, last_monthly) VALUES (?, ?) ON CONFLICT(user_id) DO UPDATE SET last_monthly = excluded.last_monthly", (r["id"], key))
            conn.commit()
    finally:
        conn.close()


def _paris_now():
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("Europe/Paris"))
    except Exception:
        return datetime.now(timezone.utc) + timedelta(hours=2)


def process_notifications():
    """One pass of the notification worker: for every account with queued events, decide
    whether it's time to send (instant mode: after a short coalescing delay and at most every
    few minutes; daily mode: once a day from 08:00), then send a single grouped email."""
    conn = get_db()
    try:
        users = conn.execute("SELECT user_id, MIN(created_at) AS oldest FROM notification_queue GROUP BY user_id").fetchall()
        for u in users:
            uid = u["user_id"]
            urow = conn.execute("SELECT email, email_verified_at, plan_status FROM users WHERE id = ?", (uid,)).fetchone()
            srow = conn.execute("SELECT data FROM app_state WHERE user_id = ?", (uid,)).fetchone()
            if not urow or not srow or not urow["email_verified_at"] or urow["plan_status"] not in ("active", "trialing", "past_due"):
                conn.execute("DELETE FROM notification_queue WHERE user_id = ?", (uid,))
                continue
            try:
                prefs = notify_prefs(json.loads(srow["data"]))
            except json.JSONDecodeError:
                prefs = dict(NOTIFY_DEFAULTS)
            last = conn.execute("SELECT last_sent_at FROM notification_state WHERE user_id = ?", (uid,)).fetchone()
            last_dt = datetime.fromisoformat(last["last_sent_at"]).replace(tzinfo=timezone.utc) if last and last["last_sent_at"] else None
            oldest = datetime.fromisoformat(u["oldest"]).replace(tzinfo=timezone.utc)
            now = datetime.now(timezone.utc)
            if prefs["frequency"] == "daily":
                paris = _paris_now()
                if paris.hour < NOTIFY_DIGEST_HOUR:
                    continue
                if last_dt and last_dt.astimezone(paris.tzinfo).date() == paris.date():
                    continue
            else:
                if (now - oldest).total_seconds() < NOTIFY_COALESCE_SECONDS:
                    continue
                if last_dt and (now - last_dt).total_seconds() < NOTIFY_MIN_GAP_SECONDS:
                    continue
            rows = conn.execute("SELECT id, kind, payload FROM notification_queue WHERE user_id = ? ORDER BY id LIMIT 500", (uid,)).fetchall()
            ids = [r["id"] for r in rows]
            events = []
            for r in rows:
                if (r["kind"] == "sale" and prefs["sales"]) or (r["kind"] == "stock" and prefs["stock"]):
                    try:
                        events.append(json.loads(r["payload"]))
                    except json.JSONDecodeError:
                        pass
            if events:
                subject, text, html_body = build_notification_email(events)
                send_email(urow["email"], subject, text, html_body)
            conn.executemany("DELETE FROM notification_queue WHERE id = ?", [(i,) for i in ids])
            conn.execute("INSERT INTO notification_state (user_id, last_sent_at) VALUES (?, datetime('now')) ON CONFLICT(user_id) DO UPDATE SET last_sent_at = excluded.last_sent_at", (uid,))
            conn.commit()
        conn.commit()
    finally:
        conn.close()


def _notify_loop():
    while True:
        try:
            process_notifications()
            process_monthly_summaries()
        except Exception:
            traceback.print_exc(file=sys.stderr)
        time.sleep(30)


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=ROOT, **kwargs)

    def end_headers(self):
        if getattr(self, "_track_cors", False):
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
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

    def _body_length(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
        except ValueError:
            raise ApiError(400, "En-tête Content-Length invalide.")
        if length < 0 or length > MAX_BODY_BYTES:
            raise ApiError(413, "Requête trop volumineuse.")
        return length

    def _read_json_body(self):
        length = self._body_length()
        if length == 0:
            return {}
        raw = self.rfile.read(length)
        try:
            return json.loads(raw or b"{}")
        except json.JSONDecodeError:
            raise ApiError(400, "Corps de requête JSON invalide.")

    def _redirect_www(self):
        """www.getcomptoir.fr -> getcomptoir.fr (301), so one canonical address serves the
        app and search engines don't index two copies of the site."""
        host = (self.headers.get("Host") or "").split(":")[0].lower()
        if host.startswith("www."):
            self.send_response(301)
            self.send_header("Location", f"https://{host[4:]}{self.path}")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return True
        return False

    def _client_ip(self):
        fwd = self.headers.get("X-Forwarded-For", "")
        return (fwd.split(",")[0].strip() if fwd else self.client_address[0]) or "?"

    def do_OPTIONS(self):
        if urllib.parse.urlparse(self.path).path == "/api/track":
            self._track_cors = True
            self.send_response(204)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        self.send_error(404)

    def do_POST(self):
        if self._redirect_www():
            return
        path = urllib.parse.urlparse(self.path).path
        if not path.startswith("/api/"):
            self.send_error(404)
            return
        if path == "/api/track":
            # Public beacon endpoint: cross-origin by design (it runs on the merchant's own
            # site), replies 204 whatever happens so it can never disturb the page.
            self._track_cors = True
            try:
                handle_track(self._read_json_body(), self.headers, self._client_ip())
            except Exception:
                pass
            self.send_response(204)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        # Stripe's webhook needs the RAW request body to verify its signature — parsing it
        # as JSON first (like every other route below) would still work for reading the
        # event, but the signature is computed over the exact bytes Stripe sent, so this
        # route reads and verifies before any JSON parsing happens.
        if path == "/api/stripe/webhook":
            try:
                length = self._body_length()
                raw = self.rfile.read(length) if length else b""
                return self._send_json(200, handle_stripe_webhook(raw, self.headers.get("Stripe-Signature")))
            except ApiError as e:
                return self._send_json(e.status, {"error": e.message})
            except Exception as e:  # pragma: no cover
                return self._send_server_error(e)
        # Same reasoning as Stripe's webhook above — Shopify signs the exact raw bytes.
        if path == "/api/connectors/shopify/webhook":
            try:
                length = self._body_length()
                raw = self.rfile.read(length) if length else b""
                return self._send_json(200, handle_shopify_webhook(self.headers, raw))
            except ApiError as e:
                return self._send_json(e.status, {"error": e.message})
            except Exception as e:  # pragma: no cover
                return self._send_server_error(e)
        woo_webhook_match = re.match(r"^/api/connectors/woocommerce/webhook/([^/]+)$", path)
        if woo_webhook_match:
            try:
                length = self._body_length()
                raw = self.rfile.read(length) if length else b""
                return self._send_json(200, handle_woocommerce_webhook(woo_webhook_match.group(1), self.headers, raw))
            except ApiError as e:
                return self._send_json(e.status, {"error": e.message})
            except Exception as e:  # pragma: no cover
                return self._send_server_error(e)
        try:
            body = self._read_json_body()
            if path == "/api/signup":
                return self._send_json(200, handle_signup(body))
            if path == "/api/login":
                return self._send_json(200, handle_login(body))
            if path == "/api/password-reset/request":
                return self._send_json(200, handle_password_reset_request(body))
            if path == "/api/password-reset/confirm":
                return self._send_json(200, handle_password_reset_confirm(body))
            if path == "/api/email-verify/confirm":
                return self._send_json(200, handle_email_verify_confirm(body))
            if path == "/api/email-verify/resend":
                return self._send_json(200, handle_email_verify_resend(self._bearer_token()))
            if path == "/api/logout":
                return self._send_json(200, handle_logout(self._bearer_token()))
            if path == "/api/connectors/custom":
                return self._send_json(200, handle_create_connector(self._bearer_token(), body))
            if path == "/api/connectors/channel":
                return self._send_json(200, handle_connect_channel(self._bearer_token(), body))
            if path == "/api/tracking/site":
                return self._send_json(200, handle_tracking_site(self._bearer_token(), body))
            if path == "/api/ingest/orders":
                return self._send_json(200, handle_ingest_order(self._bearer_token(), body))
            if path == "/api/ingest/orders/bulk":
                return self._send_json(200, handle_ingest_orders_bulk(self._bearer_token(), body))
            if path == "/api/billing/checkout":
                return self._send_json(200, handle_billing_checkout(self._bearer_token(), body))
            if path == "/api/billing/portal":
                return self._send_json(200, handle_billing_portal(self._bearer_token()))
            if path == "/api/connectors/shopify/install":
                return self._send_json(200, handle_shopify_install(self._bearer_token(), body))
            if path == "/api/connectors/woocommerce":
                return self._send_json(200, handle_create_connector(self._bearer_token(), body, channel_type="woocommerce"))
            raise ApiError(404, "Route inconnue.")
        except ApiError as e:
            self._send_json(e.status, {"error": e.message})
        except Exception as e:  # pragma: no cover
            self._send_server_error(e)

    def do_GET(self):
        if self._redirect_www():
            return
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        if path == "/api/connectors/shopify/callback":
            # Shopify navigates the merchant's actual browser here — this always ends in
            # a redirect back into the app, never a JSON response (there's no fetch() on
            # the other end of a top-level page navigation).
            params = {k: v[0] for k, v in urllib.parse.parse_qs(parsed.query).items()}
            target = handle_shopify_callback(params)
            self.send_response(302)
            self.send_header("Location", target)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        if path == "/api/me":
            try:
                return self._send_json(200, handle_me(self._bearer_token()))
            except ApiError as e:
                return self._send_json(e.status, {"error": e.message})
        if path == "/api/launch":
            return self._send_json(200, handle_launch())
        if path == "/api/health":
            status, payload = handle_health()
            return self._send_json(status, payload)
        if path == "/api/account/export":
            try:
                return self._send_json(200, handle_account_export(self._bearer_token()))
            except ApiError as e:
                return self._send_json(e.status, {"error": e.message})
        if path == "/api/tracking/stats":
            try:
                params = {k: v[0] for k, v in urllib.parse.parse_qs(parsed.query).items()}
                return self._send_json(200, handle_tracking_stats(self._bearer_token(), params))
            except ApiError as e:
                return self._send_json(e.status, {"error": e.message})
        if path == "/api/state":
            try:
                return self._send_json(200, handle_get_state(self._bearer_token()))
            except ApiError as e:
                return self._send_json(e.status, {"error": e.message})
        if not self._static_allowed():
            return self.send_error(404)
        return super().do_GET()

    def do_HEAD(self):
        if self._redirect_www():
            return
        if not self._static_allowed():
            return self.send_error(404)
        return super().do_HEAD()

    # The static handler serves the whole repo directory, so anything that isn't a public
    # web asset (server.py, Procfile, requirements.txt, dotfiles, any database file) must be
    # refused explicitly — an allowlist of extensions rather than a list of known-bad names.
    _PUBLIC_EXT = {".html", ".css", ".js", ".json", ".png", ".jpg", ".jpeg", ".svg", ".ico", ".webp", ".xml", ".txt", ".woff2", ".webmanifest"}
    _PRIVATE_NAMES = {"requirements.txt"}

    def _static_allowed(self):
        raw = urllib.parse.unquote(urllib.parse.urlparse(self.path).path)
        parts = [x for x in raw.split("/") if x]
        if any(x.startswith(".") or x == "__pycache__" for x in parts):
            return False
        fs_path = self.translate_path(self.path)
        if os.path.isdir(fs_path):
            # A directory is only served through its index page — never as a file listing.
            return os.path.exists(os.path.join(fs_path, "index.html"))
        name = os.path.basename(fs_path).lower()
        if name in self._PRIVATE_NAMES:
            return False
        return os.path.splitext(name)[1] in self._PUBLIC_EXT

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
        try:
            if path == "/api/account":
                return self._send_json(200, handle_account_delete(self._bearer_token(), self._read_json_body()))
            channel_match = re.match(r"^/api/connectors/channel/([^/]+)$", path)
            if channel_match:
                return self._send_json(200, handle_disconnect_channel(self._bearer_token(), channel_match.group(1)))
            connector_match = re.match(r"^/api/connectors/([^/]+)$", path)
            if connector_match:
                return self._send_json(200, handle_delete_connector(self._bearer_token(), connector_match.group(1)))
            self.send_error(404)
        except ApiError as e:
            self._send_json(e.status, {"error": e.message})
        except Exception as e:  # pragma: no cover
            self._send_server_error(e)

    def log_message(self, fmt, *args):
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))


# Automatic database backups to Cloudflare R2 — the SQLite file lives on a single Railway
# volume with no copy anywhere else; a disk incident there would silently erase every real
# account's data with no way back. R2 is S3-compatible, so this is a real (if partial) AWS
# Signature Version 4 implementation using only stdlib hashlib/hmac — no boto3 or any other
# SDK, same constraint as every other integration in this file. It only signs and sends a
# single PUT (no multipart, no bucket listing/deletion), which is all a one-file-per-backup
# upload needs.
R2_ACCOUNT_ID = os.environ.get("R2_ACCOUNT_ID")
R2_ACCESS_KEY_ID = os.environ.get("R2_ACCESS_KEY_ID")
R2_SECRET_ACCESS_KEY = os.environ.get("R2_SECRET_ACCESS_KEY")
R2_BUCKET_NAME = os.environ.get("R2_BUCKET_NAME")
BACKUP_INTERVAL_SECONDS = int(os.environ.get("BACKUP_INTERVAL_HOURS", "24")) * 3600


def _sigv4_hmac(key: bytes, msg: str) -> bytes:
    return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()


def _r2_put_object(key: str, data: bytes, content_type: str) -> None:
    host = f"{R2_ACCOUNT_ID}.r2.cloudflarestorage.com"
    region = "auto"
    service = "s3"
    now = datetime.now(timezone.utc)
    amz_date = now.strftime("%Y%m%dT%H%M%SZ")
    date_stamp = now.strftime("%Y%m%d")
    payload_hash = hashlib.sha256(data).hexdigest()
    canonical_uri = f"/{R2_BUCKET_NAME}/{key}"
    canonical_headers = f"host:{host}\nx-amz-content-sha256:{payload_hash}\nx-amz-date:{amz_date}\n"
    signed_headers = "host;x-amz-content-sha256;x-amz-date"
    canonical_request = "\n".join(["PUT", canonical_uri, "", canonical_headers, signed_headers, payload_hash])
    credential_scope = f"{date_stamp}/{region}/{service}/aws4_request"
    string_to_sign = "\n".join([
        "AWS4-HMAC-SHA256", amz_date, credential_scope,
        hashlib.sha256(canonical_request.encode("utf-8")).hexdigest(),
    ])
    signing_key = _sigv4_hmac(_sigv4_hmac(_sigv4_hmac(_sigv4_hmac(
        f"AWS4{R2_SECRET_ACCESS_KEY}".encode("utf-8"), date_stamp), region), service), "aws4_request")
    signature = hmac.new(signing_key, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()
    authorization = (
        f"AWS4-HMAC-SHA256 Credential={R2_ACCESS_KEY_ID}/{credential_scope}, "
        f"SignedHeaders={signed_headers}, Signature={signature}"
    )
    req = urllib.request.Request(
        f"https://{host}{canonical_uri}", data=data, method="PUT",
        headers={
            "Host": host, "x-amz-content-sha256": payload_hash, "x-amz-date": amz_date,
            "Authorization": authorization, "Content-Type": content_type,
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        resp.read()


BACKUP_STATE = {"lastSuccessAt": None, "lastSuccessEpoch": 0, "lastError": None}


def _run_backup_once():
    if not (R2_ACCOUNT_ID and R2_ACCESS_KEY_ID and R2_SECRET_ACCESS_KEY and R2_BUCKET_NAME):
        print("[sauvegarde ignorée — R2 non configuré]", file=sys.stderr)
        return
    tmp_path = None
    try:
        # sqlite3's own backup API, not a raw file copy — it produces a consistent snapshot
        # even while the live database is being written to, which a plain file read of a
        # SQLite file mid-write could not guarantee.
        fd, tmp_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        src = get_db()
        dst = sqlite3.connect(tmp_path)
        with dst:
            src.backup(dst)
        src.close()
        # A backup that can't be opened is worse than none (false comfort) — check the
        # snapshot's own integrity before it replaces anything or leaves the machine.
        check = dst.execute("PRAGMA integrity_check").fetchone()[0]
        dst.close()
        if check != "ok":
            raise RuntimeError(f"Snapshot SQLite corrompu : {check}")
        with open(tmp_path, "rb") as f:
            compressed = gzip.compress(f.read())
        key = "backups/comptoir-" + datetime.now(timezone.utc).strftime("%Y-%m-%d-%H%M%S") + ".db.gz"
        _r2_put_object(key, compressed, "application/gzip")
        BACKUP_STATE.update(lastSuccessAt=datetime.now(timezone.utc).isoformat(), lastSuccessEpoch=time.time(), lastError=None)
        print(f"[sauvegarde OK] {key} ({len(compressed)} octets)", file=sys.stderr)
    except Exception as e:
        BACKUP_STATE["lastError"] = f"{type(e).__name__}: {str(e)[:160]}"
        # A failed backup should never take the server down with it — log it loudly and
        # try again at the next interval.
        traceback.print_exc(file=sys.stderr)
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)


def _backup_loop():
    while True:
        _run_backup_once()
        time.sleep(BACKUP_INTERVAL_SECONDS)


def main():
    # Hosting platforms (Railway, Render, Fly.io...) assign a port via $PORT.
    # A CLI argument still wins locally, e.g. `python3 server.py 8082`.
    if len(sys.argv) > 1:
        port = int(sys.argv[1])
    else:
        port = int(os.environ.get("PORT", 8082))
    init_db()
    # Daemon: dies with the process, never blocks shutdown. Fires once immediately (so
    # every deploy doubles as a fresh backup) then on BACKUP_INTERVAL_SECONDS after that.
    threading.Thread(target=_backup_loop, daemon=True).start()
    threading.Thread(target=_notify_loop, daemon=True).start()
    server = http.server.ThreadingHTTPServer(("", port), Handler)
    print(f"Comptoir server running on port {port}  (db: {DB_PATH})")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()


if __name__ == "__main__":
    main()
