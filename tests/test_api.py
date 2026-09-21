"""End-to-end API tests: starts the real server on a temporary database and drives it over
HTTP with the standard library only. Run with:  python3 -m unittest discover -s tests -v"""
import json
import os
import secrets
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class Api:
    def __init__(self, base):
        self.base = base

    def call(self, path, method="GET", body=None, token=None, headers=None, raw=None):
        hd = {"Content-Type": "application/json"}
        hd.update(headers or {})
        if token:
            hd["Authorization"] = "Bearer " + token
        data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
        req = urllib.request.Request(self.base + path, data=data, headers=hd, method=method)
        try:
            r = urllib.request.urlopen(req, timeout=20)
            status, payload = r.status, r.read()
        except urllib.error.HTTPError as e:
            status, payload = e.code, e.read()
        try:
            return status, json.loads(payload or b"{}")
        except json.JSONDecodeError:
            return status, {"_raw": payload[:200]}


class ServerCase(unittest.TestCase):
    EXTRA_ENV = {"LAUNCH_AT": "2000-01-01T00:00:00+00:00"}  # sign-ups open unless a test says otherwise

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        cls.db = os.path.join(cls.tmp, "test.db")
        port = free_port()
        env = dict(os.environ, COMPTOIR_DB_PATH=cls.db, PORT=str(port), **cls.EXTRA_ENV)
        for k in ("R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET_NAME", "STRIPE_SECRET_KEY", "BREVO_API_KEY"):
            env.pop(k, None)
        cls.proc = subprocess.Popen([sys.executable, os.path.join(ROOT, "server.py")], cwd=ROOT, env=env,
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        cls.base = f"http://127.0.0.1:{port}"
        cls.api = Api(cls.base)
        for _ in range(60):
            try:
                urllib.request.urlopen(cls.base + "/api/health", timeout=1)
                break
            except Exception:
                time.sleep(0.25)

    @classmethod
    def tearDownClass(cls):
        cls.proc.terminate()
        cls.proc.wait(timeout=10)

    def sql(self, query, *args):
        c = sqlite3.connect(self.db)
        rows = c.execute(query, args).fetchall()
        c.commit()
        c.close()
        return rows

    def new_account(self, plan="croissance"):
        email = f"u{secrets.token_hex(4)}@example.com"
        s, j = self.api.call("/api/signup", "POST", {"email": email, "password": "Passw0rd!x", "acceptTerms": True})
        self.assertEqual(s, 200, j)
        tok = j["token"]
        self.sql("update users set email_verified_at=datetime('now'), plan_tier=?, plan_status='active' where email=?", plan, email)
        # A real account gets its state document the first time the app loads.
        empty = {"orders": [], "products": [], "connectors": [], "customFields": [], "expenses": []}
        self.assertEqual(self.api.call("/api/state", "PUT", {"data": json.dumps(empty)}, tok)[0], 200)
        s, j = self.api.call("/api/connectors/custom", "POST", {"label": "Site"}, tok)
        self.assertEqual(s, 200, j)
        return {"email": email, "token": tok, "key": j["apiKey"], "cid": j["connectorId"]}

    def orders(self, acc):
        s, j = self.api.call("/api/state", token=acc["token"])
        return {o.get("externalId"): o for o in json.loads(j["data"])["orders"]}


class TestPublic(ServerCase):
    def test_health(self):
        s, j = self.api.call("/api/health")
        self.assertEqual(s, 200)
        self.assertTrue(j["ok"] and j["db"])
        self.assertEqual(j["backup"]["status"], "not_configured")

    def test_private_files_not_served(self):
        for path in ("/server.py", "/Procfile", "/requirements.txt", "/.gitignore", "/tests/test_api.py", "/../server.py"):
            try:
                code = urllib.request.urlopen(self.base + path).status
            except urllib.error.HTTPError as e:
                code = e.code
            self.assertEqual(code, 404, path)

    def test_no_directory_listing(self):
        try:
            body = urllib.request.urlopen(self.base + "/icons/").read()
            self.assertNotIn(b"Directory listing", body)
        except urllib.error.HTTPError as e:
            self.assertEqual(e.code, 404)

    def test_public_assets(self):
        for path in ("/", "/app.js", "/styles.css", "/t.js", "/guide-connecteur.html", "/robots.txt"):
            self.assertEqual(urllib.request.urlopen(self.base + path).status, 200, path)

    def test_www_redirects_to_apex(self):
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, *a, **k):
                return None
        opener = urllib.request.build_opener(NoRedirect)
        req = urllib.request.Request(self.base + "/guide-shopify.html", headers={"Host": "www.getcomptoir.fr"})
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            opener.open(req)
        self.assertEqual(ctx.exception.code, 301)
        self.assertEqual(ctx.exception.headers["Location"], "https://getcomptoir.fr/guide-shopify.html")

    def test_protected_routes_need_auth(self):
        for path in ("/api/me", "/api/state", "/api/tracking/stats", "/api/account/export"):
            self.assertEqual(self.api.call(path)[0], 401, path)
        self.assertEqual(self.api.call("/api/ingest/orders", "POST", {"amount": 1})[0], 401)

    def test_oversized_body_refused(self):
        s, _ = self.api.call("/api/login", "POST", headers={"Content-Length": "999999999"}, raw=b"{}")
        self.assertIn(s, (400, 413))

    def test_track_beacon_never_errors(self):
        for raw in (b'{"site":"nope"}', b"not json", b""):
            req = urllib.request.Request(self.base + "/api/track", data=raw, headers={"Content-Type": "text/plain"}, method="POST")
            r = urllib.request.urlopen(req)
            self.assertEqual(r.status, 204)
            self.assertEqual(r.headers["Access-Control-Allow-Origin"], "*")


