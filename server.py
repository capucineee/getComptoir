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
import hmac
import html
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
import urllib.error
import urllib.parse
import urllib.request
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
CONSENT_VERSION = "2026-09-09"

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
    if user_row["email"] in FREE_FOREVER_EMAILS:
        return {"tier": "decouverte", "status": "active", "renewsAt": None, "freeForever": True}
    tier = user_row["plan_tier"]
    status = user_row["plan_status"]
    if not tier or status != "active":
        return {"tier": None, "status": status or "inactive", "renewsAt": None, "freeForever": False}
    return {"tier": tier, "status": status, "renewsAt": user_row["plan_renews_at"], "freeForever": False}


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
                  u.plan_tier, u.plan_status, u.plan_renews_at, u.stripe_customer_id
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


def require_active_plan(user):
    """Raises 402 for any account with no active plan — free-forever and grandfathered
    accounts always pass (resolve_plan gives them tier+status='active'); anyone who
    signed up after real billing shipped and hasn't subscribed yet does not."""
    plan = resolve_plan(user)
    if not plan["tier"]:
        raise ApiError(402, "Choisissez un forfait pour continuer — rendez-vous dans Facturation.")
    return plan


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
    conn.commit()
    conn.close()
    return {"ok": True}


def handle_create_connector(token, body):
    user = user_from_token(token)
    if not user:
        raise ApiError(401, "Session invalide ou expirée.")
    plan = require_active_plan(user)
    label = str(body.get("label", "")).strip()
    if not label:
        raise ApiError(400, "Le nom de la plateforme est requis.")
    connector_id = secrets.token_hex(8)
    api_key = "cpt_live_" + secrets.token_hex(24)
    conn = get_db()
    # Every custom connector the user creates shares one "custom" channel slot (this is a
    # category of channel, like Shopify or Etsy, not one slot per store) — only check and
    # consume the limit the first time, so a second custom connector doesn't need its own.
    already = conn.execute(
        "SELECT 1 FROM connected_channels WHERE user_id = ? AND channel_type = 'custom'", (user["id"],)
    ).fetchone()
    if not already:
        limit = PLAN_LIMITS[plan["tier"]]["channels"]
        current = count_connected_channels(conn, user["id"])
        if limit is not None and current >= limit:
            conn.close()
            raise ApiError(402, f"Votre forfait autorise {limit} canal{'aux' if limit > 1 else ''} connecté{'s' if limit > 1 else ''} maximum — passez à un forfait supérieur pour en connecter davantage.")
        conn.execute("INSERT INTO connected_channels (user_id, channel_type) VALUES (?, 'custom')", (user["id"],))
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
    # Free the "custom" channel slot only once no custom connector is left — a user with
    # two custom connectors deleting one should still count as using the slot.
    remaining = conn.execute("SELECT COUNT(*) FROM api_keys WHERE user_id = ?", (user["id"],)).fetchone()[0]
    if remaining == 0:
        conn.execute("DELETE FROM connected_channels WHERE user_id = ? AND channel_type = 'custom'", (user["id"],))
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

        # Plan limit on real inbound orders: count only orders this same path already
        # created this calendar month (channelType == 'custom' is unique to this endpoint),
        # not the account's whole order history — that includes older demo/seed data that
        # predates real billing and shouldn't count against it.
        user_row = conn.execute(
            "SELECT id, email, plan_tier, plan_status FROM users WHERE id = ?", (user_id,)
        ).fetchone()
        if user_row:
            plan = require_active_plan(user_row)
            limit = PLAN_LIMITS[plan["tier"]]["orders"]
            if limit is not None:
                month_prefix = datetime.now(timezone.utc).strftime("%Y-%m")
                this_month_count = sum(
                    1 for o in orders
                    if o.get("channelType") == "custom" and str(o.get("date", "")).startswith(month_prefix)
                )
                if this_month_count >= limit:
                    conn.close()
                    raise ApiError(402, f"Votre forfait autorise {limit} commandes par mois maximum via ce connecteur — passez à un forfait supérieur.")

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


def _get_or_create_stripe_customer(conn, user) -> str:
    if user["stripe_customer_id"]:
        return user["stripe_customer_id"]
    customer = stripe_request("POST", "/customers", {"email": user["email"], "metadata": {"comptoir_user_id": user["id"]}})
    conn.execute("UPDATE users SET stripe_customer_id = ? WHERE id = ?", (customer["id"], user["id"]))
    conn.commit()
    return customer["id"]


def handle_billing_checkout(token, body):
    user = user_from_token(token)
    if not user:
        raise ApiError(401, "Session invalide ou expirée.")
    if user["email"] in FREE_FOREVER_EMAILS:
        raise ApiError(400, "Ce compte est en accès gratuit permanent — aucun paiement n'est nécessaire.")
    tier = body.get("tier")
    price_id = STRIPE_PRICE_IDS.get(tier)
    if not price_id:
        raise ApiError(400, "Forfait inconnu ou non configuré.")
    conn = get_db()
    customer_id = _get_or_create_stripe_customer(conn, user)
    conn.close()
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
        "metadata": {"comptoir_user_id": user["id"], "comptoir_tier": tier},
        "subscription_data": {"metadata": {"comptoir_user_id": user["id"], "comptoir_tier": tier}},
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
            conn.execute(
                "UPDATE users SET plan_tier = ?, plan_status = 'active', stripe_subscription_id = ?, stripe_customer_id = COALESCE(stripe_customer_id, ?) WHERE id = ?",
                (tier, subscription_id, customer_id, user_id),
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
        # Stripe's webhook needs the RAW request body to verify its signature — parsing it
        # as JSON first (like every other route below) would still work for reading the
        # event, but the signature is computed over the exact bytes Stripe sent, so this
        # route reads and verifies before any JSON parsing happens.
        if path == "/api/stripe/webhook":
            try:
                length = int(self.headers.get("Content-Length", 0))
                raw = self.rfile.read(length) if length else b""
                return self._send_json(200, handle_stripe_webhook(raw, self.headers.get("Stripe-Signature")))
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
            if path == "/api/logout":
                return self._send_json(200, handle_logout(self._bearer_token()))
            if path == "/api/connectors/custom":
                return self._send_json(200, handle_create_connector(self._bearer_token(), body))
            if path == "/api/connectors/channel":
                return self._send_json(200, handle_connect_channel(self._bearer_token(), body))
            if path == "/api/ingest/orders":
                return self._send_json(200, handle_ingest_order(self._bearer_token(), body))
            if path == "/api/billing/checkout":
                return self._send_json(200, handle_billing_checkout(self._bearer_token(), body))
            if path == "/api/billing/portal":
                return self._send_json(200, handle_billing_portal(self._bearer_token()))
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
        try:
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
