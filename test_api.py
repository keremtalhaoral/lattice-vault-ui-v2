import json, os, subprocess, sys, tempfile, threading, unittest, urllib.request, urllib.error
from http.server import ThreadingHTTPServer
HERE = os.path.dirname(os.path.abspath(__file__))
import server


class ApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        out = os.path.join(cls.tmp, "v")
        env = dict(os.environ)
        env.pop("VAULT_DB", None)
        subprocess.run(
            [sys.executable, os.path.join(server.VAULT_SRC, "examples", "seed.py"), out],
            check=True,
            capture_output=True,
            env=env,
        )
        server.Handler.db_path = os.path.join(out, "vault.db")
        cls.srv = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
        cls.base = f"http://127.0.0.1:{cls.srv.server_address[1]}"

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()

    def get(self, path):
        with urllib.request.urlopen(self.base + path) as r:
            return json.loads(r.read())

    def test_events(self):
        d = self.get("/api/events")
        self.assertGreater(d["total"], 5)
        self.assertIn("items", d)
        e = d["items"][0]
        for k in ("id", "type", "ts", "source", "status", "trust", "text_short"):
            self.assertIn(k, e)

    def test_filter_and_paging(self):
        d = self.get("/api/events?status=proposed")
        self.assertTrue(d["items"])
        self.assertTrue(all(e["status"] == "proposed" for e in d["items"]))
        self.assertEqual(len(self.get("/api/events?limit=2")["items"]), 2)
        with self.assertRaises(urllib.error.HTTPError):
            self.get("/api/events?status=bogus")

    def test_bad_trust(self):
        with self.assertRaises(urllib.error.HTTPError) as c:
            self.get("/api/events?trust=bogus")
        self.assertEqual(c.exception.code, 400)

    def test_search(self):
        self.assertTrue(self.get("/api/search?q=basil")["results"])
        self.assertEqual(self.get("/api/search?q=")["results"], [])

    def test_readonly(self):
        req = urllib.request.Request(self.base + "/api/events", data=b"{}", method="POST")
        with self.assertRaises(urllib.error.HTTPError) as c:
            urllib.request.urlopen(req)
        self.assertEqual(c.exception.code, 405)
        with server.open_ro(server.Handler.db_path) as db:
            with self.assertRaises(Exception):
                db.execute("CREATE TABLE x(a)")


if __name__ == "__main__":
    unittest.main()