class TestAccounts(ServerCase):
    def test_signup_login_rules(self):
        self.assertEqual(self.api.call("/api/signup", "POST", {"email": "a@example.com", "password": "Passw0rd!x"})[0], 400)
        self.assertEqual(self.api.call("/api/signup", "POST", {"email": "a@example.com", "password": "short", "acceptTerms": True})[0], 400)
        acc = self.new_account()
        self.assertEqual(self.api.call("/api/signup", "POST", {"email": acc["email"].upper(), "password": "Passw0rd!x", "acceptTerms": True})[0], 409)
        self.assertEqual(self.api.call("/api/login", "POST", {"email": acc["email"], "password": "wrong"})[0], 401)
        self.assertEqual(self.api.call("/api/login", "POST", {"email": acc["email"], "password": "Passw0rd!x"})[0], 200)

    def test_export_has_no_secret_and_delete_removes_everything(self):
        acc = self.new_account()
        self.api.call("/api/ingest/orders", "POST", {"externalId": "D1", "amount": 10}, acc["key"])
        s, j = self.api.call("/api/account/export", token=acc["token"])
        self.assertEqual(s, 200)
        self.assertEqual(j["account"]["email"], acc["email"])
        self.assertNotIn(acc["key"], json.dumps(j))
        self.assertEqual(self.api.call("/api/account", "DELETE", {"password": "nope"}, acc["token"])[0], 403)
        self.assertEqual(self.api.call("/api/account", "DELETE", {}, acc["token"])[0], 400)
        s, j = self.api.call("/api/account", "DELETE", {"password": "Passw0rd!x"}, acc["token"])
        self.assertEqual(s, 200, j)
        self.assertEqual(self.sql("select count(*) from users where email=?", acc["email"])[0][0], 0)
        self.assertEqual(self.sql("select count(*) from api_keys where key=?", acc["key"])[0][0], 0)
        self.assertEqual(self.api.call("/api/ingest/orders", "POST", {"amount": 1}, acc["key"])[0], 401)
        self.assertEqual(self.api.call("/api/me", token=acc["token"])[0], 401)

    def test_password_reset_revokes_sessions_and_is_single_use(self):
        acc = self.new_account()
        self.api.call("/api/password-reset/request", "POST", {"email": acc["email"]})
        tok = self.sql("select token from password_resets order by rowid desc limit 1")[0][0]
        self.assertEqual(self.api.call("/api/password-reset/confirm", "POST", {"token": tok, "password": "NewPassw0rd!y"})[0], 200)
        self.assertEqual(self.api.call("/api/me", token=acc["token"])[0], 401)
        self.assertEqual(self.api.call("/api/password-reset/confirm", "POST", {"token": tok, "password": "Another1234!"})[0], 400)
        self.assertEqual(self.api.call("/api/login", "POST", {"email": acc["email"], "password": "NewPassw0rd!y"})[0], 200)

    def test_plan_limits(self):
        acc = self.new_account(plan="decouverte")
        codes = [self.api.call("/api/ingest/orders", "POST", {"externalId": f"L{i}", "amount": 5}, acc["key"])[0] for i in range(55)]
        self.assertEqual(codes.count(200), 50)
        self.assertIn(402, codes)

    def test_tenant_isolation(self):
        a, b = self.new_account(), self.new_account()
        self.api.call("/api/ingest/orders", "POST", {"externalId": "ISO1", "amount": 9}, a["key"])
        self.assertNotIn("ISO1", self.orders(b))
        self.assertIn("ISO1", self.orders(a))


