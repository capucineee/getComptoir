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


class TestNotifications(ServerCase):
    """Queue is filled by the running server; the worker pass is run in-process against the
    same database file with email sending replaced by a recorder."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        import importlib.util
        os.environ["COMPTOIR_DB_PATH"] = cls.db
        spec = importlib.util.spec_from_file_location("srv_under_test", os.path.join(ROOT, "server.py"))
        cls.srv = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.srv)
        cls.sent = []
        cls.srv.send_email = lambda to, subject, text, html_body=None: cls.sent.append((to, subject, text))

    ON = {"sales": True, "stock": True, "monthly": False, "frequency": "instant", "configured": True}

    def setUp(self):
        self.acc = self.new_account()
        self.sent.clear()
        self.put_state(notifications=dict(self.ON))

    def state(self):
        return json.loads(self.api.call("/api/state", token=self.acc["token"])[1]["data"])

    def put_state(self, **changes):
        st = self.state()
        st.update(changes)
        self.assertEqual(self.api.call("/api/state", "PUT", {"data": json.dumps(st)}, self.acc["token"])[0], 200)

    def ing(self, body):
        return self.api.call("/api/ingest/orders", "POST", body, self.acc["key"])

    def flush(self):
        # age the queue past the coalescing delay, then run one worker pass
        self.sql("update notification_queue set created_at = datetime('now','-1 hour')")
        self.sql("delete from notification_state")
        self.srv.process_notifications()

    def test_sale_is_queued_and_sent_once_grouped(self):
        for i in range(3):
            self.ing({"externalId": f"N{i}", "amount": 10 + i, "customerName": f"Client {i}", "status": "preparation"})
        self.assertEqual(self.sql("select count(*) from notification_queue")[0][0] >= 3, True)
        self.flush()
        mine = [m for m in self.sent if m[0] == self.acc["email"]]
        self.assertEqual(len(mine), 1)
        self.assertIn("3 nouvelles ventes", mine[0][1])

    def test_old_orders_and_bulk_backfill_do_not_notify(self):
        old = [{"externalId": f"H{i}", "amount": 5, "date": "2020-01-01T10:00:00Z"} for i in range(20)]
        self.api.call("/api/ingest/orders/bulk", "POST", {"orders": old}, self.acc["key"])
        self.flush()
        self.assertEqual([m for m in self.sent if m[0] == self.acc["email"]], [])

    def test_bulk_of_recent_orders_is_one_email_capped(self):
        recent = [{"externalId": f"R{i}", "amount": 5} for i in range(25)]
        self.api.call("/api/ingest/orders/bulk", "POST", {"orders": recent}, self.acc["key"])
        self.flush()
        mine = [m for m in self.sent if m[0] == self.acc["email"]]
        self.assertEqual(len(mine), 1)
        self.assertIn("25 nouvelles ventes", mine[0][1])
        self.assertIn("et 15 autres ventes", mine[0][2])

    def test_disabled_sales_are_not_queued(self):
        self.put_state(notifications=dict(self.ON, sales=False))
        self.ing({"externalId": "OFF1", "amount": 10})
        self.assertEqual(self.sql("select count(*) from notification_queue where kind='sale'")[0][0], 0)

    def test_stock_alert_only_when_crossing_the_threshold(self):
        self.put_state(products=[{"id": "p1", "name": "Bougie", "stock": 11, "threshold": 10, "channels": [], "costPrice": 1, "custom": {}}])
        self.ing({"externalId": "K1", "amount": 10, "productName": "Bougie"})   # 11 -> 10 : crosses
        self.ing({"externalId": "K2", "amount": 10, "productName": "Bougie"})   # 10 -> 9  : already low, silent
        events = [json.loads(r[0]) for r in self.sql("select payload from notification_queue where kind='stock'")]
        self.assertEqual([e["level"] for e in events], ["low"])

    def test_disabling_after_queueing_drops_the_email(self):
        self.ing({"externalId": "D1", "amount": 10})
        self.put_state(notifications=dict(self.ON, sales=False, stock=False))
        self.flush()
        self.assertEqual([m for m in self.sent if m[0] == self.acc["email"]], [])

    def test_daily_mode_waits_for_morning(self):
        from datetime import datetime, timezone
        self.put_state(notifications=dict(self.ON, frequency="daily"))
        self.ing({"externalId": "DL1", "amount": 10})
        self.sql("update notification_queue set created_at = datetime('now','-1 hour')")
        self.sql("delete from notification_state")
        real = self.srv._paris_now
        try:
            self.srv._paris_now = lambda: datetime(2026, 9, 21, 6, 0, tzinfo=timezone.utc)
            self.srv.process_notifications()
            self.assertEqual([m for m in self.sent if m[0] == self.acc["email"]], [])
            self.srv._paris_now = lambda: datetime(2026, 9, 21, 9, 0, tzinfo=timezone.utc)
            self.srv.process_notifications()
            self.assertEqual(len([m for m in self.sent if m[0] == self.acc["email"]]), 1)
        finally:
            self.srv._paris_now = real

    def test_off_by_default_and_legacy_values_are_ignored(self):
        self.put_state(notifications={"sales": True, "stock": True, "frequency": "instant"})  # no "configured": ignored
        self.ing({"externalId": "LEG1", "amount": 10})
        self.assertEqual(self.sql("select count(*) from notification_queue")[0][0], 0)
        st = self.state()
        st.pop("notifications", None)
        self.api.call("/api/state", "PUT", {"data": json.dumps(st)}, self.acc["token"])
        self.ing({"externalId": "LEG2", "amount": 10})
        self.assertEqual(self.sql("select count(*) from notification_queue")[0][0], 0)

    def test_monthly_summary_numbers_and_disclaimer(self):
        data = {
            "products": [{"id": "p1", "name": "Bougie", "costPrice": 5}, {"id": "p2", "name": "Savon", "costPrice": 0}],
            "orders": [
                {"date": "2026-08-05T10:00:00Z", "amount": 60, "status": "livree", "productId": "p1", "quantity": 2, "country": "FR"},
                {"date": "2026-08-20T10:00:00Z", "amount": 60, "status": "livree", "productId": "p2", "quantity": 1, "country": "BE"},
                {"date": "2026-08-21T10:00:00Z", "amount": 99, "status": "retour", "productId": "p1", "quantity": 1},
                {"date": "2026-07-10T10:00:00Z", "amount": 60, "status": "livree", "productId": "p1", "quantity": 1},
            ],
            "expenses": [{"date": "2026-01-15T00:00:00Z", "amount": 10, "recurrence": "monthly"}],
        }
        sm = self.srv.compute_month_summary(data, 2026, 8)
        self.assertEqual((sm["orders"], sm["returns"]), (2, 1))
        self.assertAlmostEqual(sm["ca"], 120.0)
        self.assertAlmostEqual(sm["cost"], 10.0)              # 2 x 5, the other product has no cost
        self.assertAlmostEqual(sm["expenses"], 10.0)          # one monthly occurrence in August
        self.assertAlmostEqual(sm["net"], 120 / 1.2 - 10 - 10)
        self.assertAlmostEqual(sm["caDelta"], 100.0)          # 60 -> 120
        self.assertEqual(sm["missingCost"], ["Savon"])
        subject, text, html_body = self.srv.build_monthly_email(sm)
        self.assertIn("août 2026", subject)
        self.assertIn("dépendent des données saisies", html_body)
        self.assertIn("Savon", html_body)

    def test_monthly_worker_sends_once_in_the_first_days_only(self):
        from datetime import datetime, timezone
        self.put_state(notifications=dict(self.ON, sales=False, stock=False, monthly=True))
        now = datetime.now(timezone.utc)
        py, pm = (now.year - (now.month == 1), 12 if now.month == 1 else now.month - 1)
        self.put_state(orders=[{"id": "m1", "orderNumber": 1, "externalId": "M1", "customer": "C", "amount": 50, "status": "livree", "channelType": "custom", "date": f"{py}-{pm:02d}-10T10:00:00Z", "custom": {}, "quantity": 1}])
        real = self.srv._paris_now
        try:
            self.srv._paris_now = lambda: datetime(now.year, now.month, 15, 9, 0, tzinfo=timezone.utc)   # mid-month: nothing
            self.srv.process_monthly_summaries()
            self.assertEqual([m for m in self.sent if m[0] == self.acc["email"]], [])
            self.srv._paris_now = lambda: datetime(now.year, now.month, 2, 9, 0, tzinfo=timezone.utc)    # 2nd, after 08:00: sent
            self.srv.process_monthly_summaries()
            self.srv.process_monthly_summaries()                                                          # and only once
            mine = [m for m in self.sent if m[0] == self.acc["email"]]
            self.assertEqual(len(mine), 1)
            self.assertIn("Votre bilan de", mine[0][1])
        finally:
            self.srv._paris_now = real

    def test_preview_and_test_endpoints(self):
        self.assertEqual(self.api.call("/api/notifications/preview?type=sale")[0], 401)
        s, j = self.api.call("/api/notifications/preview?type=digest", token=self.acc["token"])
        self.assertEqual(s, 200)
        self.assertIn("<html", j["html"])
        self.assertIn("Rupture", j["html"])
        s, j = self.api.call("/api/notifications/preview?type=monthly", token=self.acc["token"])
        self.assertIn("dépendent des données saisies", j["html"])
        self.assertEqual(self.api.call("/api/notifications/test", "POST", {"type": "sale"}, self.acc["token"])[0], 404)  # no test-mail endpoint

    def test_html_in_data_is_escaped_in_the_email(self):
        self.ing({"externalId": "XS1", "amount": 10, "customerName": "<script>alert(1)</script>"})
        self.flush()
        # the queued payload is rendered with escaping: no raw tag in the HTML template
        _, _, html_body = self.srv.build_notification_email([{"kind": "sale", "customer": "<script>alert(1)</script>", "amount": 1, "channel": "<b>x</b>"}])
        self.assertNotIn("<script>alert(1)</script>", html_body)


class TestTrial(ServerCase):
    """Free first month: checked in-process by capturing what is sent to Stripe."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        import importlib.util
        os.environ["COMPTOIR_DB_PATH"] = cls.db
        spec = importlib.util.spec_from_file_location("srv_trial", os.path.join(ROOT, "server.py"))
        cls.srv = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.srv)
        cls.calls = []
        cls.srv.STRIPE_PRICE_IDS = {"multicanal": "price_test"}
        cls.srv.stripe_request = lambda method, path, data=None: (cls.calls.append((method, path, data)) or {"id": "cus_1", "url": "https://checkout.example/x"})
        cls.srv.verify_stripe_signature = lambda payload, sig: True

    def account(self):
        email = f"t{secrets.token_hex(4)}@example.com"
        s, j = self.api.call("/api/signup", "POST", {"email": email, "password": "Passw0rd!x", "acceptTerms": True})
        self.sql("update users set email_verified_at=datetime('now') where email=?", email)
        return email, j["token"]

    def test_first_checkout_has_a_30_day_trial_with_card_upfront(self):
        email, tok = self.account()
        self.calls.clear()
        self.srv.handle_billing_checkout(tok, {"tier": "multicanal"})
        session = [c for c in self.calls if c[1] == "/checkout/sessions"][0][2]
        self.assertEqual(session["subscription_data"]["trial_period_days"], 30)
        self.assertEqual(session["subscription_data"]["trial_settings"]["end_behavior"]["missing_payment_method"], "cancel")
        self.assertEqual(session["payment_method_collection"], "always")
        self.assertEqual(session["metadata"]["comptoir_trial"], "1")
        me = self.api.call("/api/me", token=tok)[1]
        self.assertEqual(me["trial"], {"days": 30, "eligible": True})

    def test_trial_is_consumed_once(self):
        email, tok = self.account()
        uid = self.sql("select id from users where email=?", email)[0][0]
        event = {"type": "checkout.session.completed", "data": {"object": {"metadata": {"comptoir_user_id": uid, "comptoir_tier": "multicanal", "comptoir_trial": "1"}, "subscription": "sub_1", "customer": "cus_1"}}}
        self.srv.handle_stripe_webhook(json.dumps(event).encode(), "sig")
        row = self.sql("select plan_tier, plan_status, trial_used_at from users where id=?", uid)[0]
        self.assertEqual((row[0], row[1]), ("multicanal", "trialing"))
        self.assertIsNotNone(row[2])
        self.assertFalse(self.api.call("/api/me", token=tok)[1]["trial"]["eligible"])
        self.sql("update users set plan_tier=NULL, stripe_subscription_id=NULL where id=?", uid)   # cancelled, comes back later
        self.calls.clear()
        self.srv.handle_billing_checkout(tok, {"tier": "multicanal"})
        session = [c for c in self.calls if c[1] == "/checkout/sessions"][0][2]
        self.assertNotIn("trial_period_days", session["subscription_data"])
        self.assertEqual(session["metadata"]["comptoir_trial"], "0")

    def test_launch_endpoint_announces_trial_length(self):
        self.assertEqual(self.api.call("/api/launch")[1]["trialDays"], 30)


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