class TestOrders(ServerCase):
    def setUp(self):
        self.acc = self.new_account()

    def ing(self, body):
        return self.api.call("/api/ingest/orders", "POST", body, self.acc["key"])

    def test_validation(self):
        self.assertEqual(self.ing({"amount": -5})[0], 400)
        self.assertEqual(self.ing({"status": "livree"})[0], 400)
        self.assertEqual(self.ing({"amount": 5, "date": "hier"})[0], 400)
        self.assertEqual(self.api.call("/api/ingest/orders", "POST", [1], self.acc["key"])[0], 400)

    def test_status_workflow_and_history(self):
        self.ing({"externalId": "S1", "amount": 30, "status": "Préparation"})
        self.ing({"externalId": "S1", "amount": 30, "status": "en cours de livraison"})
        self.ing({"externalId": "S1", "amount": 30, "status": "livrée"})
        o = self.orders(self.acc)["S1"]
        self.assertEqual(o["status"], "livree")
        self.assertEqual([h["status"] for h in o["history"]], ["preparation", "en_route", "livree"])

    def test_delivered_never_regresses(self):
        self.ing({"externalId": "S2", "amount": 30, "status": "livree"})
        s, j = self.ing({"externalId": "S2", "amount": 30, "status": "fulfilled"})
        self.assertFalse(j["updated"])
        self.assertEqual(self.orders(self.acc)["S2"]["status"], "livree")

    def test_partial_update_keeps_quantity_and_status(self):
        self.ing({"externalId": "P1", "amount": 42.9, "status": "livree", "quantity": 2, "productName": "Bougie", "country": "France"})
        self.ing({"externalId": "P1", "amount": 42.9})
        o = self.orders(self.acc)["P1"]
        self.assertEqual((o["status"], o["quantity"], o["country"]), ("livree", 2, "FR"))

    def test_amount_formats_and_unknown_status(self):
        s, j = self.ing({"externalId": "F1", "amount": "1 234,50 €", "status": "blabla"})
        self.assertEqual(s, 200)
        self.assertIn("note", j)

    def test_bulk(self):
        orders = [{"externalId": f"B{i}", "amount": 10 + i, "status": "livree"} for i in range(5)] + [{"amount": "abc"}]
        s, j = self.api.call("/api/ingest/orders/bulk", "POST", {"orders": orders}, self.acc["key"])
        self.assertEqual((s, j["created"], j["failed"]), (200, 5, 1))
        self.assertEqual(self.api.call("/api/ingest/orders/bulk", "POST", {"orders": [{"amount": 1}] * 501}, self.acc["key"])[0], 400)

    def test_hostile_field_keys_are_sanitized(self):
        self.ing({"externalId": "X1", "amount": 5, "<img src=x onerror=alert(1)>": "boom", "ok_key": "fine", "v": "a" * 1000})
        custom = self.orders(self.acc)["X1"]["custom"]
        for k in custom:
            self.assertNotRegex(k, r"[<>\"'`&]")
        self.assertEqual(custom["ok_key"], "fine")
        self.assertLessEqual(max(len(v) for v in custom.values()), 300)

    def test_stale_client_save_cannot_overwrite_server_update(self):
        self.ing({"externalId": "R1", "amount": 10, "status": "preparation"})
        stale = self.api.call("/api/state", token=self.acc["token"])[1]["data"]
        time.sleep(1.1)
        self.ing({"externalId": "R1", "amount": 10, "status": "retour"})
        self.api.call("/api/state", "PUT", {"data": stale}, self.acc["token"])
        self.assertEqual(self.orders(self.acc)["R1"]["status"], "retour")

    def test_state_size_guard(self):
        s, _ = self.api.call("/api/state", "PUT", {"data": json.dumps({"x": "a" * 2_100_000})}, self.acc["token"])
        self.assertEqual(s, 413)


class TestTracking(ServerCase):
    def hit(self, key, ip, ref="", ua="Mozilla/5.0 Safari", tz="Europe/Paris"):
        body = json.dumps({"site": key, "url": "https://s.fr/p", "ref": ref, "tz": tz, "lang": "fr-FR"}).encode()
        return self.api.call("/api/track", "POST", raw=body, headers={"Content-Type": "text/plain", "User-Agent": ua, "X-Forwarded-For": ip})

    def test_counts_unique_visitors_and_ignores_bots(self):
        acc = self.new_account()
        s, j = self.api.call("/api/tracking/site", "POST", {"connectorId": acc["cid"], "channelType": "custom"}, acc["token"])
        key = j["siteKey"]
        self.assertEqual(self.api.call("/api/tracking/site", "POST", {"connectorId": acc["cid"], "channelType": "custom"}, acc["token"])[1]["siteKey"], key)
        self.assertEqual(self.api.call("/api/tracking/site", "POST", {"connectorId": "x", "channelType": "etsy"}, acc["token"])[0], 400)
        self.hit(key, "10.0.0.1", "https://www.google.com/")
        self.hit(key, "10.0.0.1")
        self.hit(key, "10.0.0.2", "https://l.instagram.com/")
        self.hit(key, "10.0.0.3", ua="Googlebot/2.1")
        stats = self.api.call("/api/tracking/stats", token=acc["token"])[1]
        self.assertEqual((stats["visitors"], stats["views"]), (2, 3))
        self.assertEqual({x["source"] for x in stats["sources"]}, {"Google", "Instagram"})
        other = self.new_account()
        self.assertEqual(self.api.call("/api/tracking/stats", token=other["token"])[1]["visitors"], 0)


class TestPreLaunch(ServerCase):
    EXTRA_ENV = {"LAUNCH_AT": "2999-01-01T09:00:00+02:00", "SIGNUP_ALLOWLIST": "early@example.com"}

    def test_launch_info(self):
        s, j = self.api.call("/api/launch")
        self.assertEqual(s, 200)
        self.assertFalse(j["open"])
        self.assertTrue(j["launchAt"].startswith("2999-01-01T07:00:00"))

    def test_signup_blocked_but_allowlist_and_login_work(self):
        s, j = self.api.call("/api/signup", "POST", {"email": "new@example.com", "password": "Passw0rd!x", "acceptTerms": True})
        self.assertEqual(s, 403, j)
        self.assertEqual(self.sql("select count(*) from users where email='new@example.com'")[0][0], 0)
        s, j = self.api.call("/api/signup", "POST", {"email": "Early@example.com", "password": "Passw0rd!x", "acceptTerms": True})
        self.assertEqual(s, 200, j)
        self.assertEqual(self.api.call("/api/login", "POST", {"email": "early@example.com", "password": "Passw0rd!x"})[0], 200)


class TestPostLaunch(ServerCase):
    def test_open(self):
        self.assertTrue(self.api.call("/api/launch")[1]["open"])


if __name__ == "__main__":
    unittest.main()
